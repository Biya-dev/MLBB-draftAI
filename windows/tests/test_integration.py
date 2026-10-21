"""End-to-end tests: real socket -> real server -> real dashboard API.

These simulate exactly what the iOS Broadcast Upload Extension will do
(same wire format, same framing) so the Python half is proven working
before any iPhone is involved.
"""

from __future__ import annotations

import socket
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from receiver.app import ReceiverApp
from receiver.protocol import encode_auth, encode_jpeg
from receiver.server import FrameServer


def make_jpeg(width: int = 640, height: int = 360, seed: int = 0) -> bytes:
    import cv2

    rng = np.random.default_rng(seed)
    img = rng.integers(0, 255, (height, width, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return bytes(buf)


@pytest.fixture()
def receiver():
    app = ReceiverApp(
        host="127.0.0.1",
        port=0,
        token="test-token",
        http_port=0,
    )
    app.start()
    yield app
    app.stop()


def connect_and_send(
    port: int, token: str, frames: list[bytes]
) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    sock.sendall(encode_auth(token))
    for f in frames:
        sock.sendall(encode_jpeg(f))
    return sock


def wait_for(predicate, timeout: float = 5.0, interval: float = 0.05) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_authenticated_stream_reaches_hub(receiver):
    port = receiver.server.bound_port
    sock = connect_and_send(port, "test-token", [make_jpeg(seed=1)])
    try:
        assert wait_for(lambda: receiver.hub.snapshot()["stats"]
                        ["frames_processed"] >= 1)
        # The sender is still connected at this point. Check its live state
        # before the cleanup below deliberately closes the socket.
        snap = receiver.hub.snapshot()
        assert snap["state"] == "connected"
        assert snap["has_frame"] is True
        assert snap["stats"]["frames_received"] == 1
        assert snap["stats"]["bytes_received"] > 0
    finally:
        sock.close()


def test_wrong_token_is_rejected(receiver):
    port = receiver.server.bound_port
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        sock.sendall(encode_auth("wrong"))
        assert wait_for(
            lambda: receiver.hub.snapshot()["state"] == "auth_failed"
        )
    finally:
        sock.close()
    snap = receiver.hub.snapshot()
    assert snap["state"] == "auth_failed"
    assert snap["has_frame"] is False
    assert any(e["category"] == "auth" for e in snap["errors"])


def test_reconnect_after_disconnect(receiver):
    port = receiver.server.bound_port
    sock = connect_and_send(port, "test-token", [make_jpeg(seed=2)])
    assert wait_for(lambda: receiver.hub.snapshot()["stats"]
                    ["frames_processed"] >= 1)
    sock.close()
    assert wait_for(
        lambda: receiver.hub.snapshot()["state"] == "disconnected"
    )

    sock2 = connect_and_send(port, "test-token", [make_jpeg(seed=3)])
    try:
        assert wait_for(lambda: receiver.hub.snapshot()["stats"]
                        ["frames_processed"] >= 2)
        assert receiver.hub.snapshot()["state"] == "connected"
    finally:
        sock2.close()


def test_corrupt_jpeg_counts_as_decode_error(receiver):
    port = receiver.server.bound_port
    sock = connect_and_send(port, "test-token", [b"\x00\x01not-a-jpeg"])
    try:
        assert wait_for(lambda: receiver.hub.snapshot()["stats"]
                        ["decode_errors"] >= 1)
    finally:
        sock.close()
    snap = receiver.hub.snapshot()
    assert snap["stats"]["frames_processed"] == 0
    assert snap["stats"]["decode_errors"] == 1


def test_fps_increases_with_frames(receiver):
    port = receiver.server.bound_port
    sock = connect_and_send(
        port, "test-token", [make_jpeg(seed=i) for i in range(5)]
    )
    try:
        assert wait_for(lambda: receiver.hub.snapshot()["stats"]
                        ["frames_processed"] >= 5)
    finally:
        sock.close()
    assert receiver.hub.snapshot()["fps"] > 0


def test_dashboard_api_reports_status(receiver):
    with TestClient(receiver.app) as client:
        r = client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert data["state"] in {"idle", "connected", "disconnected"}
        assert "fps" in data
        assert "stats" in data
        assert "errors" in data


def test_dashboard_html_loads(receiver):
    with TestClient(receiver.app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "MLBB Draft AI" in r.text
        assert "video_feed.mjpg" in r.text


def test_snapshot_endpoint_returns_404_before_any_frame(receiver):
    with TestClient(receiver.app) as client:
        r = client.get("/api/snapshot.jpg")
        assert r.status_code == 404


def test_snapshot_endpoint_returns_jpeg_after_frame(receiver):
    port = receiver.server.bound_port
    sock = connect_and_send(port, "test-token", [make_jpeg(seed=7)])
    try:
        assert wait_for(lambda: receiver.hub.snapshot()["has_frame"])
        with TestClient(receiver.app) as client:
            r = client.get("/api/snapshot.jpg")
            assert r.status_code == 200
            assert r.headers["content-type"] == "image/jpeg"
            assert r.content[:2] == b"\xff\xd8"
    finally:
        sock.close()


def test_mjpeg_stream_emits_multipart(receiver):
    """Drive the MJPEG generator directly.

    ``TestClient`` would buffer the never-ending response, so we consume
    the async generator ourselves and stop after the first frame.
    """
    import asyncio

    port = receiver.server.bound_port
    sock = connect_and_send(port, "test-token", [make_jpeg(seed=9)])
    try:
        assert wait_for(lambda: receiver.hub.snapshot()["has_frame"])

        # Consume the live stream generator.
        stream = receiver._mjpeg_stream()
        chunk = asyncio.run(_first(stream))
        assert b"--mlbframe" in chunk
        assert b"image/jpeg" in chunk
    finally:
        sock.close()


async def _first(stream):
    """Return the first chunk produced by an async generator."""
    async for item in stream:
        return item
    raise AssertionError("stream produced no output")


def test_server_without_token_accepts_frames():
    """Token is optional for trusted LAN setups."""
    from receiver.hub import FrameHub

    hub = FrameHub()
    received: list[bytes] = []
    srv = FrameServer(
        hub=hub, host="127.0.0.1", port=0, token="", on_frame=received.append
    )
    srv.start()
    try:
        sock = socket.create_connection(
            ("127.0.0.1", srv.bound_port), timeout=5
        )
        sock.sendall(encode_jpeg(b"payload"))
        assert wait_for(lambda: len(received) == 1)
        sock.close()
    finally:
        srv.stop()

