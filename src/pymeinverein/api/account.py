"""Account level calls: who is logged in and which clubs can they access."""

from __future__ import annotations

from .._transport import Transport
from ..exceptions import UnexpectedResponseError
from ..models.account import Account, Profile
from ._util import unwrap


class AccountAPI:
    """Calls that are not tied to one club."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def get(self) -> Account:
        """Return the logged-in user together with all their clubs.

        ``GET /protected/accounts``
        """
        payload = await self._transport.get("/protected/accounts")
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            raise UnexpectedResponseError("GET /protected/accounts: missing 'data'")
        return Account.model_validate(payload["data"])

    async def profile(self) -> Profile:
        """Return the logged-in user's name and e-mail address.

        ``GET /protected/accounts/profile``
        """
        path = "/protected/accounts/profile"
        payload = await self._transport.get(path)
        return Profile.model_validate(unwrap(payload, "data", f"GET {path}"))

    async def keepalive(self) -> bool:
        """Tell the server the session is still in use.

        The web application calls this every few minutes.
        ``GET /protected/auth/buhlkonto/keepalive``
        """
        payload = await self._transport.get("/protected/auth/buhlkonto/keepalive")
        return isinstance(payload, dict) and payload.get("ok") is True

    async def logout(self) -> None:
        """Tell the server that the user logged out.

        Observed behaviour: the server answers ``{}`` but does **not** revoke the
        token - it keeps working. Keep tokens secret even after logging out.
        ``GET /protected/mv365/accounts/logout``
        """
        await self._transport.get("/protected/mv365/accounts/logout")
