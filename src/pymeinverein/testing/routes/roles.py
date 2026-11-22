"""Permission roles.

Observed on the real API:

* Roles belong to user accounts. Assigning roles to a member without account
  through ``PUT .../club-members/{id}/assign/club-roles`` makes the service
  fail (it answers with its "Request Rejected" page); the role side call
  ``POST .../club-role/{id}/assign/club-members`` skips such members silently.
* Deleting a role that does not exist fails the same way.
"""

from __future__ import annotations

from aiohttp import web

from .. import seed
from .._responses import bad_request, not_found, rejected
from ..state import Json, now_iso
from ._base import NEW, RouteGroup, json_body


class RoleRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        auth = f"{NEW}/auth"
        router.add_get(f"{auth}/club-roles", self.roles)
        router.add_post(f"{auth}/club-role/create", self.create)
        router.add_put(f"{auth}/club-role/{{role_id}}/update", self.update)
        router.add_delete(f"{auth}/club-role/{{role_id}}", self.delete)
        router.add_get(
            f"{auth}/club-role/{{role_id}}/permissions/all", self.permissions
        )
        router.add_put(f"{auth}/club-role/{{role_id}}/permission-key", self.set_key)
        router.add_post(
            f"{auth}/club-role/{{role_id}}/assign/club-members", self.add_members
        )
        router.add_put(
            f"{auth}/club-role/{{role_id}}/assign/club-members", self.set_members
        )
        router.add_put(
            f"{auth}/club-members/{{member_id}}/assign/club-roles", self.set_roles
        )

    def _role(self, request: web.Request) -> tuple[int, Json] | None:
        club_id = self._club_id(request)
        if club_id is None:
            return None
        for role in self.state.roles[club_id]:
            if str(role["id"]) == request.match_info["role_id"]:
                return club_id, role
        return None

    def _holders(self, club_id: int, role_id: int) -> list[Json]:
        return [
            member
            for member in self.state.members[club_id].values()
            if role_id in self.state.member_roles.get(member["id"], [])
        ]

    def _meta(self, request: web.Request) -> Json:
        return {"params": {"clubId": int(request.match_info["club_id"])}}

    async def roles(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        with_members = request.query.get("withClubUsers") == "true"
        answer = []
        for role in self.state.roles[club_id]:
            holders = self._holders(club_id, role["id"])
            entry = {**role, "memberCount": len(holders), "correspondsTo": "Individual"}
            if with_members:
                entry["members"] = [
                    {
                        "id": member["id"],
                        "firstName": member["firstName"],
                        "lastName": member["lastName"],
                        "memberId": member["memberId"],
                        "invitationState": member["invitationState"],
                    }
                    for member in holders
                ]
            answer.append(entry)
        return web.json_response(
            {"meta": {"count": len(answer), **self._meta(request)}, "data": answer}
        )

    async def create(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not name.strip():
            return bad_request("name")
        timestamp = now_iso()
        role: Json = {
            "id": self.state.next_id(),
            "name": name,
            "description": body.get("description") or "",
            "clubId": club_id,
            "type": 0,
            "isSystemRole": False,
            "isDefault": False,
            "posIndex": len(self.state.roles[club_id]) + 1,
            "updatedAt": timestamp,
            "createdAt": timestamp,
        }
        self.state.roles[club_id].append(role)
        self.state.role_permissions[role["id"]] = seed.default_permissions(0)
        return web.json_response({"meta": self._meta(request), "data": role})

    async def update(self, request: web.Request) -> web.Response:
        found = self._role(request)
        if found is None:
            return not_found()
        _, role = found
        body = await json_body(request)
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not name.strip():
            return bad_request("name")
        role["name"] = name
        role["description"] = body.get("description") or ""
        role["updatedAt"] = now_iso()
        return web.json_response({"meta": self._meta(request)})

    async def delete(self, request: web.Request) -> web.Response:
        found = self._role(request)
        if found is None:
            return rejected()
        club_id, role = found
        self.state.roles[club_id].remove(role)
        self.state.role_permissions.pop(role["id"], None)
        for assigned in self.state.member_roles.values():
            if role["id"] in assigned:
                assigned.remove(role["id"])
        return web.json_response({"meta": self._meta(request)})

    # --------------------------------------------------------------- permissions

    async def permissions(self, request: web.Request) -> web.Response:
        found = self._role(request)
        if found is None:
            return not_found()
        _, role = found
        states = self.state.role_permissions[role["id"]]
        tree = [
            {
                "key": key,
                "name": name,
                "disabled": False,
                "type": 2,
                "state": None,
                "children": [
                    {
                        "key": child_key,
                        "name": child_name,
                        "disabled": False,
                        "type": 0,
                        "state": {
                            "original": states[child_key],
                            "current": states[child_key],
                        },
                    }
                    for child_key, child_name in children
                ],
            }
            for key, name, children in seed.PERMISSION_TREE
        ]
        return web.json_response({"meta": self._meta(request), "data": tree})

    async def set_key(self, request: web.Request) -> web.Response:
        found = self._role(request)
        if found is None:
            return not_found()
        _, role = found
        body = await json_body(request)
        states = self.state.role_permissions[role["id"]]
        key = body.get("key") if isinstance(body, dict) else None
        if key not in states:
            return bad_request("key")
        if body.get("state") not in (0, 1, 2, 3):
            return bad_request("state")
        states[key] = body["state"]
        return web.json_response({"meta": self._meta(request), "data": []})

    # ---------------------------------------------------------------- assignment

    def _has_account(self, club_id: int, member_id: object) -> bool:
        if not isinstance(member_id, int):
            return False
        member = self.state.members[club_id].get(member_id)
        return member is not None and member.get("userId") is not None

    async def add_members(self, request: web.Request) -> web.Response:
        found = self._role(request)
        if found is None:
            return not_found()
        club_id, role = found
        body = await json_body(request)
        ids = body.get("clubMemberIds") if isinstance(body, dict) else None
        if not isinstance(ids, list):
            return bad_request("clubMemberIds")
        assigned = []
        for member_id in ids:
            if not self._has_account(club_id, member_id):
                continue  # skipped without notice
            roles = self.state.member_roles.setdefault(member_id, [])
            if role["id"] not in roles:
                roles.append(role["id"])
            assigned.append({"clubUserId": member_id + 1, "clubMemberId": member_id})
        return web.json_response({"meta": self._meta(request), "data": assigned})

    async def set_members(self, request: web.Request) -> web.Response:
        found = self._role(request)
        if found is None:
            return not_found()
        club_id, role = found
        body = await json_body(request)
        ids = body.get("clubMemberIds") if isinstance(body, dict) else None
        if not isinstance(ids, list):
            return bad_request("clubMemberIds")
        for member in self.state.members[club_id].values():
            roles = self.state.member_roles.setdefault(member["id"], [])
            wanted = member["id"] in ids and self._has_account(club_id, member["id"])
            if wanted and role["id"] not in roles:
                roles.append(role["id"])
            elif not wanted and role["id"] in roles:
                roles.remove(role["id"])
        return web.json_response({"meta": self._meta(request), "data": []})

    async def set_roles(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        raw = request.match_info["member_id"]
        if club_id is None or not raw.isdecimal():
            return not_found()
        if not self._has_account(club_id, int(raw)):
            return rejected()
        body = await json_body(request)
        ids = body.get("clubRoleIds") if isinstance(body, dict) else None
        if not isinstance(ids, list):
            return bad_request("clubRoleIds")
        known = {role["id"] for role in self.state.roles[club_id]}
        self.state.member_roles[int(raw)] = [i for i in ids if i in known]
        return web.json_response({"meta": self._meta(request), "data": []})
