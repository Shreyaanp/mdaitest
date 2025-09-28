#include <vl53lXx/interfaces/i2c_interface.hpp>

I2CInterface::I2CInterface(uint8_t port, uint8_t address) : I2Cdev(port, address) {}

I2CInterface::~I2CInterface() = default;

