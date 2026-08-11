"""Fail-closed Raspberry Pi to Pico adapter over USB CDC serial."""

from __future__ import annotations

import logging
import threading
import time
from types import SimpleNamespace
from typing import Any, Callable

from .hardware_adapter import CanMcuAdapter, EStopCallback, HEALTH_TIMEOUT_SEC
from .can_protocol import CAN_ID_HEARTBEAT_V1, pack_heartbeat
from .usb_serial_protocol import UsbFrameStreamDecoder, encode_usb_frame

logger = logging.getLogger(__name__)


class UsbSerialMcuAdapter(CanMcuAdapter):
    """Carry the tested MCU v1 messages over a framed USB CDC byte stream.

    The class deliberately reuses the existing command/status codec and safety
    checks.  Only the transport changes; ACK, sequence, heartbeat and fire
    preflight semantics remain fail-closed.
    """

    def __init__(
        self,
        port: str = "/dev/serial/by-id/UNCONFIGURED-GOKKALKAN-PICO",
        baudrate: int = 115_200,
        heartbeat_timeout_sec: float = HEALTH_TIMEOUT_SEC,
        estop_callback: EStopCallback | None = None,
        dry_run: bool = True,
        physical_output_capable: bool = False,
        serial_factory: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(
            channel=port,
            bustype="usb_serial",
            bitrate=baudrate,
            heartbeat_timeout_sec=heartbeat_timeout_sec,
            estop_callback=estop_callback,
            dry_run=dry_run,
            physical_output_capable=physical_output_capable,
        )
        self.port = port
        self.baudrate = baudrate
        self._serial_factory = serial_factory
        self._serial: Any = None
        self._decoder = UsbFrameStreamDecoder()
        self._heartbeat_sequence = 0
        # Availability means the adapter implementation is present. Opening the
        # selected device remains a separate, observable health condition.
        self._can_available = True

    def _default_serial_factory(self, **kwargs: Any) -> Any:
        import serial

        port = str(kwargs.pop("port"))
        if "://" in port:
            return serial.serial_for_url(port, **kwargs)
        return serial.Serial(port=port, **kwargs)

    def start(self) -> None:
        self._running = True
        if self._dry_run:
            logger.info("UsbSerialMcuAdapter dry-run: fiziksel USB çıkışı yok.")
            return
        self._open_serial()
        if self._serial is None:
            return
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True, name="USB-CDC-RX")
        self._rx_thread.start()

    def _open_serial(self) -> None:
        try:
            factory = self._serial_factory or self._default_serial_factory
            self._serial = factory(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1,
                write_timeout=0.25,
            )
            self._bus = self._serial
            logger.info("Pico USB CDC açıldı: %s @ %d", self.port, self.baudrate)
        except Exception as exc:
            self._serial = None
            self._bus = None
            logger.error("Pico USB CDC açılamadı (%s): %s", self.port, exc)

    def close(self) -> None:
        self._running = False
        if self._rx_thread:
            self._rx_thread.join(timeout=2.0)
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        self._bus = None

    def _rx_loop(self) -> None:
        next_heartbeat = time.monotonic()
        while self._running:
            if self._serial is None:
                time.sleep(1.0)
                self._open_serial()
                continue
            try:
                now = time.monotonic()
                if now >= next_heartbeat:
                    self._heartbeat_sequence = (self._heartbeat_sequence + 1) & 0xFF
                    self._send_can(
                        CAN_ID_HEARTBEAT_V1,
                        pack_heartbeat(self._heartbeat_sequence),
                    )
                    next_heartbeat = now + 0.1
                chunk = self._serial.read(128)
                if not chunk:
                    continue
                before = self._decoder.rejected_count
                for message_id, payload in self._decoder.feed(bytes(chunk)):
                    self._handle_rx_message(SimpleNamespace(arbitration_id=message_id, data=payload))
                self._rejected_rx_count += self._decoder.rejected_count - before
            except Exception as exc:
                logger.warning("USB CDC RX hatası; bağlantı fail-closed kapatıldı: %s", exc)
                try:
                    self._serial.close()
                except Exception:
                    pass
                self._serial = None
                self._bus = None
                with self._lock:
                    self._status["motionOk"] = False
                    self._status["fireReady"] = False

    def _send_can(self, can_id: int, data: bytes) -> bool:
        if self._dry_run:
            return True
        if self._serial is None:
            return False
        monitor_only_heartbeat = can_id == CAN_ID_HEARTBEAT_V1
        if (
            not self._physical_output_capable
            and not self.port.startswith("loop://")
            and not monitor_only_heartbeat
        ):
            logger.error("Yetkisiz fiziksel USB MCU çıkışı engellendi: %s", self.port)
            return False
        try:
            frame = encode_usb_frame(can_id, data)
            written = self._serial.write(frame)
            return written == len(frame)
        except Exception as exc:
            logger.error("USB CDC TX hatası (id=0x%03X): %s", can_id, exc)
            return False

    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        if self._dry_run:
            result = super().execute(command)
            result["adapter"] = "usb_serial_mcu_adapter"
            result["message"] = "USB CDC dry-run kaydı; fiziksel çıkış yok."
            return result
        command_id = str(command.get("commandId", f"USB-{self._command_count + 1:05d}"))
        return self._execute_v1(command_id, str(command.get("kind", "")), command.get("payload", {}), command)

    def _v1_result(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        result = super()._v1_result(*args, **kwargs)
        result["adapter"] = "usb_serial_mcu_adapter"
        return result

    def health_check(self) -> dict[str, Any]:
        health = super().health_check()
        health.update(
            {
                "adapter": "usb_serial_mcu_adapter",
                "transport": "usb_serial",
                "serialPort": self.port,
                "baudrate": self.baudrate,
                "serialConnected": self._serial is not None,
                "transportRejectedFrameCount": self._decoder.rejected_count,
            }
        )
        health.pop("canChannel", None)
        health.pop("canAvailable", None)
        return health
