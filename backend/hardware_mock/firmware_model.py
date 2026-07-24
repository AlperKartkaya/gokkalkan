"""Executable host model of the Pico safety state machine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FirmwareModel:
    state: str = "BOOT"
    outputs_enabled: bool = False
    estop_active: bool = False
    fault_code: str = "NONE"
    last_heartbeat_ms: int = 0
    watchdog_timeout_ms: int = 250

    def boot_complete(self) -> str:
        self.outputs_enabled = False
        self.state = "SAFE"
        return "BOOT_COMPLETE"

    def update_inputs(
        self,
        *,
        now_ms: int,
        estop_active: bool,
        heartbeat: bool = False,
        encoder_connected: bool = True,
        encoder_overflow: bool = False,
        direction_ok: bool = True,
        deviation_ok: bool = True,
    ) -> str:
        self.estop_active = estop_active
        if heartbeat:
            self.last_heartbeat_ms = now_ms
        if estop_active:
            return self.fault("ESTOP_ACTIVE")
        if not encoder_connected:
            return self.fault("ENCODER_DISCONNECTED")
        if encoder_overflow:
            return self.fault("ENCODER_OVERFLOW")
        if not direction_ok:
            return self.fault("ENCODER_DIRECTION")
        if not deviation_ok:
            return self.fault("ENCODER_DEVIATION")
        if now_ms - self.last_heartbeat_ms > self.watchdog_timeout_ms:
            return self.fault("HEARTBEAT_TIMEOUT")
        if self.state == "SAFE" and heartbeat:
            self.state = "READY"
            return "READY"
        return "INPUTS_OK"

    def command(self, command: str) -> str:
        if command == "RESET":
            if self.estop_active:
                return "RESET_REJECTED_ESTOP"
            self.state = "SAFE"
            self.outputs_enabled = False
            self.fault_code = "NONE"
            return "RESET_ACCEPTED"
        if command == "ARM" and self.state == "READY":
            self.state = "ARMED"
            self.outputs_enabled = True
            return "ARMED"
        if command == "FIRE" and self.state == "ARMED":
            self.state = "FIRING"
            return "FIRING"
        if command in {"DISARM", "SOFT_STOP"}:
            self.state = "SAFE"
            self.outputs_enabled = False
            return "SAFE_STOP"
        return "REJECTED_STATE"

    def fault(self, reason: str) -> str:
        self.state = "FAULT"
        self.outputs_enabled = False
        self.fault_code = reason
        return reason
