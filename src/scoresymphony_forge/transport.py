from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from scoresymphony_contracts.models import JsonObject


@dataclass(frozen=True, slots=True)
class ForgeHttpResponse:
    """Minimal response surface required by the V1-to-Forge adapter."""

    status: int
    body: JsonObject | None = None


class ForgeHttpTransport(Protocol):
    """Transport boundary for public Forge HTTP operations.

    Implementations own authentication, connection management and wire encoding.
    The command adapter deliberately knows only public HTTP method/path/body
    semantics and never imports Forge database or service internals.
    """

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: JsonObject | None = None,
    ) -> ForgeHttpResponse: ...


class ForgeTransportError(RuntimeError):
    """Raised when no trustworthy Forge HTTP response is available."""


class ForgeDispatchUncertainError(ForgeTransportError):
    """Raised for upstream server failures where dispatch outcome is uncertain."""

    def __init__(self, status: int, body: JsonObject | None = None) -> None:
        self.status = status
        self.body = body
        super().__init__(f"Forge returned HTTP {status}; command outcome is uncertain")


class UrllibForgeHttpTransport:
    """Small authenticated Forge HTTP transport using the Python standard library."""

    def __init__(self, base_url: str, bearer_token: str, *, timeout_seconds: float = 10.0) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must use http or https")
        if not bearer_token:
            raise ValueError("bearer_token must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._base_url = base_url.rstrip("/") + "/"
        self._bearer_token = bearer_token
        self._timeout_seconds = timeout_seconds

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: JsonObject | None = None,
    ) -> ForgeHttpResponse:
        if not path.startswith("/") or path.startswith("//"):
            raise ForgeTransportError("Forge request path must be origin-relative")
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._bearer_token}",
        }
        if json_body is not None:
            data = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            urljoin(self._base_url, path.lstrip("/")),
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return ForgeHttpResponse(response.status, self._decode_body(response.read()))
        except HTTPError as error:
            return ForgeHttpResponse(error.code, self._decode_body(error.read()))
        except (URLError, TimeoutError, OSError) as error:
            raise ForgeTransportError("Forge request failed before a response was received") from error

    @staticmethod
    def _decode_body(raw: bytes) -> JsonObject | None:
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ForgeTransportError("Forge returned an invalid JSON response") from error
        if not isinstance(value, dict):
            raise ForgeTransportError("Forge returned a non-object JSON response")
        return value
