#pragma once

#include <cstdint>

#include "can_protocol.hpp"
#include "safety_state_machine.hpp"

namespace gokkalkan::telemetry {

struct StatusSource {
  State state{State::BOOT};
  bool estop_active{true};
  bool motion_ok{false};
  bool fire_ready{false};
  bool watchdog_ok{false};
  std::uint8_t fault_code{0};
  std::uint8_t encoder_flags{0};
  std::uint8_t firmware_major{1};
};

can::Frame status(std::uint8_t sequence, const StatusSource& source);
can::Frame estop(std::uint8_t sequence, bool active, std::uint8_t reason = 0);
can::Frame firmware(std::uint8_t sequence, std::uint8_t major,
                    std::uint8_t minor, std::uint8_t patch);
can::Frame encoder(std::uint8_t sequence, std::int16_t pan_centideg,
                   std::int16_t tilt_centideg, std::uint8_t flags);
can::Frame fault(std::uint8_t sequence, std::uint8_t code,
                 std::uint8_t detail = 0);

}  // namespace gokkalkan::telemetry
