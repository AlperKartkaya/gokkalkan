#pragma once

#include <cstdint>

#include "safety_state_machine.hpp"

namespace gokkalkan {

struct IoPolarity {
  bool estop_safe_sense_active_low;
  bool fire_interlock_active_low;
  bool trigger_released_active_low;
  bool limit_clear_active_low;
};

struct RawDigitalInputs {
  bool estop_safe_sense_level{true};
  bool fire_interlock_level{true};
  bool trigger_feedback_level{true};
  bool pan_limit_nc_level{true};
  bool tilt_limit_nc_level{true};
};

struct IoSnapshot {
  bool initialized{false};
  bool safety_chain_ok{false};
  bool fire_interlock_closed{false};
  bool trigger_released{false};
  bool pan_limit_clear{false};
  bool tilt_limit_clear{false};
};

class FailClosedDebouncer {
 public:
  explicit FailClosedDebouncer(std::uint32_t safe_delay_ms)
      : safe_delay_ms_(safe_delay_ms) {}
  bool update(bool safe_sample, std::uint32_t now_ms);
  bool value() const { return stable_safe_; }

 private:
  std::uint32_t safe_delay_ms_;
  std::uint32_t candidate_since_ms_{0};
  bool candidate_active_{false};
  bool stable_safe_{false};
};

class PicoIo {
 public:
  explicit PicoIo(IoPolarity polarity, std::uint32_t debounce_ms = 20);
  const IoSnapshot& update(const RawDigitalInputs& raw, std::uint32_t now_ms);
  void set_encoder_health(bool connected, bool overflow, bool direction_ok,
                          bool deviation_ok);
  Inputs safety_inputs() const;
  const IoSnapshot& snapshot() const { return snapshot_; }

 private:
  static bool asserted(bool level, bool active_low) {
    return active_low ? !level : level;
  }

  IoPolarity polarity_;
  FailClosedDebouncer safety_chain_;
  FailClosedDebouncer fire_interlock_;
  FailClosedDebouncer trigger_released_;
  FailClosedDebouncer pan_limit_clear_;
  FailClosedDebouncer tilt_limit_clear_;
  IoSnapshot snapshot_{};
  bool encoder_connected_{false};
  bool encoder_overflow_{false};
  bool encoder_direction_ok_{false};
  bool encoder_deviation_ok_{false};
};

}  // namespace gokkalkan
