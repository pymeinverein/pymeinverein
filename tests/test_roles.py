"""Permission roles against the mock server."""

from __future__ import annotations

import pytest

from pymeinverein import LookupFailedError, NoAccountError, RequestRejectedError
from pymeinverein.api.clubs import ClubClient
from pymeinverein.models import PermissionState, RoleType
from pymeinverein.testing import seed

OWNER, ERIKA, MAX, LENA = 7001, 7002, 7003, 7004  # Lena has no account


async def test_roles_with_members(club: ClubClient) -> None:
    roles = await club.roles.all(with_members=True)
    assert [(r.name, r.type, r.member_count) for r in roles] == [
        ("Administrator", RoleType.ADMINISTRATOR, 1),
        ("Finanzverwalter", RoleType.FINANCE_MANAGER, 1),
        ("Verwalter", RoleType.MANAGER, 0),
        ("Mitglied", RoleType.MEMBER, 1),
    ]
    assert [m.last_name for m in roles[1].members] == ["Beispiel"]
    assert all(r.is_system_role for r in roles)
    assert (await club.roles.all())[1].members == []


async def test_get_role(club: ClubClient) -> None:
    assert (await club.roles.get("Verwalter")).id == seed.ROLE_MANAGER
    assert (await club.roles.get(seed.ROLE_ADMIN)).name == "Administrator"
    with pytest.raises(LookupFailedError, match="'Mitglied'"):
        await club.roles.get("Kassenwart")


async def test_role_lifecycle(club: ClubClient) -> None:
    created = await club.roles.create("Trainer", "Darf Termine pflegen")
    assert (created.name, created.description) == ("Trainer", "Darf Termine pflegen")
    assert created.type == RoleType.CUSTOM and created.is_system_role is False

    renamed = await club.roles.update(created, name="Übungsleiter")
    assert (renamed.name, renamed.description) == (
        "Übungsleiter",
        "Darf Termine pflegen",
    )
    described = await club.roles.update("Übungsleiter", description="neu")
    assert (described.name, described.description) == ("Übungsleiter", "neu")

    await club.roles.delete("Übungsleiter")
    assert len(await club.roles.all()) == 4
    with pytest.raises(LookupFailedError):
        await club.roles.delete(created.id)


async def test_permissions(club: ClubClient) -> None:
    role = await club.roles.create("Trainer")
    tree = await club.roles.permissions(role)
    assert [node.key for node in tree] == [
        "dynamic_list_member_container",
        "calendar_container",
        "finance_container",
    ]
    assert tree[0].state is None and len(tree[0].children) == 2

    states = await club.roles.permission_states(role)
    assert set(states.values()) == {PermissionState.LOCKED}

    await club.roles.set_permission(
        role, "calendar_events_module", PermissionState.UPDATE
    )
    states = await club.roles.permission_states(role)
    assert states["calendar_events_module"] == PermissionState.UPDATE
    assert states["finance_invoices_module"] == PermissionState.LOCKED

    admin = await club.roles.permission_states("Administrator")
    assert set(admin.values()) == {PermissionState.UPDATE_AND_DELETE}


async def test_set_member_roles(club: ClubClient) -> None:
    await club.roles.set_member_roles(MAX, ["Verwalter", seed.ROLE_MEMBER])
    row = (await club.members.list(search="Max"))[0]
    assert [role.name for role in row.roles] == ["Verwalter", "Mitglied"]
    assert [m.last_name for m in await club.members.list(role="Verwalter")] == [
        "Muster"
    ]

    await club.roles.set_member_roles(MAX, [])
    assert (await club.members.list(search="Max"))[0].roles == []


async def test_roles_need_an_account(club: ClubClient) -> None:
    with pytest.raises(NoAccountError, match="Lena Probe"):
        await club.roles.set_member_roles(LENA, ["Mitglied"])
    # Without the check the service answers with its failure page.
    with pytest.raises(RequestRejectedError):
        await club._transport.put(
            f"/protected/club/{club.id}/auth/club-members/{LENA}/assign/club-roles",
            {"clubRoleIds": [seed.ROLE_MEMBER]},
        )


async def test_add_and_set_members_of_a_role(club: ClubClient) -> None:
    role = await club.roles.create("Trainer")
    # Lena has no account and is skipped without an error.
    assert await club.roles.add_members(role, [ERIKA, LENA]) == [ERIKA]
    holders = (await club.roles.get(role.id, with_members=True)).members
    assert [m.id for m in holders] == [ERIKA]
    erika = (await club.members.list(search="Erika"))[0]
    assert [r.name for r in erika.roles] == ["Finanzverwalter", "Trainer"]

    await club.roles.set_members(role, [OWNER, MAX])
    holders = (await club.roles.get(role.id, with_members=True)).members
    assert [m.id for m in holders] == [OWNER, MAX]


async def test_deleting_a_role_removes_it_from_members(club: ClubClient) -> None:
    await club.roles.delete("Finanzverwalter")
    assert (await club.members.list(search="Erika"))[0].roles == []
