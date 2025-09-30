#include "frame_publisher.hpp"
#include "rgb_grabber.hpp"
#include <iostream>
#include <cstring>

namespace mdai {

FramePublisher::FramePublisher(const Config& config)
    : config_(config)
    , context_(std::make_unique<zmq::context_t>(1))
    , socket_(std::make_unique<zmq::socket_t>(*context_, zmq::socket_type::pub))
{
    // Set high water mark (drop old frames if subscriber slow)
    socket_->setsockopt(ZMQ_SNDHWM, config_.high_water_mark);
    
    // Bind to endpoint
    socket_->bind(config_.endpoint);
    
    std::cout << "Frame publisher bound to: " << config_.endpoint << std::endl;
}

FramePublisher::~FramePublisher() {
    socket_->close();
}

bool FramePublisher::publish(const RGBFrame& frame) {
    try {
        // Message format:
        // [4 bytes: width] [4 bytes: height] [8 bytes: timestamp] 
        // [4 bytes: frame_number] [N bytes: JPEG data]
        
        size_t header_size = sizeof(uint32_t) * 2 + sizeof(uint64_t) + sizeof(uint32_t);
        size_t total_size = header_size + frame.data.size();
        
        zmq::message_t message(total_size);
        uint8_t* ptr = static_cast<uint8_t*>(message.data());
        
        // Write header
        std::memcpy(ptr, &frame.width, sizeof(uint32_t));
        ptr += sizeof(uint32_t);
        
        std::memcpy(ptr, &frame.height, sizeof(uint32_t));
        ptr += sizeof(uint32_t);
        
        std::memcpy(ptr, &frame.timestamp_ms, sizeof(uint64_t));
        ptr += sizeof(uint64_t);
        
        std::memcpy(ptr, &frame.frame_number, sizeof(uint32_t));
        ptr += sizeof(uint32_t);
        
        // Write JPEG data
        std::memcpy(ptr, frame.data.data(), frame.data.size());
        
        // Send with DONTWAIT (non-blocking)
        auto result = socket_->send(message, zmq::send_flags::dontwait);
        
        if (result) {
            published_count_++;
            return true;
        } else {
            dropped_count_++;
            return false;
        }
        
    } catch (const zmq::error_t& e) {
        std::cerr << "ZMQ publish error: " << e.what() << std::endl;
        dropped_count_++;
        return false;
    }
}

} // namespace mdai
