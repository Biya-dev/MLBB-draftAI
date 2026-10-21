"""TCP ingest server: accepts the iPhone sender and pushes frames to the hub.

Runs in a background thread so the FastAPI dashboard stays responsive.
Binds only to a local network interface; no cloud services are contacted.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from typing import Callable, Optional

from .hub import FrameHub, LinkState
from .protocol import FrameDecoder, FrameType, ProtocolError

log = logging.getLogger("receiver.server")

#: Called with each decoded JPEG payload.
FrameCallback = Callable[[bytes], None]


class FrameServer:
    """Accepts one sender at a time and decodes its stream."""

    def __init__(
        self,
        hub: FrameHub,
        host: str = "0.0.0.0",
        port: int = 8765,
        token: str = "",
        auth_timeout: float = 10.0,
        read_timeout: float = 30.0,
        on_frame: Optional[FrameCallback] = None,
    ) -> None:
        self.hub = hub
        self.host = host
        self.port = port
        self.token = token
        self.auth_timeout = auth_timeout
        self.read_timeout = read_timeout
        self.on_frame = on_frame
        self._server: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.bound_port: Optional[int] = None

    # -- lifecycle --------------------------------------------------------
    def start(self) -> None:
        """Bind, listen and serve in a background thread."""
        if self._thread is not None:
            return
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(4)
        srv.settimeout(0.5)
        self._server = srv
        self.bound_port = srv.getsockname()[1]
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._serve, name="frame-server", daemon=True
        )
        self._thread.start()
        log.info("Frame server listening on %s:%s", self.host, self.bound_port)

    def stop(self) -> None:
        self._stop.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, addr = self._server.accept()  # type: ignore[union-attr]
            except socket.timeout:
                continue
            except OSError:
                break
            peer = f"{addr[0]}:{addr[1]}"
            log.info("Sender connected: %s", peer)
            threading.Thread(
                target=self._handle,
                args=(conn, peer),
                name=f"session-{addr[0]}",
                daemon=True,
            ).start()

    # -- session ----------------------------------------------------------
    def _handle(self, conn: socket.socket, peer: str) -> None:
        """Authenticate then stream frames, until the sender goes away.

        Auth and frames are handled in a single read loop because the
        sender may pack AUTH + the first frame into one TCP segment.
        """
        self.hub.set_state(
            LinkState.CONNECTING, f"Handshaking with {peer}...", peer=peer
        )
        decoder = FrameDecoder()
        authenticated = not self.token
        deadline = time.time() + self.auth_timeout
        try:
            conn.settimeout(self.read_timeout)
            while not self._stop.is_set():
                if not authenticated and time.time() > deadline:
                    self.hub.set_state(
                        LinkState.AUTH_FAILED,
                        f"No auth from {peer} within "
                        f"{self.auth_timeout:.0f}s.",
                    )
                    self.hub.note_error("auth", "Authentication timed out.")
                    return
                try:
                    chunk = conn.recv(65536)
                except socket.timeout:
                    # Sender is alive but idle (e.g. static screen).
                    continue
                if not chunk:
                    if authenticated:
                        self.hub.note_disconnect(
                            f"{peer} closed the connection."
                        )
                    else:
                        self.hub.set_state(
                            LinkState.AUTH_FAILED,
                            f"{peer} closed before auth.",
                        )
                        self.hub.note_error(
                            "auth", "Connection closed before auth."
                        )
                    return
                self.hub.note_bytes(len(chunk))
                try:
                    frames = decoder.feed(chunk)
                except ProtocolError as exc:
                    self.hub.note_error("protocol", str(exc))
                    self.hub.note_disconnect(f"Protocol error: {exc}")
                    return
                for frame_type, payload in frames:
                    if not authenticated:
                        ok = self._check_auth(frame_type, payload, peer)
                        if not ok:
                            return
                        authenticated = True
                        deadline = time.time() + self.read_timeout
                        continue
                    if frame_type != FrameType.FRAME:
                        self.hub.note_error(
                            "protocol",
                            f"Unexpected frame type {frame_type} after auth.",
                        )
                        continue
                    self.hub.note_frame_received()
                    if self.on_frame is not None:
                        self.on_frame(payload)
        except (ProtocolError, ConnectionResetError, OSError) as exc:
            self.hub.note_disconnect(f"Connection from {peer} failed: {exc}")
        finally:
            try:
                conn.close()
            except OSError:
                pass
            if self.hub.snapshot()["state"] not in ("auth_failed", "error"):
                self.hub.set_state(
                    LinkState.DISCONNECTED,
                    f"Waiting for reconnect from {peer}.",
                )
            log.info("Sender disconnected: %s", peer)

    def _check_auth(
        self, frame_type: int, payload: bytes, peer: str
    ) -> bool:
        """Validate the AUTH frame. Returns False to abort the session."""
        if frame_type != FrameType.AUTH:
            self.hub.set_state(
                LinkState.AUTH_FAILED, f"{peer} did not send AUTH first."
            )
            self.hub.note_error(
                "auth", "Expected AUTH frame but got another type."
            )
            return False
        if payload.decode("utf-8", "replace") != self.token:
            self.hub.set_state(
                LinkState.AUTH_FAILED, f"Wrong token from {peer}."
            )
            self.hub.note_error("auth", "Invalid shared token.")
            return False
        self.hub.set_state(
            LinkState.CONNECTED, f"Authenticated iPhone at {peer}.", peer=peer
        )
        log.info("Sender authenticated: %s", peer)
        return True

