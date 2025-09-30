#include "rgb_grabber.hpp"
#include "frame_publisher.hpp"
#include <csignal>
#include <iostream>
#include <atomic>
#include <thread>

std::atomic<bool> running{true};

void signal_handler(int signal) {
    std::cout << "\nShutting down..." << std::endl;
    running = false;
}

void print_stats(const mdai::RGBGrabber& grabber, 
                 const mdai::FramePublisher& publisher) {
    while (running) {
        std::this_thread::sleep_for(std::chrono::seconds(5));
        
        if (!running) break;
        
        std::cout << "Stats: "
                  << "Captured=" << grabber.get_frame_count()
                  << " FPS=" << grabber.get_fps()
                  << " Published=" << publisher.get_published_count()
                  << " Dropped=" << publisher.get_dropped_count()
                  << std::endl;
    }
}

int main(int argc, char* argv[]) {
    // Setup signal handlers
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    // Parse arguments
    mdai::RGBGrabber::Config grabber_config;
    mdai::FramePublisher::Config publisher_config;
    
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--width" && i + 1 < argc) {
            grabber_config.width = std::stoi(argv[++i]);
        } else if (arg == "--height" && i + 1 < argc) {
            grabber_config.height = std::stoi(argv[++i]);
        } else if (arg == "--fps" && i + 1 < argc) {
            grabber_config.fps = std::stoi(argv[++i]);
        } else if (arg == "--quality" && i + 1 < argc) {
            grabber_config.jpeg_quality = std::stoi(argv[++i]);
        } else if (arg == "--endpoint" && i + 1 < argc) {
            publisher_config.endpoint = argv[++i];
        } else if (arg == "--help") {
            std::cout << "RGB Frame Grabber for mDAI\n"
                      << "Usage: " << argv[0] << " [options]\n"
                      << "Options:\n"
                      << "  --width N       Frame width (default: 640)\n"
                      << "  --height N      Frame height (default: 480)\n"
                      << "  --fps N         Frames per second (default: 30)\n"
                      << "  --quality N     JPEG quality 0-100 (default: 85)\n"
                      << "  --endpoint URL  ZMQ endpoint (default: ipc:///tmp/mdai_rgb_frames)\n"
                      << "  --help          Show this help\n";
            return 0;
        }
    }

    // Create grabber and publisher
    mdai::RGBGrabber grabber(grabber_config);
    mdai::FramePublisher publisher(publisher_config);

    // Start capture
    if (!grabber.start()) {
        std::cerr << "Failed to start RGB grabber" << std::endl;
        return 1;
    }

    // Start stats thread
    std::thread stats_thread(print_stats, std::ref(grabber), std::ref(publisher));

    // Main loop: publish frames
    mdai::RGBFrame frame;
    while (running && grabber.is_running()) {
        if (grabber.get_latest_frame(frame)) {
            publisher.publish(frame);
        }
        
        // Small sleep to avoid busy-wait
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    // Cleanup
    grabber.stop();
    stats_thread.join();

    std::cout << "Shutdown complete" << std::endl;
    return 0;
}
