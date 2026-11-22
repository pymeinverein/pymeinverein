"""Live test for permission roles."""

from __future__ import annotations

import pytest

from pymeinverein import NoAccountError
from pymeinverein.api.clubs import ClubClient
from pymeinverein.models import PermissionState, RoleType

from .conftest import MARKER

pytestmark = pytest.mark.live


async def test_role_lifecycle(demo_club: ClubClient) -> None:
    club = demo_club
    account = await club._transport.get("/protected/accounts")
    my_user_id = account["data"]["user"]["id"]
    # A sample member of the demo club that has a user account (not ourselves).
    holder = next(
        m for m in await club.members.query() if m.user_id not in (None, my_user_id)
    )
    original = [r.id for r in (await club.members.list(search=holder.email))[0].roles]
    try:
        role = await club.roles.create(f"{MARKER} role", "created by a test")
        assert role.type == RoleType.CUSTOM

        updated = await club.roles.update(role, name=f"{MARKER} role2")
        assert (updated.name, updated.description) == (
            f"{MARKER} role2",
            "created by a test",
        )

        key = "calendar_events_module"
        states = await club.roles.permission_states(role)
        assert states[key] == PermissionState.LOCKED
        await club.roles.set_permission(role, key, PermissionState.READ)
        changed = await club.roles.permission_states(role)
        assert changed[key] == PermissionState.READ
        assert {k: v for k, v in changed.items() if k != key} == {
            k: v for k, v in states.items() if k != key
        }

        without_account = await club.members.create(
            first_name=MARKER, last_name="NoAccount"
        )
        with pytest.raises(NoAccountError):
            await club.roles.set_member_roles(without_account.id, [role])
        assert await club.roles.add_members(role, [without_account.id]) == []

        assert await club.roles.add_members(role, [holder.id]) == [holder.id]
        with_members = await club.roles.get(role.id, with_members=True)
        assert [m.id for m in with_members.members] == [holder.id]

        await club.roles.set_member_roles(holder.id, original)
        assert (await club.roles.get(role.id)).member_count == 0

        await club.roles.set_members(role, [holder.id])
        assert (await club.roles.get(role.id)).member_count == 1
        await club.roles.delete(role)
        now = [r.id for r in (await club.members.list(search=holder.email))[0].roles]
        assert now == original
    finally:
        for leftover in await club.roles.all():
            if MARKER in leftover.name:
                await club.roles.delete(leftover.id)
        await club.roles.set_member_roles(holder.id, original)
