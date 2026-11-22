"""Invitations to the member portal and requests to join the club.

Nothing is e-mailed: invitations are recorded in ``state.sent_invitations``.

Observed on the real API: inviting sets ``invitationState`` to 1 (invited) and
``invitedAt``; revoking answers ``204`` and sets the state to 3 (revoked).
The join request handlers are assumptions - the real ones could not be tried.
"""

from __future__ import annotations

from aiohttp import web

from .._responses import bad_request, data, not_found
from ..state import now_iso
from ._base import NEW, OLD, RouteGroup, json_body

ACCEPTED, INVITED, REQUESTED, REVOKED, NOT_INVITED, REJECTED = range(6)


class InvitationRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        router.add_post(f"{NEW}/members/invite", self.invite)
        router.add_post(f"{OLD}/members/{{member_id}}/invite/revoke", self.revoke)
        router.add_get(f"{NEW}/requested-members", self.requested)
        router.add_post(f"{NEW}/members/{{member_id}}/join/accept", self.accept)
        router.add_post(f"{NEW}/members/{{member_id}}/join/reject", self.reject)

    async def invite(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        ids = body.get("memberIds") if isinstance(body, dict) else None
        role_ids = body.get("clubRoleIds") if isinstance(body, dict) else None
        if not isinstance(ids, list) or not isinstance(role_ids, list):
            return bad_request("memberIds")
        invited = 0
        for member_id in ids:
            member = self.state.members[club_id].get(member_id)
            if (
                member is None
                or not member.get("email")
                or member["invitationState"] in (ACCEPTED, REQUESTED)
                or member.get("userId") is not None
            ):
                continue
            member["invitationState"] = INVITED
            member["invitedAt"] = now_iso()
            member["_invited_roles"] = list(role_ids)
            self.state.sent_invitations.append((member_id, member["email"]))
            invited += 1
        return web.json_response(
            {"data": {"invited": invited, "notInvited": len(ids) - invited}}
        )

    async def revoke(self, request: web.Request) -> web.Response:
        member = self._member(request)
        if member is None:
            return not_found()
        if member["invitationState"] == INVITED:
            member["invitationState"] = REVOKED
        return web.Response(status=204)

    async def requested(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        return data(
            [
                self._detail(member, with_country=True)
                for member in self.state.members[club_id].values()
                if member["invitationState"] == REQUESTED
            ]
        )

    async def accept(self, request: web.Request) -> web.Response:
        member = self._member(request)
        if member is None or member["invitationState"] != REQUESTED:
            return not_found()
        member["invitationState"] = ACCEPTED
        member["userId"] = self.state.next_id()
        return web.json_response({})

    async def reject(self, request: web.Request) -> web.Response:
        member = self._member(request)
        if member is None or member["invitationState"] != REQUESTED:
            return not_found()
        member["invitationState"] = REJECTED
        return web.json_response({})
