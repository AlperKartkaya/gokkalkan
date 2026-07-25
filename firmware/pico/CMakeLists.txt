cmake_minimum_required(VERSION 3.16)
option(GOKKALKAN_BUILD_PICO "Build RP2040 firmware with the Pico SDK" OFF)
if(GOKKALKAN_BUILD_PICO)
  if(NOT DEFINED ENV{PICO_SDK_PATH})
    message(FATAL_ERROR "PICO_SDK_PATH is required for a Pico build")
  endif()
  include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)
endif()
project(gokkalkan_pico_firmware VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(gokkalkan_firmware_core
  src/safety_state_machine.cpp
  src/can_protocol.cpp
)
target_include_directories(gokkalkan_firmware_core PUBLIC include)
target_compile_options(gokkalkan_firmware_core PRIVATE -Wall -Wextra -Wpedantic)

enable_testing()
add_executable(firmware_host_tests tests/host_tests.cpp)
target_link_libraries(firmware_host_tests PRIVATE gokkalkan_firmware_core)
target_compile_definitions(firmware_host_tests PRIVATE
  GOKKALKAN_VECTOR_PATH="${CMAKE_CURRENT_SOURCE_DIR}/test_vectors.csv"
)
add_test(NAME firmware_host_tests COMMAND firmware_host_tests)

if(GOKKALKAN_BUILD_PICO)
  pico_sdk_init()
  add_executable(gokkalkan_pico src/pico_main.cpp)
  target_link_libraries(gokkalkan_pico PRIVATE
    gokkalkan_firmware_core pico_stdlib hardware_watchdog hardware_gpio
  )
  pico_add_extra_outputs(gokkalkan_pico)
endif()
