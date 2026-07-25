#include "can_protocol.hpp"
#include "safety_state_machine.hpp"
#include <cassert>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

using gokkalkan::Command;
using gokkalkan::Inputs;
using gokkalkan::SafetyStateMachine;

static Command command(const std::string& value) {
  if (value == "BOOT_COMPLETE") return Command::BOOT_COMPLETE;
  if (value == "HEARTBEAT") return Command::HEARTBEAT;
  if (value == "ARM") return Command::ARM;
  if (value == "FIRE") return Command::FIRE;
  return Command::DISARM;
}
static void reach(SafetyStateMachine& machine, const std::string& state) {
  machine.apply(Command::BOOT_COMPLETE, 0);
  if (state == "BOOT" || state == "SAFE") return;
  machine.apply(Command::HEARTBEAT, 1);
  if (state == "READY") return;
  machine.apply(Command::ARM, 2);
  if (state == "ARMED") return;
  machine.apply(Command::FIRE, 3);
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
}
