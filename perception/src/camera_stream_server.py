"""Small no-framework HTTP server for the latest physical camera frame."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class CameraFrameStore:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._jpeg: bytes | None = None
        self._sequence = 0
        self._timestamp: str | None = None

    def update_jpeg(self, jpeg: bytes, timestamp: str) -> None:
        if not jpeg.startswith(b"\xff\xd8"):
            raise ValueError("camera frame is not JPEG")
        with self._condition:
            self._jpeg = bytes(jpeg)
            self._timestamp = timestamp
            self._sequence += 1
            self._condition.notify_all()

    def update_image(self, image: Any, timestamp: str) -> None:
        import cv2

        ok, encoded = cv2.imencode(
            ".jpg",
            image,
            [int(cv2.IMWRITE_JPEG_QUALITY), 82],
        )
        if not ok:
            raise RuntimeError("camera frame JPEG encoding failed")
        self.update_jpeg(encoded.tobytes(), timestamp)

    def latest(self) -> tuple[bytes | None, int, str | None]:
        with self._condition:
            return self._jpeg, self._sequence, self._timestamp

    def wait_after(
        self,
        sequence: int,
        timeout: float = 1.0,
    ) -> tuple[bytes | None, int, str | None]:
        with self._condition:
            if self._sequence <= sequence:
                self._condition.wait(timeout=timeout)
            return self._jpeg, self._sequence, self._timestamp


def build_camera_stream_server(
    host: str,
    port: int,
    store: CameraFrameStore,
) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/camera/frame.jpg":
                jpeg, _sequence, _timestamp = store.latest()
                if jpeg is None:
                    self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "camera frame unavailable")
                    return
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(jpeg)))
                self.end_headers()
                self.wfile.write(jpeg)
                return
            if self.path == "/camera/live.mjpg":
                self.send_response(HTTPStatus.OK)
                self.send_header(
                    "Content-Type",
                    "multipart/x-mixed-replace; boundary=frame",
                )
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                sequence = -1
                try:
                    while True:
                        jpeg, next_sequence, timestamp = store.wait_after(sequence)
                        if jpeg is None or next_sequence == sequence:
                            continue
                        sequence = next_sequence
                        header = (
                            b"--frame\r\nContent-Type: image/jpeg\r\n"
                            + f"Content-Length: {len(jpeg)}\r\n".encode()
                            + f"X-Frame-Timestamp: {timestamp or ''}\r\n\r\n".encode()
                        )
                        self.wfile.write(header + jpeg + b"\r\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
            elif self.path == "/health":
                jpeg, sequence, timestamp = store.latest()
                payload = json.dumps(
                    {
                        "ok": jpeg is not None,
                        "hasFrame": jpeg is not None,
                        "sequence": sequence,
                        "latestFrameAt": timestamp,
                        "source": "physical-camera",
                    }
                ).encode()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

    return ThreadingHTTPServer((host, port), Handler)


class CameraStreamService:
    def __init__(self, host: str = "127.0.0.1", port: int = 8090) -> None:
        self.store = CameraFrameStore()
        self.server = build_camera_stream_server(host, port, self.store)
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
            name="CameraStream",
        )
        self._thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        if self._thread:
            self._thread.join(timeout=2)

    def update_image(self, image: Any, timestamp: str) -> None:
        self.store.update_image(image, timestamp)
