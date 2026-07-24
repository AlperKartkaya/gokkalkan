#include "can_protocol.hpp"

namespace gokkalkan::can {
std::uint8_t crc8(const std::uint8_t* data, std::size_t size) {
  std::uint8_t crc = 0;
  for (std::size_t i = 0; i < size; ++i) {
    crc ^= data[i];
    for (int bit = 0; bit < 8; ++bit)
      crc = (crc & 0x80U) ? static_cast<std::uint8_t>((crc << 1U) ^ 0x07U)
                          : static_cast<std::uint8_t>(crc << 1U);
  }
  return crc;
}
bool valid(const Frame& frame) {
  return frame[0] == protocol_version && frame[7] == crc8(frame.data(), 7);
}
bool sequence_is_newer(std::uint8_t candidate, std::uint8_t previous) {
  const auto delta = static_cast<std::uint8_t>(candidate - previous);
  return delta >= 1U && delta <= 127U;
}
}
