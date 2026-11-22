"""Shared base of the mock's route groups: lookups and member shaping."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from aiohttp import web

from .. import seed
from ..state import Json, MockState

#: URL prefix of the newer club endpoints.
NEW = "/protected/club/{club_id}"
#: URL prefix of the older ("mv365") club endpoints.
OLD = "/protected/mv365/clubs/{club_id}"

_ROW_KEYS = (
    "id",
    "firstName",
    "lastName",
    "formOfAddress",
    "title",
    "email",
    "additionalEmail",
    "phone",
    "phoneNotes",
    "phone2",
    "phone2Notes",
    "mobilePhone",
    "mobilePhoneNotes",
    "birthday",
    "gender",
    "type",
    "maritalStatus",
    "editedBy",
    "editedAtDate",
    "memberId",
    "state",
    "invitationState",
    "membershipBeginAt",
    "membershipEndAt",
    "createdAt",
    "notes",
    "isPerson",
    "isHonoured",
    "communicationChannel",
    "blockedCommunication",
    "useUnionReport",
)


def public(item: Json) -> Json:
    """Drop the mock's internal keys (leading underscore) before sending."""
    return {key: value for key, value in item.items() if not key.startswith("_")}


async def json_body(request: web.Request) -> Any:
    """The decoded JSON body, or ``None`` if there is none."""
    try:
        return await request.json()
    except json.JSONDecodeError:
        return None


class RouteGroup:
    """Base class: one subclass per area of the API."""

    def __init__(self, state: MockState) -> None:
        self.state = state

    def register(self, router: web.UrlDispatcher) -> None:
        raise NotImplementedError

    # -------------------------------------------------------------------- lookup

    def _club_id(self, request: web.Request) -> int | None:
        raw = request.match_info["club_id"]
        if raw.isdecimal() and int(raw) in self.state.clubs:
            return int(raw)
        return None

    def _member(self, request: web.Request) -> Json | None:
        club_id = self._club_id(request)
        raw = request.match_info["member_id"]
        if club_id is None or not raw.isdecimal():
            return None
        return self.state.members[club_id].get(int(raw))

    def _list(self, request: web.Request) -> Json | None:
        club_id = self._club_id(request)
        raw = request.match_info["list_id"]
        if club_id is None or not raw.isdecimal():
            return None
        return self.state.lists[club_id].get(int(raw))

    # ------------------------------------------------------------ member shaping

    def _sub_area_chain(self, club_id: int, sub_area_id: int | None) -> list[Json]:
        """The sub area and its parents, as list rows carry them."""
        by_id = {sub["id"]: sub for sub in self.state.sub_areas[club_id]}
        chain: list[Json] = []
        while sub_area_id in by_id:
            sub = by_id[sub_area_id]
            chain.append(
                {
                    "level": sub["level"],
                    "name": sub["name"],
                    "areaId": sub["areaId"],
                    "id": sub["id"],
                    "parentId": sub["parentId"],
                    "alias": sub["alias"],
                }
            )
            sub_area_id = sub["parentId"]
        return chain

    def _detail(self, member: Json, *, with_country: bool) -> Json:
        detail = public(member)
        if with_country and isinstance(detail.get("address"), dict):
            names = {country["id"]: country["name"] for country in seed.COUNTRIES}
            address = dict(detail["address"])
            address["country"] = names.get(int(address.get("countryId") or 0))
            detail["address"] = address
        return detail

    def _row(self, club_id: int, member: Json, *, versioned: bool = True) -> Json:
        """A member as it appears in the content of a list.

        Without a version header the real API sends ``memberIndividualFieldData``
        and the membership histories instead of ``individualFieldData``.
        """
        row: Json = {key: member.get(key) for key in _ROW_KEYS}
        row["address"] = self._detail(member, with_country=True).get("address")
        areas: list[Json] = []
        for history in member.get("histories", []):
            if not history.get("isFormer"):
                areas.extend(self._sub_area_chain(club_id, history.get("subAreaId")))
        row["clubSubAreas"] = areas
        role_names = {role["id"]: role["name"] for role in self.state.roles[club_id]}
        row["roles"] = [
            {"id": role_id, "name": role_names[role_id]}
            for role_id in self.state.member_roles.get(member["id"], [])
            if role_id in role_names
        ]
        if versioned:
            row["individualFieldData"] = [
                {
                    "individualFieldId": item["individualFieldId"],
                    "values": item["values"],
                }
                for item in member.get("memberIndividualFieldData", [])
            ]
        else:
            row["memberIndividualFieldData"] = member.get(
                "memberIndividualFieldData", []
            )
            row["histories"] = member.get("histories", [])
        row["paymentType"] = member.get("paymentType")
        row["clubMemberContributionRates"] = []
        row["clubMemberSepaMandates"] = []
        full_name = f"{member.get('firstName') or ''} {member.get('lastName') or ''}"
        row["receiver"] = full_name.strip()
        return row

    @staticmethod
    def _test(actual: Any, operator: str, expected: Any) -> bool:
        if operator == "=":
            return str(actual) == str(expected)
        if operator == "!=":
            if expected is None:
                return actual is not None
            return str(actual) != str(expected)
        # Other operators exist on the real service; the mock lets them pass.
        return True

    def _matches(
        self,
        member: Json,
        criteria: Sequence[Json],
        field_criteria: Sequence[Json] = (),
    ) -> bool:
        """Evaluate list criteria like the real service was seen to do.

        Rules on different columns must all hold; several rules on the same
        column (or custom field) are alternatives.
        """
        by_column: dict[str, list[Json]] = {}
        for rule in criteria:
            by_column.setdefault(rule["columnName"], []).append(rule)
        for column, rules in by_column.items():
            actual = member.get(column)
            if not any(self._test(actual, r["operator"], r["value"]) for r in rules):
                return False
        by_field: dict[int, list[Json]] = {}
        for rule in field_criteria:
            by_field.setdefault(rule["individualFieldId"], []).append(rule)
        values = {
            item["individualFieldId"]: item["values"]
            for item in member.get("memberIndividualFieldData", [])
        }
        for field_id, rules in by_field.items():
            actual_values = values.get(field_id, [])
            if not any(
                any(self._test(v, r["operator"], r["value"]) for v in actual_values)
                for r in rules
            ):
                return False
        return True

    def _list_members(self, club_id: int, item: Json) -> list[Json]:
        members = list(self.state.members[club_id].values())
        if item["listType"] == 1:
            return [
                member
                for member in members
                if self._matches(member, item["_criteria"], item["_field_criteria"])
            ]
        if item["departmentId"] is not None:
            department = item["departmentId"]
            return [
                member
                for member in members
                if any(
                    area["id"] == department
                    for history in member.get("histories", [])
                    if not history.get("isFormer")
                    for area in self._sub_area_chain(club_id, history.get("subAreaId"))
                )
            ]
        return [m for m in members if m["id"] in item["_member_ids"]]
