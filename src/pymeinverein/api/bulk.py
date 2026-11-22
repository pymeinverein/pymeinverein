"""Bulk edits: change many members with one call."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from .._transport import Transport
from ..models.masterdata import IndividualField
from ..models.member import (
    BulkResult,
    CommunicationChannel,
    MemberState,
    PaymentMethod,
    SubArea,
)
from ._util import to_payload, unwrap
from .masterdata import MasterDataAPI


def custom_values(value: Any) -> list[str]:
    """Convert a Python value into the list of strings custom fields store."""
    if value is None:
        return []
    if isinstance(value, bool):
        return ["true" if value else "false"]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [item for part in value for item in custom_values(part)]
    return [str(to_payload(value))]


class MemberBulkAPI:
    """The calls behind the web application's "Massenänderung" (bulk edit).

    Every method takes the ids of the members to change and returns a
    :class:`~pymeinverein.models.member.BulkResult` that names the members the
    API skipped, with a reason code.
    """

    def __init__(
        self, transport: Transport, club_id: int, master_data: MasterDataAPI
    ) -> None:
        self._transport = transport
        self._master_data = master_data
        self._base = f"/protected/club/{club_id}/members/bulk-edit"

    async def _send(self, method: str, name: str, body: dict[str, Any]) -> BulkResult:
        path = f"{self._base}/{name}"
        payload = await self._transport.request(method, path, json_body=body)
        return BulkResult.model_validate(unwrap(payload, "meta", f"{method} {path}"))

    async def set_custom_fields(
        self,
        member_ids: Iterable[int],
        values: Mapping[int | str | IndividualField, Any],
        *,
        notes: str | None = None,
    ) -> BulkResult:
        """Set custom field values (and optionally the notes) for many members.

        ``values`` maps a custom field (id or name) to its new value.
        ``PUT /protected/club/{clubId}/members/bulk-edit/individual-field-data``
        """
        data = [
            {
                "individualFieldId": await self._master_data.resolve_individual_field(
                    field
                ),
                "values": custom_values(value),
            }
            for field, value in values.items()
        ]
        body: dict[str, Any] = {
            "clubMemberIds": list(member_ids),
            "individualFieldData": data,
        }
        if notes is not None:
            body["notes"] = notes
        return await self._send("PUT", "individual-field-data", body)

    async def set_communication_channel(
        self, member_ids: Iterable[int], channel: CommunicationChannel
    ) -> BulkResult:
        """Choose how the club writes to these members (e-mail or letter).

        ``PUT /protected/club/{clubId}/members/bulk-edit/communication-type``
        """
        return await self._send(
            "PUT",
            "communication-type",
            {"clubMemberIds": list(member_ids), "communicationType": int(channel)},
        )

    async def set_payment_method(
        self, member_ids: Iterable[int], method: PaymentMethod
    ) -> BulkResult:
        """Change how these members pay.

        Members without a SEPA mandate are skipped when switching to direct
        debit (reason ``NO_SEPA_MANDATE``).
        ``PUT /protected/club/{clubId}/members/bulk-edit/payment-types``
        """
        return await self._send(
            "PUT",
            "payment-types",
            {"clubMemberIds": list(member_ids), "paymentType": int(method)},
        )

    async def add_membership(
        self,
        member_ids: Iterable[int],
        department: int | str | SubArea | None,
        *,
        start: date,
        end: date | None = None,
        status: MemberState = MemberState.ACTIVE,
        honoured: bool = False,
    ) -> BulkResult:
        """Add a membership period in a department (or function) to many members.

        ``department`` is an id, a unique name or a path such as
        ``"1. Mannschaft - Damen/Spieler"``; ``None`` adds a membership that is
        not tied to a department.
        ``POST /protected/club/{clubId}/members/bulk-edit/memberships``
        """
        sub_area_id = (
            None
            if department is None
            else await self._master_data.resolve_sub_area(department)
        )
        return await self._send(
            "POST",
            "memberships",
            {
                "clubMemberIds": list(member_ids),
                "history": {
                    "membershipStart": to_payload(start),
                    "membershipEnd": to_payload(end),
                    "status": int(status),
                    "subAreaId": sub_area_id,
                    "isHonoured": honoured,
                },
            },
        )

    async def update_membership(
        self,
        member_ids: Iterable[int],
        department: int | str | SubArea,
        *,
        end: date | None = None,
        status: MemberState = MemberState.ACTIVE,
        honoured: bool = False,
    ) -> BulkResult:
        """Change the existing membership of many members in one department.

        Use it to end memberships (``end=..., status=MemberState.FORMER``) or to
        switch between active and passive. Members that have no membership in
        that department are skipped (reason ``NOT_A_CLUB_MEMBER``).
        ``PUT /protected/club/{clubId}/members/bulk-edit/memberships``
        """
        sub_area_id = await self._master_data.resolve_sub_area(department)
        return await self._send(
            "PUT",
            "memberships",
            {
                "clubMemberIds": list(member_ids),
                "subAreaId": sub_area_id,
                "history": {
                    "membershipEnd": to_payload(end),
                    "status": int(status),
                    "subAreaId": sub_area_id,
                    "isHonoured": honoured,
                },
            },
        )
