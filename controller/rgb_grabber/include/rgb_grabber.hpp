#pragma once

#include <librealsense2/rs.hpp>
#include <atomic>
#include <memory>
#include <string>
#include <vector>

namespace mdai {

struct RGBFrame {
    std::vector<uint8_t> data;
    int width;
    int height;
    uint64_t timestamp_ms;
    uint32_t frame_number;
};

class RGBGrabber {
public:
    struct Config {
        int width = 640;
        int height = 480;
        int fps = 30;
        int jpeg_quality = 85;
        std::string device_serial;  // Empty = use any device
    };

    explicit RGBGrabber(const Config& config);
    ~RGBGrabber();

    // Start/stop capture
    bool start();
    void stop();
    bool is_running() const { return running_; }

    // Get latest frame (non-blocking)
    bool get_latest_frame(RGBFrame& frame);
    
    // Statistics
    uint64_t get_frame_count() const { return frame_count_; }
    double get_fps() const;

private:
    void capture_loop();
    bool encode_jpeg(const rs2::video_frame& frame, std::vector<uint8_t>& output);

    Config config_;
    std::unique_ptr<rs2::pipeline> pipeline_;
    std::atomic<bool> running_{false};
    std::atomic<uint64_t> frame_count_{0};
    
    // Latest frame (lock-free single producer, single consumer)
    std::atomic<RGBFrame*> latest_frame_{nullptr};
    RGBFrame frame_buffer_[2];  // Double buffer
    std::atomic<int> write_buffer_{0};
    
    uint64_t start_time_ms_;
};

} // namespace mdai
