"""Fixtures for the tests that talk to the real service. Not run by default.

    export MEINVEREIN_EMAIL=... MEINVEREIN_PASSWORD=...
    uv run pytest -m live

The tests only ever write to a club that the API itself marks as demo club
(``isDemo: true``). Everything they create is named ``pymeinverein-test...`` and
is removed again, also when an assertion fails.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest

from pymeinverein import MeinVereinClient
from pymeinverein.api.clubs import ClubClient

#: Every object the live tests create carries this text in its name.
MARKER = "pymeinverein-test"


@pytest.fixture
async def demo_club() -> AsyncIterator[ClubClient]:
    if not os.environ.get("MEINVEREIN_EMAIL") or not os.environ.get(
        "MEINVEREIN_PASSWORD"
    ):
        pytest.skip("MEINVEREIN_EMAIL / MEINVEREIN_PASSWORD are not set")
    async with MeinVereinClient() as mv:
        demo = [club for club in await mv.clubs.list() if club.is_demo]
        if len(demo) != 1:
            pytest.skip("the account needs exactly one demo club")
        club = await mv.clubs.get(demo[0].id)
        assert club.is_demo, "refusing to write to a club that is not a demo club"
        try:
            yield club
        finally:
            leftovers = await club.members.query([("firstName", "=", MARKER)])
            if leftovers:
                await club.members.delete(*(m.id for m in leftovers), missing_ok=True)
            for item in await club.lists.all():
                if item.name.startswith(MARKER):
                    await club.lists.delete(item)
