"""Answers in the formats of the real API."""

from __future__ import annotations

from typing import Any

from aiohttp import web


def api_error(
    status: int, name: str, errors: list[dict[str, Any]] | None = None
) -> web.Response:
    """Build an error answer with the ``errorInfo`` envelope."""
    return web.json_response(
        {
            "errorInfo": {
                "errors": errors or [],
                "name": name,
                "message": name,
                "statusCode": status,
            }
        },
        status=status,
    )


def bad_request(
    param: str, msg: Any = "INVALID", value: Any = "INVALID"
) -> web.Response:
    return api_error(
        400, "BadRequestError", [{"param": param, "msg": msg, "value": value}]
    )


def not_found() -> web.Response:
    """The real API answers unknown ids and paths with an empty ``404``."""
    return web.Response(status=404)


def data(payload: Any, meta: dict[str, Any] | None = None) -> web.Response:
    """The ``{"meta": ..., "data": ...}`` envelope of the newer endpoints."""
    return web.json_response({"meta": meta or {}, "data": payload})


_REJECTED_PAGE = (
    "<html><head><title>Request Rejected</title></head><body>The requested URL "
    "was rejected. Please consult with your administrator.<br><br>Your support "
    "ID is: 1234567890123456789<br><br><a href='javascript:history.back();'>"
    "[Go Back]</a></body></html>"
)


def rejected() -> web.Response:
    """The page the real service sends (with status 200) when it refuses or
    fails on a request."""
    return web.Response(text=_REJECTED_PAGE, content_type="text/html")
