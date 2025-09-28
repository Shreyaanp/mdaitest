#pragma once

#include <cstdint>

#include <vl53lXx/interfaces/i2cdev.hpp>

/**
 * Thin wrapper that exposes the I2Cdev implementation under the I2CInterface
 * name used by the original VL53L0X Arduino/Linux port.
 */
class I2CInterface : public I2Cdev {
  public:
    I2CInterface(uint8_t port, uint8_t address);
    ~I2CInterface() override;
};

