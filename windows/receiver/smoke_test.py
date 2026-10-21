"""Manual smoke test: run the receiver and push synthetic frames at it.

Simulates the iPhone sender over a real socket against the real server,
then verifies the dashboard HTTP endpoints respond correctly.

Usage:
    python -m receiver.smoke_test --token test --frames 30
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.request

import cv2
import numpy as np

from .app import ReceiverApp
from .protocol import encode_auth, encode_jpeg


def synthetic_frame(index: int) -> bytes:
    """A moving test pattern that looks like a screen."""
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.putText(
        img, f"MLBB Draft AI - frame {index}", (60, 360),
        cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 255, 0), 4, cv2.LINE_AA,
    )
    cv2.rectangle(
        img, (50, 50), (50 + (index * 20) % 1100, 650), (255, 120, 0), 6
    )
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    assert ok
    return bytes(buf)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Receiver smoke test.")
    parser.add_argument("--token", default="smoke-token")
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--http-port", type=int, default=8099)
    args = parser.parse_args(argv)

    app = ReceiverApp(
        host="127.0.0.1", port=0, token=args.token, http_port=args.http_port
    )
    app.start()
    port = app.server.bound_port
    print(f"[smoke] ingest port {port}")

    import uvicorn
    import threading

    config = uvicorn.Config(
        app.app, host="127.0.0.1", port=args.http_port, log_level="warning"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1.5)

    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    sock.sendall(encode_auth(args.token))
    delay = 1.0 / max(args.fps, 0.1)
    for i in range(args.frames):
        sock.sendall(encode_jpeg(synthetic_frame(i)))
        time.sleep(delay)
    sock.close()
    time.sleep(0.5)

    base = f"http://127.0.0.1:{args.http_port}"
    status = json.loads(urllib.request.urlopen(f"{base}/api/status").read())
    print("[smoke] status:", status["state"], "fps:", status["fps"])
    print("[smoke] stats:", status["stats"])

    snap = urllib.request.urlopen(f"{base}/api/snapshot.jpg").read()
    print(f"[smoke] snapshot.jpg: {len(snap)} bytes, header={snap[:2]!r}")

    html = urllib.request.urlopen(f"{base}/").read().decode("utf-8")
    print(f"[smoke] dashboard html: {len(html)} bytes, "
          f"has title={'MLBB Draft AI' in html}")

    ok = (
        status["stats"]["frames_processed"] == args.frames
        and status["stats"]["decode_errors"] == 0
        and snap[:2] == b"\xff\xd8"
        and "MLBB Draft AI" in html
    )
    print("[smoke] RESULT:", "PASS" if ok else "FAIL")

    app.stop()
    server.should_exit = True
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
