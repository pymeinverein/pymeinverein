"""Member lists: the default lists of every club and lists created by users."""

from __future__ import annotations

from collections.abc import Iterable

from .._transport import Transport
from ..exceptions import LookupFailedError
from ..models.lists import (
    DefaultListType,
    FieldCriterion,
    ListCriterion,
    ListType,
    MemberList,
    RemoveResult,
)
from ..models.masterdata import IndividualField
from ..models.member import Member
from ._util import to_payload, unwrap
from .masterdata import MasterDataAPI

#: A list id, a list name or one of the default lists.
type ListRef = int | str | DefaultListType | MemberList
#: A rule on a member column: a model or ``(column, operator, value)``.
type CriterionSpec = ListCriterion | tuple[str, str, object]
#: A rule on a custom field: a model or ``(field id or name, operator, value)``.
type FieldCriterionSpec = (
    FieldCriterion | tuple[int | str | IndividualField, str, object]
)


def _text(value: object) -> str | None:
    """Criteria values are sent as text; ``None`` stays ``None``."""
    return None if value is None else str(to_payload(value))


class ListsAPI:
    """Read and manage the member lists of one club.

    Wherever a list is expected you can pass its id, its exact name, a
    :class:`~pymeinverein.models.lists.DefaultListType` or a ``MemberList``.
    """

    def __init__(
        self, transport: Transport, club_id: int, master_data: MasterDataAPI
    ) -> None:
        self._transport = transport
        self._master_data = master_data
        self._base = f"/protected/club/{club_id}/list"

    async def all(self) -> list[MemberList]:
        """Return all lists of the club.

        ``GET /protected/club/{clubId}/list/all``
        """
        path = f"{self._base}/all"
        payload = await self._transport.get(path)
        lists = unwrap(payload, "data", f"GET {path}")
        return [MemberList.model_validate(item) for item in lists]

    async def get(self, ref: ListRef) -> MemberList:
        """Look up one list by id, exact name or default list type."""
        if isinstance(ref, MemberList):
            return ref
        lists = await self.all()
        if isinstance(ref, DefaultListType):
            # Department lists share one default type, so they are not unique.
            matches = [item for item in lists if item.default_list_type == ref]
            wanted = f"default list {ref.name}"
        elif isinstance(ref, int):
            matches = [item for item in lists if item.id == ref]
            wanted = f"list id {ref}"
        else:
            matches = [item for item in lists if item.name.strip() == ref.strip()]
            wanted = f"list name {ref!r}"
        if len(matches) != 1:
            names = ", ".join(repr(item.name) for item in lists)
            raise LookupFailedError(
                f"Expected exactly one match for {wanted}, found {len(matches)}. "
                f"Available lists: {names or 'none'}"
            )
        return matches[0]

    async def _id(self, ref: ListRef) -> int:
        if isinstance(ref, MemberList):
            return ref.id
        if isinstance(ref, int) and not isinstance(ref, DefaultListType):
            return ref
        return (await self.get(ref)).id

    async def members(self, ref: ListRef) -> list[Member]:
        """Return the members on a list.

        The rows include resolved departments, roles and custom field values.
        ``POST /protected/club/{clubId}/list/{listId}`` with an empty JSON object
        and the header ``x-api-version: v3`` (the version the web application
        uses; older versions answer with a different row layout).
        """
        path = f"{self._base}/{await self._id(ref)}"
        payload = await self._transport.post(path, {}, api_version="v3")
        rows = unwrap(payload, "data", f"POST {path}")
        return [Member.model_validate(row) for row in rows]

    async def criteria(self, ref: ListRef) -> list[ListCriterion]:
        """Return the filter rules of a dynamic list.

        ``GET /protected/club/{clubId}/list/criteria/{listId}``
        """
        path = f"{self._base}/criteria/{await self._id(ref)}"
        payload = await self._transport.get(path)
        rules = unwrap(payload, "data", f"GET {path}")
        return [ListCriterion.model_validate(rule) for rule in rules]

    async def field_criteria(self, ref: ListRef) -> list[FieldCriterion]:
        """Return the filter rules of a dynamic list that use custom fields.

        ``GET /protected/club/{clubId}/list/individual-field-criteria/{listId}``
        """
        path = f"{self._base}/individual-field-criteria/{await self._id(ref)}"
        payload = await self._transport.get(path)
        rules = unwrap(payload, "data", f"GET {path}")
        return [FieldCriterion.model_validate(rule) for rule in rules]

    async def set_criteria(
        self,
        ref: ListRef,
        criteria: Iterable[CriterionSpec] = (),
        field_criteria: Iterable[FieldCriterionSpec] = (),
    ) -> None:
        """Replace all filter rules of a dynamic list.

        ``criteria`` are rules on member columns, ``field_criteria`` rules on
        custom fields, each as ``(name, operator, value)``::

            await club.lists.set_criteria(
                "Torhüter",
                [("type", "=", 1), ("state", "=", 0), ("state", "=", 2)],
                [("Position", "=", "Tor")],
            )

        Rules on different columns must all hold; several rules on the same
        column are alternatives (the example selects members that are active
        *or* passive). Verified operators are ``=`` and ``!=``; ``!=`` with the
        value ``None`` means "is filled in".

        Like the web application this deletes the existing rules and creates
        the new ones (``DELETE`` and ``POST .../list/criteria`` and
        ``.../list/individual-field-criteria``).
        """
        list_id = await self._id(ref)
        columns = []
        for rule in criteria:
            if isinstance(rule, ListCriterion):
                rule = (rule.column_name, rule.operator, rule.value)
            column, operator, value = rule
            columns.append(
                {"columnName": column, "operator": operator, "value": _text(value)}
            )
        fields = []
        for field_rule in field_criteria:
            if isinstance(field_rule, FieldCriterion):
                field_rule = (
                    field_rule.individual_field_id,
                    field_rule.operator,
                    field_rule.value,
                )
            field, operator, value = field_rule
            fields.append(
                {
                    "individualFieldId": (
                        await self._master_data.resolve_individual_field(field)
                    ),
                    "operator": operator,
                    "value": _text(value),
                }
            )

        old_ids = [rule.id for rule in await self.criteria(list_id)]
        if old_ids:
            await self._transport.delete(
                f"{self._base}/criteria", {"criteriaIds": old_ids}
            )
        old_field_ids = [rule.id for rule in await self.field_criteria(list_id)]
        if old_field_ids:
            await self._transport.delete(
                f"{self._base}/individual-field-criteria/{list_id}",
                {"criteriaIds": old_field_ids},
            )
        if columns:
            await self._transport.post(
                f"{self._base}/criteria/{list_id}", {"criteria": columns}
            )
        if fields:
            await self._transport.post(
                f"{self._base}/individual-field-criteria/",
                {"listId": list_id, "criteria": fields},
            )

    async def create(
        self,
        name: str,
        *,
        type: ListType | None = None,
        source_list: ListRef | None = None,
        criteria: Iterable[CriterionSpec] = (),
        field_criteria: Iterable[FieldCriterionSpec] = (),
    ) -> MemberList:
        """Create a list.

        Without rules a static list is created; fill it with
        :meth:`add_members`. With ``criteria`` and/or ``field_criteria`` (see
        :meth:`set_criteria`) a dynamic list is created that selects its
        members by those rules.
        ``POST /protected/club/{clubId}/list/create``
        """
        criteria = list(criteria)
        field_criteria = list(field_criteria)
        if type is None:
            dynamic = bool(criteria or field_criteria)
            type = ListType.DYNAMIC if dynamic else ListType.STATIC
        source_id = None if source_list is None else await self._id(source_list)
        path = f"{self._base}/create"
        payload = await self._transport.post(
            path, {"name": name, "type": int(type), "sourceListId": source_id}
        )
        created = MemberList.model_validate(unwrap(payload, "data", f"POST {path}"))
        if criteria or field_criteria:
            await self.set_criteria(created, criteria, field_criteria)
        return created

    async def copy(self, ref: ListRef, name: str) -> MemberList:
        """Duplicate a list under a new name, including its rules.

        ``POST /protected/club/{clubId}/list/{listId}/copy``
        """
        path = f"{self._base}/{await self._id(ref)}/copy"
        payload = await self._transport.post(path, {"name": name})
        return MemberList.model_validate(unwrap(payload, "data", f"POST {path}"))

    async def set_favourite(self, ref: ListRef, favourite: bool = True) -> None:
        """Mark a list as favourite of the logged-in user, or remove the mark.

        ``POST`` / ``DELETE /protected/club/{clubId}/list/favorites/{listId}``
        """
        path = f"{self._base}/favorites/{await self._id(ref)}"
        if favourite:
            await self._transport.post(path)
        else:
            await self._transport.delete(path)

    async def rename(self, ref: ListRef, name: str) -> None:
        """Change the name of a list.

        ``PUT /protected/club/{clubId}/list/{listId}``
        """
        await self._transport.put(f"{self._base}/{await self._id(ref)}", {"name": name})

    async def delete(self, ref: ListRef) -> None:
        """Delete a list. The members on it are not deleted.

        ``DELETE /protected/club/{clubId}/list/{listId}``
        """
        await self._transport.delete(f"{self._base}/{await self._id(ref)}")

    async def add_members(self, ref: ListRef, member_ids: Iterable[int]) -> None:
        """Put members on a static list.

        ``POST /protected/club/{clubId}/list/assign-members/{listId}``
        """
        await self._transport.post(
            f"{self._base}/assign-members/{await self._id(ref)}",
            {"clubMemberIds": list(member_ids)},
        )

    async def remove_members(
        self, ref: ListRef, member_ids: Iterable[int]
    ) -> RemoveResult:
        """Take members off a static list.

        ``POST /protected/club/{clubId}/list/remove-members/{listId}``
        """
        path = f"{self._base}/remove-members/{await self._id(ref)}"
        payload = await self._transport.post(path, {"clubMemberIds": list(member_ids)})
        return RemoveResult.model_validate(unwrap(payload, "meta", f"POST {path}"))
