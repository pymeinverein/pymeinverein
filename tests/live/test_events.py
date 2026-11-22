"""Live test for calendar events. No participants, no notifications."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from pymeinverein import NotFoundError
from pymeinverein.api.clubs import ClubClient

from .conftest import MARKER

pytestmark = pytest.mark.live


async def test_event_lifecycle(demo_club: ClubClient) -> None:
    club = demo_club
    try:
        category = await club.events.create_category(f"{MARKER} cat", "#123456")
        assert category.color == "#123456"

        event = await club.events.create(
            f"{MARKER} event",
            datetime(2031, 3, 1, 18, 0, tzinfo=UTC),
            datetime(2031, 3, 1, 20, 0, tzinfo=UTC),
            category=category,
            location="Vereinsheim",
            notes="created by a test",
        )
        assert event.id is not None and event.event_length == 7200
        assert event.participants == []

        updated = await club.events.update(event.id, title=f"{MARKER} event2")
        assert (updated.title, updated.description) == (
            f"{MARKER} event2",
            "Vereinsheim",
        )
        assert [e.id for e in await club.events.search(MARKER)] == [event.id]
        in_range = await club.events.list(
            date(2031, 2, 1), date(2031, 4, 1), categories=[category]
        )
        assert [e.id for e in in_range] == [event.id]

        await club.events.delete(event.id)
        with pytest.raises(NotFoundError):
            await club.events.get(event.id)
        await club.events.delete_category(category)
    finally:
        for leftover in await club.events.search(MARKER):
            if leftover.id is not None:
                await club.events.delete(leftover.id)
        for item in await club.events.categories():
            if MARKER in item.name:
                await club.events.delete_category(item.id)


async def test_demo_calendar_can_be_read(demo_club: ClubClient) -> None:
    today = date.today()
    entries = await demo_club.events.list(
        today.replace(month=1, day=1), today.replace(month=12, day=31), birthdays=True
    )
    assert any(entry.is_birthday for entry in entries)
