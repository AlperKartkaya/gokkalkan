#include "fire_output.hpp"

namespace gokkalkan {

bool FireOutput::start(std::uint32_t now_ms, std::uint32_t duration_ms) {
  if (active_ || duration_ms == 0 || duration_ms > kMaximumPulseMs) return false;
  started_ms_ = now_ms;
  duration_ms_ = duration_ms;
  active_ = true;
  output_.write(true);
  return true;
}

bool FireOutput::tick(std::uint32_t now_ms) {
  if (!active_) return false;
  if (now_ms - started_ms_ < duration_ms_) return false;
  force_off();
  return true;
}

void FireOutput::force_off() {
  output_.write(false);
  active_ = false;
  duration_ms_ = 0;
}

}  // namespace gokkalkan
