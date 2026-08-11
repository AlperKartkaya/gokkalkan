#include "pico/stdlib.h"
#include "hardware/watchdog.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>

#include "can_protocol.hpp"
#include "safety_state_machine.hpp"
#include "usb_serial_protocol.hpp"

namespace {
constexpr std::uint16_t kCommandMeta = 0x10F;
constexpr std::uint16_t kPanTilt = 0x110;
constexpr std::uint16_t kFire = 0x111;
constexpr std::uint16_t kSystem = 0x112;
constexpr std::uint16_t kHeartbeat = 0x120;
constexpr std::uint16_t kStatus = 0x200;
constexpr std::uint16_t kAck = 0x210;

struct PendingCommand {
  bool valid{false};
  std::uint8_t sequence{0};
  std::uint16_t tag{0};
  std::uint8_t kind{0};
};

std::uint8_t state_value(gokkalkan::State state) {
  return static_cast<std::uint8_t>(state);
}

void send_message(std::uint16_t id, const std::array<std::uint8_t, 8>& payload) {
  gokkalkan::usb::Message message;
  message.id = id;
  message.size = payload.size();
  std::copy(payload.begin(), payload.end(), message.payload.begin());
  std::array<std::uint8_t, gokkalkan::usb::max_encoded_size> encoded{};
  std::size_t encoded_size = 0;
  if (!gokkalkan::usb::encode(message, encoded, encoded_size)) return;
  for (std::size_t i = 0; i < encoded_size; ++i) putchar_raw(encoded[i]);
}

void send_ack(std::uint8_t sequence, std::uint16_t tag, std::uint8_t result,
              gokkalkan::State state) {
  std::array<std::uint8_t, 8> frame{
      1, sequence, static_cast<std::uint8_t>(tag >> 8U),
      static_cast<std::uint8_t>(tag), result, state_value(state), 0, 0};
  frame[7] = gokkalkan::can::crc8(frame.data(), 7);
  send_message(kAck, frame);
}

void send_status(std::uint8_t sequence, const gokkalkan::SafetyStateMachine& safety) {
  const std::uint8_t flags = safety.outputs_enabled() ? 0x02U : 0U;
  std::array<std::uint8_t, 8> frame{
      1, sequence, state_value(safety.state()), flags, 0, 0, 1, 0};
  frame[7] = gokkalkan::can::crc8(frame.data(), 7);
  send_message(kStatus, frame);
}
}  // namespace

// Actuator pin assignments deliberately remain disabled until the reviewed
// board revision exists. USB transport and the fail-closed state machine are
// operational; no GPIO can energise a motor or firing interface in this build.
int main() {
  stdio_init_all();
  gokkalkan::SafetyStateMachine safety;
  gokkalkan::Inputs inputs;
  safety.apply(gokkalkan::Command::BOOT_COMPLETE,
               to_ms_since_boot(get_absolute_time()), inputs);
  gokkalkan::usb::StreamDecoder decoder;
  PendingCommand pending;
  std::uint8_t status_sequence = 0;
  std::uint32_t last_status_ms = 0;
  watchdog_enable(250, true);

  while (true) {
    const auto now = to_ms_since_boot(get_absolute_time());
    int value = getchar_timeout_us(0);
    while (value != PICO_ERROR_TIMEOUT) {
      gokkalkan::usb::Message message;
      if (decoder.push(static_cast<std::uint8_t>(value), message) &&
          message.size == 8) {
        gokkalkan::can::Frame frame{};
        std::copy_n(message.payload.begin(), 8, frame.begin());
        if (gokkalkan::can::valid(frame)) {
          if (message.id == kHeartbeat) {
            safety.apply(gokkalkan::Command::HEARTBEAT, now, inputs);
          } else if (message.id == kCommandMeta) {
            pending = {true, frame[1],
                       static_cast<std::uint16_t>(frame[2] << 8U) | frame[3],
                       frame[4]};
          } else if (pending.valid && frame[1] == pending.sequence) {
            std::uint8_t result = 1;  // NACK_STATE unless explicitly accepted.
            if (message.id == kSystem && pending.kind == 3) {
              const std::uint8_t operation = frame[2];
              const char* reason = "REJECTED_STATE";
              if (operation == 0 || operation == 2)
                reason = safety.apply(gokkalkan::Command::DISARM, now, inputs);
              else if (operation == 1)
                reason = safety.apply(gokkalkan::Command::ARM, now, inputs);
              else if (operation == 3)
                reason = safety.apply(gokkalkan::Command::RESET, now, inputs);
              result = (std::strcmp(reason, "SAFE_STOP") == 0 ||
                        std::strcmp(reason, "ARMED") == 0 ||
                        std::strcmp(reason, "RESET_ACCEPTED") == 0)
                           ? 0
                           : 1;
            } else if (message.id == kFire && pending.kind == 2) {
              const char* reason = safety.apply(gokkalkan::Command::FIRE, now, inputs);
              result = std::strcmp(reason, "FIRING") == 0 ? 0 : 1;
            } else if (message.id == kPanTilt && pending.kind == 1) {
              // Board pin mapping/output stage is not approved yet.
              result = 1;
            } else {
              result = 4;  // NACK_COMMAND
            }
            send_ack(pending.sequence, pending.tag, result, safety.state());
            pending.valid = false;
          }
        }
      }
      value = getchar_timeout_us(0);
    }

    safety.tick(now, inputs);
    if (now - last_status_ms >= 100U) {
      send_status(++status_sequence, safety);
      last_status_ms = now;
    }
    watchdog_update();
    sleep_ms(1);
  }
}
