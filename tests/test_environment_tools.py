from __future__ import annotations

import json
import subprocess
import socket
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

from gokkalkan_backend.operator_http_server import build_http_server
from gokkalkan_backend.static_server import build_static_server
from gokkalkan_backend.telemetry_log import JsonlTelemetryStore
from gokkalkan_backend.telemetry_recorder import TelemetryRecorder


class TelemetryRecorderTest(unittest.TestCase):
    def test_recorder_accepts_only_typed_json_datagrams(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = TelemetryRecorder(
                Path(tmp) / "recorder.sock",
                Path(tmp) / "records.jsonl",
                max_bytes=1_048_576,
            )

            invalid = recorder._record_datagram(b'{"payload": {}}')
            valid = recorder._record_datagram(
                json.dumps(
                    {
                        "recordType": "doctor_test",
                        "payload": {"physicalOutput": False},
                    }
                ).encode("utf-8")
            )

            self.assertIsNone(invalid)
            self.assertIsNotNone(valid)
            records = recorder.store.read_all()
            self.assertEqual(len(records), 1)
            self.assertFalse(records[0]["payload"]["physicalOutput"])

    def test_jsonl_store_rotates_before_exceeding_configured_quota(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonlTelemetryStore(
                Path(tmp) / "quota.jsonl",
                max_bytes=480,
            )

            store.append("quota", {"value": "a" * 100})
            store.append("quota", {"value": "b" * 100})

            self.assertTrue(store.rotated_path.exists())
            retained_bytes = (
                store.path.stat().st_size + store.rotated_path.stat().st_size
            )
            self.assertLessEqual(retained_bytes, 480)

    def test_jsonl_store_serializes_concurrent_http_style_writers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonlTelemetryStore(Path(tmp) / "concurrent.jsonl")

            with ThreadPoolExecutor(max_workers=8) as pool:
                records = list(
                    pool.map(
                        lambda index: store.append("concurrent", {"index": index}),
                        range(200),
                    )
                )

            persisted = store.read_all()

        self.assertEqual(len(persisted), 200)
        self.assertEqual(
            {record["recordId"] for record in records},
            set(range(1, 201)),
        )
        self.assertNotIn("corrupt", {record["recordType"] for record in persisted})


class StaticServerTest(unittest.TestCase):
    def test_static_server_health_and_spa_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text(
                "<h1>Gökkalkan</h1>",
                encoding="utf-8",
            )
            server = build_static_server(
                "127.0.0.1",
                0,
                root=root,
                api_base="http://127.0.0.1:1",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            port = server.server_address[1]
            try:
                with urlopen(f"http://127.0.0.1:{port}/healthz") as response:
                    health = json.loads(response.read())
                with urlopen(f"http://127.0.0.1:{port}/operator/route") as response:
                    html = response.read().decode("utf-8")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertTrue(health["ok"])
        self.assertIn("Gökkalkan", html)


class OperatorServerLifecycleTest(unittest.TestCase):
    def test_operator_server_emits_only_configured_cors_origin(self) -> None:
        server = build_http_server(
            "127.0.0.1",
            0,
            allowed_origins=("http://127.0.0.1:4173",),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            allowed = Request(
                f"http://127.0.0.1:{port}/health",
                headers={"Origin": "http://127.0.0.1:4173"},
            )
            denied = Request(
                f"http://127.0.0.1:{port}/health",
                headers={"Origin": "http://untrusted.invalid"},
            )
            with urlopen(allowed) as response:
                allowed_origin = response.headers["Access-Control-Allow-Origin"]
            with urlopen(denied) as response:
                denied_origin = response.headers["Access-Control-Allow-Origin"]
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(allowed_origin, "http://127.0.0.1:4173")
        self.assertIsNone(denied_origin)

    def test_sim_server_handles_sigterm_with_clean_exit(self) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        original = Path("config/runtime/sim.toml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "sim.toml"
            telemetry_path = Path(tmp) / "server.jsonl"
            config.write_text(
                original.replace(
                    'path = "telemetry_data/operator-api-sim.jsonl"',
                    f'path = "{telemetry_path}"',
                ),
                encoding="utf-8",
            )
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "gokkalkan_backend.operator_http_server",
                    "--config",
                    str(config),
                    "--port",
                    str(port),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                for _ in range(50):
                    try:
                        with urlopen(
                            f"http://127.0.0.1:{port}/health",
                            timeout=0.1,
                        ) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        threading.Event().wait(0.05)
                else:
                    self.fail("SIM server did not become ready")
                process.terminate()
                return_code = process.wait(timeout=3)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=2)

        self.assertEqual(return_code, 0)


class DeploymentManifestTest(unittest.TestCase):
    def test_pi_manifest_and_systemd_contract_validate(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/verify_pi_manifest.py",
                "--manifest-only",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: manifest schema 1", result.stdout)


if __name__ == "__main__":
    unittest.main()
