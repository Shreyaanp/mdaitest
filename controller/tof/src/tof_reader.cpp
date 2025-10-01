#include "tof_reader.hpp"

#include <chrono>
#include <cctype>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/i2c-dev.h>

uint64_t monotonic_millis() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count();
}

bool write_gpio_value(const std::string& path, bool high) {
    if (path.empty()) {
        return true;
    }
    std::ofstream ofs(path);
    if (!ofs) {
        std::cerr << "Failed to open GPIO path: " << path << std::endl;
        return false;
    }
    ofs << (high ? "1" : "0");
    return ofs.good();
}

// Raw I2C VL53L0X implementation
class RawVL53L0X {
private:
    int file;
    int addr = 0x29;

public:
    bool init(int bus_number, uint8_t i2c_address) {
        addr = i2c_address;
        
        // Open I2C bus
        std::string filename = "/dev/i2c-" + std::to_string(bus_number);
        file = open(filename.c_str(), O_RDWR);
        if (file < 0) {
            std::cerr << "Error: Could not open I2C device " << filename << std::endl;
            return false;
        }

        // Set I2C slave address
        if (ioctl(file, I2C_SLAVE, addr) < 0) {
            std::cerr << "Error: Could not set I2C address" << std::endl;
            close(file);
            return false;
        }

        // Check if VL53L0X is present
        uint8_t model_id = readReg8(0xC0);
        if (model_id != 0xEE) {
            std::cerr << "Error: VL53L0X not found. Expected model ID 0xEE, got 0x" 
                      << std::hex << (int)model_id << std::endl;
            close(file);
            return false;
        }

        // Initialize sensor
        initSensor();
        
        return true;
    }

    void initSensor() {
        // Minimal init - just enable the sensor
        writeReg8(0x88, 0x00);
        writeReg8(0x80, 0x01);
        writeReg8(0xFF, 0x01);
        writeReg8(0x00, 0x00);
        writeReg8(0x91, readReg8(0x91) | 0x3C);
        writeReg8(0x00, 0x01);
        writeReg8(0xFF, 0x00);
        writeReg8(0x80, 0x00);
        
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    uint16_t readRangeSingleMillimeters() {
        // Start single shot measurement
        writeReg8(0x00, 0x01);

        // Wait for measurement to complete
        uint32_t timeout = 0;
        while ((readReg8(0x13) & 0x07) == 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
            timeout++;
            if (timeout > 50) {
                return 0; // Timeout
            }
        }

        // Read the range result
        uint16_t range = readReg16(0x1E);

        // Clear interrupt
        writeReg8(0x0B, 0x01);

        return range;
    }

    void closeDevice() {
        if (file >= 0) {
            ::close(file);
            file = -1;
        }
    }

private:
    uint8_t readReg8(uint8_t reg) {
        uint8_t data = 0;
        if (write(file, &reg, 1) == 1) {
            if (read(file, &data, 1) != 1) {
                data = 0;
            }
        }
        return data;
    }

    uint16_t readReg16(uint8_t reg) {
        uint8_t data[2] = {0, 0};
        if (write(file, &reg, 1) == 1) {
            if (read(file, data, 2) != 2) {
                data[0] = data[1] = 0;
            }
        }
        return (data[0] << 8) | data[1];
    }

    void writeReg8(uint8_t reg, uint8_t value) {
        uint8_t data[2] = {reg, value};
        if (write(file, data, 2) != 2) {
            // Write failed, but continue
        }
    }
};

ToFReader::ToFReader(const ToFConfig& cfg) : config_(cfg) {}

ToFReader::~ToFReader() {
    if (raw_sensor_) {
        raw_sensor_->closeDevice();
    }
}

int ToFReader::parse_bus_number(const std::string& bus) const {
    auto pos = bus.rfind("i2c-");
    if (pos != std::string::npos) {
        try {
            return std::stoi(bus.substr(pos + 4));
        } catch (...) {
        }
    }
    // Fallback: try to parse trailing digits
    std::string digits;
    for (auto it = bus.rbegin(); it != bus.rend(); ++it) {
        if (std::isdigit(*it)) {
            digits.insert(digits.begin(), *it);
        } else if (!digits.empty()) {
            break;
        }
    }
    if (!digits.empty()) {
        try {
            return std::stoi(digits);
        } catch (...) {
        }
    }
    return 1;
}

bool ToFReader::reset_sensor() {
    if (config_.xshut_path.empty()) {
        return true;
    }
    if (!write_gpio_value(config_.xshut_path, false)) {
        return false;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
    if (!write_gpio_value(config_.xshut_path, true)) {
        return false;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
    return true;
}

bool ToFReader::initialize_sensor() {
    try {
        raw_sensor_ = std::make_unique<RawVL53L0X>();
        if (!raw_sensor_->init(bus_number_, config_.i2c_address)) {
            std::cerr << "Raw VL53L0X init failed" << std::endl;
            raw_sensor_.reset();
            return false;
        }
    } catch (const std::exception& ex) {
        std::cerr << "Raw VL53L0X init exception: " << ex.what() << std::endl;
        raw_sensor_.reset();
        return false;
    } catch (...) {
        std::cerr << "Raw VL53L0X init exception: unknown error" << std::endl;
        raw_sensor_.reset();
        return false;
    }

    initialized_ = true;
    return true;
}

bool ToFReader::init() {
    bus_number_ = parse_bus_number(config_.i2c_bus);

    initialized_ = false;
    raw_sensor_.reset();

    if (!reset_sensor()) {
        return false;
    }

    return initialize_sensor();
}

std::optional<ToFMeasurement> ToFReader::read_once() {
    if (!initialized_ || !raw_sensor_) {
        if (!init()) {
            return std::nullopt;
        }
    }

    uint16_t distance = 0;
    try {
        distance = raw_sensor_->readRangeSingleMillimeters();
    } catch (const std::exception& ex) {
        std::cerr << "Raw VL53L0X read exception: " << ex.what() << std::endl;
        raw_sensor_.reset();
        initialized_ = false;
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        return std::nullopt;
    } catch (...) {
        std::cerr << "Raw VL53L0X read exception: unknown error" << std::endl;
        raw_sensor_.reset();
        initialized_ = false;
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        return std::nullopt;
    }

    // Filter out obviously bad readings but be less strict than the original
    if (distance == 0 || distance > 8000) {
        return std::nullopt;
    }

    ToFMeasurement measurement;
    measurement.distance_mm = distance;
    measurement.signal_rate = 1000.0f;  // Dummy signal rate since we don't read it in raw mode
    measurement.timestamp_ms = monotonic_millis();
    return measurement;
}
