#pragma once

#include <zmq.hpp>
#include <string>
#include <memory>

namespace mdai {

struct RGBFrame;

class FramePublisher {
public:
    struct Config {
        std::string endpoint = "ipc:///tmp/mdai_rgb_frames";
        int high_water_mark = 2;  // Drop old frames if subscriber is slow
    };

    explicit FramePublisher(const Config& config);
    ~FramePublisher();

    bool publish(const RGBFrame& frame);
    
    // Statistics
    uint64_t get_published_count() const { return published_count_; }
    uint64_t get_dropped_count() const { return dropped_count_; }

private:
    Config config_;
    std::unique_ptr<zmq::context_t> context_;
    std::unique_ptr<zmq::socket_t> socket_;
    uint64_t published_count_{0};
    uint64_t dropped_count_{0};
};

} // namespace mdai
