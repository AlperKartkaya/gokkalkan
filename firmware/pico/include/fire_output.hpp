#pragma once

#include <cstdint>

namespace gokkalkan {

class DigitalOutput {
 public:
  virtual ~DigitalOutput() = default;
  virtual void write(bool active) = 0;
};

class FireOutput {
 public:
  static constexpr std::uint32_t kMaximumPulseMs = 120;
  explicit FireOutput(DigitalOutput& output) : output_(output) {
    output_.write(false);
  }
  bool start(std::uint32_t now_ms, std::uint32_t duration_ms);
  bool tick(std::uint32_t now_ms);
  void force_off();
  bool active() const { return active_; }

 private:
  DigitalOutput& output_;
  bool active_{false};
  std::uint32_t started_ms_{0};
  std::uint32_t duration_ms_{0};
};

}  // namespace gokkalkan
