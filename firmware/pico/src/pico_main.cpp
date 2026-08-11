#include "pico/stdlib.h"
#include "hardware/watchdog.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>

#include "can_protocol.hpp"
#include "board_config.hpp"
#include "fire_output.hpp"
#include "io_hal.hpp"
#include "safety_state_machine.hpp"
#include "telemetry_frames.hpp"
#include "usb_serial_protocol.hpp"

namespace {
constexpr std::uint16_t kCommandMeta = 0x10F;
constexpr std::uint16_t kPanTilt = 0x110;
constexpr std::uint16_t kFire = 0x111;
constexpr std::uint16_t kSystem = 0x112;
constexpr std::uint16_t kHeartbeat = 0x120;
constexpr std::uint16_t kStatus = 0x200;
constexpr std::uint16_t kEstop = 0x201;
constexpr std::uint16_t kFirmware = 0x202;
constexpr std::uint16_t kEncoder = 0x203;
constexpr std::uint16_t kFault = 0x204;
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

std::uint8_t encoder_flags(const gokkalkan::Inputs& inputs) {
  return (inputs.direction_ok ? 0x02U : 0U) |
         (inputs.encoder_connected ? 0x04U : 0U) |
         (inputs.encoder_overflow ? 0x08U : 0U) |
         (!inputs.deviation_ok ? 0x10U : 0U);
}

void send_status(std::uint8_t sequence, std::uint32_t now_ms,
                 const gokkalkan::SafetyStateMachine& safety,
                 const gokkalkan::Inputs& inputs) {
  const bool motion_ok = !inputs.estop && inputs.encoder_connected &&
                         !inputs.encoder_overflow && inputs.direction_ok &&
                         inputs.deviation_ok;
  const bool fire_ready = safety.state() == gokkalkan::State::ARMED &&
                          motion_ok && inputs.fire_interlock_closed &&
                          inputs.trigger_released;
  send_message(kStatus, gokkalkan::telemetry::status(
      sequence,
      {safety.state(), inputs.estop, motion_ok, fire_ready,
       safety.heartbeat_ok(now_ms),
       static_cast<std::uint8_t>(safety.fault_code()),
       encoder_flags(inputs), 1}));
}

#if defined(GOKKALKAN_ENABLE_ACTUATORS)
class PicoFirePin final : public gokkalkan::DigitalOutput {
 public:
  explicit PicoFirePin(std::uint8_t pin) : pin_(pin) {
    gpio_init(pin_);
    gpio_set_dir(pin_, GPIO_OUT);
    write(false);
  }
  void write(bool active) override {
    gpio_put(pin_, active == gokkalkan::board::kFireOutputActiveHigh);
  }
 private:
  std::uint8_t pin_;
};

void configure_input(std::uint8_t pin) {
  gpio_init(pin);
  gpio_set_dir(pin, GPIO_IN);
  gpio_pull_up(pin);
}
#endif
}  // namespace

// Actuator pin assignments deliberately remain disabled until the reviewed
// board revision exists. USB transport and the fail-closed state machine are
// operational; no GPIO can energise a motor or firing interface in this build.
int main() {
  stdio_init_all();
  gokkalkan::SafetyStateMachine safety;
  gokkalkan::Inputs inputs;
#if defined(GOKKALKAN_ENABLE_ACTUATORS)
  configure_input(gokkalkan::board::kPins.estop_safe_sense);
  configure_input(gokkalkan::board::kPins.fire_interlock);
  configure_input(gokkalkan::board::kPins.trigger_feedback);
  configure_input(gokkalkan::board::kPins.pan_limit_nc);
  configure_input(gokkalkan::board::kPins.tilt_limit_nc);
  gokkalkan::PicoIo io(
      {gokkalkan::board::kEstopSafeSenseActiveLow,
       gokkalkan::board::kFireInterlockActiveLow,
       gokkalkan::board::kTriggerReleasedActiveLow,
       gokkalkan::board::kLimitClearActiveLow});
  PicoFirePin fire_pin(gokkalkan::board::kPins.fire_output);
  gokkalkan::FireOutput fire_output(fire_pin);
#else
  inputs.estop = true;
  inputs.fire_interlock_closed = false;
  inputs.trigger_released = false;
  inputs.encoder_connected = false;
  inputs.direction_ok = false;
  inputs.deviation_ok = false;
#endif
  safety.apply(gokkalkan::Command::BOOT_COMPLETE,
               to_ms_since_boot(get_absolute_time()), inputs);
  gokkalkan::usb::StreamDecoder decoder;
  PendingCommand pending;
  std::uint8_t status_sequence = 0;
  std::uint32_t last_status_ms = 0;
  bool last_estop = inputs.estop;
  auto last_fault = safety.fault_code();
  send_message(kFirmware, gokkalkan::telemetry::firmware(1, 1, 0, 0));
  watchdog_enable(250, true);

  while (true) {
    const auto now = to_ms_since_boot(get_absolute_time());
#if defined(GOKKALKAN_ENABLE_ACTUATORS)
    gokkalkan::RawDigitalInputs raw;
    raw.estop_safe_sense_level = gpio_get(gokkalkan::board::kPins.estop_safe_sense);
    raw.fire_interlock_level = gpio_get(gokkalkan::board::kPins.fire_interlock);
    raw.trigger_feedback_level = gpio_get(gokkalkan::board::kPins.trigger_feedback);
    raw.pan_limit_nc_level = gpio_get(gokkalkan::board::kPins.pan_limit_nc);
    raw.tilt_limit_nc_level = gpio_get(gokkalkan::board::kPins.tilt_limit_nc);
    io.update(raw, now);
    // Encoder GPIO decoding remains fail-closed until the purchased encoder's
    // output type and counts/revolution are recorded in the signed pin map.
    io.set_encoder_health(false, false, false, false);
    inputs = io.safety_inputs();
#endif
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
#if defined(GOKKALKAN_ENABLE_ACTUATORS)
              if (result == 0 && !fire_output.start(
                                     now, gokkalkan::FireOutput::kMaximumPulseMs))
                result = 1;
#endif
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
#if defined(GOKKALKAN_ENABLE_ACTUATORS)
    fire_output.tick(now);
    if (!safety.fire_output_enabled()) fire_output.force_off();
#endif
    if (inputs.estop != last_estop) {
      send_message(kEstop, gokkalkan::telemetry::estop(
          ++status_sequence, inputs.estop, inputs.estop ? 1 : 0));
      last_estop = inputs.estop;
    }
    if (safety.fault_code() != last_fault) {
      if (safety.fault_code() != gokkalkan::FaultCode::NONE)
        send_message(kFault, gokkalkan::telemetry::fault(
            ++status_sequence,
            static_cast<std::uint8_t>(safety.fault_code())));
      last_fault = safety.fault_code();
    }
    if (now - last_status_ms >= 100U) {
      send_status(++status_sequence, now, safety, inputs);
      send_message(kEncoder, gokkalkan::telemetry::encoder(
          status_sequence, 0, 0, encoder_flags(inputs)));
      last_status_ms = now;
    }
    watchdog_update();
    sleep_ms(1);
  }
}
