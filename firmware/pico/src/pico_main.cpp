#include "pico/stdlib.h"
#include "hardware/watchdog.h"
#include "safety_state_machine.hpp"

// Pin assignments remain board-revision configuration.  Until that reviewed
// mapping exists, all actuator outputs are initialized low and never enabled.
int main() {
  stdio_init_all();
  gokkalkan::SafetyStateMachine safety;
  safety.apply(gokkalkan::Command::BOOT_COMPLETE, to_ms_since_boot(get_absolute_time()));
  watchdog_enable(250, true);
  while (true) {
    const auto now = to_ms_since_boot(get_absolute_time());
    safety.tick(now, {});
    watchdog_update();
    sleep_ms(10);
  }
}
