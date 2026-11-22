"""Account, clubs and transport error handling against the mock server."""

from __future__ import annotations

import pytest

from pymeinverein import (
    LookupFailedError,
    MeinVereinClient,
    NotFoundError,
    RequestRejectedError,
)
from pymeinverein.testing import DEMO_CLUB_ID, DEMO_EMAIL, REGULAR_CLUB_ID, MockServer


async def test_account(client: MeinVereinClient) -> None:
    account = await client.account.get()
    assert account.user.email == DEMO_EMAIL
    assert account.user.first_name == "Demo"
    assert {club.id for club in account.clubs} == {REGULAR_CLUB_ID, DEMO_CLUB_ID}
    assert account.selected_club_id == DEMO_CLUB_ID


async def test_keepalive(client: MeinVereinClient) -> None:
    assert await client.account.keepalive() is True


async def test_list_clubs(client: MeinVereinClient) -> None:
    clubs = await client.clubs.list()
    assert [club.name for club in clubs] == ["Musterverein e.V.", "Demoverein"]
    assert [club.is_demo for club in clubs] == [False, True]


async def test_get_club_by_id_name_and_default(client: MeinVereinClient) -> None:
    assert (await client.clubs.get(REGULAR_CLUB_ID)).name == "Musterverein e.V."
    by_name = await client.clubs.get(name="Demoverein")
    assert by_name.id == DEMO_CLUB_ID and by_name.is_demo
    # Without arguments the club selected in the web application is used.
    assert (await client.clubs.get()).id == DEMO_CLUB_ID


async def test_get_unknown_club(client: MeinVereinClient) -> None:
    with pytest.raises(LookupFailedError, match="Musterverein"):
        await client.clubs.get(name="does not exist")


async def test_select_club(server: MockServer, client: MeinVereinClient) -> None:
    club = await client.clubs.get(REGULAR_CLUB_ID)
    await club.select()
    assert server.state.selected_club_id == REGULAR_CLUB_ID
    assert (await client.clubs.get()).id == REGULAR_CLUB_ID


async def test_firewall_rejection_is_an_error(
    server: MockServer, client: MeinVereinClient
) -> None:
    server.state.rejected_paths.add("/protected/accounts")
    with pytest.raises(RequestRejectedError) as excinfo:
        await client.account.get()
    assert excinfo.value.support_id == "1234567890123456789"


async def test_unknown_endpoint_is_not_found(client: MeinVereinClient) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        await client._transport.get("/protected/does-not-exist")
    assert excinfo.value.status == 404
