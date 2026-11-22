"""Exceptions raised by pymeinverein.

Every error the library raises on purpose derives from :class:`MeinVereinError`,
so ``except MeinVereinError`` catches everything API related.
"""

from __future__ import annotations

from typing import Any


class MeinVereinError(Exception):
    """Base class of all pymeinverein errors."""


class AuthenticationError(MeinVereinError):
    """Login failed or the session token is missing, invalid or expired."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        #: Machine readable code reported by the Buhl login (if any).
        self.code = code


class TwoFactorRequiredError(AuthenticationError):
    """The account uses two-factor authentication and no code was supplied."""


class LoginThrottledError(AuthenticationError):
    """Too many wrong passwords; the login is blocked for ``wait_seconds``."""

    def __init__(
        self, message: str, *, wait_seconds: float, code: str | None = None
    ) -> None:
        super().__init__(message, code=code)
        self.wait_seconds = wait_seconds


class ApiError(MeinVereinError):
    """The API answered with an error status.

    ``status`` is the HTTP status, ``name`` the error name reported by the API
    (for example ``BadRequestError``) and ``errors`` the list of field errors.
    """

    def __init__(
        self,
        status: int,
        message: str,
        *,
        method: str = "",
        url: str = "",
        name: str | None = None,
        errors: list[dict[str, Any]] | None = None,
        body: str | None = None,
    ) -> None:
        location = f"{method} {url}: " if method and url else ""
        super().__init__(f"{location}HTTP {status}: {message}")
        self.status = status
        self.message = message
        self.method = method
        self.url = url
        self.name = name
        self.errors = errors or []
        self.body = body


class BadRequestError(ApiError):
    """HTTP 400/422: the API rejected the request data."""


class PermissionDeniedError(ApiError):
    """HTTP 403: the logged-in user may not perform this action."""


class NotFoundError(ApiError):
    """HTTP 404: the object (or the endpoint) does not exist."""


class ServerError(ApiError):
    """HTTP 5xx: the API failed to process the request."""


class RequestRejectedError(MeinVereinError):
    """The service answered with its "Request Rejected" page.

    The page comes from the firewall in front of the API, with status ``200``.
    It appears for requests the firewall blocks and, as far as can be told from
    the outside, also when the server fails on a request (for example because a
    required field is missing). ``support_id`` is the id shown on the page.
    """

    def __init__(self, method: str, url: str, support_id: str | None = None) -> None:
        suffix = f" (support id {support_id})" if support_id else ""
        super().__init__(f"{method} {url}: request rejected by the firewall{suffix}")
        self.method = method
        self.url = url
        self.support_id = support_id


class UnexpectedResponseError(MeinVereinError):
    """The API answered with something this library does not understand."""


class LookupFailedError(MeinVereinError):
    """A lookup by name matched no object or more than one object."""


class NoAccountError(MeinVereinError):
    """The member has no MeinVerein user account, which the action requires.

    Roles, for example, can only be given to members who were invited and have
    accepted the invitation.
    """
