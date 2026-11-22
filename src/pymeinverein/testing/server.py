"""A mock of the MeinVerein API (and of the Buhl login) built on ``aiohttp.web``.

The mock keeps its data in memory (:class:`~pymeinverein.testing.state.MockState`)
and answers with the same status codes, body shapes and quirks that were
observed on the real service, so the client can be tested without network
access or credentials::

    async with MockServer() as server:
        async with MeinVereinClient(DEMO_EMAIL, DEMO_PASSWORD, **server.client_kwargs()) as mv:
            ...

One server plays both hosts: paths below ``/mein-buhlkonto`` imitate
``www.buhl.de``, everything else imitates ``api.meinverein.de``.
"""

from __future__ import annotations

import html
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Self, TypedDict
from urllib.parse import quote

from aiohttp import web

from ._responses import not_found, rejected
from .routes import ClubRoutes
from .state import Json, MockState, MockUser

type Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

LOGIN_PREFIX = "/mein-buhlkonto"


class ClientKwargs(TypedDict):
    """The ``MeinVereinClient`` arguments that select the server to talk to."""

    api_url: str
    login_url: str


class MockServer:
    """Runs the mock on a local port.

    ``port=0`` (the default) picks a free port; read :attr:`url` after
    :meth:`start`. The server is an async context manager.
    """

    def __init__(
        self,
        state: MockState | None = None,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        self.state = state if state is not None else MockState.demo()
        self._host = host
        self._port = port
        self._runner: web.AppRunner | None = None
        self.app = self._build_app()

    # ------------------------------------------------------------------ lifecycle

    @property
    def url(self) -> str:
        """Base URL of the running server, e.g. ``http://127.0.0.1:43211``."""
        if self._runner is None:
            raise RuntimeError("The mock server is not running")
        return f"http://{self._host}:{self._port}"

    @property
    def api_url(self) -> str:
        return self.url

    @property
    def login_url(self) -> str:
        return self.url + LOGIN_PREFIX

    def client_kwargs(self) -> ClientKwargs:
        """Keyword arguments that point a ``MeinVereinClient`` at this server."""
        return {"api_url": self.api_url, "login_url": self.login_url}

    async def start(self) -> None:
        if self._runner is not None:
            return
        runner = web.AppRunner(self.app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, self._host, self._port)
        await site.start()
        if self._port == 0:
            self._port = int(runner.addresses[0][1])
        self._runner = runner

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.stop()

    # ---------------------------------------------------------------------- setup

    def _build_app(self) -> web.Application:
        app = web.Application(middlewares=[self._middleware])
        router = app.router

        # www.buhl.de
        router.add_get(LOGIN_PREFIX + "/", self._login_page)
        router.add_post(LOGIN_PREFIX + "/wp-json/api/v1/login", self._buhl_login)

        # api.meinverein.de - session
        router.add_post("/auth/buhlkonto/token", self._token)
        router.add_get("/protected/accounts", self._accounts)
        router.add_get("/protected/auth/buhlkonto/keepalive", self._keepalive)
        router.add_get("/protected/accounts/profile", self._profile)
        router.add_get("/protected/mv365/accounts/logout", self._logout)
        router.add_post("/protected/mv365/clubs/{club_id}/selected", self._select_club)

        ClubRoutes(self.state).register(router)
        return app

    @web.middleware
    async def _middleware(
        self, request: web.Request, handler: Handler
    ) -> web.StreamResponse:
        path = request.path
        if not path.startswith(LOGIN_PREFIX):
            self.state.requests.append((request.method, path))
            self.state.api_versions.append(request.headers.get("x-api-version"))
        if path in self.state.rejected_paths:
            # The firewall answers 200 with an HTML page, like the real one.
            return rejected()
        if path.startswith("/protected/"):
            if self._user(request) is None:
                return web.Response(status=401)
        return await handler(request)

    # -------------------------------------------------------------------- helpers

    def _user(self, request: web.Request) -> MockUser | None:
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme != "Bearer":
            return None
        email = self.state.tokens.get(token)
        return self.state.users.get(email) if email else None

    def _club(self, request: web.Request) -> Json | None:
        """Return the club named in the path if the caller may access it."""
        try:
            club_id = int(request.match_info["club_id"])
        except ValueError:
            return None
        return self.state.clubs.get(club_id)

    # ------------------------------------------------------------------ Buhl login

    async def _login_page(self, request: web.Request) -> web.Response:
        return web.Response(
            text="<html><body><form id='form-login'></form></body></html>",
            content_type="text/html",
        )

    async def _buhl_login(self, request: web.Request) -> web.Response:
        form = await request.post()
        email = str(form.get("eml-user", ""))
        password = str(form.get("psw-user", ""))
        if form.get("action") != "LoginUser":
            return web.json_response({"success": False, "code": "invalid-action"})

        user = self.state.users.get(email)
        if user is not None and user.locked_ms > 0:
            return web.json_response(
                {
                    "success": False,
                    "code": "wrong-password-wait",
                    "message": "Zu viele Fehlversuche. Bitte warten.",
                    "waitTime": user.locked_ms,
                }
            )
        if user is None or user.password != password:
            return web.json_response(
                {
                    "success": False,
                    "successPassword": False,
                    "skipMuleTester": False,
                    "code": "invalid-user-credential",
                    "message": "E-Mail-Adresse oder Passwort ist nicht korrekt.",
                }
            )

        if user.two_factor_code is not None:
            ticket = str(form.get("BuhlTicket", ""))
            code = str(form.get("TwoFactorToken", ""))
            pending = self.state.two_factor_tickets.get(ticket)
            if pending != email or code != user.two_factor_code:
                invalid_ticket = self.state.issue_ticket(email)
                self.state.tickets.pop(invalid_ticket)
                self.state.two_factor_tickets[invalid_ticket] = email
                return web.json_response(
                    {
                        "success": False,
                        "code": "twofactorauthentication-failed",
                        "message": "Bitte Sicherheitscode eingeben.",
                        "InvalidTicket": invalid_ticket,
                    }
                )
            self.state.two_factor_tickets.pop(ticket, None)

        ticket = self.state.issue_ticket(email)
        action = (
            f"{request.scheme}://{request.host}/auth/buhlkonto/token"
            f"?eml={quote('bW9jaw==')}&eml_extra=0123456789abcdef"
        )
        redirection = (
            f'<form action="{html.escape(action)}" method="post" id="postRedirectForm">'
            f'<input type="hidden" value="{html.escape(ticket)}" name="BuhlTicket" />'
            "</form>"
        )
        return web.json_response(
            {
                "success": True,
                "successPassword": True,
                "skipMuleTester": False,
                "code": "ok",
                "hashMail": "0" * 64,
                "redirection": redirection,
            }
        )

    async def _token(self, request: web.Request) -> web.Response:
        form = await request.post()
        email = self.state.tickets.pop(str(form.get("BuhlTicket", "")), None)
        if email is None:
            raise web.HTTPFound("https://web.meinverein.de/error")
        token = self.state.issue_token(email)
        raise web.HTTPFound(
            f"https://web.meinverein.de/login?token={quote(token)}&isAdClient=false"
        )

    # --------------------------------------------------------------------- session

    async def _accounts(self, request: web.Request) -> web.Response:
        user = self._user(request)
        assert user is not None
        return web.json_response(
            {
                "rooms": [],
                "data": {
                    "user": user.to_api(),
                    "clubs": list(self.state.clubs.values()),
                    "clubSettings": [],
                    "clubStorages": [],
                    "selectedClubId": self.state.selected_club_id,
                    "clubRoles": [],
                    "clubUsers": [],
                },
                "authToken": request.headers["Authorization"].partition(" ")[2],
            }
        )

    async def _profile(self, request: web.Request) -> web.Response:
        user = self._user(request)
        assert user is not None
        return web.json_response(
            {
                "data": {
                    "id": user.id,
                    "email": user.email,
                    "firstName": user.first_name,
                    "lastName": user.last_name,
                    "allowRemoteMaintenance": None,
                    "ocrAutoFillSettings": {},
                }
            }
        )

    async def _keepalive(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def _logout(self, request: web.Request) -> web.Response:
        # Observed on the real API: logout answers "{}" and the token keeps
        # working afterwards (it is a stateless JWT without expiry).
        return web.json_response({})

    async def _select_club(self, request: web.Request) -> web.Response:
        club = self._club(request)
        if club is None:
            return not_found()
        self.state.selected_club_id = club["id"]
        # The real API answers 200 with an empty body here.
        return web.Response(status=200)
