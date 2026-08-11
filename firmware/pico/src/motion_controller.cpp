#include "motion_controller.hpp"

#include <algorithm>
#include <cmath>

namespace gokkalkan {

AxisController::AxisController(AxisConfig config, StepOutput& output)
    : config_(config), output_(output) {
  output_.set_enabled(false);
}

void AxisController::set_referenced(double angle_deg) {
  if (angle_deg < config_.minimum_deg || angle_deg > config_.maximum_deg) {
    fault();
    return;
  }
  expected_angle_deg_ = angle_deg;
  target_angle_deg_ = angle_deg;
  state_ = AxisState::IDLE;
  direction_ = 0;
  output_.set_enabled(false);
}

bool AxisController::command_target(double target_deg) {
  if (state_ == AxisState::REFERENCE_REQUIRED || state_ == AxisState::FAULT ||
      target_deg < config_.minimum_deg || target_deg > config_.maximum_deg ||
      config_.steps_per_degree <= 0.0 || config_.maximum_step_rate_hz <= 0.0)
    return false;
  target_angle_deg_ = target_deg;
  const double error = target_angle_deg_ - expected_angle_deg_;
  if (std::abs(error) <= config_.settle_tolerance_deg) {
    state_ = AxisState::IDLE;
    direction_ = 0;
    output_.set_enabled(false);
    return true;
  }
  direction_ = error > 0.0 ? 1 : -1;
  output_.set_direction(direction_ > 0);
  output_.set_enabled(true);
  state_ = AxisState::MOVING;
  current_step_rate_hz_ = std::min(100.0, config_.maximum_step_rate_hz);
  next_step_us_ = 0;
  return true;
}

void AxisController::tick(std::uint64_t now_us, double encoder_angle_deg,
                          bool negative_limit_clear,
                          bool positive_limit_clear) {
  if (state_ != AxisState::MOVING && state_ != AxisState::SETTLING) return;
  if ((direction_ < 0 && !negative_limit_clear) ||
      (direction_ > 0 && !positive_limit_clear)) {
    fault();
    return;
  }
  const double error = target_angle_deg_ - encoder_angle_deg;
  if (std::abs(error) <= config_.settle_tolerance_deg) {
    expected_angle_deg_ = target_angle_deg_;
    state_ = AxisState::IDLE;
    direction_ = 0;
    output_.set_enabled(false);
    return;
  }
  if (last_tick_us_ != 0 && config_.acceleration_steps_s2 > 0.0) {
    const double dt = static_cast<double>(now_us - last_tick_us_) / 1'000'000.0;
    current_step_rate_hz_ = std::min(
        config_.maximum_step_rate_hz,
        current_step_rate_hz_ + config_.acceleration_steps_s2 * dt);
  }
  last_tick_us_ = now_us;
  if (next_step_us_ != 0 && now_us < next_step_us_) return;
  output_.pulse();
  const double step_deg = 1.0 / config_.steps_per_degree;
  expected_angle_deg_ += direction_ * step_deg;
  const auto interval = static_cast<std::uint64_t>(
      std::max(1.0, 1'000'000.0 / current_step_rate_hz_));
  next_step_us_ = now_us + interval;
}

void AxisController::stop() {
  output_.set_enabled(false);
  state_ = state_ == AxisState::FAULT ? AxisState::FAULT : AxisState::IDLE;
  direction_ = 0;
  current_step_rate_hz_ = 0.0;
}

void AxisController::fault() {
  output_.set_enabled(false);
  state_ = AxisState::FAULT;
  direction_ = 0;
  current_step_rate_hz_ = 0.0;
}

}  // namespace gokkalkan
