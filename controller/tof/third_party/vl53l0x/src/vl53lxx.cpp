#include <vl53lXx/vl53lxx.hpp>
#include <vl53lXx/interfaces/i2c_interface.hpp>

VL53LXX::VL53LXX(uint8_t port, const uint8_t address, const int16_t xshutGPIOPin, bool ioMode2v8, float *calib) :
    i2c(new I2CInterface(port, address)),
    xshutGPIOPin(xshutGPIOPin),
    ioMode2v8(ioMode2v8)
{
    if (calib) {
        this->calib[0] = calib[0];
        this->calib[1] = calib[1];
    } else {
        this->calib[0] = DEFAULT_CALIB[0];
        this->calib[1] = DEFAULT_CALIB[1];
    }
}

VL53LXX::~VL53LXX() {
    delete i2c;
    i2c = nullptr;
}

void VL53LXX::powerOn() {
    // GPIO toggling is optional; real hardware reset is handled externally.
}

void VL53LXX::powerOff() {
    // See comment in powerOn().
}

void VL53LXX::initGPIO() {
    gpioInitialized = true;
}

