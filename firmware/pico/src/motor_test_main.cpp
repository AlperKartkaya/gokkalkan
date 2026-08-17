#include <cctype>
#include <cstdio>
#include <cstring>
#include <initializer_list>

#include "hardware/gpio.h"
#include "hardware/watchdog.h"
#include "pico/stdlib.h"

#ifndef GOKKALKAN_TEST_STEP_PIN
#define GOKKALKAN_TEST_STEP_PIN 2
#endif
#ifndef GOKKALKAN_TEST_DIR_PIN
#define GOKKALKAN_TEST_DIR_PIN 3
#endif
#ifndef GOKKALKAN_TEST_ENABLE_PIN
#define GOKKALKAN_TEST_ENABLE_PIN 4
#endif
#ifndef GOKKALKAN_TEST_SIGNAL_ACTIVE_HIGH
#define GOKKALKAN_TEST_SIGNAL_ACTIVE_HIGH 1
#endif

namespace {
constexpr uint32_t kMinFrequencyHz = 10;
constexpr uint32_t kMaxFrequencyHz = 1000;
constexpr uint32_t kMaxStepsPerCommand = 2000;
constexpr uint64_t kArmTimeoutUs = 10'000'000;
constexpr size_t kLineCapacity = 96;
constexpr bool kActiveLevel = GOKKALKAN_TEST_SIGNAL_ACTIVE_HIGH != 0;
constexpr bool kInactiveLevel = !kActiveLevel;

bool armed = false;
bool moving = false;
bool step_level = false;
uint32_t remaining_steps = 0;
uint32_t half_period_us = 0;
uint64_t next_edge_us = 0;
uint64_t arm_deadline_us = 0;

void write_signal(uint pin, bool asserted) {
  gpio_put(pin, asserted ? kActiveLevel : kInactiveLevel);
}

void safe_outputs() {
  moving = false;
  step_level = false;
  remaining_steps = 0;
  write_signal(GOKKALKAN_TEST_STEP_PIN, false);
  write_signal(GOKKALKAN_TEST_ENABLE_PIN, false);
}

void disarm(const char* reason) {
  safe_outputs();
  armed = false;
  std::printf("OK DISARMED %s\n", reason);
}

void print_status() {
  std::printf("STATUS armed=%d moving=%d remaining=%lu pins=STEP:%d,DIR:%d,ENA:%d active=%s\n",
              armed ? 1 : 0, moving ? 1 : 0,
              static_cast<unsigned long>(remaining_steps), GOKKALKAN_TEST_STEP_PIN,
              GOKKALKAN_TEST_DIR_PIN, GOKKALKAN_TEST_ENABLE_PIN,
              kActiveLevel ? "HIGH" : "LOW");
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
    write_signal(GOKKALKAN_TEST_ENABLE_PIN, true);
    std::printf("OK ARMED timeout_ms=10000\n");
    return;
  }
  if (std::strcmp(line, "STOP") == 0 || std::strcmp(line, "DISARM") == 0) {
    disarm("operator");
    return;
  }

  char direction[4] = {};
  unsigned long steps = 0;
  unsigned long frequency = 0;
  if (std::sscanf(line, "MOVE %3s %lu %lu", direction, &steps, &frequency) == 3) {
    if (!armed) {
      std::printf("ERR NOT_ARMED\n");
      return;
    }
    if ((std::strcmp(direction, "CW") != 0 && std::strcmp(direction, "CCW") != 0) ||
        steps == 0 || steps > kMaxStepsPerCommand || frequency < kMinFrequencyHz ||
        frequency > kMaxFrequencyHz) {
      std::printf("ERR RANGE direction=CW|CCW steps=1..2000 hz=10..1000\n");
      return;
    }
    write_signal(GOKKALKAN_TEST_DIR_PIN, std::strcmp(direction, "CW") == 0);
    sleep_us(20);
    remaining_steps = static_cast<uint32_t>(steps);
    half_period_us = 500'000U / static_cast<uint32_t>(frequency);
    step_level = false;
    moving = true;
    arm_deadline_us = time_us_64() + kArmTimeoutUs;
    next_edge_us = time_us_64();
    std::printf("OK MOVING direction=%s steps=%lu hz=%lu\n", direction, steps, frequency);
    return;
  }
  std::printf("ERR COMMAND use STATUS|ARM|MOVE CW|CCW <steps> <hz>|STOP\n");
}

void service_motion(uint64_t now_us) {
  if (armed && now_us >= arm_deadline_us) {
    disarm("timeout");
    return;
  }
  if (!moving || now_us < next_edge_us) return;
  step_level = !step_level;
  write_signal(GOKKALKAN_TEST_STEP_PIN, step_level);
  next_edge_us = now_us + half_period_us;
  if (!step_level && --remaining_steps == 0) {
    moving = false;
    write_signal(GOKKALKAN_TEST_STEP_PIN, false);
    std::printf("OK MOVE_COMPLETE\n");
  }
}
}  // namespace

int main() {
  stdio_init_all();
  for (const uint pin : {GOKKALKAN_TEST_STEP_PIN, GOKKALKAN_TEST_DIR_PIN,
                         GOKKALKAN_TEST_ENABLE_PIN}) {
    gpio_init(pin);
    gpio_set_dir(pin, GPIO_OUT);
    write_signal(pin, false);
  }
  watchdog_enable(2000, true);
  sleep_ms(1200);
  std::printf("GOKKALKAN MOTOR TEST READY; outputs=SAFE\n");
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
