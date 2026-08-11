#include "io_hal.hpp"

namespace gokkalkan {

bool FailClosedDebouncer::update(bool safe_sample, std::uint32_t now_ms) {
  if (!safe_sample) {
    stable_safe_ = false;
    candidate_active_ = false;
    return false;
  }
  if (stable_safe_) return true;
  if (!candidate_active_) {
    candidate_active_ = true;
    candidate_since_ms_ = now_ms;
  }
  if (now_ms - candidate_since_ms_ >= safe_delay_ms_) stable_safe_ = true;
  return stable_safe_;
}

PicoIo::PicoIo(IoPolarity polarity, std::uint32_t debounce_ms)
    : polarity_(polarity),
      safety_chain_(debounce_ms),
      fire_interlock_(debounce_ms),
      trigger_released_(debounce_ms),
      pan_limit_clear_(debounce_ms),
      tilt_limit_clear_(debounce_ms) {}

const IoSnapshot& PicoIo::update(const RawDigitalInputs& raw,
                                 std::uint32_t now_ms) {
  snapshot_.initialized = true;
  snapshot_.safety_chain_ok = safety_chain_.update(
      asserted(raw.estop_safe_sense_level,
               polarity_.estop_safe_sense_active_low), now_ms);
  snapshot_.fire_interlock_closed = fire_interlock_.update(
      asserted(raw.fire_interlock_level, polarity_.fire_interlock_active_low),
      now_ms);
  snapshot_.trigger_released = trigger_released_.update(
      asserted(raw.trigger_feedback_level,
               polarity_.trigger_released_active_low), now_ms);
  snapshot_.pan_limit_clear = pan_limit_clear_.update(
      asserted(raw.pan_limit_nc_level, polarity_.limit_clear_active_low),
      now_ms);
  snapshot_.tilt_limit_clear = tilt_limit_clear_.update(
      asserted(raw.tilt_limit_nc_level, polarity_.limit_clear_active_low),
      now_ms);
  return snapshot_;
}

void PicoIo::set_encoder_health(bool connected, bool overflow,
                                bool direction_ok, bool deviation_ok) {
  encoder_connected_ = connected;
  encoder_overflow_ = overflow;
  encoder_direction_ok_ = direction_ok;
  encoder_deviation_ok_ = deviation_ok;
}

Inputs PicoIo::safety_inputs() const {
  Inputs inputs;
  inputs.estop = !snapshot_.initialized || !snapshot_.safety_chain_ok;
  inputs.fire_interlock_closed = snapshot_.fire_interlock_closed;
  inputs.trigger_released = snapshot_.trigger_released;
  inputs.encoder_connected = encoder_connected_;
  inputs.encoder_overflow = encoder_overflow_;
  inputs.direction_ok = encoder_direction_ok_;
  inputs.deviation_ok = encoder_deviation_ok_;
  inputs.pan_limit_clear = snapshot_.pan_limit_clear;
  inputs.tilt_limit_clear = snapshot_.tilt_limit_clear;
  return inputs;
}

}  // namespace gokkalkan
