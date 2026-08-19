#include <cctype>
#include <cstdio>
#include <cstring>
#include <initializer_list>

#include "hardware/gpio.h"
#include "hardware/watchdog.h"
#include "pico/stdlib.h"

namespace {
// Driver 1 Pinout (Common Anode 5V via Logic Level Converter)
constexpr uint kDriver1StepPin = 15; // GP15 (pin 20) -> PUL-
constexpr uint kDriver1DirPin  = 14; // GP14 (pin 19) -> DIR-

// Driver 2 Pinout (Common Anode 5V via Logic Level Converter)
constexpr uint kDriver2StepPin = 12; // GP12 (pin 16) -> PUL-
constexpr uint kDriver2DirPin  = 11; // GP11 (pin 15) -> DIR-

constexpr uint32_t kMinFrequencyHz = 10;
constexpr uint32_t kMaxFrequencyHz = 4000;
constexpr uint32_t kMaxStepsPerCommand = 64000;
constexpr uint64_t kArmTimeoutUs = 120'000'000;
constexpr size_t kLineCapacity = 96;

bool armed = false;
bool moving = false;
bool step_level = false;
int active_driver_mode = 0; // 0: BOTH, 1: Driver 1, 2: Driver 2

uint32_t remaining_steps = 0;
uint32_t half_period_us = 0;
uint64_t next_edge_us = 0;
uint64_t arm_deadline_us = 0;

void set_step_pin(uint pin, bool active_pulse) {
  // Common Anode (+5V on PUL+):
  // Active pulse -> Pico 0 (LOW) -> Converter 0V -> Opto LED ON
  // Inactive pulse -> Pico 1 (HIGH) -> Converter +5V -> Opto LED OFF
  gpio_put(pin, active_pulse ? 0 : 1);
}

void set_dir_pin(uint pin, bool is_cw) {
  gpio_put(pin, is_cw ? 0 : 1);
}

void safe_outputs() {
  moving = false;
  step_level = false;
  remaining_steps = 0;
  set_step_pin(kDriver1StepPin, false);
  set_step_pin(kDriver2StepPin, false);
}

void disarm(const char* reason) {
  safe_outputs();
  armed = false;
  std::printf("OK DISARMED %s\n", reason);
}

void print_status() {
  std::printf("STATUS armed=%d moving=%d remaining=%lu driver_mode=%s D1(PUL:GP15,DIR:GP14) D2(PUL:GP12,DIR:GP11) mode=COMMON_ANODE_5V_CONVERTER\n",
              armed ? 1 : 0, moving ? 1 : 0,
              static_cast<unsigned long>(remaining_steps),
              active_driver_mode == 0 ? "BOTH(D1+D2)" : (active_driver_mode == 1 ? "DRIVER_1" : "DRIVER_2"));
}

void uppercase(char* text) {
  for (; *text != '\0'; ++text) {
    *text = static_cast<char>(std::toupper(static_cast<unsigned char>(*text)));
  }
}

void handle_command(char* line) {
  uppercase(line);
  if (std::strcmp(line, "STATUS") == 0) {
    print_status();
    return;
  }
  if (std::strcmp(line, "ARM") == 0) {
    safe_outputs();
    armed = true;
    arm_deadline_us = time_us_64() + kArmTimeoutUs;
    std::printf("OK ARMED timeout_ms=120000\n");
    return;
  }
  if (std::strcmp(line, "STOP") == 0 || std::strcmp(line, "DISARM") == 0) {
    disarm("operator");
    return;
  }

  int driver_num = 0; // 0: BOTH
  char direction[4] = {};
  unsigned long steps = 0;
  unsigned long frequency = 0;

  // Format: MOVE <0|1|2|BOTH> <CW|CCW> <steps> <hz>
  if (std::sscanf(line, "MOVE %d %3s %lu %lu", &driver_num, direction, &steps, &frequency) == 4 ||
      (std::sscanf(line, "MOVE %3s %lu %lu", direction, &steps, &frequency) == 3 && (driver_num = 0))) {
    if (!armed) {
      std::printf("ERR NOT_ARMED\n");
      return;
    }
    if (driver_num < 0 || driver_num > 2) {
      std::printf("ERR INVALID_DRIVER must be 0(BOTH), 1, or 2\n");
      return;
    }
    if ((std::strcmp(direction, "CW") != 0 && std::strcmp(direction, "CCW") != 0) ||
        steps == 0 || steps > kMaxStepsPerCommand || frequency < kMinFrequencyHz ||
        frequency > kMaxFrequencyHz) {
      std::printf("ERR RANGE driver=0(BOTH)|1|2 direction=CW|CCW steps=1..%lu hz=%lu..%lu\n",
                  static_cast<unsigned long>(kMaxStepsPerCommand),
                  static_cast<unsigned long>(kMinFrequencyHz),
                  static_cast<unsigned long>(kMaxFrequencyHz));
      return;
    }

    active_driver_mode = driver_num;
    bool is_cw = (std::strcmp(direction, "CW") == 0);

    if (driver_num == 1 || driver_num == 0) {
      set_dir_pin(kDriver1DirPin, is_cw);
    }
    if (driver_num == 2 || driver_num == 0) {
      set_dir_pin(kDriver2DirPin, is_cw);
    }

    sleep_us(50);
    remaining_steps = static_cast<uint32_t>(steps);
    half_period_us = 500'000U / static_cast<uint32_t>(frequency);
    if (half_period_us < 5) half_period_us = 5;
    step_level = false;
    moving = true;
    arm_deadline_us = time_us_64() + kArmTimeoutUs;
    next_edge_us = time_us_64();
    std::printf("OK MOVING mode=%s direction=%s steps=%lu hz=%lu\n",
                driver_num == 0 ? "BOTH(GP15+GP12)" : (driver_num == 1 ? "GP15" : "GP12"),
                direction, steps, frequency);
    return;
  }
  std::printf("ERR COMMAND use STATUS|ARM|MOVE [0|1|2] CW|CCW <steps> <hz>|STOP\n");
}

void service_motion(uint64_t now_us) {
  if (armed && now_us >= arm_deadline_us) {
    disarm("timeout");
    return;
  }
  if (!moving || now_us < next_edge_us) return;
  step_level = !step_level;
  if (active_driver_mode == 1 || active_driver_mode == 0) {
    set_step_pin(kDriver1StepPin, step_level);
  }
  if (active_driver_mode == 2 || active_driver_mode == 0) {
    set_step_pin(kDriver2StepPin, step_level);
  }
  next_edge_us = now_us + half_period_us;
  if (!step_level && --remaining_steps == 0) {
    moving = false;
    set_step_pin(kDriver1StepPin, false);
    set_step_pin(kDriver2StepPin, false);
    std::printf("OK MOVE_COMPLETE\n");
  }
}
}  // namespace

int main() {
  stdio_init_all();
  for (const uint pin : {kDriver1StepPin, kDriver1DirPin,
                         kDriver2StepPin, kDriver2DirPin}) {
    gpio_init(pin);
    gpio_set_dir(pin, GPIO_OUT);
  }
  safe_outputs();
  watchdog_enable(2000, true);
  sleep_ms(1200);
  std::printf("GOKKALKAN SYNC DUAL MOTOR TEST READY; outputs=SAFE\n");
  print_status();
  char line[kLineCapacity] = {};
  size_t length = 0;
  while (true) {
    watchdog_update();
    service_motion(time_us_64());
    const int input = getchar_timeout_us(0);
    if (input == PICO_ERROR_TIMEOUT) {
      tight_loop_contents();
    } else if (input == '\r' || input == '\n') {
      if (length != 0) {
        line[length] = '\0';
        handle_command(line);
        length = 0;
      }
    } else if (length + 1 < kLineCapacity && input >= 0 && input <= 127) {
      line[length++] = static_cast<char>(input);
    } else {
      length = 0;
      std::printf("ERR LINE_TOO_LONG\n");
    }
  }
}
