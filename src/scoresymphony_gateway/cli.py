from __future__ import annotations

import os
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer
from wsgiref.simple_server import make_server

from scoresymphony_forge import ForgeIntegrationAdapter, UrllibForgeHttpTransport

from .app import GatewayApplication


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def _read_secret(name: str) -> str:
    file_name = os.environ.get(f"{name}_FILE")
    if file_name:
        try:
            value = Path(file_name).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"{name}_FILE could not be read") from exc
        if not value:
            raise RuntimeError(f"{name}_FILE must not be empty")
        return value

    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} or {name}_FILE is required")
    return value


def build_application() -> GatewayApplication:
    base_url = os.environ.get("FORGE_BASE_URL", "http://127.0.0.1:3000")
    token = _read_secret("FORGE_BEARER_TOKEN")
    client_token = _read_secret("SCORESYMPHONY_GATEWAY_BEARER_TOKEN")
    timeout = float(os.environ.get("SCORESYMPHONY_FORGE_TIMEOUT_SECONDS", "10"))
    page_limit = int(os.environ.get("SCORESYMPHONY_EVENT_PAGE_LIMIT", "100"))
    transport = UrllibForgeHttpTransport(base_url, token, timeout_seconds=timeout)
    return GatewayApplication(
        ForgeIntegrationAdapter(transport, event_page_limit=page_limit),
        client_token,
    )


def main() -> None:
    host = os.environ.get("SCORESYMPHONY_GATEWAY_HOST", "127.0.0.1")
    port = int(os.environ.get("SCORESYMPHONY_GATEWAY_PORT", "8080"))
    application = build_application()
    with make_server(host, port, application, server_class=ThreadingWSGIServer) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
