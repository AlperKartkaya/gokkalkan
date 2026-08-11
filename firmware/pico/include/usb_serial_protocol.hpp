#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace gokkalkan::usb {
constexpr std::uint8_t transport_version = 1;
constexpr std::size_t max_payload_size = 64;
constexpr std::size_t max_encoded_size = 128;

struct Message {
  std::uint16_t id{0};
  std::array<std::uint8_t, max_payload_size> payload{};
  std::size_t size{0};
};

std::uint16_t crc16_ccitt(const std::uint8_t* data, std::size_t size);
bool encode(const Message& message, std::array<std::uint8_t, max_encoded_size>& output,
            std::size_t& output_size);
bool decode(const std::uint8_t* encoded, std::size_t encoded_size, Message& message);

class StreamDecoder {
 public:
  bool push(std::uint8_t byte, Message& message);
  std::uint32_t rejected_count() const { return rejected_count_; }

 private:
  std::array<std::uint8_t, max_encoded_size> buffer_{};
  std::size_t size_{0};
  std::uint32_t rejected_count_{0};
};
}  // namespace gokkalkan::usb
