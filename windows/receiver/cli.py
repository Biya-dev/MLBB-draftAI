"""Command line entry point for the MLBB Draft AI screen receiver.

Usage:
    python -m receiver --host 0.0.0.0 --port 8765 --http-port 8080 --token secret

Everything is local-only: the receiver never contacts an external service.
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys

import uvicorn

from .app import ReceiverApp


def local_ip_addresses() -> list[str]:
    """Best-effort list of this machine's IPv4 addresses."""
    found: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            addr = info[4][0]
            if not addr.startswith("127.") and ":" not in addr:
                found.add(addr)
    except OSError:
        pass
    return sorted(found)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="receiver",
        description="Local-only MLBB Draft AI iPhone screen receiver.",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Ingest bind address (default: 0.0.0.0, all interfaces).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="TCP port the iPhone streams frames to (default: 8765).",
    )
    parser.add_argument(
        "--http-host",
        default="0.0.0.0",
        help="Dashboard bind address (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=8080,
        help="Dashboard HTTP port (default: 8080).",
    )
    parser.add_argument(
        "--token",
        default="",
        help="Shared token the iPhone must send in its AUTH frame. "
        "Use the same value on both devices.",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=1280,
        help="Max frame width after scaling (default: 1280).",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=70,
        help="JPEG quality for the dashboard stream (default: 70).",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Logging verbosity (default: info).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    app = ReceiverApp(
        host=args.host,
        port=args.port,
        token=args.token,
        http_host=args.http_host,
        http_port=args.http_port,
        max_width=args.max_width,
        jpeg_quality=args.jpeg_quality,
    )
    app.start()

    addresses = local_ip_addresses()
    print("=" * 64)
    print(" MLBB Draft AI - Screen Receiver (Phase 1)")
    print("=" * 64)
    print(f" Dashboard : http://127.0.0.1:{args.http_port}/")
    for addr in addresses or ["<no LAN IP found>"]:
        print(f"            http://{addr}:{args.http_port}/")
    print(f" Ingest   : TCP {args.host}:{args.port} (iPhone streams here)")
    print(f" Token    : {'(none - open LAN)' if not args.token else 'set'}")
    print("=" * 64)
    print(" Press Ctrl+C to stop.")
    print()

    try:
        uvicorn.run(app.app, host=args.http_host, port=args.http_port,
                    log_level=args.log_level)
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
        print("\nReceiver stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
