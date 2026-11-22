"""Custom field definitions and dynamic list rules against the mock server."""

from __future__ import annotations

import pytest

from pymeinverein import ListType, LookupFailedError, NotFoundError
from pymeinverein.api.clubs import ClubClient
from pymeinverein.models import FieldCriterion, IndividualFieldType, ListCriterion
from pymeinverein.testing import seed

# --------------------------------------------------------------- custom fields


async def test_custom_field_lifecycle(club: ClubClient) -> None:
    created = await club.custom_fields.create(
        "Trikotgröße", IndividualFieldType.SELECT, options=["S", "M", "L"]
    )
    assert (created.name, created.type, created.options) == (
        "Trikotgröße",
        IndividualFieldType.SELECT,
        ["S", "M", "L"],
    )
    assert [f.name for f in await club.custom_fields.all()] == [
        "Spielberechtigt",
        "Position",
        "Trikotgröße",
    ]

    updated = await club.custom_fields.update(created, options=["S", "M", "L", "XL"])
    assert updated.options == ["S", "M", "L", "XL"] and updated.name == "Trikotgröße"
    renamed = await club.custom_fields.update("Trikotgröße", name="Trikot", suffix="EU")
    assert (renamed.name, renamed.suffix, renamed.options) == (
        "Trikot",
        "EU",
        ["S", "M", "L", "XL"],
    )

    await club.members.set_custom_field(7003, "Trikot", "XL")
    assert (await club.members.get(7003)).custom_values[created.id] == ["XL"]

    await club.custom_fields.delete("Trikot")
    assert created.id not in (await club.members.get(7003)).custom_values
    with pytest.raises(LookupFailedError):
        await club.custom_fields.get("Trikot")
    with pytest.raises(NotFoundError):
        await club.custom_fields.delete(created.id)


async def test_text_field_defaults(club: ClubClient) -> None:
    field = await club.custom_fields.create("Bemerkung")
    assert (field.type, field.options, field.suffix) == (
        IndividualFieldType.TEXT,
        [],
        None,
    )
    assert (await club.custom_fields.get(field.id)).name == "Bemerkung"


# --------------------------------------------------------------- dynamic lists


async def test_same_column_rules_are_alternatives(club: ClubClient) -> None:
    # Seeded like a real default list: type = 1, state = 0, state = 2.
    members = await club.lists.members(seed.LIST_NOT_FORMER)
    assert [m.last_name for m in members] == [
        "User",
        "Beispiel",
        "Muster",
        "Probe",
        "Test",
        "Skizze",
    ]


async def test_create_dynamic_list_with_rules(club: ClubClient) -> None:
    keepers = await club.lists.create(
        "Torhüter",
        criteria=[("type", "=", 1)],
        field_criteria=[("Position", "=", "Tor")],
    )
    assert keepers.list_type == ListType.DYNAMIC
    assert [m.last_name for m in await club.lists.members(keepers)] == ["Beispiel"]

    rules = await club.lists.criteria(keepers)
    assert [(r.column_name, r.operator, r.value) for r in rules] == [("type", "=", "1")]
    field_rules = await club.lists.field_criteria(keepers)
    assert [(r.individual_field_id, r.value) for r in field_rules] == [
        (seed.FIELD_POSITION, "Tor")
    ]

    # The list follows the data.
    await club.members.set_custom_field(7005, "Position", "Tor")
    assert [m.last_name for m in await club.lists.members("Torhüter")] == [
        "Beispiel",
        "Test",
    ]


async def test_set_criteria_replaces_all_rules(club: ClubClient) -> None:
    created = await club.lists.create("Auswahl", criteria=[("state", "=", 1)])
    assert len(await club.lists.members(created)) == 2

    await club.lists.set_criteria(
        created,
        [ListCriterion(column_name="type", value="1"), ("birthday", "!=", None)],
        [
            FieldCriterion(individual_field_id=seed.FIELD_POSITION, value="Tor"),
            (seed.FIELD_POSITION, "=", "Sturm"),
        ],
    )
    assert [m.last_name for m in await club.lists.members(created)] == [
        "Beispiel",
        "Muster",
    ]
    assert [r.column_name for r in await club.lists.criteria(created)] == [
        "type",
        "birthday",
    ]

    await club.lists.set_criteria(created)  # no rules: everyone
    assert await club.lists.criteria(created) == []
    assert await club.lists.field_criteria(created) == []
    assert len(await club.lists.members(created)) == 10


async def test_explicit_list_type(club: ClubClient) -> None:
    empty_dynamic = await club.lists.create("Leer", type=ListType.DYNAMIC)
    assert empty_dynamic.list_type == ListType.DYNAMIC
    static = await club.lists.create("Fest")
    assert static.list_type == ListType.STATIC


async def test_copy_list(club: ClubClient) -> None:
    copy = await club.lists.copy("Ehemalige Mitglieder", "Ehemalige (Kopie)")
    assert copy.name == "Ehemalige (Kopie)" and not copy.is_default_list
    assert [m.last_name for m in await club.lists.members(copy)] == [
        "Vorlage",
        "Entwurf",
    ]
    board = await club.lists.copy("Vorstand", "Vorstand 2")
    assert [m.id for m in await club.lists.members(board)] == [7001, 7002]


async def test_favourites(club: ClubClient) -> None:
    await club.lists.set_favourite("Vorstand")
    assert (await club.lists.get("Vorstand")).is_favourite is True
    await club.lists.set_favourite("Vorstand", False)
    assert (await club.lists.get("Vorstand")).is_favourite is False


async def test_query_accepts_other_operators(club: ClubClient) -> None:
    with_birthday = await club.members.query([("birthday", "!=", None)])
    assert [m.last_name for m in with_birthday] == [
        "Beispiel",
        "Muster",
        "Probe",
        "Test",
    ]
