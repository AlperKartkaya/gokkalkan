"""Tarihsel Pico/CAN adaptörü ve ortak donanım adaptör sözleşmesi.

Aktif saha taşıması ``arduino_motor_adapter.ArduinoUnoMotorAdapter`` içindedir.
Bu modüldeki CAN uygulaması yalnız geriye dönük regresyon testleri için korunur:
  RPi5 (bu modül, python-can) ← legacy CAN bus → Pico

CAN Mesaj Haritası:
  0x100  RPi5 → Pico  Pan/Tilt konum komutu (8 byte)
  0x101  RPi5 → Pico  Ateş komutu           (8 byte)
  0x102  RPi5 → Pico  Sistem komutu          (8 byte)  arm/disarm/soft-stop
  0x200  Pico → RPi5  Durum raporu           (8 byte)  mevcut açı, E-stop, sağlık
  0x201  Pico → RPi5  E-Stop acil olayı      (1 byte)  anında iletim

python-can kurulu değilse legacy adaptör mock modda çalışır ve uyarı loglar.
"""

from __future__ import annotations

import logging
import struct
import threading
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, Callable

from .can_protocol import (
    CAN_ID_ACK_V1,
    CAN_ID_ENCODER_V1,
    CAN_ID_ESTOP_V1,
    CAN_ID_FAULT_V1,
    CAN_ID_FIRMWARE_V1,
    CAN_ID_STATUS_V1,
    SequenceGuard,
    unpack_ack as unpack_ack_v1,
    unpack_encoder as unpack_encoder_v1,
    unpack_firmware as unpack_firmware_v1,
    unpack_estop as unpack_estop_v1,
    unpack_fault as unpack_fault_v1,
    unpack_status as unpack_status_v1,
    command_tag,
    pack_command_meta,
    pack_fire as pack_fire_v1,
    pack_pantilt as pack_pantilt_v1,
    pack_system as pack_system_v1,
    KIND_FIRE,
    KIND_PANTILT,
    KIND_SYSTEM,
    CAN_ID_COMMAND_META,
    CAN_ID_FIRE_CMD_V1,
    CAN_ID_PANTILT_CMD_V1,
    CAN_ID_SYS_CMD_V1,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CAN ID Sabitleri
# ---------------------------------------------------------------------------
CAN_ID_PANTILT_CMD: int = 0x100
CAN_ID_FIRE_CMD: int    = 0x101
CAN_ID_SYS_CMD: int     = 0x102
CAN_ID_STATUS: int      = 0x200
CAN_ID_ESTOP_EVENT: int = 0x201

# ---------------------------------------------------------------------------
# Protokol Sabitleri
# ---------------------------------------------------------------------------
CENTIDEG_PER_DEG: int = 100          # int16 çözünürlüğü: 0.01°
INT16_MAX: int        = 32767        # ≈ ±327.67°
RATE_CENTIDEG_MAX: int = 65535       # uint16
HEALTH_TIMEOUT_SEC: float = 2.0      # Pico sessizlik eşiği
RECONNECT_INTERVAL_SEC: float = 5.0  # Otomatik yeniden bağlanma aralığı

EStopCallback = Callable[[bool], None]


# ---------------------------------------------------------------------------
# Yardımcı Fonksiyonlar
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _xor8(data: bytes) -> int:
    """7 byte'ın XOR toplamını döndürür (8. byte checksum alanı için)."""
    result = 0
    for b in data:
        result ^= b
    return result & 0xFF


# ---------------------------------------------------------------------------
# CAN Mesaj Codec — Pan/Tilt Komutu (0x100)
# ---------------------------------------------------------------------------

def pack_pantilt_cmd(
    pan_centideg: int,
    tilt_centideg: int,
    rate_centideg_per_sec: int,
    deadman_active: bool,
) -> bytes:
    """Pan/tilt komutunu 8 byte CAN çerçevesine kodlar.

    Byte düzeni (big-endian):
      0–1  pan_centideg           int16   signed   örn. 4500 → 45.00°
      2–3  tilt_centideg          int16   signed
      4–5  rate_centideg_per_sec  uint16  unsigned
      6    flags                  uint8   bit0=deadman_active
      7    XOR checksum           uint8   bytes 0–6 XOR
    """
    pan_c  = max(-INT16_MAX, min(INT16_MAX, pan_centideg))
    tilt_c = max(-INT16_MAX, min(INT16_MAX, tilt_centideg))
    rate_c = max(0, min(RATE_CENTIDEG_MAX, rate_centideg_per_sec))
    flags  = 0x01 if deadman_active else 0x00
    body   = struct.pack(">hhHB", pan_c, tilt_c, rate_c, flags)
    return body + bytes([_xor8(body)])


def unpack_pantilt_cmd(data: bytes) -> dict[str, Any] | None:
    """Kodlanmış pan/tilt komutunu çözer.

    Returns:
        dict with panDeg, tiltDeg, rateDegPerSec, deadmanActive
        None if length or checksum is wrong
    """
    if len(data) != 8:
        return None
    if data[7] != _xor8(data[:7]):
        return None
    pan_c, tilt_c, rate_c, flags = struct.unpack(">hhHB", data[:7])
    return {
        "panDeg":        pan_c  / CENTIDEG_PER_DEG,
        "tiltDeg":       tilt_c / CENTIDEG_PER_DEG,
        "rateDegPerSec": rate_c / CENTIDEG_PER_DEG,
        "deadmanActive": bool(flags & 0x01),
    }


# ---------------------------------------------------------------------------
# CAN Mesaj Codec — Ateş Komutu (0x101)
# ---------------------------------------------------------------------------

def pack_fire_cmd(fire: bool, stage: int) -> bytes:
    """Ateş komutunu 8 byte CAN çerçevesine kodlar.

    Byte düzeni:
      0  fire_active  uint8  0x01=ateş, 0x00=iptal
      1  stage        uint8  1/2/3
      2–6 sıfır (reserved)
      7  XOR checksum
    """
    stage_b = max(1, min(3, stage))
    body    = bytes([0x01 if fire else 0x00, stage_b, 0, 0, 0, 0, 0])
    return body + bytes([_xor8(body)])


# ---------------------------------------------------------------------------
# CAN Mesaj Codec — Sistem Komutu (0x102)
# ---------------------------------------------------------------------------

def pack_sys_cmd(arm: bool) -> bytes:
    """Sistem arm/disarm komutunu kodlar."""
    body = bytes([0x01 if arm else 0x00, 0, 0, 0, 0, 0, 0])
    return body + bytes([_xor8(body)])


# ---------------------------------------------------------------------------
# CAN Mesaj Codec — legacy MCU Durum Paketi (0x200)
# ---------------------------------------------------------------------------

def pack_status(
    pan_centideg: int,
    tilt_centideg: int,
    estop_active: bool,
    motion_ok: bool,
    fire_ready: bool,
    error_code: int = 0,
) -> bytes:
    """Pico tarafının gönderdiği durum paketini kodlar (simülatör için).

    Byte düzeni:
      0–1  pan_centideg   int16
      2–3  tilt_centideg  int16
      4    flags          uint8  bit0=estop, bit1=motion_ok, bit2=fire_ready
      5    error_code     uint8
      6    sıfır
      7    XOR checksum
    """
    flags = (
        (0x01 if estop_active else 0x00)
        | (0x02 if motion_ok else 0x00)
        | (0x04 if fire_ready else 0x00)
    )
    pan_c  = max(-INT16_MAX, min(INT16_MAX, pan_centideg))
    tilt_c = max(-INT16_MAX, min(INT16_MAX, tilt_centideg))
    body   = struct.pack(">hhBBx", pan_c, tilt_c, flags, error_code & 0xFF)
    return body + bytes([_xor8(body)])


def unpack_status(data: bytes) -> dict[str, Any] | None:
    """Pico durum paketini (0x200) çözer.

    Returns:
        dict with panDeg, tiltDeg, estopActive, motionOk, fireReady, errorCode
        None if malformed
    """
    if len(data) != 8 or data[7] != _xor8(data[:7]):
        return None
    try:
        pan_c, tilt_c, flags, error_code = struct.unpack(">hhBB", data[:6])
    except struct.error:
        return None
    return {
        "panDeg":      pan_c  / CENTIDEG_PER_DEG,
        "tiltDeg":     tilt_c / CENTIDEG_PER_DEG,
        "estopActive": bool(flags & 0x01),
        "motionOk":    bool(flags & 0x02),
        "fireReady":   bool(flags & 0x04),
        "errorCode":   error_code,
        "receivedAt":  _utc_now(),
    }


# ---------------------------------------------------------------------------
# Soyut Donanım Adaptörü
# ---------------------------------------------------------------------------

class HardwareAdapterBase(ABC):
    """Tüm donanım adaptörlerinin uyması gereken arayüz sözleşmesi.

    Alt sınıflar:
      DryRunHardwareAdapter  — fiziksel çıkış yok, geliştirme/test
      ArduinoUnoMotorAdapter — aktif saha satır protokolü (ayrı modül)
      UsbSerialMcuAdapter    — legacy USB CDC/COBS regresyon taşıması
      CanMcuAdapter          — tarihsel CAN test uyumluluğu
    """

    @abstractmethod
    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        """Yüksek seviyeli komut al (ManualAimCommand / FireIntent / SysCmd).

        Her zaman bir sonuç dict döndürmeli; exception fırlatmamalı.
        Sonuç zorunlu alanlar: commandId, kind, accepted, physicalOutput, createdAt
        """
        ...

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Bağlantı sağlığı ve son MCU durumunu döndür."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Bağlantıyı güvenli şekilde kapat."""
        ...


# ---------------------------------------------------------------------------
# CAN MCU Adaptörü (Tarihsel test/geriye uyumluluk)
# ---------------------------------------------------------------------------

class CanMcuAdapter(HardwareAdapterBase):
    """Legacy CAN bus MCU adaptörü (Arduino saha yolunu kullanmaz).

    Gerçek donanım adaptörü doğrudan oluşturulmamalıdır. LIVE yapılandırması,
    fiziksel interlock ve readiness kontrolü için ``runtime_mode`` factory'si
    kullanılmalıdır.

    Kullanım — geliştirme makinesi, sanal CAN (setup_virtual_can.sh sonrası):
        adapter = CanMcuAdapter(
            channel="vcan0",
            bustype="socketcan",
            dry_run=False,
            physical_output_capable=False,
        )
        adapter.start()

    Kullanım — macOS / python-can virtual (OS kurulum gerektirmez):
        adapter = CanMcuAdapter(
            channel="test",
            bustype="virtual",
            dry_run=False,
            physical_output_capable=False,
        )
        adapter.start()

    python-can kurulu değilse: uyarı loglanır, mock modda çalışmaya devam eder.
    """

    def __init__(
        self,
        channel: str = "vcan0",
        bustype: str = "socketcan",
        bitrate: int = 500_000,
        heartbeat_timeout_sec: float = HEALTH_TIMEOUT_SEC,
        estop_callback: EStopCallback | None = None,
        dry_run: bool = True,
        physical_output_capable: bool = False,
    ) -> None:
        self.channel   = channel
        self.bustype   = bustype
        self.bitrate   = bitrate
        self._heartbeat_timeout_sec = heartbeat_timeout_sec
        self._estop_cb = estop_callback
        self._dry_run  = dry_run
        self._physical_output_capable = physical_output_capable

        self._bus: Any          = None
        self._lock              = threading.Lock()
        self._running           = False
        self._rx_thread: threading.Thread | None = None
        self._command_count     = 0
        self._commands: list[dict[str, Any]] = []

        # Son Pico durumu (RX thread tarafından güncellenir)
        self._status: dict[str, Any] = {
            "panDeg": 0.0, "tiltDeg": 0.0,
            "estopActive": False, "motionOk": True,
            "fireReady": False, "errorCode": 0,
            "receivedAt": None,
            "firmwareVersion": None,
            "protocolVersion": 0,
            "encoderOk": False,
        }
        self._rx_guards = {
            CAN_ID_STATUS_V1: SequenceGuard(),
            CAN_ID_FIRMWARE_V1: SequenceGuard(),
            CAN_ID_ENCODER_V1: SequenceGuard(),
            CAN_ID_ESTOP_V1: SequenceGuard(),
            CAN_ID_FAULT_V1: SequenceGuard(),
            CAN_ID_ACK_V1: SequenceGuard(),
        }
        self._last_ack: dict[str, Any] | None = None
        self._rejected_rx_count = 0
        self._tx_sequence = 0
        self._ack_event = threading.Event()

        self._can_available = self._probe_can_import()

    # ------------------------------------------------------------------
    # Başlatma / Kapatma
    # ------------------------------------------------------------------

    def _probe_can_import(self) -> bool:
        try:
            import can  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "python-can bulunamadı; CanMcuAdapter mock modda çalışıyor. "
                "Kurulum: pip install python-can"
            )
            return False

    def start(self) -> None:
        """CAN bağlantısını aç ve arka plan RX dinleyicisini başlat."""
        self._running = True
        if self._dry_run or not self._can_available:
            logger.info(
                "CanMcuAdapter: mock/dry-run modda başlatıldı (CAN çıkışı yok)."
            )
            return
        self._open_bus()
        self._rx_thread = threading.Thread(
            target=self._rx_loop, daemon=True, name="CAN-RX"
        )
        self._rx_thread.start()
        logger.info(
            "CanMcuAdapter: başlatıldı — kanal=%s bustype=%s bitrate=%d",
            self.channel, self.bustype, self.bitrate,
        )

    def set_estop_callback(self, callback: EStopCallback) -> None:
        """Bind CAN E-Stop notifications to the Mission Core queue bridge."""

        self._estop_cb = callback
        with self._lock:
            active = bool(self._status.get("estopActive", False))
        if active:
            callback(True)

    def _open_bus(self) -> None:
        try:
            import can
            self._bus = can.interface.Bus(
                channel=self.channel,
                bustype=self.bustype,
                bitrate=self.bitrate,
            )
            logger.info("CAN bus açıldı: %s (%s)", self.channel, self.bustype)
        except Exception as exc:
            logger.error(
                "CAN bus açılamadı (%s %s): %s — mock modda devam.",
                self.channel, self.bustype, exc,
            )
            self._bus = None

    def close(self) -> None:
        """Bağlantıyı güvenli kapat."""
        self._running = False
        if self._rx_thread:
            self._rx_thread.join(timeout=2.0)
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except Exception:
                pass
            self._bus = None
        logger.info("CanMcuAdapter: kapatıldı.")

    # ------------------------------------------------------------------
    # RX Döngüsü (arka plan thread)
    # ------------------------------------------------------------------

    def _rx_loop(self) -> None:
        """Pico'dan gelen CAN mesajlarını sürekli oku."""
        while self._running:
            if self._bus is None:
                time.sleep(RECONNECT_INTERVAL_SEC)
                self._open_bus()
                continue
            try:
                msg = self._bus.recv(timeout=1.0)
                if msg is None:
                    continue
                self._handle_rx_message(msg)
            except Exception as exc:
                logger.warning("CAN RX hatası: %s", exc)
                time.sleep(0.5)

    def _handle_rx_message(self, msg: Any) -> None:
        arb_id = msg.arbitration_id
        data   = bytes(msg.data)

        if arb_id == CAN_ID_STATUS:
            parsed_v1 = unpack_status_v1(data)
            parsed = parsed_v1 or unpack_status(data)
            if parsed:
                sequence = parsed.get("sequence") if parsed_v1 else None
                if sequence is not None and not self._rx_guards[CAN_ID_STATUS_V1].accept(int(sequence)):
                    self._rejected_rx_count += 1
                    return
                parsed["receivedAt"] = _utc_now()
                parsed["receivedMonotonicNs"] = time.monotonic_ns()
                with self._lock:
                    prev_estop = self._status.get("estopActive", False)
                    self._status.update(parsed)
                    if parsed["estopActive"] != prev_estop and self._estop_cb:
                        # E-stop durum değişikliği — callback'i kilitsiz çağır
                        threading.Thread(
                            target=self._estop_cb,
                            args=(parsed["estopActive"],),
                            daemon=True,
                        ).start()
            else:
                self._rejected_rx_count += 1

        elif arb_id == CAN_ID_FIRMWARE_V1:
            parsed = unpack_firmware_v1(data)
            if parsed and self._rx_guards[CAN_ID_FIRMWARE_V1].accept(int(parsed["sequence"])):
                with self._lock:
                    self._status.update(parsed)
                    self._status["receivedAt"] = _utc_now()
            else:
                self._rejected_rx_count += 1

        elif arb_id == CAN_ID_ENCODER_V1:
            parsed = unpack_encoder_v1(data)
            if parsed and self._rx_guards[CAN_ID_ENCODER_V1].accept(int(parsed["sequence"])):
                encoder_ok = bool(
                    parsed["connected"]
                    and parsed["directionOk"]
                    and parsed["zeroReferenced"]
                    and not parsed["overflow"]
                    and not parsed["deviationFault"]
                )
                with self._lock:
                    self._status.update(parsed)
                    self._status["encoderOk"] = encoder_ok
                    self._status["receivedAt"] = _utc_now()
            else:
                self._rejected_rx_count += 1

        elif arb_id == CAN_ID_ACK_V1:
            parsed = unpack_ack_v1(data)
            if parsed and self._rx_guards[CAN_ID_ACK_V1].accept(int(parsed["sequence"])):
                with self._lock:
                    self._last_ack = parsed
                self._ack_event.set()
            else:
                self._rejected_rx_count += 1

        elif arb_id == CAN_ID_ESTOP_EVENT:
            parsed = unpack_estop_v1(data)
            if parsed:
                if not self._rx_guards[CAN_ID_ESTOP_V1].accept(int(parsed["sequence"])):
                    self._rejected_rx_count += 1
                    return
                active = bool(parsed["active"])
            elif len(data) == 1:
                active = bool(data[0])
            else:
                self._rejected_rx_count += 1
                return
            if data:
                with self._lock:
                    self._status["estopActive"] = active
                if self._estop_cb:
                    threading.Thread(
                        target=self._estop_cb, args=(active,), daemon=True
                    ).start()
                logger.warning("MCU E-Stop acil olayı alındı: aktif=%s", active)

        elif arb_id == CAN_ID_FAULT_V1:
            parsed = unpack_fault_v1(data)
            if parsed and self._rx_guards[CAN_ID_FAULT_V1].accept(int(parsed["sequence"])):
                with self._lock:
                    self._status["faultCode"] = parsed["fault"]
                    self._status["faultDetail"] = parsed["detail"]
                    self._status["motionOk"] = False
                    self._status["fireReady"] = False
            else:
                self._rejected_rx_count += 1

    # ------------------------------------------------------------------
    # TX — CAN Mesajı Gönder
    # ------------------------------------------------------------------

    def _send_can(self, can_id: int, data: bytes) -> bool:
        """Tek bir CAN çerçevesi gönderir. Başarısızsa False döner."""
        if self._dry_run or not self._can_available:
            return True   # mock modda başarılı say
        virtual_channel = self.bustype == "virtual" or self.channel.startswith("vcan")
        if not self._physical_output_capable and not virtual_channel:
            logger.error(
                "Yetkisiz fiziksel CAN çıkışı engellendi (channel=%s, id=0x%03X).",
                self.channel,
                can_id,
            )
            return False
        if self._bus is None:
            logger.error("CAN bus bağlı değil; mesaj gönderilemedi (id=0x%03X).", can_id)
            return False
        try:
            import can
            frame = can.Message(
                arbitration_id=can_id, data=data, is_extended_id=False
            )
            self._bus.send(frame)
            return True
        except Exception as exc:
            logger.error("CAN TX hatası (id=0x%03X): %s", can_id, exc)
            return False

    # ------------------------------------------------------------------
    # execute() — Yüksek Seviyeli Komut İşleme
    # ------------------------------------------------------------------

    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        kind    = command.get("kind", "")
        payload = command.get("payload", {})
        ok      = False
        detail: dict[str, Any] = {}

        command_id = str(command.get("commandId", f"CAN-{self._command_count + 1:05d}"))
        virtual_channel = self.bustype == "virtual" or self.channel.startswith("vcan")
        if not self._dry_run and (self._physical_output_capable or virtual_channel):
            return self._execute_v1(command_id, kind, payload, command)

        if kind == "ManualAimCommand":
            pan_delta_deg  = float(payload.get("panDeltaDeg",  0.0))
            tilt_delta_deg = float(payload.get("tiltDeltaDeg", 0.0))
            rate_deg_s     = float(payload.get("rateLimitDegPerSec", 10.0))
            deadman        = bool(payload.get("deadmanActive", False))

            with self._lock:
                new_pan  = self._status["panDeg"]  + pan_delta_deg
                new_tilt = self._status["tiltDeg"] + tilt_delta_deg

            pan_c  = int(new_pan  * CENTIDEG_PER_DEG)
            tilt_c = int(new_tilt * CENTIDEG_PER_DEG)
            rate_c = int(rate_deg_s * CENTIDEG_PER_DEG)
            data   = pack_pantilt_cmd(pan_c, tilt_c, rate_c, deadman)
            ok     = self._send_can(CAN_ID_PANTILT_CMD, data)
            detail = {
                "targetPanDeg":  new_pan,
                "targetTiltDeg": new_tilt,
                "rateDegPerSec": rate_deg_s,
            }

        elif kind == "FireIntent":
            stage  = int(payload.get("stage", 1))
            target = command.get("target") or {}
            data   = pack_fire_cmd(fire=True, stage=stage)
            ok     = self._send_can(CAN_ID_FIRE_CMD, data)
            detail = {"targetId": target.get("trackId")}

        elif kind == "SysCmd":
            arm  = bool(payload.get("arm", False))
            data = pack_sys_cmd(arm=arm)
            ok   = self._send_can(CAN_ID_SYS_CMD, data)
            detail = {"arm": arm}

        else:
            logger.warning("CanMcuAdapter: tanınmayan komut türü '%s'.", kind)

        self._command_count += 1
        physical_out = (
            ok
            and not self._dry_run
            and self._physical_output_capable
            and self._bus is not None
        )

        if ok and physical_out:
            msg = "CAN komutu Pico MCU'ya iletildi."
        elif ok and self._bus is not None and not self._dry_run:
            msg = "CAN komutu HIL/sanal CAN hattına iletildi; fiziksel çıkış yetkisi yok."
        elif ok:
            msg = "Mock/dry-run modda kaydedildi; fiziksel CAN çıkışı yok."
        else:
            msg = "CAN TX başarısız; komut iletilemedi."

        result: dict[str, Any] = {
            "adapter":        "can_mcu_adapter",
            "commandId":      command.get("commandId", f"CAN-{self._command_count:05d}"),
            "kind":           kind,
            "accepted":       ok,
            "completed":      ok,
            "physicalOutput": physical_out,
            "dryRun":         not physical_out,
            "detail":         detail,
            "message":        msg,
            "createdAt":      _utc_now(),
        }
        with self._lock:
            self._commands.append({"command": command, "result": result})
            if len(self._commands) > 50:
                self._commands.pop(0)
        return result

    def _execute_v1(
        self,
        command_id: str,
        kind: str,
        payload: dict[str, Any],
        command: dict[str, Any],
    ) -> dict[str, Any]:
        """Send one correlated v1 transaction and require a bounded ACK."""

        if kind == "FireIntent":
            preflight_error = self._fire_preflight_error()
            if preflight_error:
                result = self._v1_result(
                    command_id,
                    kind,
                    False,
                    self._tx_sequence,
                    preflight_error,
                )
                with self._lock:
                    self._commands.append({"command": command, "result": result})
                self._command_count += 1
                return result

        self._tx_sequence = (self._tx_sequence + 1) & 0xFF
        sequence = self._tx_sequence
        if kind == "ManualAimCommand":
            with self._lock:
                pan = float(self._status.get("panDeg", 0.0)) + float(payload.get("panDeltaDeg", 0.0))
                tilt = float(self._status.get("tiltDeg", 0.0)) + float(payload.get("tiltDeltaDeg", 0.0))
            kind_code, can_id = KIND_PANTILT, CAN_ID_PANTILT_CMD_V1
            frame = pack_pantilt_v1(sequence, int(pan * 100), int(tilt * 100))
            flags = 1 if payload.get("deadmanActive") else 0
        elif kind == "FireIntent":
            kind_code, can_id = KIND_FIRE, CAN_ID_FIRE_CMD_V1
            frame = pack_fire_v1(sequence, True, int(payload.get("stage", 1)))
            flags = 0
        elif kind == "SysCmd":
            kind_code, can_id = KIND_SYSTEM, CAN_ID_SYS_CMD_V1
            frame = pack_system_v1(sequence, 1 if payload.get("arm") else 0)
            flags = 0
        else:
            return self._v1_result(command_id, kind, False, sequence, "NACK_COMMAND")

        self._ack_event.clear()
        with self._lock:
            self._last_ack = None
        sent = self._send_can(
            CAN_ID_COMMAND_META,
            pack_command_meta(sequence, command_id, kind_code, flags),
        ) and self._send_can(can_id, frame)
        acknowledged = sent and self._ack_event.wait(timeout=0.25)
        with self._lock:
            ack = dict(self._last_ack) if self._last_ack else None
        accepted = bool(
            acknowledged
            and ack
            and ack.get("sequence") == sequence
            and ack.get("commandTag") == command_tag(command_id)
            and ack.get("result") == "ACK"
        )
        result = self._v1_result(
            command_id,
            kind,
            accepted,
            sequence,
            str(ack.get("result") if ack else "ACK_TIMEOUT"),
        )
        with self._lock:
            self._commands.append({"command": command, "result": result})
        self._command_count += 1
        return result

    def _fire_preflight_error(self) -> str | None:
        """Require fresh, explicitly armed MCU state before transmitting FIRE.

        Backend Safety Gate authorization is necessary but not sufficient.  The
        adapter also fails closed when Pico status is stale, faulted, E-Stop is
        active, encoder health is missing, or the physical fire interlock is
        not reported ready.
        """

        with self._lock:
            status = dict(self._status)
        received_at = status.get("receivedAt")
        if not received_at:
            return "FIRE_PREFLIGHT_NO_STATUS"
        try:
            received = datetime.fromisoformat(str(received_at).replace("Z", "+00:00"))
            if (datetime.now(UTC) - received).total_seconds() >= self._heartbeat_timeout_sec:
                return "FIRE_PREFLIGHT_STALE_STATUS"
        except (TypeError, ValueError):
            return "FIRE_PREFLIGHT_BAD_TIMESTAMP"
        if bool(status.get("estopActive", False)):
            return "FIRE_PREFLIGHT_ESTOP"
        if status.get("state") != "ARMED":
            return "FIRE_PREFLIGHT_NOT_ARMED"
        if not bool(status.get("fireReady", False)):
            return "FIRE_PREFLIGHT_INTERLOCK_OPEN"
        if not bool(status.get("encoderOk", False)):
            return "FIRE_PREFLIGHT_ENCODER_UNHEALTHY"
        if int(status.get("faultCode", status.get("errorCode", 0)) or 0) != 0:
            return "FIRE_PREFLIGHT_MCU_FAULT"
        return None

    def _v1_result(
        self, command_id: str, kind: str, accepted: bool, sequence: int, result_code: str
    ) -> dict[str, Any]:
        return {
            "adapter": "can_mcu_adapter",
            "protocolVersion": 1,
            "commandId": command_id,
            "sequence": sequence,
            "kind": kind,
            "accepted": accepted,
            "completed": accepted,
            "physicalOutput": accepted and self._physical_output_capable and self._bus is not None,
            "dryRun": not (accepted and self._physical_output_capable and self._bus is not None),
            "resultCode": result_code,
            "message": "Pico ACK doğrulandı." if accepted else "Komut fail-closed reddedildi.",
            "createdAt": _utc_now(),
        }

    # ------------------------------------------------------------------
    # health_check()
    # ------------------------------------------------------------------

    def health_check(self) -> dict[str, Any]:
        with self._lock:
            status = dict(self._status)

        age_sec: float | None = None
        if status.get("receivedAt"):
            try:
                last = datetime.fromisoformat(
                    status["receivedAt"].replace("Z", "+00:00")
                )
                age_sec = (datetime.now(UTC) - last).total_seconds()
            except Exception:
                pass

        pico_reachable = (
            self._bus is not None
            and age_sec is not None
            and age_sec < self._heartbeat_timeout_sec
        )
        return {
            "adapter":             "can_mcu_adapter",
            "canChannel":          self.channel,
            "busConnected":        self._bus is not None,
            "picoReachable":       pico_reachable,
            "canAvailable":        self._can_available,
            "dryRun":              self._dry_run or not self._can_available,
            "lastStatusAgeSec":    age_sec,
            "mcuStatus":           status,
            "commandCount":        self._command_count,
            "protocolVersion":     status.get("protocolVersion", 0),
            "firmwareVersion":     status.get("firmwareVersion"),
            "encoderOk":           bool(status.get("encoderOk", False)),
            "lastAck":             self._last_ack,
            "rejectedRxCount":     self._rejected_rx_count,
            "physicalOutputEnabled": (
                not self._dry_run
                and self._physical_output_capable
                and self._bus is not None
            ),
        }

    @property
    def current_pan_deg(self) -> float:
        with self._lock:
            return float(self._status.get("panDeg", 0.0))

    @property
    def current_tilt_deg(self) -> float:
        with self._lock:
            return float(self._status.get("tiltDeg", 0.0))

    @property
    def estop_active(self) -> bool:
        with self._lock:
            return bool(self._status.get("estopActive", False))


# ---------------------------------------------------------------------------
# GPIO E-Stop Monitörü (RPi5 Doğrudan GPIO — İkincil Güvence)
# ---------------------------------------------------------------------------

class GpioEStopMonitor:
    """RPi5 GPIO pinini doğrudan izleyen E-Stop monitörü.

    Birincil durum yolu: Pico → MCU taşıması → on_can_estop()
    İkincil yol (yedek): RPi5 GPIO pin interrupt → bu sınıf.

    Avantaj: CAN bus arızasında bile fiziksel kesme çalışır.

    Kullanım:
        monitor = GpioEStopMonitor(
            service_callback=service.set_estop,
            gpio_pin=17,           # BCM numaralama
            gpio_active_low=True,  # NC kontak (açık→active)
        )
        monitor.start()
        # ... servis ömrü ...
        monitor.stop()

    RPi.GPIO kurulu değilse devre dışı kalır ve uyarı loglanır.
    """

    def __init__(
        self,
        service_callback: EStopCallback,
        gpio_pin: int | None = None,
        gpio_active_low: bool = True,
    ) -> None:
        self._callback     = service_callback
        self._gpio_pin     = gpio_pin
        self._active_low   = gpio_active_low
        self._gpio_active  = False

    def on_can_estop(self, active: bool) -> None:
        """MCU adapter'ından gelen E-Stop olayını ilet.

        Ad tarihsel uyumluluk için korunur; USB ve CAN adapter callback'i olabilir.
        """
        logger.warning("E-Stop MCU olayı alındı: aktif=%s", active)
        self._callback(active)

    def start(self) -> None:
        """GPIO interrupt'ı kur (RPi5 üzerinde ikincil güvence)."""
        if self._gpio_pin is None:
            logger.info("GpioEStopMonitor: gpio_pin belirtilmedi; yalnız MCU durum yolu aktif.")
            return
        try:
            import RPi.GPIO as GPIO  # type: ignore[import]
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(
                self._gpio_pin, GPIO.IN,
                pull_up_down=GPIO.PUD_UP if self._active_low else GPIO.PUD_DOWN,
            )
            GPIO.add_event_detect(
                self._gpio_pin, GPIO.BOTH,
                callback=self._gpio_isr,
                bouncetime=50,
            )
            self._gpio_active = True
            logger.info(
                "GpioEStopMonitor: GPIO interrupt aktif (BCM pin %d, active_low=%s).",
                self._gpio_pin, self._active_low,
            )
        except ImportError:
            logger.warning(
                "RPi.GPIO bulunamadı; GPIO E-Stop devre dışı. "
                "MCU durum kanalı üzerinden E-Stop bildirimi hâlâ aktif."
            )
        except Exception as exc:
            logger.error("GpioEStopMonitor başlatma hatası: %s", exc)

    def _gpio_isr(self, channel: int) -> None:
        try:
            import RPi.GPIO as GPIO  # type: ignore[import]
            raw    = GPIO.input(channel)
            active = (raw == 0) if self._active_low else (raw == 1)
            logger.warning(
                "GPIO E-Stop interrupt: pin=%d raw=%d aktif=%s", channel, raw, active
            )
            self._callback(active)
        except Exception as exc:
            logger.error("GPIO ISR hatası: %s", exc)

    def stop(self) -> None:
        if not self._gpio_active or self._gpio_pin is None:
            return
        try:
            import RPi.GPIO as GPIO  # type: ignore[import]
            GPIO.remove_event_detect(self._gpio_pin)
            GPIO.cleanup(self._gpio_pin)
            logger.info("GpioEStopMonitor: durduruldu.")
        except Exception:
            pass
