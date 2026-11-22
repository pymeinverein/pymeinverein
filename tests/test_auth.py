"""Login flow, token handling and logout against the mock server."""

from __future__ import annotations

import pytest

from pymeinverein import (
    AuthenticationError,
    LoginThrottledError,
    MeinVereinClient,
    TwoFactorRequiredError,
    UnexpectedResponseError,
)
from pymeinverein.auth import parse_redirect_form
from pymeinverein.testing import DEMO_EMAIL, DEMO_PASSWORD, MockServer


async def test_login_stores_token(server: MockServer) -> None:
    async with MeinVereinClient(
        DEMO_EMAIL, DEMO_PASSWORD, **server.client_kwargs()
    ) as mv:
        assert mv.is_logged_in
        assert mv.token in server.state.tokens
        # The one-time ticket must have been used up.
        assert server.state.tickets == {}


async def test_wrong_password(server: MockServer) -> None:
    mv = MeinVereinClient(DEMO_EMAIL, "wrong", **server.client_kwargs())
    with pytest.raises(AuthenticationError) as excinfo:
        await mv.login()
    assert excinfo.value.code == "invalid-user-credential"
    assert not mv.is_logged_in
    await mv.close()


async def test_context_manager_closes_session_on_failed_login(
    server: MockServer,
) -> None:
    with pytest.raises(AuthenticationError):
        async with MeinVereinClient(DEMO_EMAIL, "wrong", **server.client_kwargs()):
            pytest.fail("the body must not run")


async def test_missing_credentials(
    server: MockServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MEINVEREIN_TOKEN", raising=False)
    monkeypatch.delenv("MEINVEREIN_EMAIL", raising=False)
    monkeypatch.delenv("MEINVEREIN_PASSWORD", raising=False)
    mv = MeinVereinClient(**server.client_kwargs())
    with pytest.raises(AuthenticationError, match="No credentials"):
        await mv.login()


async def test_credentials_from_environment(
    server: MockServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MEINVEREIN_TOKEN", raising=False)
    monkeypatch.setenv("MEINVEREIN_EMAIL", DEMO_EMAIL)
    monkeypatch.setenv("MEINVEREIN_PASSWORD", DEMO_PASSWORD)
    async with MeinVereinClient(**server.client_kwargs()) as mv:
        assert (await mv.account.get()).user.email == DEMO_EMAIL


async def test_throttled_login(server: MockServer) -> None:
    server.state.users[DEMO_EMAIL].locked_ms = 30_000
    mv = MeinVereinClient(DEMO_EMAIL, DEMO_PASSWORD, **server.client_kwargs())
    with pytest.raises(LoginThrottledError) as excinfo:
        await mv.login()
    assert excinfo.value.wait_seconds == 30
    await mv.close()


async def test_two_factor_required(server: MockServer) -> None:
    server.state.users[DEMO_EMAIL].two_factor_code = "123456"
    mv = MeinVereinClient(DEMO_EMAIL, DEMO_PASSWORD, **server.client_kwargs())
    with pytest.raises(TwoFactorRequiredError):
        await mv.login()
    await mv.close()


async def test_two_factor_with_code(server: MockServer) -> None:
    server.state.users[DEMO_EMAIL].two_factor_code = "123456"
    async with MeinVereinClient(
        DEMO_EMAIL, DEMO_PASSWORD, two_factor="123456", **server.client_kwargs()
    ) as mv:
        assert mv.is_logged_in


async def test_two_factor_with_async_callable(server: MockServer) -> None:
    server.state.users[DEMO_EMAIL].two_factor_code = "654321"

    async def ask() -> str:
        return "654321"

    async with MeinVereinClient(
        DEMO_EMAIL, DEMO_PASSWORD, two_factor=ask, **server.client_kwargs()
    ) as mv:
        assert mv.is_logged_in


async def test_two_factor_wrong_code(server: MockServer) -> None:
    server.state.users[DEMO_EMAIL].two_factor_code = "123456"
    mv = MeinVereinClient(
        DEMO_EMAIL, DEMO_PASSWORD, two_factor=lambda: "000000", **server.client_kwargs()
    )
    with pytest.raises(AuthenticationError):
        await mv.login()
    await mv.close()


async def test_ticket_is_only_sent_to_the_api_host(server: MockServer) -> None:
    # The login form points at the mock; a client configured for another API
    # host must refuse to post the ticket there.
    mv = MeinVereinClient(
        DEMO_EMAIL,
        DEMO_PASSWORD,
        api_url="http://api.invalid",
        login_url=server.login_url,
    )
    with pytest.raises(UnexpectedResponseError, match="unexpected host"):
        await mv.login()
    await mv.close()
    assert server.state.tokens == {}


async def test_token_can_be_reused(
    server: MockServer, client: MeinVereinClient
) -> None:
    assert client.token is not None
    async with MeinVereinClient(token=client.token, **server.client_kwargs()) as other:
        assert (await other.account.get()).user.email == DEMO_EMAIL


async def test_token_skips_the_login(server: MockServer) -> None:
    token = server.state.issue_token(DEMO_EMAIL)
    async with MeinVereinClient(token=token, **server.client_kwargs()) as mv:
        assert mv.token == token
        assert (await mv.account.get()).user.email == DEMO_EMAIL
    # No credentials were needed and the login page was never contacted.
    assert server.state.tickets == {}
    assert ("POST", "/auth/buhlkonto/token") not in server.state.requests


async def test_token_wins_over_credentials(server: MockServer) -> None:
    token = server.state.issue_token(DEMO_EMAIL)
    async with MeinVereinClient(
        DEMO_EMAIL, "wrong password", token=token, **server.client_kwargs()
    ) as mv:
        assert mv.token == token


@pytest.mark.parametrize("prefix", ["", "Bearer ", "bearer ", "  Bearer  "])
async def test_token_as_copied_from_the_browser(
    server: MockServer, prefix: str
) -> None:
    token = server.state.issue_token(DEMO_EMAIL)
    async with MeinVereinClient(
        token=f"{prefix}{token}\n", **server.client_kwargs()
    ) as mv:
        assert mv.token == token
        assert await mv.account.keepalive()


async def test_token_from_environment(
    server: MockServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = server.state.issue_token(DEMO_EMAIL)
    monkeypatch.setenv("MEINVEREIN_TOKEN", f"Bearer {token}")
    monkeypatch.delenv("MEINVEREIN_EMAIL", raising=False)
    monkeypatch.delenv("MEINVEREIN_PASSWORD", raising=False)
    async with MeinVereinClient(**server.client_kwargs()) as mv:
        assert mv.token == token
        assert (await mv.account.get()).user.email == DEMO_EMAIL


async def test_explicit_token_beats_environment(
    server: MockServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEINVEREIN_TOKEN", "from-environment")
    token = server.state.issue_token(DEMO_EMAIL)
    async with MeinVereinClient(token=token, **server.client_kwargs()) as mv:
        assert mv.token == token


async def test_empty_token_means_login(
    server: MockServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEINVEREIN_TOKEN", "  ")
    async with MeinVereinClient(
        DEMO_EMAIL, DEMO_PASSWORD, **server.client_kwargs()
    ) as mv:
        assert mv.token in server.state.tokens


async def test_logout_forgets_token_locally(
    server: MockServer, client: MeinVereinClient
) -> None:
    token = client.token
    await client.logout()
    assert client.token is None
    assert ("GET", "/protected/mv365/accounts/logout") in server.state.requests
    with pytest.raises(AuthenticationError, match="Not logged in"):
        await client.account.get()
    # Like the real API, the mock does not revoke the token on logout.
    assert token in server.state.tokens


async def test_invalid_token_raises(server: MockServer) -> None:
    async with MeinVereinClient(token="nonsense", **server.client_kwargs()) as mv:
        with pytest.raises(AuthenticationError, match="401"):
            await mv.account.get()


def test_parse_redirect_form() -> None:
    action, fields = parse_redirect_form(
        '<form action="https://api.example/auth?a=1&amp;b=2" method="post">'
        '<input type="hidden" value="T+/=" name="BuhlTicket" /></form>'
    )
    assert action == "https://api.example/auth?a=1&b=2"
    assert fields == {"BuhlTicket": "T+/="}


def test_parse_redirect_form_without_ticket() -> None:
    with pytest.raises(UnexpectedResponseError):
        parse_redirect_form("<form action='x'></form>")
