#include "rgb_grabber.hpp"
#include <chrono>
#include <cstring>
#include <iostream>
#include <thread>

// For JPEG encoding (minimal dependencies for Jetson)
extern "C" {
#include <jpeglib.h>
}

namespace mdai {

uint64_t get_timestamp_ms() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(
        steady_clock::now().time_since_epoch()
    ).count();
}

RGBGrabber::RGBGrabber(const Config& config)
    : config_(config)
    , pipeline_(std::make_unique<rs2::pipeline>())
    , start_time_ms_(get_timestamp_ms())
{
    // Initialize double buffer
    frame_buffer_[0].data.reserve(config_.width * config_.height * 3);
    frame_buffer_[1].data.reserve(config_.width * config_.height * 3);
}

RGBGrabber::~RGBGrabber() {
    stop();
}

bool RGBGrabber::start() {
    if (running_) {
        return true;
    }

    try {
        rs2::config cfg;
        cfg.enable_stream(RS2_STREAM_COLOR, config_.width, config_.height, 
                         RS2_FORMAT_RGB8, config_.fps);
        
        if (!config_.device_serial.empty()) {
            cfg.enable_device(config_.device_serial);
        }

        pipeline_->start(cfg);
        running_ = true;
        start_time_ms_ = get_timestamp_ms();

        // Start capture thread
        std::thread([this]() { capture_loop(); }).detach();

        std::cout << "RGB Grabber started: " << config_.width << "x" 
                  << config_.height << " @ " << config_.fps << " FPS" << std::endl;
        return true;

    } catch (const rs2::error& e) {
        std::cerr << "RealSense error: " << e.what() << std::endl;
        return false;
    }
}

void RGBGrabber::stop() {
    if (!running_) {
        return;
    }

    running_ = false;
    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    if (pipeline_) {
        pipeline_->stop();
    }

    std::cout << "RGB Grabber stopped. Captured " << frame_count_ 
              << " frames" << std::endl;
}

void RGBGrabber::capture_loop() {
    while (running_) {
        try {
            // Wait for frame with timeout
            rs2::frameset frames = pipeline_->wait_for_frames(1000);
            rs2::video_frame color_frame = frames.get_color_frame();

            if (!color_frame) {
                continue;
            }

            // Get write buffer
            int write_idx = write_buffer_.load();
            RGBFrame& frame = frame_buffer_[write_idx];

            // Encode JPEG
            if (encode_jpeg(color_frame, frame.data)) {
                frame.width = color_frame.get_width();
                frame.height = color_frame.get_height();
                frame.timestamp_ms = get_timestamp_ms();
                frame.frame_number = frame_count_.fetch_add(1);

                // Swap buffers (lock-free)
                write_buffer_.store(1 - write_idx);
                latest_frame_.store(&frame);
            }

        } catch (const rs2::error& e) {
            std::cerr << "Frame capture error: " << e.what() << std::endl;
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
}

bool RGBGrabber::encode_jpeg(const rs2::video_frame& frame, 
                              std::vector<uint8_t>& output) {
    const int width = frame.get_width();
    const int height = frame.get_height();
    const uint8_t* data = static_cast<const uint8_t*>(frame.get_data());

    // Setup JPEG compression
    struct jpeg_compress_struct cinfo;
    struct jpeg_error_mgr jerr;

    cinfo.err = jpeg_std_error(&jerr);
    jpeg_create_compress(&cinfo);

    // Output to memory
    unsigned char* mem = nullptr;
    unsigned long mem_size = 0;
    jpeg_mem_dest(&cinfo, &mem, &mem_size);

    cinfo.image_width = width;
    cinfo.image_height = height;
    cinfo.input_components = 3;  // RGB
    cinfo.in_color_space = JCS_RGB;

    jpeg_set_defaults(&cinfo);
    jpeg_set_quality(&cinfo, config_.jpeg_quality, TRUE);
    
    // Fast compression for real-time
    cinfo.dct_method = JDCT_FASTEST;

    jpeg_start_compress(&cinfo, TRUE);

    // Write scanlines
    JSAMPROW row_pointer[1];
    int row_stride = width * 3;

    while (cinfo.next_scanline < cinfo.image_height) {
        row_pointer[0] = const_cast<JSAMPROW>(&data[cinfo.next_scanline * row_stride]);
        jpeg_write_scanlines(&cinfo, row_pointer, 1);
    }

    jpeg_finish_compress(&cinfo);
    jpeg_destroy_compress(&cinfo);

    // Copy to output vector
    output.assign(mem, mem + mem_size);
    free(mem);

    return !output.empty();
}

bool RGBGrabber::get_latest_frame(RGBFrame& frame) {
    RGBFrame* latest = latest_frame_.load();
    if (!latest) {
        return false;
    }

    // Copy frame data
    frame = *latest;
    return true;
}

double RGBGrabber::get_fps() const {
    uint64_t elapsed_ms = get_timestamp_ms() - start_time_ms_;
    if (elapsed_ms == 0) {
        return 0.0;
    }
    return (frame_count_ * 1000.0) / elapsed_ms;
}

} // namespace mdai
