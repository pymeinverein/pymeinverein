"""Calendar events against the mock server."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from pymeinverein import LookupFailedError, NotFoundError
from pymeinverein.api.clubs import ClubClient
from pymeinverein.testing import seed


async def test_categories(club: ClubClient) -> None:
    categories = await club.events.categories()
    assert [(c.name, c.type) for c in categories] == [
        ("Training", "custom"),
        ("Standard", "default"),
        ("Aktive/ Passive Mitglieder", "birthday"),
    ]


async def test_category_lifecycle(club: ClubClient) -> None:
    created = await club.events.create_category("Turniere", "#00aa00")
    assert (created.name, created.color, created.type) == (
        "Turniere",
        "#00aa00",
        "custom",
    )
    await club.events.delete_category("Turniere")
    assert len(await club.events.categories()) == 3
    with pytest.raises(LookupFailedError):
        await club.events.delete_category("Turniere")


async def test_list_events(club: ClubClient) -> None:
    november = await club.events.list(date(2026, 11, 1), date(2026, 11, 30))
    assert [e.title for e in november] == ["Vorstandssitzung", "Training Damen"]
    assert november[0].category is not None
    assert november[0].category.name == "Standard"
    assert november[0].start_date == datetime(2026, 11, 14, 18, tzinfo=UTC)

    training = await club.events.list(
        date(2026, 11, 1), date(2026, 12, 31), categories=["Training"]
    )
    assert [e.title for e in training] == ["Training Damen"]
    found = await club.events.list(date(2026, 1, 1), date(2026, 12, 31), search="feier")
    assert [e.title for e in found] == ["Weihnachtsfeier"]


async def test_birthdays_are_optional(club: ClubClient) -> None:
    entries = await club.events.list(
        date(2026, 11, 1), date(2026, 11, 30), birthdays=True
    )
    birthdays = [e for e in entries if e.is_birthday]
    assert [e.title for e in birthdays] == ["Max Muster hat Geburtstag"]
    assert birthdays[0].full_day and birthdays[0].id is None


async def test_the_api_returns_nothing_without_categories(club: ClubClient) -> None:
    # The library therefore always names the categories.
    payload = await club._transport.get(
        f"/protected/mv365/clubs/{club.id}/events",
        params={
            "body": '{"startDate": "2026-01-01", "endDate": "2026-12-31", '
            '"searchText": null, "categoryIds": null}'
        },
    )
    assert payload == {"events": []}


async def test_event_lifecycle(club: ClubClient) -> None:
    created = await club.events.create(
        "Sommerfest",
        datetime(2027, 7, 3, 14, 0, tzinfo=UTC),
        datetime(2027, 7, 3, 22, 0, tzinfo=UTC),
        location="Sportplatz",
        notes="Grill mitbringen",
    )
    assert created.id is not None
    assert (created.title, created.description, created.notes) == (
        "Sommerfest",
        "Sportplatz",
        "Grill mitbringen",
    )
    assert created.category_id == seed.CATEGORY_DEFAULT  # the standard category
    assert created.event_length == 8 * 3600

    updated = await club.events.update(
        created.id, title="Sommerfest 2027", category_id=seed.CATEGORY_CUSTOM
    )
    assert (updated.title, updated.category_id, updated.description) == (
        "Sommerfest 2027",
        seed.CATEGORY_CUSTOM,
        "Sportplatz",
    )
    assert [e.id for e in await club.events.search("sommer")] == [created.id]
    assert (await club.events.get(created.id)).title == "Sommerfest 2027"

    await club.events.delete(created.id)
    with pytest.raises(NotFoundError):
        await club.events.get(created.id)


async def test_full_day_event_from_dates(club: ClubClient) -> None:
    event = await club.events.create(
        "Ausflug",
        date(2027, 5, 1),
        date(2027, 5, 2),
        category="Training",
        full_day=True,
    )
    assert event.full_day and event.category_id == seed.CATEGORY_CUSTOM
    assert event.start_date == datetime(2027, 5, 1, tzinfo=UTC)


async def test_unknown_event_and_category(club: ClubClient) -> None:
    with pytest.raises(NotFoundError):
        await club.events.delete(1)
    with pytest.raises(LookupFailedError, match="'Standard'"):
        await club.events.create(
            "x", date(2027, 1, 1), date(2027, 1, 2), category="Gibt es nicht"
        )
