from __future__ import annotations

from pathlib import Path

from gokkalkan_backend.arduino_motor_adapter import (
    FIELD_PROFILE_ID,
    PAN_DIR_PIN,
    PAN_PUL_PIN,
    PULSES_PER_REVOLUTION,
    TILT_DIR_PIN,
    TILT_PUL_PIN,
)
from gokkalkan_backend.runtime_config import load_runtime_config


FIRMWARE_PATH = Path("realtimetesting/arduino_uno/arduino_uno.ino")


def test_r1_firmware_matches_adapter_pin_profile_and_calibration():
    firmware = FIRMWARE_PATH.read_text(encoding="utf-8")

    assert f'FIELD_PROFILE[] = "{FIELD_PROFILE_ID}"' in firmware
    assert f"PIN_M1_PUL = {PAN_PUL_PIN}" in firmware
    assert f"PIN_M1_DIR = {PAN_DIR_PIN}" in firmware
    assert f"PIN_M2_PUL = {TILT_PUL_PIN}" in firmware
    assert f"PIN_M2_DIR = {TILT_DIR_PIN}" in firmware
    assert f"MAX_STEP_COUNT = {PULSES_PER_REVOLUTION}UL" in firmware
    assert 'Serial.println(F("PONG"))' in firmware
    assert 'Serial.print(F("PROFILE "))' in firmware


def test_r1_firmware_rejects_unbounded_motion_and_has_jog_watchdog():
    firmware = FIRMWARE_PATH.read_text(encoding="utf-8")

    assert "parseBoundedUnsigned" in firmware
    assert "atol(" not in firmware
    assert "MAX_RUN_DURATION_SEC = 15UL" in firmware
    assert "JOG_TIMEOUT_MS = 1000UL" in firmware
    assert 'Serial.println(F("ERR JOG_TIMEOUT_STOPPED"))' in firmware
    assert 'Serial.print(F("ERR UNKNOWN_COMMAND "))' in firmware


def test_r1_firmware_keeps_run_acknowledgements_machine_readable():
    firmware = FIRMWARE_PATH.read_text(encoding="utf-8")

    assert 'Serial.print(F("OK RUNNING "))' in firmware
    assert 'Serial.println(F("OK COMPLETED"))' in firmware
    assert "BASLATILDI" not in firmware
    assert "last_status_print_ms" not in firmware


def test_all_runtime_profiles_request_the_r1_firmware_profile():
    for path in Path("config/runtime").glob("*.toml"):
        assert load_runtime_config(path).mcu.field_profile == FIELD_PROFILE_ID
