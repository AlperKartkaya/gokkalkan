#include "encoder_monitor.hpp"

#include <cmath>
#include <cstdlib>

namespace gokkalkan {

void EncoderMonitor::reference(std::int32_t count, double angle_deg) {
  reference_count_ = count;
  previous_count_ = count;
  reference_angle_deg_ = angle_deg;
  status_.angle_deg = angle_deg;
  status_.zero_referenced = true;
  status_.overflow = false;
  status_.direction_ok = true;
  status_.deviation_ok = true;
}

const EncoderStatus& EncoderMonitor::update(std::int32_t count,
                                            int commanded_direction,
                                            double expected_angle_deg) {
  if (!status_.connected || !status_.zero_referenced ||
      config_.counts_per_degree <= 0.0) {
    status_.deviation_ok = false;
    return status_;
  }
  const auto delta = static_cast<std::int64_t>(count) - previous_count_;
  const auto from_reference = static_cast<std::int64_t>(count) - reference_count_;
  status_.overflow = std::llabs(from_reference) > config_.overflow_guard_counts;
  status_.angle_deg = reference_angle_deg_ +
                      static_cast<double>(from_reference) /
                          config_.counts_per_degree;
  if (commanded_direction > 0 && delta < 0) status_.direction_ok = false;
  if (commanded_direction < 0 && delta > 0) status_.direction_ok = false;
  status_.deviation_ok =
      std::abs(status_.angle_deg - expected_angle_deg) <=
      config_.max_deviation_deg;
  previous_count_ = count;
  return status_;
}

}  // namespace gokkalkan
