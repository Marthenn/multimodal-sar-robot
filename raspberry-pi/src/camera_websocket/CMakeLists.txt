cmake_minimum_required(VERSION 3.10)
project(camera_websocket_server)

set(CMAKE_CXX_STANDARD 11)

# Find OpenCV
find_package(OpenCV REQUIRED)

# Try to find libwebsockets with pkg-config if available
find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBWEBSOCKETS libwebsockets)

if(LIBWEBSOCKETS_FOUND)
    message(STATUS "Found libwebsockets via pkg-config")
    include_directories(${LIBWEBSOCKETS_INCLUDE_DIRS})
    link_directories(${LIBWEBSOCKETS_LIBRARY_DIRS})
else()
    message(WARNING "libwebsockets not found via pkg-config, falling back to manual paths")
    set(LIBWEBSOCKETS_INCLUDE_DIRS "/usr/include" "/usr/include/libwebsockets")
    set(LIBWEBSOCKETS_LIBRARIES "websockets")
    include_directories(${LIBWEBSOCKETS_INCLUDE_DIRS})
endif()

# Include OpenCV headers
include_directories(${OpenCV_INCLUDE_DIRS})

# Add executable
add_executable(camera_websocket_server ${CMAKE_SOURCE_DIR}/camera_websocket_server.cpp)

# Link libraries
target_link_libraries(camera_websocket_server ${OpenCV_LIBS} ${LIBWEBSOCKETS_LIBRARIES})
