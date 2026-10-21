"""OpenCV-based frame processing for the receiver.

Phase 1 deliberately does *no* hero recognition or draft analysis. This
module only does the work needed for a reliable live feed:

    * decode JPEG bytes into a BGR image
    * downscale to a bounded width (so the dashboard stays light)
    * draw an overlay with timestamp / resolution

Everything is defensive: a corrupt JPEG from a flaky phone must never kill
the ingest thread.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

#: Longest edge (px) the processed frame is scaled to.
DEFAULT_MAX_WIDTH = 1280

#: JPEG quality used when re-encoding for the browser (0-100).
DEFAULT_JPEG_QUALITY = 70


@dataclass
class ProcessResult:
    """Outcome of processing one inbound frame."""

    ok: bool
    image: np.ndarray | None = None
    jpeg: bytes | None = None
    error: str | None = None
    processing_ms: float = 0.0


class FrameProcessor:
    """Decode + scale + annotate frames coming off the wire."""

    def __init__(
        self,
        max_width: int = DEFAULT_MAX_WIDTH,
        jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    ) -> None:
        if max_width < 16:
            raise ValueError("max_width must be >= 16")
        self.max_width = max_width
        self.jpeg_quality = max(1, min(100, jpeg_quality))
        self._encode_params = [
            cv2.IMWRITE_JPEG_QUALITY,
            self.jpeg_quality,
        ]

    def decode(self, jpeg_bytes: bytes) -> np.ndarray:
        """Decode JPEG bytes to a BGR image. Raises ValueError if invalid."""
        if not jpeg_bytes:
            raise ValueError("empty JPEG payload")
        buf = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("cv2.imdecode returned None (corrupt JPEG)")
        return image

    def resize(self, image: np.ndarray) -> np.ndarray:
        """Downscale so the width is at most ``max_width``; no upscaling."""
        height, width = image.shape[:2]
        if width <= self.max_width:
            return image
        scale = self.max_width / float(width)
        new_w = self.max_width
        new_h = max(1, int(round(height * scale)))
        return cv2.resize(
            image, (new_w, new_h), interpolation=cv2.INTER_AREA
        )

    def annotate(self, image: np.ndarray) -> np.ndarray:
        """Draw a small status strip along the top of the frame."""
        out = image.copy()
        h, w = out.shape[:2]
        strip_h = max(24, h // 18)
        label = time.strftime("%H:%M:%S")
        cv2.rectangle(out, (0, 0), (w, strip_h), (0, 0, 0), -1)
        cv2.putText(
            out,
            label,
            (8, strip_h - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            max(0.4, strip_h / 40.0),
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
        return out

    def process(self, jpeg_bytes: bytes) -> ProcessResult:
        """Full pipeline: decode -> resize -> annotate -> JPEG encode."""
        started = time.perf_counter()
        try:
            image = self.decode(jpeg_bytes)
            image = self.resize(image)
            image = self.annotate(image)
            ok, buf = cv2.imencode(".jpg", image, self._encode_params)
            if not ok:
                raise ValueError("cv2.imencode failed to encode JPEG")
            elapsed = (time.perf_counter() - started) * 1000.0
            return ProcessResult(
                ok=True,
                image=image,
                jpeg=bytes(buf),
                processing_ms=elapsed,
            )
        except Exception as exc:  # noqa: BLE001 - never kill the ingest thread
            elapsed = (time.perf_counter() - started) * 1000.0
            return ProcessResult(
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                processing_ms=elapsed,
            )
