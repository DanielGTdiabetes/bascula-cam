"""Servidor HTTP sencillo para simular Nightscout en pruebas locales."""

from __future__ import annotations

import argparse
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Tuple


log = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mock Nightscout para pruebas")
    parser.add_argument("--host", default="127.0.0.1", help="Dirección de escucha")
    parser.add_argument("--port", type=int, default=5000, help="Puerto del servidor")
    parser.add_argument("--sgv", type=float, default=100.0, help="Valor fijo de glucosa (mg/dL)")
    parser.add_argument(
        "--trend",
        type=str,
        default="Flat",
        help="Texto opcional para trend",
    )
    return parser.parse_args()


def _build_payload(sgv: float, trend: str) -> Tuple[int, dict]:
    entry = {
        "sgv": int(sgv),
        "direction": trend,
    }
    return 200, [entry]


def run_server(host: str, port: int, sgv: float, trend: str) -> None:
    payload = json.dumps(_build_payload(sgv, trend)[1]).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # type: ignore[override]
            if self.path.startswith("/api/v1/entries"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format: str, *args):  # type: ignore[override]
            log.debug("%s - - %s", self.address_string(), format % args)

    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), Handler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info("Nightscout mock escuchando en http://%s:%s con SGV=%s", host, port, sgv)
    try:
        thread.join()
    except KeyboardInterrupt:
        log.info("Mock Nightscout detenido por el usuario")
    finally:
        server.shutdown()
        server.server_close()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(level=logging.INFO)
    run_server(args.host, args.port, args.sgv, args.trend)


if __name__ == "__main__":
    main()

