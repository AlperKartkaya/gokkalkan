#pragma once
#include <array>
#include <cstdint>

namespace gokkalkan::can {
constexpr std::uint8_t protocol_version = 1;
using Frame = std::array<std::uint8_t, 8>;
std::uint8_t crc8(const std::uint8_t* data, std::size_t size);
bool valid(const Frame& frame);
bool sequence_is_newer(std::uint8_t candidate, std::uint8_t previous);
}
