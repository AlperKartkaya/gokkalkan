#pragma once

#include <array>
#include <cstdint>

namespace gokkalkan::board {

constexpr std::uint8_t kUnverifiedPin = 0xFFU;
constexpr char kBoardRevision[] = "GKK-IO-REV-A";

struct Pins {
  std::uint8_t estop_safe_sense{kUnverifiedPin};
  std::uint8_t fire_interlock{kUnverifiedPin};
  std::uint8_t trigger_feedback{kUnverifiedPin};
  std::uint8_t fire_output{kUnverifiedPin};
  std::uint8_t pan_limit_nc{kUnverifiedPin};
  std::uint8_t tilt_limit_nc{kUnverifiedPin};
  std::uint8_t pan_step{kUnverifiedPin};
  std::uint8_t pan_dir{kUnverifiedPin};
  std::uint8_t pan_enable{kUnverifiedPin};
  std::uint8_t tilt_step{kUnverifiedPin};
  std::uint8_t tilt_dir{kUnverifiedPin};
  std::uint8_t tilt_enable{kUnverifiedPin};
  std::uint8_t pan_encoder_a{kUnverifiedPin};
  std::uint8_t pan_encoder_b{kUnverifiedPin};
  std::uint8_t tilt_encoder_a{kUnverifiedPin};
  std::uint8_t tilt_encoder_b{kUnverifiedPin};
};

// GKK-IO-REV-A keeps the motor-test GP2/GP3/GP4 assignment for PAN and
// allocates the remaining safety, motion and encoder signals contiguously.
// Electrical polarity and isolated I/O behaviour still require the physical
// acceptance measurements recorded in docs/hardware/GKK-IO-REV-A_PIN_MAP.md.
constexpr Pins kPins{
    8,   // estop_safe_sense
    9,   // fire_interlock
    10,  // trigger_feedback
    11,  // fire_output
    12,  // pan_limit_nc
    13,  // tilt_limit_nc
    2,   // pan_step
    3,   // pan_dir
    4,   // pan_enable
    5,   // tilt_step
    6,   // tilt_dir
    7,   // tilt_enable
    14,  // pan_encoder_a
    15,  // pan_encoder_b
    16,  // tilt_encoder_a
    17,  // tilt_encoder_b
};

constexpr bool pins_verified(const Pins& pins) {
  const std::array<std::uint8_t, 16> values{
      pins.estop_safe_sense, pins.fire_interlock, pins.trigger_feedback,
      pins.fire_output, pins.pan_limit_nc, pins.tilt_limit_nc, pins.pan_step,
      pins.pan_dir, pins.pan_enable, pins.tilt_step, pins.tilt_dir,
      pins.tilt_enable, pins.pan_encoder_a, pins.pan_encoder_b,
      pins.tilt_encoder_a, pins.tilt_encoder_b};
  for (std::size_t i = 0; i < values.size(); ++i) {
    if (values[i] == kUnverifiedPin) return false;
    for (std::size_t j = i + 1; j < values.size(); ++j)
      if (values[i] == values[j]) return false;
  }
  return true;
}

// These values must be replaced only from the signed as-built pin map.
constexpr bool kEstopSafeSenseActiveLow = true;
constexpr bool kFireInterlockActiveLow = true;
constexpr bool kTriggerReleasedActiveLow = true;
constexpr bool kLimitClearActiveLow = true;
constexpr bool kFireOutputActiveHigh = true;

#if defined(GOKKALKAN_ENABLE_ACTUATORS)
static_assert(kBoardRevision[0] != 'U', "Actuator build requires a reviewed board revision");
static_assert(pins_verified(kPins), "Actuator build requires unique verified GPIO pins");
#endif

}  // namespace gokkalkan::board
