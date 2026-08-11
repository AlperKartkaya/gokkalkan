#pragma once

#include <cstdint>

namespace gokkalkan {

struct EncoderConfig {
  double counts_per_degree;
  double max_deviation_deg;
  std::int32_t overflow_guard_counts;
};

struct EncoderStatus {
  bool connected{false};
  bool zero_referenced{false};
  bool direction_ok{true};
  bool overflow{false};
  bool deviation_ok{true};
  double angle_deg{0.0};
};

class EncoderMonitor {
 public:
  explicit EncoderMonitor(EncoderConfig config) : config_(config) {}
  void set_connected(bool connected) { status_.connected = connected; }
  void reference(std::int32_t count, double angle_deg = 0.0);
  const EncoderStatus& update(std::int32_t count, int commanded_direction,
                              double expected_angle_deg);
  const EncoderStatus& status() const { return status_; }

 private:
  EncoderConfig config_;
  EncoderStatus status_{};
  std::int32_t reference_count_{0};
  std::int32_t previous_count_{0};
  double reference_angle_deg_{0.0};
};

}  // namespace gokkalkan
