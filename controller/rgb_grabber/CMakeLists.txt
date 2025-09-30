# RGB Frame Grabber for Jetson Nano
# Optimized for real-time capture without blocking

cmake_minimum_required(VERSION 3.10)
project(rgb_grabber VERSION 1.0.0 LANGUAGES CXX)

# C++14 for Jetson Nano compatibility
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Optimization flags for Jetson Nano
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -march=native -mtune=native")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread")

# Find dependencies
find_package(realsense2 REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBZMQ REQUIRED libzmq)

# Include directories
include_directories(
    ${realsense2_INCLUDE_DIR}
    ${LIBZMQ_INCLUDE_DIRS}
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# Source files
set(SOURCES
    src/rgb_grabber.cpp
    src/frame_publisher.cpp
    src/main.cpp
)

# Executable
add_executable(rgb-grabber ${SOURCES})

# Link libraries
target_link_libraries(rgb-grabber
    ${realsense2_LIBRARY}
    ${LIBZMQ_LIBRARIES}
    pthread
)

# Install
install(TARGETS rgb-grabber DESTINATION bin)
