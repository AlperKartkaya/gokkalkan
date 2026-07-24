from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from gokkalkan_backend import cli
from gokkalkan_backend.telemetry_session import (
    SessionTelemetryStore,
    build_evidence_package,
    replay_session,
    verify_evidence,
    verify_session,
)


class TelemetrySessionTest(unittest.TestCase):
    def test_single_writer_serializes_concurrent_producers_into_wal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionTelemetryStore(
                Path(tmp) / "run.session", min_free_bytes=0
            )
            with ThreadPoolExecutor(max_workers=12) as pool:
                records = list(
                    pool.map(
                        lambda index: store.append("event", {"index": index}),
                        range(200),
                    )
                )
            metadata = store.metadata()
            with closing(sqlite3.connect(store.db_path)) as connection:
                journal = connection.execute("PRAGMA journal_mode").fetchone()[0]
            store.close()

            self.assertEqual({r["sequence"] for r in records}, set(range(1, 201)))
            self.assertEqual(metadata["recordCount"], 200)
            self.assertTrue(metadata["writerThreadAlive"])
            self.assertEqual(journal.lower(), "wal")
            self.assertTrue(verify_session(Path(tmp) / "run.session")["ok"])

    def test_manifest_hashes_environment_and_input_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "runtime.toml"
            calibration = root / "calibration.json"
            bom = root / "bom.csv"
            config.write_text("profile='SIM'\n", encoding="utf-8")
            calibration.write_text('{"offset": 0}', encoding="utf-8")
            bom.write_text("part,count\nTFA50-L,1\n", encoding="utf-8")
            store = SessionTelemetryStore(
                root / "manifest.session",
                min_free_bytes=0,
                operator_id="OP-01",
                build_id="BUILD-7",
                source_files={
                    "config": config,
                    "calibration": calibration,
                    "bom": bom,
                },
            )
            store.append("event", {"physicalOutput": False})
            store.close()

            manifest = json.loads(store.manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["finalized"])
            self.assertTrue(manifest["evidenceValid"])
            self.assertEqual(manifest["operatorId"], "OP-01")
            self.assertEqual(manifest["buildId"], "BUILD-7")
            self.assertEqual(set(manifest["sourceFiles"]), {"config", "calibration", "bom"})
            self.assertIn("packages", manifest["environment"])
            self.assertTrue(manifest["gitSha"])

    def test_media_common_timebase_replay_and_evidence_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "camera.mp4"
            video.write_bytes(b"simulated-video-not-physical-evidence")
            store = SessionTelemetryStore(
                root / "linked.session", min_free_bytes=0
            )
            camera = store.append(
                "camera_frame",
                {
                    "commandId": "CMD-42",
                    "trackId": "T-1",
                    "physicalOutput": False,
                },
            )
            store.append(
                "safety",
                {
                    "commandId": "CMD-42",
                    "decision": "ALLOWED",
                    "reason": "ALLOWED",
                    "physicalOutput": False,
                },
            )
            store.append(
                "can_frame",
                {
                    "commandId": "CMD-42",
                    "ack": "ACK",
                    "physicalOutput": False,
                },
            )
            store.append(
                "lidar_packet",
                {
                    "commandId": "CMD-42",
                    "trackId": "T-1",
                    "distanceM": 12.4,
                    "physicalOutput": False,
                },
            )
            result = store.append(
                "command_result",
                {
                    "commandId": "CMD-42",
                    "accepted": True,
                    "physicalOutput": False,
                },
            )
            store.index_media(
                kind="video",
                path=video,
                start_monotonic_ns=camera["monotonicNs"],
                end_monotonic_ns=result["monotonicNs"],
                metadata={"cameraId": "CAM-1"},
            )
            store.close()

            first = replay_session(store.session_dir)
            second = replay_session(store.session_dir)
            self.assertTrue(first["ok"])
            self.assertTrue(first["replayOnly"])
            self.assertFalse(first["physicalOutput"])
            self.assertEqual(first["decisionDigest"], second["decisionDigest"])
            archive = root / "evidence.zip"
            package = build_evidence_package(
                store.session_dir,
                archive,
                capability_id="WP-05-TRACE",
                start_monotonic_ns=camera["monotonicNs"],
                end_monotonic_ns=result["monotonicNs"],
            )
            self.assertEqual(package["eventCount"], 5)
            self.assertEqual(package["mediaCount"], 1)
            self.assertTrue(verify_evidence(archive)["ok"])
            with zipfile.ZipFile(archive) as evidence_zip:
                self.assertTrue(
                    any(name.startswith("media/") for name in evidence_zip.namelist())
                )

    def test_missing_media_and_low_disk_mark_session_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionTelemetryStore(
                root / "invalid.session",
                min_free_bytes=2**63,
            )
            bulk = store.append("camera_frame", {"pixels": "omitted"})
            store.index_media(
                kind="video",
                path=root / "missing.mp4",
                start_monotonic_ns=1,
                end_monotonic_ns=2,
            )
            store.close()

            self.assertTrue(bulk["payload"]["dropped"])
            verification = verify_session(store.session_dir)
            self.assertFalse(verification["ok"])
            self.assertIn("MANIFEST_MARKED_INVALID", verification["errors"])

    def test_rotation_retention_and_quota_are_explicit_integrity_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionTelemetryStore(
                Path(tmp) / "rotation.session",
                min_free_bytes=0,
                max_bytes=3_000,
                segment_bytes=1_024,
                retention_segments=2,
            )
            for index in range(20):
                store.append(
                    "event",
                    {"index": index, "value": "x" * 180, "physicalOutput": False},
                )
            metadata = store.metadata()
            store.close()

            self.assertLessEqual(metadata["segmentCount"], 2)
            self.assertLessEqual(metadata["sizeBytes"], 3_000)
            self.assertFalse(verify_session(store.session_dir)["ok"])

    def test_cli_verifies_session_and_rejects_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionTelemetryStore(root / "cli.session", min_free_bytes=0)
            store.append("event", {"physicalOutput": False})
            store.close()
            self.assertEqual(cli.main(["replay", "verify", str(store.session_dir)]), 0)
            segment = next(store.session_dir.glob("events-*.jsonl"))
            segment.write_text("tampered\n", encoding="utf-8")
            self.assertEqual(cli.main(["evidence", "verify", str(store.session_dir)]), 1)
            self.assertFalse(verify_session(store.session_dir)["ok"])

    def test_corrupt_database_is_reported_not_raised(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionTelemetryStore(
                Path(tmp) / "corrupt.session", min_free_bytes=0
            )
            store.append("event", {"physicalOutput": False})
            store.close()
            store.db_path.write_bytes(b"not-a-sqlite-database")

            result = verify_session(store.session_dir)
            replay = replay_session(store.session_dir)

            self.assertFalse(result["ok"])
            self.assertTrue(any(error.startswith("SQLITE_ERROR") for error in result["errors"]))
            self.assertEqual(replay["events"], [])
            self.assertFalse(replay["physicalOutput"])


if __name__ == "__main__":
    unittest.main()
