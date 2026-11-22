"""The entry point of the library: :class:`MeinVereinClient`."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version
from types import TracebackType
from typing import Self

import aiohttp

from . import auth
from ._transport import Transport
from .api.account import AccountAPI
from .api.clubs import ClubsAPI
from .exceptions import AuthenticationError

ENV_EMAIL = "MEINVEREIN_EMAIL"
ENV_PASSWORD = "MEINVEREIN_PASSWORD"
ENV_TOKEN = "MEINVEREIN_TOKEN"


def _clean_token(token: str | None) -> str | None:
    """Accept a token as copied from a browser: strip blanks and ``Bearer``."""
    if token is None:
        return None
    token = token.strip()
    if token[:7].lower() == "bearer ":
        token = token[7:].strip()
    return token or None


def _user_agent() -> str:
    try:
        return f"pymeinverein/{version('pymeinverein')}"
    except PackageNotFoundError:
        return "pymeinverein"


class MeinVereinClient:
    """Async client for the WISO MeinVerein Web API.

    Use it as an async context manager; entering logs in, leaving closes the
    HTTP session::

        async with MeinVereinClient("me@example.org", "secret") as mv:
            club = await mv.clubs.get(name="My Club")

    ``email`` and ``password`` default to the environment variables
    ``MEINVEREIN_EMAIL`` and ``MEINVEREIN_PASSWORD``.

    To skip the login, pass a session ``token`` instead (or set
    ``MEINVEREIN_TOKEN``): from :attr:`token` after an earlier login, or the
    ``Authorization`` header of the web application - a leading ``Bearer`` is
    removed. A token always wins over credentials; they are not needed then::

        async with MeinVereinClient(token=saved_token) as mv:
            ...

    ``api_url`` and ``login_url`` only need to be changed to talk to the mock
    server from :mod:`pymeinverein.testing`.
    """

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        *,
        token: str | None = None,
        two_factor: auth.TwoFactorProvider | None = None,
        api_url: str = auth.DEFAULT_API_URL,
        login_url: str = auth.DEFAULT_LOGIN_URL,
        session: aiohttp.ClientSession | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._email = email if email is not None else os.environ.get(ENV_EMAIL)
        self._password = (
            password if password is not None else os.environ.get(ENV_PASSWORD)
        )
        self._two_factor = two_factor
        self._login_url = login_url
        self._timeout = timeout
        self._owns_session = session is None
        self._session = session
        self._transport = Transport(self._get_session, api_url)
        self._transport.token = _clean_token(
            token if token is not None else os.environ.get(ENV_TOKEN)
        )

        #: Calls about the logged-in user.
        self.account = AccountAPI(self._transport)
        #: The clubs of the logged-in user.
        self.clubs = ClubsAPI(self._transport, self.account)

    def _get_session(self) -> aiohttp.ClientSession:
        # Created on first use: aiohttp sessions need a running event loop.
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": _user_agent()},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            )
        return self._session

    @property
    def token(self) -> str | None:
        """The session token, ``None`` before :meth:`login`.

        Treat it like a password: it grants full access to the account.
        """
        return self._transport.token

    @property
    def is_logged_in(self) -> bool:
        return self._transport.token is not None

    async def login(self) -> None:
        """Log in with the configured credentials and store the session token.

        Not needed when a token was given; entering the client calls it only
        if there is no token yet.
        """
        if not self._email or not self._password:
            raise AuthenticationError(
                "No credentials: pass email and password or set "
                f"{ENV_EMAIL} and {ENV_PASSWORD}"
            )
        self._transport.token = await auth.login(
            self._get_session(),
            self._email,
            self._password,
            api_url=self._transport.api_url,
            login_url=self._login_url,
            two_factor=self._two_factor,
        )

    async def logout(self) -> None:
        """Notify the server of the logout and forget the token locally.

        The server does not revoke the token (see ``AccountAPI.logout``).
        """
        if self._transport.token is None:
            return
        try:
            await self.account.logout()
        finally:
            self._transport.token = None

    async def close(self) -> None:
        """Close the HTTP session (unless it was passed in by the caller)."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> Self:
        try:
            if not self.is_logged_in:
                await self.login()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
