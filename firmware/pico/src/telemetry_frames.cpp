#include "telemetry_frames.hpp"

namespace gokkalkan::telemetry {
namespace {
can::Frame finish(can::Frame frame) {
  frame[7] = can::crc8(frame.data(), 7);
  return frame;
}
}  // namespace

can::Frame status(std::uint8_t sequence, const StatusSource& source) {
  const std::uint8_t flags =
      (source.estop_active ? 0x01U : 0U) |
      (source.motion_ok ? 0x02U : 0U) |
      (source.fire_ready ? 0x04U : 0U) |
      (source.watchdog_ok ? 0x08U : 0U);
  return finish({can::protocol_version, sequence,
                 static_cast<std::uint8_t>(source.state), flags,
                 source.fault_code, source.encoder_flags,
                 source.firmware_major, 0});
}

can::Frame estop(std::uint8_t sequence, bool active, std::uint8_t reason) {
  return finish({can::protocol_version, sequence,
                 static_cast<std::uint8_t>(active), reason, 0, 0, 0, 0});
}

can::Frame firmware(std::uint8_t sequence, std::uint8_t major,
                    std::uint8_t minor, std::uint8_t patch) {
  return finish({can::protocol_version, sequence, major, minor, patch,
                 can::protocol_version, 0, 0});
}

can::Frame encoder(std::uint8_t sequence, std::int16_t pan_centideg,
                   std::int16_t tilt_centideg, std::uint8_t flags) {
  return finish({can::protocol_version, sequence,
                 static_cast<std::uint8_t>(pan_centideg >> 8),
                 static_cast<std::uint8_t>(pan_centideg),
                 static_cast<std::uint8_t>(tilt_centideg >> 8),
                 static_cast<std::uint8_t>(tilt_centideg), flags, 0});
}

can::Frame fault(std::uint8_t sequence, std::uint8_t code,
                 std::uint8_t detail) {
  return finish({can::protocol_version, sequence, code, detail, 0, 0, 0, 0});
}

}  // namespace gokkalkan::telemetry
