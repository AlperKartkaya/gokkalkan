#pragma once

#include <cstdint>

namespace gokkalkan {

enum class AxisState : std::uint8_t {
  DISABLED,
  REFERENCE_REQUIRED,
  IDLE,
  MOVING,
  SETTLING,
  FAULT
};

struct AxisConfig {
  double steps_per_degree;
  double minimum_deg;
  double maximum_deg;
  double maximum_step_rate_hz;
  double acceleration_steps_s2;
  double settle_tolerance_deg;
};

class StepOutput {
 public:
  virtual ~StepOutput() = default;
  virtual void set_enabled(bool enabled) = 0;
  virtual void set_direction(bool positive) = 0;
  virtual void pulse() = 0;
};

class AxisController {
 public:
  AxisController(AxisConfig config, StepOutput& output);
  void set_referenced(double angle_deg);
  bool command_target(double target_deg);
  void tick(std::uint64_t now_us, double encoder_angle_deg,
            bool negative_limit_clear, bool positive_limit_clear);
  void stop();
  void fault();

  AxisState state() const { return state_; }
  double expected_angle_deg() const { return expected_angle_deg_; }
  double target_angle_deg() const { return target_angle_deg_; }
  int commanded_direction() const { return direction_; }

 private:
  AxisConfig config_;
  StepOutput& output_;
  AxisState state_{AxisState::REFERENCE_REQUIRED};
  double expected_angle_deg_{0.0};
  double target_angle_deg_{0.0};
  double current_step_rate_hz_{0.0};
  std::uint64_t last_tick_us_{0};
  std::uint64_t next_step_us_{0};
  int direction_{0};
};

}  // namespace gokkalkan
