import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "perception" / "src"))

from camera_stream_server import CameraFrameStore, build_camera_stream_server


def test_camera_stream_serves_only_actual_stored_jpeg() -> None:
    store = CameraFrameStore()
    server = build_camera_stream_server("127.0.0.1", 0, store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        try:
            urllib.request.urlopen(f"{base}/camera/frame.jpg")
            raise AssertionError("empty stream should fail closed")
        except urllib.error.HTTPError as exc:
            assert exc.code == 503

        fake_jpeg = b"\xff\xd8physical-camera-bytes\xff\xd9"
        store.update_jpeg(fake_jpeg, "2026-07-26T10:00:00Z")
        with urllib.request.urlopen(f"{base}/camera/frame.jpg") as response:
            assert response.headers["Content-Type"] == "image/jpeg"
            assert response.read() == fake_jpeg
        with urllib.request.urlopen(f"{base}/health") as response:
            health = json.load(response)
        assert health["source"] == "physical-camera"
        assert health["hasFrame"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
