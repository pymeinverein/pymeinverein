"""Low level HTTP helper shared by all API groups.

The transport adds the ``Authorization`` header, decodes JSON and converts the
different ways the API signals errors into exceptions:

* regular error statuses with a JSON ``errorInfo`` body,
* error statuses with an empty body (``401`` and ``404``),
* the web application firewall, which answers ``200 OK`` with an HTML page.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import Any

import aiohttp

from .exceptions import (
    ApiError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    RequestRejectedError,
    ServerError,
    UnexpectedResponseError,
)

type Params = Mapping[str, str | int | float]

_SUPPORT_ID = re.compile(r"support ID is:\s*(\d+)", re.IGNORECASE)
_STATUS_ERRORS: dict[int, type[ApiError]] = {
    400: BadRequestError,
    403: PermissionDeniedError,
    404: NotFoundError,
    422: BadRequestError,
}


def _error_text(msg: Any) -> str:
    """Flatten the ``msg`` of a field error, which is text, a list or an object."""
    if isinstance(msg, dict):
        return _error_text(msg.get("msg", msg))
    if isinstance(msg, list):
        return "/".join(_error_text(item) for item in msg)
    return str(msg)


class Transport:
    """Sends authenticated requests to the MeinVerein API."""

    def __init__(
        self, session_provider: Callable[[], aiohttp.ClientSession], api_url: str
    ) -> None:
        # The session is created lazily because aiohttp sessions must be created
        # while an event loop is running.
        self._session_provider = session_provider
        self.api_url = api_url.rstrip("/")
        self.token: str | None = None

    def url(self, path: str) -> str:
        """Return the absolute URL for an API path such as ``/protected/accounts``."""
        return f"{self.api_url}/{path.lstrip('/')}"

    def _headers(self, accept: str, api_version: str | None = None) -> dict[str, str]:
        if self.token is None:
            raise AuthenticationError("Not logged in: call login() first")
        headers = {"Authorization": f"Bearer {self.token}", "Accept": accept}
        if api_version is not None:
            # Some endpoints exist in several versions that answer with
            # different data; the web application selects one with this header.
            headers["x-api-version"] = api_version
        return headers

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Params | None = None,
        json_body: Any = None,
        form: aiohttp.FormData | None = None,
        api_version: str | None = None,
    ) -> Any:
        """Send a request and return the decoded JSON body.

        Returns ``None`` when the API answers with an empty body.
        ``api_version`` sets the ``x-api-version`` header (``"v2"``, ``"v3"``).
        ``form`` sends a multipart form (file uploads) instead of JSON.
        """
        url = self.url(path)
        async with self._session_provider().request(
            method,
            url,
            params=params,
            json=json_body if form is None else None,
            data=form,
            headers=self._headers("application/json, text/plain, */*", api_version),
        ) as response:
            text = await response.text()
            content_type = response.content_type
            status = response.status

        self._raise_for_error(method, url, status, content_type, text)
        if not text.strip():
            return None
        try:
            return json.loads(text)
        except ValueError as exc:
            raise UnexpectedResponseError(
                f"{method} {url}: expected JSON but got {content_type}: {text[:200]!r}"
            ) from exc

    async def request_bytes(
        self, method: str, path: str, *, params: Params | None = None
    ) -> bytes:
        """Send a request and return the raw body (images, downloads)."""
        url = self.url(path)
        async with self._session_provider().request(
            method, url, params=params, headers=self._headers("*/*")
        ) as response:
            body = await response.read()
            content_type = response.content_type
            status = response.status
        if status >= 400 or content_type == "text/html":
            text = body.decode("utf-8", "replace")
            self._raise_for_error(method, url, status, content_type, text)
        return body

    async def get(
        self,
        path: str,
        *,
        params: Params | None = None,
        api_version: str | None = None,
    ) -> Any:
        return await self.request("GET", path, params=params, api_version=api_version)

    async def post(
        self,
        path: str,
        json_body: Any = None,
        *,
        params: Params | None = None,
        api_version: str | None = None,
    ) -> Any:
        body = {} if json_body is None else json_body
        return await self.request(
            "POST", path, params=params, json_body=body, api_version=api_version
        )

    async def post_form(self, path: str, form: aiohttp.FormData) -> Any:
        """``POST`` a multipart form, used for file uploads."""
        return await self.request("POST", path, form=form)

    async def put(self, path: str, json_body: Any = None) -> Any:
        body = {} if json_body is None else json_body
        return await self.request("PUT", path, json_body=body)

    async def patch(
        self, path: str, json_body: Any = None, *, api_version: str | None = None
    ) -> Any:
        body = {} if json_body is None else json_body
        return await self.request(
            "PATCH", path, json_body=body, api_version=api_version
        )

    async def delete(self, path: str, json_body: Any = None) -> Any:
        return await self.request("DELETE", path, json_body=json_body)

    @staticmethod
    def _raise_for_error(
        method: str, url: str, status: int, content_type: str, text: str
    ) -> None:
        if content_type == "text/html" and "Request Rejected" in text:
            match = _SUPPORT_ID.search(text)
            raise RequestRejectedError(method, url, match.group(1) if match else None)
        if status < 400:
            return
        if status == 401:
            raise AuthenticationError("The API rejected the session token (HTTP 401)")

        name: str | None = None
        message = text.strip()[:500] or "no details"
        errors: list[dict[str, Any]] = []
        try:
            payload = json.loads(text)
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            info = payload.get("errorInfo", payload)
            if isinstance(info, dict):
                # Most errors carry "name"; the document service sends "code".
                for key in ("name", "code"):
                    if isinstance(info.get(key), str):
                        name = info[key]
                        break
                if isinstance(info.get("message"), str):
                    message = info["message"]
                raw_errors = info.get("errors")
                if isinstance(raw_errors, list):
                    errors = [e for e in raw_errors if isinstance(e, dict)]
        if errors:
            details = ", ".join(
                f"{e.get('param', '?')}: {_error_text(e.get('msg', '?'))}"
                for e in errors
            )
            message = f"{message} ({details})"

        error_class = _STATUS_ERRORS.get(
            status, ServerError if status >= 500 else ApiError
        )
        raise error_class(
            status,
            message,
            method=method,
            url=url,
            name=name,
            errors=errors,
            body=text,
        )
