"""Members: read, create, change, delete.

Quirks copied from the real API:

* ``PATCH .../members/{id}`` needs ``lastName``, replaces ``address`` as a whole
  and clears the e-mail address when the body has no ``email``.
* ``POST .../members/delete`` counts unknown ids as deleted.
* ``DELETE .../members/{id}`` does not exist (``404``).
* ``POST /protected/club/{id}/members`` (the quick-create call) stores only a
  few fields; ``POST /protected/mv365/clubs/{id}/members`` stores all of them.
* A member's ``state`` is derived from the membership periods (``histories``);
  sending ``state`` or ``membershipEndAt`` has no effect.
* Custom field values are stored as given; options are not checked.
"""

from __future__ import annotations

from aiohttp import web

from .. import seed
from .._responses import api_error, bad_request, data, not_found
from ..state import Json, now_iso
from ._base import NEW, OLD, RouteGroup, json_body, public

_READ_ONLY = {"id", "clubId", "createdAt"}
_DERIVED = ("state", "membershipEndAt", "isHonoured", "pictureExists")
#: The only fields the quick-create call was seen to store.
_QUICK_CREATE_FIELDS = {
    "firstName",
    "lastName",
    "type",
    "isPerson",
    "email",
    "phone",
    "address",
}


class MemberRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        router.add_post(f"{NEW}/members", self.quick_create_member)
        router.add_post(f"{OLD}/members", self.create_member)
        router.add_post(f"{NEW}/members/delete", self.delete_members)
        router.add_get(f"{NEW}/members/{{member_id}}", self.get_member)
        router.add_get(f"{OLD}/members/next-number/{{kind}}", self.next_number)
        router.add_get(f"{OLD}/members/{{member_id}}", self.get_member_legacy)
        router.add_patch(f"{OLD}/members/{{member_id}}", self.patch_member)
        router.add_get(f"{NEW}/user/exists", self.user_exists)
        router.add_get(
            "/mv365/clubs/{club_id}/members/{member_id}/image", self.member_image
        )
        router.add_post(f"{OLD}/members/{{member_id}}/images", self.upload_image)
        router.add_delete(f"{OLD}/members/{{member_id}}/images", self.delete_image)
        field_data = f"{NEW}/list/individual-field-data"
        router.add_post(field_data, self.set_field_value)
        router.add_put(field_data, self.set_field_value)
        router.add_delete(field_data + "/", self.delete_field_value)

    async def get_member(self, request: web.Request) -> web.Response:
        member = self._member(request)
        if member is None:
            return not_found()
        return web.json_response({"data": self._detail(member, with_country=True)})

    async def get_member_legacy(self, request: web.Request) -> web.Response:
        member = self._member(request)
        if member is None:
            return not_found()
        return web.json_response({"clubMember": public(member)})

    async def _new_member(self, request: web.Request) -> Json | web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        if not isinstance(body, dict) or not isinstance(body.get("lastName"), str):
            problem = {"location": "body", "param": "lastName", "msg": "Invalid value"}
            return bad_request("lastName", problem, problem)
        fields = {k: v for k, v in body.items() if k not in ("id", "clubId")}
        if request.path.startswith("/protected/club/"):
            fields = {k: v for k, v in fields.items() if k in _QUICK_CREATE_FIELDS}
        if fields.get("memberId") is None:
            fields.pop("memberId", None)
        return self.state.add_member(club_id, fields)

    async def create_member(self, request: web.Request) -> web.Response:
        member = await self._new_member(request)
        if isinstance(member, web.Response):
            return member
        return web.json_response({"clubMember": public(member)})

    async def quick_create_member(self, request: web.Request) -> web.Response:
        member = await self._new_member(request)
        if isinstance(member, web.Response):
            return member
        return web.json_response({"data": {"id": member["id"]}})

    async def patch_member(self, request: web.Request) -> web.Response:
        member = self._member(request)
        if member is None:
            return not_found()
        body = await json_body(request)
        last_name = body.get("lastName") if isinstance(body, dict) else None
        if not isinstance(last_name, str) or not last_name:
            return api_error(
                400,
                "BadRequestError",
                [{"location": "body", "param": "lastName", "msg": "Invalid value"}],
            )
        derived = {key: member.get(key) for key in _DERIVED}
        for key, value in body.items():
            if key not in _READ_ONLY and not key.startswith("_"):
                member[key] = value
        # The status follows from the membership periods; it cannot be set.
        member.update(derived)
        self.state.sync_membership(member)
        if "email" not in body:
            # Observed quirk: a body without "email" clears the address.
            member["email"] = ""
        for key in ("birthday", "membershipBeginAt", "membershipEndAt"):
            member[key] = seed.iso_day(member.get(key))
        member["updatedAt"] = member["editedAtDate"] = now_iso()
        return web.json_response({"clubMember": public(member)})

    async def delete_members(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        ids = body.get("clubMemberIds") if isinstance(body, dict) else None
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            return bad_request("clubMemberIds")
        for member_id in ids:
            self.state.members[club_id].pop(member_id, None)
            self.state.member_roles.pop(member_id, None)
            for item in self.state.lists[club_id].values():
                if member_id in item["_member_ids"]:
                    item["_member_ids"].remove(member_id)
        # Observed quirk: ids that never existed are counted as deleted too.
        return web.json_response(
            {"meta": {"deletedCount": len(ids), "skippedCount": 0}}
        )

    async def next_number(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        if not request.match_info["kind"].isdecimal():
            return bad_request("requestParameter")
        return data({"next": self.state.next_member_number(club_id)})

    async def user_exists(self, request: web.Request) -> web.Response:
        if self._club_id(request) is None:
            return not_found()
        return web.json_response(request.query.get("email", "") in self.state.users)

    async def member_image(self, request: web.Request) -> web.Response:
        member = self._member(request)
        if member is None or member["id"] not in self.state.pictures:
            return not_found()
        return web.Response(
            body=self.state.pictures[member["id"]], content_type="image/jpeg"
        )

    async def upload_image(self, request: web.Request) -> web.Response:
        member = self._member(request)
        if member is None:
            return not_found()
        form = await request.post()
        upload = form.get("memberPicture")
        if not isinstance(upload, web.FileField):
            return bad_request("memberPicture")
        self.state.pictures[member["id"]] = upload.file.read()
        member["pictureExists"] = True
        return web.json_response({})

    async def delete_image(self, request: web.Request) -> web.Response:
        member = self._member(request)
        if member is None:
            return not_found()
        self.state.pictures.pop(member["id"], None)
        member["pictureExists"] = False
        return web.json_response({})

    # ------------------------------------------------------- custom field values

    def _field_target(self, request: web.Request, body: object) -> Json | None:
        club_id = self._club_id(request)
        if club_id is None or not isinstance(body, dict):
            return None
        member_id = body.get("clubMemberId")
        if not isinstance(member_id, int):
            return None
        member = self.state.members[club_id].get(member_id)
        known = {field["id"] for field in self.state.individual_fields[club_id]}
        if member is None or body.get("individualFieldId") not in known:
            return None
        return member

    async def set_field_value(self, request: web.Request) -> web.Response:
        """``POST`` and ``PUT`` both create or replace the value."""
        body = await json_body(request)
        member = self._field_target(request, body)
        if member is None:
            return not_found()
        values = body.get("values")
        if not isinstance(values, list):
            return bad_request("values")
        set_custom_value(member, body["individualFieldId"], values)
        return data(
            {
                "clubId": member["clubId"],
                "clubMemberId": member["id"],
                "individualFieldId": body["individualFieldId"],
                "values": values,
            }
        )

    async def delete_field_value(self, request: web.Request) -> web.Response:
        body = await json_body(request)
        member = self._field_target(request, body)
        if member is None:
            return not_found()
        set_custom_value(member, body["individualFieldId"], None)
        return web.Response(status=200)


def set_custom_value(member: Json, field_id: int, values: list[str] | None) -> None:
    """Replace (or with ``None`` remove) a member's value of a custom field."""
    kept = [
        item
        for item in member.get("memberIndividualFieldData", [])
        if item["individualFieldId"] != field_id
    ]
    if values is not None:
        kept.append(
            {
                "clubId": member["clubId"],
                "clubMemberId": member["id"],
                "individualFieldId": field_id,
                "values": values,
            }
        )
    member["memberIndividualFieldData"] = kept
