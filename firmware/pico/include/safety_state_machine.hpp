#pragma once
#include <cstdint>
#include <string_view>

namespace gokkalkan {
enum class State : std::uint8_t { BOOT, SAFE, READY, ARMED, FIRING, FAULT };
enum class Command { BOOT_COMPLETE, HEARTBEAT, ARM, FIRE, DISARM, RESET };
enum class FaultCode : std::uint8_t {
  NONE = 0,
  ESTOP_ACTIVE = 1,
  FIRE_INTERLOCK_OPEN = 2,
  TRIGGER_FEEDBACK_STUCK = 3,
  ENCODER_DISCONNECTED = 4,
  ENCODER_OVERFLOW = 5,
  ENCODER_DIRECTION = 6,
  ENCODER_DEVIATION = 7,
  HEARTBEAT_TIMEOUT = 8,
  INTERNAL = 255
};

struct Inputs {
  bool estop{false};
  bool fire_interlock_closed{false};
  bool trigger_released{true};
  bool encoder_connected{true};
  bool encoder_overflow{false};
  bool direction_ok{true};
  bool deviation_ok{true};
  bool pan_limit_clear{true};
  bool tilt_limit_clear{true};
};

class SafetyStateMachine {
 public:
  const char* apply(Command command, std::uint32_t now_ms, Inputs inputs = {});
  const char* tick(std::uint32_t now_ms, Inputs inputs);
  State state() const { return state_; }
  bool outputs_enabled() const { return outputs_enabled_; }
  bool fire_output_enabled() const { return fire_output_enabled_; }
  FaultCode fault_code() const { return fault_code_; }
  bool heartbeat_ok(std::uint32_t now_ms) const {
    return last_heartbeat_ms_ != 0 &&
           now_ms - last_heartbeat_ms_ <= watchdog_timeout_ms_;
  }
  const char* fault(const char* reason);
 private:
  State state_{State::BOOT};
  bool outputs_enabled_{false};
  bool fire_output_enabled_{false};
  std::uint32_t last_heartbeat_ms_{0};
  std::uint32_t fire_started_ms_{0};
  FaultCode fault_code_{FaultCode::NONE};
  static constexpr std::uint32_t watchdog_timeout_ms_{250};
  static constexpr std::uint32_t fire_pulse_max_ms_{120};
};
const char* state_name(State state);
}
