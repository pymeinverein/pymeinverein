"""Members and contacts of a club: read, create, change, delete, export."""

from __future__ import annotations

import asyncio
import builtins
from datetime import date
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

import aiohttp

from .._transport import Transport
from ..exceptions import LookupFailedError
from ..export import ExportFormat, FieldSpec, export_members, resolve_fields
from ..filters import MemberFilter
from ..models.lists import DefaultListType, ListCriterion
from ..models.masterdata import IndividualField
from ..models.member import (
    DeleteResult,
    InviteResult,
    Member,
    MemberState,
    MembershipPeriod,
    MemberType,
    SubArea,
)
from ..models.roles import ClubRole, RoleType
from ._util import to_payload, unwrap
from .bulk import MemberBulkAPI, custom_values
from .lists import ListRef, ListsAPI
from .masterdata import MasterDataAPI


def _period_body(item: dict[str, Any], period: MembershipPeriod) -> dict[str, Any]:
    """Write the wanted state of ``period`` into the API's history entry ``item``."""
    status = period.effective_status()
    item["membershipStart"] = to_payload(period.start)
    item["membershipEnd"] = None if period.end is None else to_payload(period.end)
    item["status"] = int(status)
    item["isFormer"] = status == MemberState.FORMER
    item["isHonoured"] = period.honoured
    return item


#: A criterion for :meth:`MembersAPI.query`: a model or ``(column, operator, value)``.
type Criterion = ListCriterion | tuple[str, str, object]


class MembersAPI:
    """Manage the members and contacts of one club.

    MeinVerein keeps members, contacts and companies together and tells them
    apart by ``type`` (see :class:`~pymeinverein.models.member.MemberType`).
    """

    def __init__(
        self,
        transport: Transport,
        club_id: int,
        lists: ListsAPI,
        master_data: MasterDataAPI,
    ) -> None:
        self._transport = transport
        self._lists = lists
        self._master_data = master_data
        self._base = f"/protected/club/{club_id}"
        self._legacy = f"/protected/mv365/clubs/{club_id}"
        self._public = f"/mv365/clubs/{club_id}"
        #: Bulk edits of many members at once.
        self.bulk = MemberBulkAPI(transport, club_id, master_data)

    # ----------------------------------------------------------------- reading

    async def get(self, member_id: int) -> Member:
        """Return one member with all details.

        Raises :class:`~pymeinverein.exceptions.NotFoundError` for unknown ids.
        ``GET /protected/club/{clubId}/members/{memberId}``
        """
        path = f"{self._base}/members/{member_id}"
        payload = await self._transport.get(path)
        return Member.model_validate(unwrap(payload, "data", f"GET {path}"))

    async def query(self, criteria: Iterable[Criterion] = ()) -> builtins.list[Member]:
        """Return members selected by the server with list style criteria.

        Each criterion is ``(column, operator, value)``, for example
        ``("state", "=", 1)`` for former members. Without criteria everyone is
        returned. The rows have no department names; use :meth:`list` for those.
        ``POST /protected/club/{clubId}/list/all-members`` without a version
        header (with ``x-api-version: v2`` the API only sends id, names, type,
        state, roles and birthday).
        """
        rules: builtins.list[dict[str, str | None]] = []
        for criterion in criteria:
            if isinstance(criterion, ListCriterion):
                criterion = (
                    criterion.column_name,
                    criterion.operator,
                    criterion.value,
                )
            column, operator, value = criterion
            rules.append(
                {
                    "columnName": column,
                    "operator": operator,
                    "value": None if value is None else str(value),
                }
            )
        path = f"{self._base}/list/all-members"
        payload = await self._transport.post(path, {"criterias": rules})
        rows = unwrap(payload, "data", f"POST {path}")
        return [Member.model_validate(row) for row in rows]

    async def next_number(self, type: MemberType = MemberType.MEMBER) -> str:
        """Return the member number MeinVerein would assign next.

        ``GET /protected/mv365/clubs/{clubId}/members/next-number/{type}``
        """
        path = f"{self._legacy}/members/next-number/{int(type)}"
        data = unwrap(await self._transport.get(path), "data", f"GET {path}")
        return str(unwrap(data, "next", f"GET {path}"))

    async def user_exists(self, email: str) -> bool:
        """Tell whether a MeinVerein *user account* with this e-mail exists.

        This is about login accounts, not about members of the club: several
        members may share an e-mail address.
        ``GET /protected/club/{clubId}/user/exists?email=...``
        """
        payload = await self._transport.get(
            f"{self._base}/user/exists", params={"email": email}
        )
        return payload is True

    async def picture(self, member_id: int, size: str = "medium") -> bytes:
        """Return the member's picture (JPEG); ``size`` is small, medium or large.

        ``GET /mv365/clubs/{clubId}/members/{memberId}/image?type={size}``
        """
        return await self._transport.request_bytes(
            "GET", f"{self._public}/members/{member_id}/image", params={"type": size}
        )

    # ----------------------------------------------------------------- writing

    async def create(
        self,
        *,
        last_name: str,
        first_name: str | None = None,
        type: MemberType = MemberType.MEMBER,
        is_person: bool | None = None,
        **fields: Any,
    ) -> Member:
        """Create a member (or a contact / company with ``type=``).

        ``last_name`` is the only field the API requires; for companies it is
        the company name. Further fields are passed by name, in ``snake_case``
        or in the API's ``camelCase``::

            await club.members.create(
                first_name="Ada",
                last_name="Lovelace",
                email="ada@example.org",
                birthday=date(1815, 12, 10),
                address={"address_line1": "Main St 1", "zip": "12345", "city": "X"},
            )

        The member number is assigned by MeinVerein unless ``member_id`` is given.
        Returns the created member as stored by the server.

        ``POST /protected/mv365/clubs/{clubId}/members``. (The web application
        has a second create call, ``POST /protected/club/{clubId}/members``,
        for its quick "new contact" dialog. That one silently ignores most
        fields - birthday, gender, notes, ... - so it is not used here.)
        """
        if is_person is None:
            is_person = type != MemberType.COMPANY
        body: dict[str, Any] = {
            "lastName": last_name,
            "type": int(type),
            "isPerson": 1 if is_person else 0,
        }
        if first_name is not None:
            body["firstName"] = first_name
        body.update(to_payload(fields))
        path = f"{self._legacy}/members"
        payload = await self._transport.post(path, body)
        created = unwrap(payload, "clubMember", f"POST {path}")
        # Read it back through the detail call so the result has the same
        # shape as get() (the create answer lacks, for example, the country name).
        return await self.get(int(unwrap(created, "id", f"POST {path}")))

    async def update(self, member_id: int, **changes: Any) -> Member:
        """Change fields of a member and return the updated member.

        Pass the fields to change by name (``snake_case`` or ``camelCase``). A
        dict given for ``address`` or ``notifications`` is merged into the
        existing value, so ``address={"city": "Berlin"}`` keeps the street.

        Why this is not a plain partial update: the API accepts partial bodies
        but silently clears some fields that are left out (the e-mail address,
        for one). Like the web application, this method therefore loads the
        member, applies the changes and sends the whole object back.

        ``GET`` then ``PATCH /protected/mv365/clubs/{clubId}/members/{memberId}``,
        both with ``x-api-version: v2`` like the web application.
        """
        path = f"{self._legacy}/members/{member_id}"
        current = unwrap(
            await self._transport.get(path, api_version="v2"),
            "clubMember",
            f"GET {path}",
        )
        body: dict[str, Any] = dict(current)
        for key, value in to_payload(changes).items():
            if isinstance(value, Mapping) and isinstance(body.get(key), Mapping):
                body[key] = {**body[key], **value}
            else:
                body[key] = value
        payload = await self._transport.patch(path, body, api_version="v2")
        return Member.model_validate(unwrap(payload, "clubMember", f"PATCH {path}"))

    async def delete(
        self,
        *member_ids: int,
        force_payers: bool = False,
        missing_ok: bool = False,
    ) -> DeleteResult:
        """Delete one or more members permanently.

        The API reports success even for ids that do not exist. Unless
        ``missing_ok`` is set, every id is therefore checked first and
        :class:`~pymeinverein.exceptions.NotFoundError` is raised before
        anything is deleted.

        ``force_payers`` also deletes members who pay for other members; without
        it the API skips them (see ``skipped_count`` of the result).
        ``POST /protected/club/{clubId}/members/delete``
        """
        if not member_ids:
            return DeleteResult()
        if not missing_ok:
            for member_id in member_ids:
                await self.get(member_id)
        path = f"{self._base}/members/delete"
        payload = await self._transport.post(
            path,
            {"clubMemberIds": list(member_ids), "forcePayersDelete": force_payers},
        )
        return DeleteResult.model_validate(unwrap(payload, "meta", f"POST {path}"))

    # ------------------------------------------------------------ custom fields

    async def set_custom_field(
        self, member_id: int, field: int | str | IndividualField, value: Any
    ) -> None:
        """Set the value of a custom field ("individuelles Feld") for one member.

        ``field`` is the id or the name of the field. ``value`` may be text, a
        number, a date, a boolean or - for multiple choice fields - a list. The
        API stores everything as text. A multiple choice field stores ``null``
        for values that are not among its options (they are lost; reading
        leaves them out); other fields were not seen to check their options.
        ``PUT /protected/club/{clubId}/list/individual-field-data``
        """
        field_id = await self._master_data.resolve_individual_field(field)
        await self._transport.put(
            f"{self._base}/list/individual-field-data",
            {
                "individualFieldId": field_id,
                "clubMemberId": member_id,
                "values": custom_values(value),
            },
        )

    async def clear_custom_field(
        self, member_id: int, field: int | str | IndividualField
    ) -> None:
        """Remove a member's value of a custom field.

        ``DELETE /protected/club/{clubId}/list/individual-field-data/``
        """
        field_id = await self._master_data.resolve_individual_field(field)
        await self._transport.delete(
            f"{self._base}/list/individual-field-data/",
            {"clubMemberId": member_id, "individualFieldId": field_id},
        )

    # ----------------------------------------------------------------- pictures

    async def set_picture(
        self,
        member_id: int,
        image: bytes | str | Path,
        *,
        content_type: str = "image/jpeg",
    ) -> None:
        """Upload a member's picture, given as bytes or as path of an image file.

        ``POST /protected/mv365/clubs/{clubId}/members/{memberId}/images``
        (multipart form, field ``memberPicture``)
        """
        if not isinstance(image, bytes):
            image = await asyncio.to_thread(Path(image).read_bytes)
        form = aiohttp.FormData(quote_fields=False)
        form.add_field(
            "memberPicture", image, filename="picture", content_type=content_type
        )
        await self._transport.post_form(
            f"{self._legacy}/members/{member_id}/images", form
        )

    async def delete_picture(self, member_id: int) -> None:
        """Remove a member's picture.

        ``DELETE /protected/mv365/clubs/{clubId}/members/{memberId}/images``
        """
        await self._transport.delete(f"{self._legacy}/members/{member_id}/images")

    # --------------------------------------------------------------- membership

    async def set_membership(
        self,
        member_id: int,
        department: int | str | SubArea | None = None,
        *,
        start: date | None = None,
        end: date | None = None,
        status: MemberState | None = None,
        honoured: bool | None = None,
    ) -> Member:
        """Add or change a member's membership period in a department.

        MeinVerein records membership as *periods* ("histories"): one per
        department or function, each with start, end and status. The member's
        overall status is derived from them - setting ``state`` directly has no
        effect.

        If the member already has a period for ``department`` it is changed
        (only the arguments you pass); otherwise a new one is added, starting at
        ``start`` (default: the member's membership begin, else today).
        ``department`` is an id, a unique name or a path like
        ``"1. Mannschaft - Damen/Spieler"``; ``None`` means the club as a whole.

        Like :meth:`update` this loads the member and sends the whole object
        back (``GET`` + ``PATCH /protected/mv365/clubs/{clubId}/members/{id}``).
        """
        sub_area_id = (
            None
            if department is None
            else await self._master_data.resolve_sub_area(department)
        )
        path = f"{self._legacy}/members/{member_id}"
        current = unwrap(
            await self._transport.get(path, api_version="v2"),
            "clubMember",
            f"GET {path}",
        )
        histories = [dict(item) for item in current.get("histories") or []]
        period = next(
            (item for item in histories if item.get("subAreaId") == sub_area_id), None
        )
        if period is None:
            begin = start or current.get("membershipBeginAt") or date.today()
            period = {
                "subAreaId": sub_area_id,
                "membershipStart": to_payload(begin),
                "membershipEnd": None,
                "status": int(MemberState.ACTIVE),
                "isHonoured": False,
            }
            histories.append(period)
        elif start is not None:
            period["membershipStart"] = to_payload(start)
        if end is not None:
            period["membershipEnd"] = to_payload(end)
        if status is not None:
            period["status"] = int(status)
        if honoured is not None:
            period["isHonoured"] = honoured
        period["isFormer"] = period["status"] == MemberState.FORMER
        return await self.update(member_id, histories=histories)

    async def set_memberships(
        self,
        member_id: int,
        periods: Iterable[MembershipPeriod],
        *,
        replace: bool = False,
    ) -> Member:
        """Set several membership periods of a member with one update.

        Each :class:`~pymeinverein.models.member.MembershipPeriod` describes the
        complete period for its department: start, end (``None`` = open, an
        existing end date is removed), status and honour. A period the member
        already has for that department is changed in place, otherwise one is
        added. Periods for other departments are kept, unless ``replace`` is
        set; then they are removed.

        A department may appear only once. Like :meth:`update` this loads the
        member and sends the whole object back
        (``GET`` + ``PATCH /protected/mv365/clubs/{clubId}/members/{id}``).
        """
        wanted: dict[int | None, MembershipPeriod] = {}
        for period in periods:
            sub_area_id = (
                None
                if period.department is None
                else await self._master_data.resolve_sub_area(period.department)
            )
            if sub_area_id in wanted:
                raise ValueError(
                    f"Department {period.department!r} is given more than once"
                )
            wanted[sub_area_id] = period

        path = f"{self._legacy}/members/{member_id}"
        current = unwrap(
            await self._transport.get(path, api_version="v2"),
            "clubMember",
            f"GET {path}",
        )
        histories: builtins.list[dict[str, Any]] = []
        seen: set[int | None] = set()
        for item in current.get("histories") or []:
            sub_area_id = item.get("subAreaId")
            if sub_area_id in wanted and sub_area_id not in seen:
                seen.add(sub_area_id)
                histories.append(_period_body(dict(item), wanted[sub_area_id]))
            elif not replace:
                histories.append(dict(item))
        for sub_area_id, period in wanted.items():
            if sub_area_id not in seen:
                histories.append(_period_body({"subAreaId": sub_area_id}, period))
        return await self.update(member_id, histories=histories)

    async def end_membership(self, member_id: int, end: date | None = None) -> Member:
        """Make a member a former member as of ``end`` (default: today).

        All open membership periods are closed and marked as former. A member
        without any period gets one for the club as a whole, so the end date is
        recorded.
        """
        end = end or date.today()
        path = f"{self._legacy}/members/{member_id}"
        current = unwrap(
            await self._transport.get(path, api_version="v2"),
            "clubMember",
            f"GET {path}",
        )
        histories = [dict(item) for item in current.get("histories") or []]
        if not histories:
            begin = current.get("membershipBeginAt") or end
            histories.append(
                {
                    "subAreaId": None,
                    "membershipStart": to_payload(begin),
                    "isHonoured": False,
                }
            )
        for period in histories:
            if not period.get("membershipEnd"):
                period["membershipEnd"] = to_payload(end)
            period["status"] = int(MemberState.FORMER)
            period["isFormer"] = True
        return await self.update(member_id, histories=histories)

    # -------------------------------------------------------------- invitations

    async def invite(
        self,
        *member_ids: int,
        roles: Iterable[int | ClubRole] | None = None,
    ) -> InviteResult:
        """Invite members to the club's MeinVerein portal. **Sends e-mails.**

        Every invited member gets an e-mail with a link to create an account.
        ``roles`` are the roles the members receive once they accept; by
        default the club's built-in member role ("Mitglied").

        Members without e-mail address and members that already have an account
        are not invited; the result counts both groups. A member's progress is
        visible in ``invitation_state``
        (see :class:`~pymeinverein.models.member.InvitationState`).
        ``POST /protected/club/{clubId}/members/invite``
        """
        if roles is None:
            path = f"{self._base}/auth/club-roles"
            available = unwrap(await self._transport.get(path), "data", f"GET {path}")
            role_ids = [
                int(role["id"])
                for role in available
                if role.get("type") == RoleType.MEMBER
            ]
        else:
            role_ids = [
                role.id if isinstance(role, ClubRole) else int(role) for role in roles
            ]
        path = f"{self._base}/members/invite"
        payload = await self._transport.post(
            path, {"memberIds": list(member_ids), "clubRoleIds": role_ids}
        )
        return InviteResult.model_validate(unwrap(payload, "data", f"POST {path}"))

    async def revoke_invitation(self, member_id: int) -> None:
        """Withdraw an invitation that was not accepted yet.

        ``POST /protected/mv365/clubs/{clubId}/members/{memberId}/invite/revoke``
        """
        await self._transport.post(f"{self._legacy}/members/{member_id}/invite/revoke")

    async def join_requests(self) -> builtins.list[Member]:
        """Return people who asked to join the club and wait for an answer.

        ``GET /protected/club/{clubId}/requested-members``
        """
        path = f"{self._base}/requested-members"
        payload = await self._transport.get(path)
        requests = unwrap(payload, "data", f"GET {path}")
        return [Member.model_validate(item) for item in requests]

    async def accept_join_request(self, member_id: int) -> None:
        """Accept a request to join the club.

        Not verified against the real service (the demo club has no requests).
        ``POST /protected/club/{clubId}/members/{memberId}/join/accept``
        """
        await self._transport.post(f"{self._base}/members/{member_id}/join/accept")

    async def reject_join_request(self, member_id: int) -> None:
        """Reject a request to join the club.

        Not verified against the real service (the demo club has no requests).
        ``POST /protected/club/{clubId}/members/{memberId}/join/reject``
        """
        await self._transport.post(f"{self._base}/members/{member_id}/join/reject")

    # ------------------------------------------------------ listing and export

    async def export(
        self,
        path: str | Path | None = None,
        *,
        format: ExportFormat | None = None,
        fields: FieldSpec = "minimal",
        omit_empty: bool = False,
        delimiter: str = ",",
        encoding: str = "utf-8",
        from_list: ListRef | None = None,
        type: MemberType | str | int | None = None,
        status: MemberState | str | int | None = None,
        department: str | int | None = None,
        role: str | int | None = None,
        search: str | None = None,
        where: Callable[[Member], bool] | None = None,
    ) -> str:
        """Export members as JSON or CSV and return the text.

        With ``path`` the text is also written to that file; the format then
        defaults to the file extension (``.json`` or ``.csv``), otherwise to
        JSON. ``fields`` is a field set (``"minimal"``, ``"contact"``,
        ``"full"``), a list of fields or a mapping ``header -> field``; see
        :mod:`pymeinverein.export`. The filter arguments are those of
        :meth:`list`.
        """
        target = Path(path) if path is not None else None
        if format is None:
            suffix = target.suffix.lower() if target else ".json"
            if suffix not in (".json", ".csv"):
                raise ValueError(
                    f"Cannot derive the format from {str(target)!r}; pass format="
                )
            format = "csv" if suffix == ".csv" else "json"

        columns = resolve_fields(fields)
        individual_fields: builtins.list[IndividualField] = []
        if any(field.startswith("custom.") for _, field in columns):
            individual_fields = await self._master_data.individual_fields()
        members = await self.list(
            from_list=from_list,
            type=type,
            status=status,
            department=department,
            role=role,
            search=search,
            where=where,
        )
        text = export_members(
            members,
            format,
            fields=fields,
            individual_fields=individual_fields,
            omit_empty=omit_empty,
            delimiter=delimiter,
        )
        if target is not None:
            await asyncio.to_thread(
                target.write_text, text, encoding=encoding, newline=""
            )
        return text

    async def list(
        self,
        *,
        from_list: ListRef | None = None,
        type: MemberType | str | int | None = None,
        status: MemberState | str | int | None = None,
        department: str | int | None = None,
        role: str | int | None = None,
        search: str | None = None,
        where: Callable[[Member], bool] | None = None,
    ) -> builtins.list[Member]:
        """Return members, optionally filtered.

        ``from_list`` chooses the list to read (id, name or default list type);
        by default the list of everyone (members, former members and contacts)
        is used. The other arguments narrow the result down, see
        :class:`~pymeinverein.filters.MemberFilter`::

            await club.members.list(type="member", status="active")
            await club.members.list(department="1. Mannschaft - Damen")
            await club.members.list(from_list="Vorstand")

        The rows contain department names, roles and custom field values but
        not every detail; use :meth:`get` for the full record of one member.
        """
        member_filter = MemberFilter(
            type=type,
            status=status,
            department=department,
            role=role,
            search=search,
            where=where,
        )
        if from_list is None:
            try:
                everyone = await self._lists.get(DefaultListType.ALL_CONTACTS)
            except LookupFailedError:
                # No such default list (unexpected): ask the server for everyone.
                return member_filter.apply(await self.query())
            members = await self._lists.members(everyone)
        else:
            members = await self._lists.members(from_list)
        return member_filter.apply(members)
