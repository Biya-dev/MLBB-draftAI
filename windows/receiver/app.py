"""FastAPI dashboard: live MJPEG feed + status JSON + a clean HTML UI."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse

from .frame_processor import FrameProcessor
from .hub import FrameHub
from .server import FrameServer

log = logging.getLogger("receiver.app")

BOUNDARY = "mlbframe"

_TEMPLATE = Path(__file__).with_name("dashboard.html")


class ReceiverApp:
    """Owns the hub, the frame server and the dashboard HTTP app."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        token: str = "",
        http_host: str = "0.0.0.0",
        http_port: int = 8080,
        max_width: int = 1280,
        jpeg_quality: int = 70,
    ) -> None:
        self.hub = FrameHub()
        self.processor = FrameProcessor(
            max_width=max_width, jpeg_quality=jpeg_quality
        )
        self._frame_seq = 0
        self.server = FrameServer(
            hub=self.hub,
            host=host,
            port=port,
            token=token,
            on_frame=self._on_frame,
        )
        self.http_host = http_host
        self.http_port = http_port
        self.app = self._build_app()

    # -- frame pipeline ---------------------------------------------------
    def _on_frame(self, jpeg_bytes: bytes) -> None:
        """Called on the ingest thread for every inbound frame."""
        result = self.processor.process(jpeg_bytes)
        if not result.ok or result.jpeg is None:
            self.hub.note_decode_error(result.error or "unknown decode error")
            return
        self._frame_seq += 1
        self.hub.publish(result.jpeg, self._frame_seq, result.processing_ms)

    # -- routes -----------------------------------------------------------
    def _build_app(self) -> FastAPI:
        app = FastAPI(
            title="MLBB Draft AI - Screen Receiver",
            version="1.0.0",
            docs_url="/api/docs",
        )

        @app.get("/api/status")
        async def status() -> dict:
            snap = self.hub.snapshot()
            snap["ingest_port"] = self.server.bound_port
            snap["http_port"] = self.http_port
            return snap

        @app.get("/api/snapshot.jpg")
        async def snapshot_jpg() -> Response:
            frame = self.hub.current_frame()
            if frame is None:
                return Response(status_code=404, content=b"no frame yet")
            return Response(
                content=frame,
                media_type="image/jpeg",
                headers={"Cache-Control": "no-store"},
            )

        @app.get("/video_feed.mjpg")
        async def video_feed() -> StreamingResponse:
            return StreamingResponse(
                self._mjpeg_stream(),
                media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                    "Connection": "close",
                    "X-Accel-Buffering": "no",
                },
            )

        @app.get("/", response_class=HTMLResponse)
        async def index() -> HTMLResponse:
            return HTMLResponse(_TEMPLATE.read_text(encoding="utf-8"))

        return app

    async def _mjpeg_stream(self) -> AsyncIterator[bytes]:
        """Yield the latest frame whenever it changes."""
        self.hub.add_client()
        last_seq = -1
        try:
            while True:
                snap = self.hub.snapshot()
                seq = snap["frame_seq"]
                if seq != last_seq and snap["has_frame"]:
                    last_seq = seq
                    frame = self.hub.current_frame()
                    if frame:
                        head = (
                            f"--{BOUNDARY}\r\n"
                            f"Content-Type: image/jpeg\r\n"
                            f"Content-Length: {len(frame)}\r\n\r\n"
                        ).encode("ascii")
                        yield head + frame + b"\r\n"
                await asyncio.sleep(1.0 / 20.0)
        finally:
            self.hub.remove_client()

    # -- lifecycle --------------------------------------------------------
    def start(self) -> None:
        self.server.start()

    def stop(self) -> None:
        self.server.stop()
