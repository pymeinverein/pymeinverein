"""Shared fixtures: a running mock server and a client logged in to it."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from pymeinverein import MeinVereinClient
from pymeinverein.api.clubs import ClubClient
from pymeinverein.testing import DEMO_EMAIL, DEMO_PASSWORD, MockServer


@pytest.fixture(autouse=True)
def _no_token_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """A MEINVEREIN_TOKEN of the developer must not leak into the mock tests."""
    monkeypatch.delenv("MEINVEREIN_TOKEN", raising=False)


@pytest.fixture
async def server() -> AsyncIterator[MockServer]:
    async with MockServer() as mock:
        yield mock


@pytest.fixture
async def client(server: MockServer) -> AsyncIterator[MeinVereinClient]:
    async with MeinVereinClient(
        DEMO_EMAIL, DEMO_PASSWORD, **server.client_kwargs()
    ) as mv:
        yield mv


@pytest.fixture
async def club(client: MeinVereinClient) -> ClubClient:
    """The demo club of the mock server."""
    return await client.clubs.get(name="Demoverein")
