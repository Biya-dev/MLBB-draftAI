"""Shared state: latest frame, connection status, FPS counters, error log.

Thread-safe. The ingest thread writes, the FastAPI/UI threads read.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum


class LinkState(str, Enum):
    """Lifecycle of the phone -> PC link."""

    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    AUTH_FAILED = "auth_failed"
    ERROR = "error"


@dataclass
class Stats:
    """Rolling counters shown on the dashboard."""

    frames_received: int = 0
    frames_processed: int = 0
    frames_dropped: int = 0
    decode_errors: int = 0
    bytes_received: int = 0
    last_frame_at: float = 0.0
    processing_ms: float = 0.0
    started_at: float = 0.0

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.started_at


class FrameHub:
    """Holds the most recent processed frame and tracks link health."""

    #: How many frame timestamps to keep for the FPS estimate.
    FPS_WINDOW = 30

    def __init__(self, max_errors: int = 20) -> None:
        self._lock = threading.Lock()
        self._frame: bytes | None = None
        self._frame_seq = 0
        self._frame_at = 0.0
        self._state = LinkState.IDLE
        self._state_message = "Waiting for the iPhone to connect."
        self._peer: str | None = None
        self._stats = Stats(started_at=time.time())
        self._errors: deque[dict] = deque(maxlen=max_errors)
        self._timestamps: deque[float] = deque(maxlen=self.FPS_WINDOW)
        self._clients = 0

    # -- connection state -------------------------------------------------
    def set_state(
        self,
        state: LinkState,
        message: str = "",
        peer: str | None = None,
    ) -> None:
        with self._lock:
            self._state = state
            if message:
                self._state_message = message
            if peer is not None:
                self._peer = peer

    def set_peer(self, peer: str) -> None:
        with self._lock:
            self._peer = peer

    # -- frames -----------------------------------------------------------
    def publish(
        self, jpeg: bytes, frame_seq: int, processing_ms: float = 0.0
    ) -> None:
        """Store a new processed JPEG as the current live frame."""
        with self._lock:
            self._frame = jpeg
            self._frame_seq = frame_seq
            self._frame_at = time.time()
            self._timestamps.append(self._frame_at)
            self._stats.frames_processed += 1
            self._stats.processing_ms = processing_ms

    def current_frame(self) -> bytes | None:
        with self._lock:
            return self._frame

    def frame_age_seconds(self) -> float | None:
        with self._lock:
            if not self._frame_at:
                return None
            return time.time() - self._frame_at


    # -- counters ---------------------------------------------------------
    def note_bytes(self, count: int) -> None:
        with self._lock:
            self._stats.bytes_received += count

    def note_frame_received(self) -> None:
        with self._lock:
            self._stats.frames_received += 1

    def note_decode_error(self, message: str) -> None:
        with self._lock:
            self._stats.decode_errors += 1
            self._stats.frames_dropped += 1
            self._push_error_locked("decode", message)

    def note_error(self, category: str, message: str) -> None:
        with self._lock:
            self._push_error_locked(category, message)

    def _push_error_locked(self, category: str, message: str) -> None:
        self._errors.append(
            {
                "at": time.strftime("%H:%M:%S"),
                "category": category,
                "message": message,
            }
        )

    def note_disconnect(self, message: str) -> None:
        with self._lock:
            self._state = LinkState.DISCONNECTED
            self._state_message = message
            self._push_error_locked("link", message)

    def reset_counters(self) -> None:
        with self._lock:
            self._stats = Stats(started_at=time.time())
            self._timestamps.clear()

    # -- derived metrics --------------------------------------------------
    def _fps_locked(self) -> float:
        """FPS over the recent window. Caller must hold the lock."""
        if len(self._timestamps) < 2:
            return 0.0
        span = self._timestamps[-1] - self._timestamps[0]
        if span <= 0:
            return 0.0
        return (len(self._timestamps) - 1) / span

    def fps(self) -> float:
        with self._lock:
            return self._fps_locked()

    def snapshot(self) -> dict:
        """Everything the dashboard needs, as a plain dict."""
        with self._lock:
            age = time.time() - self._frame_at if self._frame_at else None
            return {
                "state": self._state.value,
                "message": self._state_message,
                "peer": self._peer,
                "fps": round(self._fps_locked(), 2),
                "frame_age_seconds": round(age, 2) if age is not None else None,
                "has_frame": self._frame is not None,
                "frame_seq": self._frame_seq,
                "clients": self._clients,
                "stats": {
                    "frames_received": self._stats.frames_received,
                    "frames_processed": self._stats.frames_processed,
                    "frames_dropped": self._stats.frames_dropped,
                    "decode_errors": self._stats.decode_errors,
                    "bytes_received": self._stats.bytes_received,
                    "processing_ms": round(self._stats.processing_ms, 2),
                    "uptime_seconds": round(self._stats.uptime_seconds, 1),
                },
                "errors": list(self._errors),
            }

    # -- dashboard client tracking ---------------------------------------
    def add_client(self) -> None:
        with self._lock:
            self._clients += 1

    def remove_client(self) -> None:
        with self._lock:
            self._clients = max(0, self._clients - 1)
