#include "usb_serial_protocol.hpp"

namespace gokkalkan::usb {
std::uint16_t crc16_ccitt(const std::uint8_t* data, std::size_t size) {
  std::uint16_t crc = 0xFFFFU;
  for (std::size_t i = 0; i < size; ++i) {
    crc ^= static_cast<std::uint16_t>(data[i]) << 8U;
    for (int bit = 0; bit < 8; ++bit)
      crc = (crc & 0x8000U) ? static_cast<std::uint16_t>((crc << 1U) ^ 0x1021U)
                            : static_cast<std::uint16_t>(crc << 1U);
  }
  return crc;
}

static bool cobs_encode(const std::uint8_t* input, std::size_t input_size,
                        std::array<std::uint8_t, max_encoded_size>& output,
                        std::size_t& output_size) {
  std::size_t write = 1, code_index = 0;
  std::uint8_t code = 1;
  for (std::size_t read = 0; read < input_size; ++read) {
    if (input[read] == 0) {
      output[code_index] = code;
      code_index = write++;
      code = 1;
    } else {
      if (write >= output.size() - 1) return false;
      output[write++] = input[read];
      if (++code == 0xFFU) {
        output[code_index] = code;
        code_index = write++;
        code = 1;
      }
    }
  }
  output[code_index] = code;
  output[write++] = 0;
  output_size = write;
  return true;
}

static bool cobs_decode(const std::uint8_t* input, std::size_t input_size,
                        std::array<std::uint8_t, max_encoded_size>& output,
                        std::size_t& output_size) {
  std::size_t read = 0, write = 0;
  while (read < input_size) {
    const std::uint8_t code = input[read++];
    if (code == 0 || read + code - 1 > input_size) return false;
    for (std::uint8_t i = 1; i < code; ++i) {
      if (write >= output.size()) return false;
      output[write++] = input[read++];
    }
    if (code != 0xFFU && read < input_size) output[write++] = 0;
  }
  output_size = write;
  return true;
}

bool encode(const Message& message, std::array<std::uint8_t, max_encoded_size>& output,
            std::size_t& output_size) {
  if (message.id > 0x7FFU || message.size > max_payload_size) return false;
  std::array<std::uint8_t, max_encoded_size> raw{};
  raw[0] = transport_version;
  raw[1] = static_cast<std::uint8_t>(message.id >> 8U);
  raw[2] = static_cast<std::uint8_t>(message.id);
  raw[3] = static_cast<std::uint8_t>(message.size);
  for (std::size_t i = 0; i < message.size; ++i) raw[4 + i] = message.payload[i];
  const std::size_t body_size = 4 + message.size;
  const auto crc = crc16_ccitt(raw.data(), body_size);
  raw[body_size] = static_cast<std::uint8_t>(crc >> 8U);
  raw[body_size + 1] = static_cast<std::uint8_t>(crc);
  return cobs_encode(raw.data(), body_size + 2, output, output_size);
}

bool decode(const std::uint8_t* encoded, std::size_t encoded_size, Message& message) {
  std::array<std::uint8_t, max_encoded_size> raw{};
  std::size_t raw_size = 0;
  if (!cobs_decode(encoded, encoded_size, raw, raw_size) || raw_size < 6) return false;
  const std::size_t body_size = raw_size - 2;
  const auto received_crc = static_cast<std::uint16_t>(raw[body_size] << 8U) | raw[body_size + 1];
  if (crc16_ccitt(raw.data(), body_size) != received_crc || raw[0] != transport_version) return false;
  const auto id = static_cast<std::uint16_t>(
      (static_cast<std::uint16_t>(raw[1]) << 8U) |
      static_cast<std::uint16_t>(raw[2]));
  const auto size = static_cast<std::size_t>(raw[3]);
  if (id > 0x7FFU || size > max_payload_size || body_size != 4 + size) return false;
  message.id = id;
  message.size = size;
  for (std::size_t i = 0; i < size; ++i) message.payload[i] = raw[4 + i];
  return true;
}

bool StreamDecoder::push(std::uint8_t byte, Message& message) {
  if (byte == 0) {
    if (size_ == 0) return false;
    const bool valid = decode(buffer_.data(), size_, message);
    if (!valid) ++rejected_count_;
    size_ = 0;
    return valid;
  }
  if (size_ >= buffer_.size()) {
    size_ = 0;
    ++rejected_count_;
    return false;
  }
  buffer_[size_++] = byte;
  return false;
}
}  // namespace gokkalkan::usb
