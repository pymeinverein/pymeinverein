"""Live tests for custom field definitions and dynamic lists."""

from __future__ import annotations

import pytest

from pymeinverein import ListType
from pymeinverein.api.clubs import ClubClient
from pymeinverein.models import IndividualFieldType

from .conftest import MARKER

pytestmark = pytest.mark.live


async def test_custom_field_and_dynamic_list(demo_club: ClubClient) -> None:
    club = demo_club
    try:
        field = await club.custom_fields.create(
            f"{MARKER} field", IndividualFieldType.SELECT, options=["A", "B"]
        )
        updated = await club.custom_fields.update(
            field, name=f"{MARKER} field2", options=["A", "B", "C"], suffix="x"
        )
        assert (updated.options, updated.suffix) == (["A", "B", "C"], "x")
        assert (await club.custom_fields.get(field.id)).name == f"{MARKER} field2"

        first = await club.members.create(first_name=MARKER, last_name="DynA")
        second = await club.members.create(first_name=MARKER, last_name="DynB")
        await club.members.set_custom_field(first.id, field.id, "A")
        await club.members.set_custom_field(second.id, field.id, "B")

        dynamic = await club.lists.create(
            f"{MARKER} dyn",
            criteria=[("type", "=", 1), ("firstName", "=", MARKER)],
            field_criteria=[(field.id, "=", "A")],
        )
        assert dynamic.list_type == ListType.DYNAMIC
        assert [m.id for m in await club.lists.members(dynamic)] == [first.id]
        assert len(await club.lists.criteria(dynamic)) == 2
        assert len(await club.lists.field_criteria(dynamic)) == 1

        # Two rules on one field are alternatives.
        await club.lists.set_criteria(
            dynamic,
            [("firstName", "=", MARKER)],
            [(field.id, "=", "A"), (field.id, "=", "B")],
        )
        both = {m.id for m in await club.lists.members(dynamic)}
        assert both == {first.id, second.id}

        copy = await club.lists.copy(dynamic, f"{MARKER} copy")
        assert len(await club.lists.criteria(copy)) == 1

        await club.lists.set_favourite(dynamic)
        assert (await club.lists.get(dynamic.id)).is_favourite is True
        await club.lists.set_favourite(dynamic, False)
        assert (await club.lists.get(dynamic.id)).is_favourite is False

        await club.lists.set_criteria(dynamic)
        assert await club.lists.criteria(dynamic) == []
        assert await club.lists.field_criteria(dynamic) == []
    finally:
        for field in await club.custom_fields.all():
            if MARKER in field.name:
                await club.custom_fields.delete(field.id)
