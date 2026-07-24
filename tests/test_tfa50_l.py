from __future__ import annotations

import unittest

from gokkalkan_backend.tfa50_l import (
    TFA50LFrameError,
    TFA50LStreamDecoder,
    parse_measurement_frame,
)


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


if __name__ == "__main__":
    unittest.main()
