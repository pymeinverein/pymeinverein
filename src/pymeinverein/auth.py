"""Login to MeinVerein through the Buhl account ("buhl:Konto") single sign-on.

MeinVerein has no login of its own. The web application sends the browser to the
Buhl account page; after a successful login that page posts a one-time
``BuhlTicket`` to the MeinVerein API, which answers with a redirect that carries
the session token (a JWT). This module replays those steps:

1. ``GET  {login_url}/?buhlparam=1050105`` - opens a session (cookies).
2. ``POST {login_url}/wp-json/api/v1/login`` - sends e-mail and password and
   returns JSON. On success the ``redirection`` field holds an HTML form that
   targets ``{api_url}/auth/buhlkonto/token`` and contains the ``BuhlTicket``.
3. ``POST {api_url}/auth/buhlkonto/token?...`` - answers ``302`` with
   ``Location: https://web.meinverein.de/login?token=<JWT>``.

The token is then sent as ``Authorization: Bearer <JWT>`` with every API call.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlsplit

import aiohttp

from .exceptions import (
    AuthenticationError,
    LoginThrottledError,
    TwoFactorRequiredError,
    UnexpectedResponseError,
)

DEFAULT_API_URL = "https://api.meinverein.de"
DEFAULT_LOGIN_URL = "https://www.buhl.de/mein-buhlkonto"

#: Tells the Buhl account page that the login is for "MeinVerein Web".
BUHL_PARAM = "1050105"

#: A fixed code, or a (sync or async) callable that returns the current code.
type TwoFactorProvider = str | Callable[[], str | Awaitable[str]]

_THROTTLE_CODES = {"wrong-password-wait", "wrong-twofactor-token-wait"}


class _FormParser(HTMLParser):
    """Extracts the action and the input fields of the first form in a snippet."""

    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "form" and self.action is None:
            self.action = values.get("action")
        elif tag == "input" and "name" in values:
            self.fields[values["name"]] = values.get("value", "")


def parse_redirect_form(html: str) -> tuple[str, dict[str, str]]:
    """Return ``(action_url, fields)`` of the form the Buhl login responds with."""
    parser = _FormParser()
    parser.feed(html)
    parser.close()
    if not parser.action or "BuhlTicket" not in parser.fields:
        raise UnexpectedResponseError(
            "The Buhl login succeeded but did not return a ticket form"
        )
    return parser.action, parser.fields


def _origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme, parts.netloc


async def _resolve_two_factor(provider: TwoFactorProvider) -> str:
    if isinstance(provider, str):
        return provider
    result = provider()
    if isinstance(result, str):
        return result
    return await result


async def _post_login(
    session: aiohttp.ClientSession,
    login_url: str,
    fields: dict[str, str],
) -> dict[str, Any]:
    page_url = f"{login_url}/?buhlparam={BUHL_PARAM}"
    origin = "://".join(_origin(login_url))
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Origin": origin,
        "Referer": page_url,
        "X-Requested-With": "XMLHttpRequest",
    }
    async with session.post(
        f"{login_url}/wp-json/api/v1/login", data=fields, headers=headers
    ) as response:
        text = await response.text()
        status = response.status
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise UnexpectedResponseError(
            f"The Buhl login answered HTTP {status} without JSON: {text[:200]!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise UnexpectedResponseError("The Buhl login answered with unexpected JSON")
    return payload


async def login(
    session: aiohttp.ClientSession,
    email: str,
    password: str,
    *,
    api_url: str = DEFAULT_API_URL,
    login_url: str = DEFAULT_LOGIN_URL,
    two_factor: TwoFactorProvider | None = None,
) -> str:
    """Log in with a Buhl account and return the MeinVerein session token.

    Raises :class:`~pymeinverein.exceptions.AuthenticationError` (or one of its
    subclasses) when the credentials are wrong, the login is throttled or a
    two-factor code is needed but ``two_factor`` was not given.
    """
    api_url = api_url.rstrip("/")
    login_url = login_url.rstrip("/")

    # Step 1: open a session on the login page (sets the cookies the POST needs).
    async with session.get(f"{login_url}/", params={"buhlparam": BUHL_PARAM}) as page:
        await page.read()

    # Step 2: send the credentials.
    fields = {
        "action": "LoginUser",
        "post_type": "POST",
        "eml-user": email.strip(),
        "psw-user": password,
        "passed-get-param": "",
        "passed-ls-param": "",
        "rdr-buhlparam": BUHL_PARAM,
    }
    payload = await _post_login(session, login_url, fields)

    if payload.get("code") == "twofactorauthentication-failed":
        if two_factor is None:
            raise TwoFactorRequiredError(
                "This account requires a two-factor code; pass two_factor=...",
                code="twofactorauthentication-failed",
            )
        fields["BuhlTicket"] = str(payload.get("InvalidTicket", ""))
        fields["TwoFactorToken"] = await _resolve_two_factor(two_factor)
        payload = await _post_login(session, login_url, fields)

    if payload.get("success") is not True:
        code = payload.get("code")
        code = code if isinstance(code, str) else None
        message = str(payload.get("message") or code or "Login failed")
        if code in _THROTTLE_CODES:
            try:
                wait_seconds = float(payload.get("waitTime", 0)) / 1000
            except TypeError, ValueError:
                wait_seconds = 0.0
            raise LoginThrottledError(message, wait_seconds=wait_seconds, code=code)
        raise AuthenticationError(message, code=code)

    redirection = payload.get("redirection")
    if not isinstance(redirection, str):
        raise UnexpectedResponseError(
            "The Buhl login succeeded but returned no redirect form"
        )
    action, form_fields = parse_redirect_form(redirection)

    # The ticket is a credential: only ever send it to the configured API host.
    if _origin(action) != _origin(api_url):
        raise UnexpectedResponseError(
            f"Refusing to send the login ticket to unexpected host {action!r}"
        )

    # Step 3: exchange the ticket for the session token.
    async with session.post(
        action,
        data=form_fields,
        headers={"Origin": "://".join(_origin(login_url)), "Referer": login_url + "/"},
        allow_redirects=False,
    ) as response:
        await response.read()
        location = response.headers.get("Location", "")
        status = response.status

    tokens = parse_qs(urlsplit(location).query).get("token")
    if status not in (301, 302, 303, 307, 308) or not tokens:
        raise AuthenticationError(
            "MeinVerein did not accept the login ticket "
            f"(HTTP {status}, redirect to {urlsplit(location).path or 'nowhere'})"
        )
    return tokens[0]
