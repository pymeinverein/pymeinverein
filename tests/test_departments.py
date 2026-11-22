"""Department structure against the mock server."""

from __future__ import annotations

import pytest

from pymeinverein import LookupFailedError, NotFoundError
from pymeinverein.api.clubs import ClubClient
from pymeinverein.testing import seed


async def test_tree_and_flat_list(club: ClubClient) -> None:
    tree = await club.departments.tree()
    assert [(area.level, area.name) for area in tree] == [
        (1, "Mannschaften"),
        (2, "Rollen"),
        (3, "Ebene 3"),
    ]
    names = [(sub.level, sub.name) for sub in await club.departments.all()]
    assert names == [
        (1, "1. Mannschaft - Damen"),
        (1, "1. Mannschaft - Herren"),
        (2, "Spieler"),
        (2, "Spieler"),
    ]


async def test_get_by_id_name_and_path(club: ClubClient) -> None:
    assert (await club.departments.get(seed.DEPARTMENT_MEN)).name == (
        "1. Mannschaft - Herren"
    )
    women = await club.departments.get("1. Mannschaft - Damen")
    assert women.id == seed.DEPARTMENT_WOMEN and women.level == 1
    players = await club.departments.get("1. Mannschaft - Damen/Spieler")
    assert players.id == seed.PLAYERS_WOMEN and players.parent_id == women.id
    with pytest.raises(LookupFailedError):
        await club.departments.get("Spieler")
    with pytest.raises(LookupFailedError):
        await club.departments.get(424242)


async def test_create_department_function_and_third_level(club: ClubClient) -> None:
    youth = await club.departments.create("Jugend", alias="JU")
    assert (youth.level, youth.parent_id, youth.alias) == (1, None, "JU")
    assert youth.area_id == seed.AREA_TEAMS

    trainers = await club.departments.create("Trainer", parent="Jugend")
    assert (trainers.level, trainers.parent_id) == (2, youth.id)
    assert trainers.area_id == seed.AREA_FUNCTIONS

    head = await club.departments.create("Cheftrainer", parent="Jugend/Trainer")
    assert (head.level, head.parent_id) == (3, trainers.id)

    with pytest.raises(LookupFailedError, match="no level 4"):
        await club.departments.create("zu tief", parent=head)


async def test_update(club: ClubClient) -> None:
    renamed = await club.departments.update("1. Mannschaft - Damen", name="Damen I")
    assert renamed.name == "Damen I" and renamed.id == seed.DEPARTMENT_WOMEN
    aliased = await club.departments.update("Damen I", alias="D1")
    assert (aliased.name, aliased.alias) == ("Damen I", "D1")
    # Members of the department see the new name.
    assert (await club.members.list(search="Erika"))[0].departments == ["Damen I"]


async def test_copy_includes_children(club: ClubClient) -> None:
    copy = await club.departments.copy("1. Mannschaft - Herren")
    assert copy.name == "1. Mannschaft - Herren - Kopie" and copy.level == 1
    below = [sub for sub in await club.departments.all() if sub.parent_id == copy.id]
    assert [sub.name for sub in below] == ["Spieler"]


async def test_delete_cascades_but_keeps_members(club: ClubClient) -> None:
    await club.departments.delete("1. Mannschaft - Damen")
    remaining = {sub.id for sub in await club.departments.all()}
    assert remaining == {seed.DEPARTMENT_MEN, seed.PLAYERS_MEN}

    erika = await club.members.get(7002)
    assert erika.is_active
    assert [period.sub_area_id for period in erika.histories] == [None]
    assert (await club.members.list(search="Erika"))[0].departments == []

    with pytest.raises(NotFoundError):
        await club.departments.delete(seed.DEPARTMENT_WOMEN)


async def test_rename_level(club: ClubClient) -> None:
    level = await club.departments.rename_level(1, "Teams")
    assert (level.level, level.name) == (1, "Teams")
    assert (await club.departments.tree())[0].name == "Teams"
    with pytest.raises(LookupFailedError):
        await club.departments.rename_level(9, "nope")
