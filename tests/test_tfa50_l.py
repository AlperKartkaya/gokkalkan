from __future__ import annotations

import unittest
import pytest

from gokkalkan_backend.tfa50_l import (
    TFA50LFrameError,
    TFA50LStreamDecoder,
    frequency_command,
    parse_measurement_frame,
    parse_tfmini_frame,
    parse_identity_response,
)
from gokkalkan_backend.lidar_adapter import probe_tfa50l_uart

pytestmark = pytest.mark.protocol


class TFA50LProtocolTest(unittest.TestCase):
    def test_datasheet_example_decodes_little_endian_distance(self) -> None:
        measurement = parse_measurement_frame(bytes.fromhex("5C 02 11 EC"))

        self.assertTrue(measurement.valid)
        self.assertFalse(measurement.no_detection)
        self.assertEqual(measurement.distance_cm, 4354)
        self.assertAlmostEqual(measurement.distance_m or 0.0, 43.54)

    def test_no_detection_sentinel_is_not_a_valid_range(self) -> None:
        measurement = parse_measurement_frame(bytes.fromhex("5C FF FF 01"))

        self.assertFalse(measurement.valid)
        self.assertTrue(measurement.no_detection)
        self.assertEqual(measurement.distance_cm, 65535)
        self.assertIsNone(measurement.distance_m)

    def test_invalid_header_or_checksum_is_rejected(self) -> None:
        with self.assertRaisesRegex(TFA50LFrameError, "header"):
            parse_measurement_frame(bytes.fromhex("00 02 11 EC"))

        with self.assertRaisesRegex(TFA50LFrameError, "checksum"):
            parse_measurement_frame(bytes.fromhex("5C 02 11 00"))

    def test_stream_decoder_handles_chunks_noise_and_corrupt_frames(self) -> None:
        decoder = TFA50LStreamDecoder()

        self.assertEqual(decoder.feed(bytes.fromhex("00 99 5C 02")), [])
        measurements = decoder.feed(
            bytes.fromhex(
                "11 EC "  # önceki parçadaki geçerli 43,54 m ölçümünü tamamlar
                "5C 02 11 00 "  # bozuk checksum; atlanmalı
                "5C FF FF 01"  # geçerli no-detection çerçevesi
            )
        )

        self.assertEqual([item.distance_cm for item in measurements], [4354, 65535])
        self.assertEqual(decoder.rejected_frame_count, 1)
        self.assertGreaterEqual(decoder.discarded_byte_count, 2)

    def test_receive_only_probe_decodes_frames_without_writing_commands(self) -> None:
        class ReceiveOnlySerial:
            def __init__(self) -> None:
                self.chunks = [bytes.fromhex("5C 02 11 EC"), b""]
                self.closed = False

            def read(self, _size: int = 64) -> bytes:
                return self.chunks.pop(0) if self.chunks else b""

            def close(self) -> None:
                self.closed = True

        serial = ReceiveOnlySerial()
        ticks = iter((0.0, 0.0, 0.02, 0.2))
        result = probe_tfa50l_uart(
            "/dev/fake",
            timeout_sec=0.1,
            serial_factory=lambda **_kwargs: serial,
            monotonic=lambda: next(ticks),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "RECEIVE_ONLY")
        self.assertEqual(result["validFrameCount"], 1)
        self.assertEqual(result["lastMeasurement"]["distanceM"], 43.54)
        self.assertTrue(serial.closed)

    def test_identity_and_frequency_control_frames_follow_datasheet(self) -> None:
        self.assertEqual(
            parse_identity_response(
                bytes.fromhex("5A 8D 02 10 01 5F"), response_code=0x8D
            ),
            "S00272",
        )
        self.assertEqual(
            parse_identity_response(
                bytes.fromhex("5A 96 02 03 02 62"), response_code=0x96
            ),
            "V2.3",
        )
        self.assertEqual(frequency_command(1000), bytes.fromhex("5A 0B 02 E7 03 08"))

    def test_tfmini_9byte_frame_decodes_distance_strength_and_temperature(self) -> None:
        # Example 9-byte frame: 59 59 [Dist: 0x00FA = 250cm = 2.50m] [Strength: 0x03E8 = 1000] [Temp: 0x08FC = 2300 -> 31.5C] [Checksum = 0x9B]
        raw = bytes.fromhex("59 59 FA 00 E8 03 FC 08 9B")
        measurement = parse_tfmini_frame(raw)

        self.assertTrue(measurement.valid)
        self.assertFalse(measurement.no_detection)
        self.assertEqual(measurement.distance_cm, 250)
        self.assertAlmostEqual(measurement.distance_m or 0.0, 2.50)
        self.assertEqual(measurement.signal_strength, 1000)
        self.assertEqual(measurement.protocol, "TF-Luna/TFmini")

    def test_tfmini_no_detection_handling(self) -> None:
        # Distance = 0 or 0xFFFF
        raw_zero = bytes.fromhex("59 59 00 00 00 00 00 00 B2")
        meas_zero = parse_tfmini_frame(raw_zero)
        self.assertTrue(meas_zero.no_detection)
        self.assertFalse(meas_zero.valid)
        self.assertIsNone(meas_zero.distance_m)

    def test_stream_decoder_handles_mixed_tfmini_and_tfa50l_frames(self) -> None:
        decoder = TFA50LStreamDecoder()
        # Stream contains: 4-byte TFA50-L (43.54m), noise bytes, 9-byte TFmini (2.50m)
        chunk = bytes.fromhex("5C 02 11 EC 00 FF 59 59 FA 00 E8 03 FC 08 9B")
        measurements = decoder.feed(chunk)

        self.assertEqual(len(measurements), 2)
        self.assertEqual(measurements[0].distance_cm, 4354)
        self.assertEqual(measurements[1].distance_cm, 250)


if __name__ == "__main__":
    unittest.main()
