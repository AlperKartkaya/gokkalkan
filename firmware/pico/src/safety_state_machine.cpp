#include "safety_state_machine.hpp"

namespace gokkalkan {
const char* state_name(State state) {
  switch (state) {
    case State::BOOT: return "BOOT"; case State::SAFE: return "SAFE";
    case State::READY: return "READY"; case State::ARMED: return "ARMED";
    case State::FIRING: return "FIRING"; case State::FAULT: return "FAULT";
  }
  return "FAULT";
}
const char* SafetyStateMachine::fault(const char* reason) {
  state_ = State::FAULT; outputs_enabled_ = false; fire_output_enabled_ = false; return reason;
}
const char* SafetyStateMachine::tick(std::uint32_t now_ms, Inputs inputs) {
  if (inputs.estop) return fault("ESTOP_ACTIVE");
  if ((state_ == State::ARMED || state_ == State::FIRING) && !inputs.fire_interlock_closed)
    return fault("FIRE_INTERLOCK_OPEN");
  if (state_ == State::FIRING && !inputs.trigger_released)
    return fault("TRIGGER_FEEDBACK_STUCK");
  if (!inputs.encoder_connected) return fault("ENCODER_DISCONNECTED");
  if (inputs.encoder_overflow) return fault("ENCODER_OVERFLOW");
  if (!inputs.direction_ok) return fault("ENCODER_DIRECTION");
  if (!inputs.deviation_ok) return fault("ENCODER_DEVIATION");
  if ((state_ == State::READY || state_ == State::ARMED || state_ == State::FIRING)
      && now_ms - last_heartbeat_ms_ > watchdog_timeout_ms_)
    return fault("HEARTBEAT_TIMEOUT");
  if (state_ == State::FIRING && now_ms - fire_started_ms_ >= fire_pulse_max_ms_) {
    fire_output_enabled_ = false;
    state_ = State::ARMED;
    return "FIRE_PULSE_COMPLETE";
  }
  return "INPUTS_OK";
}
const char* SafetyStateMachine::apply(Command command, std::uint32_t now_ms, Inputs inputs) {
  const char* health = tick(now_ms, inputs);
  if (state_ == State::FAULT && command != Command::RESET) return health;
  switch (command) {
    case Command::BOOT_COMPLETE:
      state_ = State::SAFE; outputs_enabled_ = false; fire_output_enabled_ = false; return "BOOT_COMPLETE";
    case Command::HEARTBEAT:
      last_heartbeat_ms_ = now_ms;
      if (state_ == State::SAFE) state_ = State::READY;
      return "READY";
    case Command::ARM:
      if (!inputs.fire_interlock_closed) return "REJECTED_INTERLOCK";
      if (state_ == State::READY) { state_ = State::ARMED; outputs_enabled_ = true; return "ARMED"; }
      return "REJECTED_STATE";
    case Command::FIRE:
      if (!inputs.fire_interlock_closed || !inputs.trigger_released) return "REJECTED_INTERLOCK";
      if (state_ == State::ARMED) {
        state_ = State::FIRING;
        fire_started_ms_ = now_ms;
        fire_output_enabled_ = true;
        return "FIRING";
      }
      return "REJECTED_STATE";
    case Command::DISARM:
      state_ = State::SAFE; outputs_enabled_ = false; fire_output_enabled_ = false; return "SAFE_STOP";
    case Command::RESET:
      if (inputs.estop) return "RESET_REJECTED_ESTOP";
      state_ = State::SAFE; outputs_enabled_ = false; fire_output_enabled_ = false; return "RESET_ACCEPTED";
  }
  return "REJECTED_STATE";
}
}
