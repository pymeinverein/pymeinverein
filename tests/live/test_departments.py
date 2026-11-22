"""Live test for the department structure."""

from __future__ import annotations

import pytest

from pymeinverein.api.clubs import ClubClient

from .conftest import MARKER

pytestmark = pytest.mark.live


async def test_department_lifecycle(demo_club: ClubClient) -> None:
    club = demo_club
    try:
        before = {sub.id for sub in await club.departments.all()}

        department = await club.departments.create(f"{MARKER} dept", alias="PT")
        assert (department.level, department.alias) == (1, "PT")
        function = await club.departments.create(f"{MARKER} func", parent=department)
        assert (function.level, function.parent_id) == (2, department.id)

        renamed = await club.departments.update(department, name=f"{MARKER} renamed")
        assert (renamed.name, renamed.alias) == (f"{MARKER} renamed", "PT")
        by_path = await club.departments.get(f"{MARKER} renamed/{MARKER} func")
        assert by_path.id == function.id

        copy = await club.departments.copy(department.id)
        assert copy.name == f"{MARKER} renamed - Kopie"
        below = [s for s in await club.departments.all() if s.parent_id == copy.id]
        assert [s.name for s in below] == [f"{MARKER} func"]

        member = await club.members.create(first_name=MARKER, last_name="InDept")
        await club.members.set_membership(member.id, function.id)
        await club.departments.delete(department.id)  # deletes the function too
        periods = (await club.members.get(member.id)).histories
        assert [period.sub_area_id for period in periods] == [None]

        await club.departments.delete(copy)
        assert {sub.id for sub in await club.departments.all()} == before
    finally:
        for sub in sorted(await club.departments.all(), key=lambda s: -(s.level or 0)):
            if MARKER in sub.name:
                try:
                    await club.departments.delete(sub.id)
                except Exception:  # already removed with its parent
                    pass
