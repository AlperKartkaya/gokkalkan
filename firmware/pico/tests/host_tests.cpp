#include "can_protocol.hpp"
#include "board_config.hpp"
#include "io_hal.hpp"
#include "encoder_monitor.hpp"
#include "fire_output.hpp"
#include "motion_controller.hpp"
#include "telemetry_frames.hpp"
#include "safety_state_machine.hpp"
#include "usb_serial_protocol.hpp"
#include <cassert>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

using gokkalkan::Command;
using gokkalkan::Inputs;
using gokkalkan::SafetyStateMachine;

class TestStepOutput final : public gokkalkan::StepOutput {
 public:
  void set_enabled(bool value) override { enabled = value; }
  void set_direction(bool value) override { positive = value; }
  void pulse() override { ++pulses; }
  bool enabled{false};
  bool positive{false};
  int pulses{0};
};

class TestDigitalOutput final : public gokkalkan::DigitalOutput {
 public:
  void write(bool value) override { active = value; }
  bool active{false};
};

static Command command(const std::string& value) {
  if (value == "BOOT_COMPLETE") return Command::BOOT_COMPLETE;
  if (value == "HEARTBEAT") return Command::HEARTBEAT;
  if (value == "ARM") return Command::ARM;
  if (value == "FIRE") return Command::FIRE;
  return Command::DISARM;
}
static void reach(SafetyStateMachine& machine, const std::string& state) {
  Inputs safe_inputs;
  safe_inputs.fire_interlock_closed = true;
  machine.apply(Command::BOOT_COMPLETE, 0);
  if (state == "BOOT" || state == "SAFE") return;
  machine.apply(Command::HEARTBEAT, 1, safe_inputs);
  if (state == "READY") return;
  machine.apply(Command::ARM, 2, safe_inputs);
  if (state == "ARMED") return;
  machine.apply(Command::FIRE, 3, safe_inputs);
}
int main() {
  std::ifstream input(GOKKALKAN_VECTOR_PATH);
  assert(input.good());
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') continue;
    std::vector<std::string> fields;
    std::stringstream stream(line);
    std::string field;
    while (std::getline(stream, field, ',')) fields.push_back(field);
    assert(fields.size() == 7);
    SafetyStateMachine machine;
    reach(machine, fields[1]);
    Inputs inputs;
    inputs.fire_interlock_closed = true;
    if (fields[3] == "estop") inputs.estop = true;
    if (fields[3] == "encoder_disconnected") inputs.encoder_connected = false;
    if (fields[3] == "encoder_overflow") inputs.encoder_overflow = true;
    if (fields[3] == "direction_fault") inputs.direction_ok = false;
    if (fields[3] == "deviation_fault") inputs.deviation_ok = false;
    const char* reason = machine.apply(command(fields[2]), 4, inputs);
    assert(fields[4] == gokkalkan::state_name(machine.state()));
    assert(fields[5] == reason);
    assert((fields[6] == "1") == machine.outputs_enabled());
  }
  gokkalkan::can::Frame valid{1, 2, 3, 4, 5, 6, 7, 0};
  valid[7] = gokkalkan::can::crc8(valid.data(), 7);
  assert(gokkalkan::can::valid(valid));
  valid[3] ^= 1;
  assert(!gokkalkan::can::valid(valid));
  assert(gokkalkan::can::sequence_is_newer(0, 255));
  assert(!gokkalkan::can::sequence_is_newer(5, 5));

  gokkalkan::usb::Message usb_message;
  usb_message.id = 0x210;
  usb_message.size = 8;
  for (std::size_t i = 0; i < usb_message.size; ++i)
    usb_message.payload[i] = static_cast<std::uint8_t>(i);
  std::array<std::uint8_t, gokkalkan::usb::max_encoded_size> encoded{};
  std::size_t encoded_size = 0;
  assert(gokkalkan::usb::encode(usb_message, encoded, encoded_size));
  assert(encoded[encoded_size - 1] == 0);
  gokkalkan::usb::Message decoded;
  assert(gokkalkan::usb::decode(encoded.data(), encoded_size - 1, decoded));
  assert(decoded.id == usb_message.id && decoded.size == usb_message.size);
  assert(decoded.payload[4] == 4);
  encoded[3] ^= 1;
  assert(!gokkalkan::usb::decode(encoded.data(), encoded_size - 1, decoded));

  SafetyStateMachine firing;
  Inputs safe_inputs;
  safe_inputs.fire_interlock_closed = true;
  firing.apply(Command::BOOT_COMPLETE, 0, safe_inputs);
  firing.apply(Command::HEARTBEAT, 1, safe_inputs);
  assert(std::string(firing.apply(Command::ARM, 2, safe_inputs)) == "ARMED");
  assert(std::string(firing.apply(Command::FIRE, 3, safe_inputs)) == "FIRING");
  assert(firing.fire_output_enabled());
  assert(std::string(firing.tick(123, safe_inputs)) == "FIRE_PULSE_COMPLETE");
  assert(!firing.fire_output_enabled());
  assert(firing.state() == gokkalkan::State::ARMED);

  SafetyStateMachine rejected;
  rejected.apply(Command::BOOT_COMPLETE, 0);
  rejected.apply(Command::HEARTBEAT, 1);
  assert(std::string(rejected.apply(Command::ARM, 2)) == "REJECTED_INTERLOCK");
  assert(!rejected.outputs_enabled());

  assert(!gokkalkan::board::pins_verified(gokkalkan::board::kPins));

  gokkalkan::PicoIo io({true, true, true, true}, 20);
  gokkalkan::RawDigitalInputs safe_levels;
  safe_levels.estop_safe_sense_level = false;
  safe_levels.fire_interlock_level = false;
  safe_levels.trigger_feedback_level = false;
  safe_levels.pan_limit_nc_level = false;
  safe_levels.tilt_limit_nc_level = false;
  io.set_encoder_health(true, false, true, true);
  io.update(safe_levels, 0);
  assert(io.safety_inputs().estop);  // Safe transitions are debounced.
  io.update(safe_levels, 20);
  Inputs io_safe = io.safety_inputs();
  assert(!io_safe.estop && io_safe.fire_interlock_closed);
  assert(io_safe.trigger_released && io_safe.encoder_connected);
  assert(io_safe.pan_limit_clear && io_safe.tilt_limit_clear);

  safe_levels.estop_safe_sense_level = true;
  io.update(safe_levels, 21);
  assert(io.safety_inputs().estop);  // Unsafe transitions are immediate.

  gokkalkan::PicoIo disconnected({true, true, true, true}, 20);
  disconnected.update({}, 100);
  const Inputs disconnected_inputs = disconnected.safety_inputs();
  assert(disconnected_inputs.estop);
  assert(!disconnected_inputs.encoder_connected);

  TestStepOutput step_output;
  gokkalkan::AxisController axis({100.0, -10.0, 10.0, 1000.0, 2000.0, 0.01},
                                 step_output);
  assert(!axis.command_target(1.0));
  axis.set_referenced(0.0);
  assert(axis.command_target(1.0));
  assert(step_output.enabled && step_output.positive);
  for (std::uint64_t now_us = 1000; now_us < 300000; now_us += 1000)
    axis.tick(now_us, axis.expected_angle_deg(), true, true);
  assert(step_output.pulses > 0);
  axis.tick(301000, 1.0, true, true);
  assert(axis.state() == gokkalkan::AxisState::IDLE);
  assert(!step_output.enabled);
  assert(!axis.command_target(11.0));
  assert(axis.command_target(-1.0));
  axis.tick(302000, 0.9, false, true);
  assert(axis.state() == gokkalkan::AxisState::FAULT);

  gokkalkan::EncoderMonitor encoder({100.0, 0.5, 100000});
  encoder.set_connected(true);
  encoder.reference(1000);
  auto encoder_status = encoder.update(1100, 1, 1.0);
  assert(encoder_status.angle_deg == 1.0);
  assert(encoder_status.direction_ok && encoder_status.deviation_ok);
  encoder_status = encoder.update(1090, 1, 1.0);
  assert(!encoder_status.direction_ok);

  TestDigitalOutput fire_pin;
  gokkalkan::FireOutput fire_output(fire_pin);
  assert(!fire_pin.active);
  assert(!fire_output.start(0, 121));
  assert(fire_output.start(10, 120));
  assert(fire_pin.active && fire_output.active());
  assert(!fire_output.tick(129));
  assert(fire_output.tick(130));
  assert(!fire_pin.active && !fire_output.active());

  const auto status_frame = gokkalkan::telemetry::status(
      7, {gokkalkan::State::ARMED, false, true, true, true, 0, 0x07, 1});
  assert(gokkalkan::can::valid(status_frame));
  assert(status_frame[1] == 7 && status_frame[2] == 3);
  assert(status_frame[3] == 0x0E);
  const auto estop_frame = gokkalkan::telemetry::estop(8, true, 1);
  assert(gokkalkan::can::valid(estop_frame) && estop_frame[2] == 1);
  const auto firmware_frame = gokkalkan::telemetry::firmware(9, 1, 2, 3);
  assert(gokkalkan::can::valid(firmware_frame) && firmware_frame[4] == 3);
  const auto encoder_frame = gokkalkan::telemetry::encoder(10, 100, -200, 0x07);
  assert(gokkalkan::can::valid(encoder_frame));
  assert(encoder_frame[2] == 0 && encoder_frame[3] == 100);
  const auto fault_frame = gokkalkan::telemetry::fault(11, 8);
  assert(gokkalkan::can::valid(fault_frame) && fault_frame[2] == 8);
}
