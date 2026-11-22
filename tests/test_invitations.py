"""Invitations and join requests against the mock server (no e-mail is sent)."""

from __future__ import annotations

import pytest

from pymeinverein import NotFoundError
from pymeinverein.api.clubs import ClubClient
from pymeinverein.models import InvitationState
from pymeinverein.testing import DEMO_CLUB_ID, MockServer, seed

OWNER, LENA, JONAS, GRETA = 7001, 7004, 7005, 7006


async def test_invite_and_revoke(server: MockServer, club: ClubClient) -> None:
    result = await club.members.invite(LENA)
    assert (result.invited, result.not_invited) == (1, 0)
    assert server.state.sent_invitations == [(LENA, "lena.probe@example.org")]

    lena = await club.members.get(LENA)
    assert lena.invitation_state == InvitationState.INVITED
    assert lena.invited_at is not None
    # By default the built-in member role is requested for the new account.
    stored = server.state.members[DEMO_CLUB_ID][LENA]
    assert stored["_invited_roles"] == [seed.ROLE_MEMBER]
    assert "_invited_roles" not in lena.to_api()

    await club.members.revoke_invitation(LENA)
    assert (await club.members.get(LENA)).invitation_state == InvitationState.REVOKED


async def test_invite_several_with_roles(server: MockServer, club: ClubClient) -> None:
    manager = await club.roles.get("Verwalter")
    # Jonas has no e-mail address, the owner already has an account.
    result = await club.members.invite(LENA, JONAS, OWNER, GRETA, roles=[manager])
    assert (result.invited, result.not_invited) == (2, 2)
    assert [member_id for member_id, _ in server.state.sent_invitations] == [
        LENA,
        GRETA,
    ]
    stored = server.state.members[DEMO_CLUB_ID][GRETA]
    assert stored["_invited_roles"] == [seed.ROLE_MANAGER]


async def test_revoke_unknown_member(club: ClubClient) -> None:
    with pytest.raises(NotFoundError):
        await club.members.revoke_invitation(1)


async def test_join_requests(server: MockServer, club: ClubClient) -> None:
    assert await club.members.join_requests() == []
    for name in ("Anna", "Bert"):
        server.state.add_member(
            DEMO_CLUB_ID,
            {"firstName": name, "lastName": "Anfrage", "invitationState": 2},
        )
    requests = await club.members.join_requests()
    assert [m.first_name for m in requests] == ["Anna", "Bert"]
    assert all(m.invitation_state == InvitationState.REQUESTED for m in requests)

    await club.members.accept_join_request(requests[0].id)
    await club.members.reject_join_request(requests[1].id)
    assert await club.members.join_requests() == []
    states = [(await club.members.get(m.id)).invitation_state for m in requests]
    assert states == [InvitationState.ACCEPTED, InvitationState.REJECTED]
    with pytest.raises(NotFoundError):
        await club.members.accept_join_request(requests[0].id)
