"""Live test for invitations. **Sends one real e-mail** - opt-in twice over.

Besides ``-m live`` it needs the address the invitation may go to::

    MEINVEREIN_TEST_INVITE_EMAIL=you@example.org uv run pytest -m live \\
        tests/live/test_invitations.py

Without the variable the test is skipped, so a plain live run sends nothing.
"""

from __future__ import annotations

import os

import pytest

from pymeinverein.api.clubs import ClubClient
from pymeinverein.models import InvitationState

from .conftest import MARKER

pytestmark = pytest.mark.live


async def test_invite_and_revoke(demo_club: ClubClient) -> None:
    address = os.environ.get("MEINVEREIN_TEST_INVITE_EMAIL")
    if not address:
        pytest.skip("MEINVEREIN_TEST_INVITE_EMAIL is not set; no e-mail is sent")
    club = demo_club
    member = await club.members.create(
        first_name=MARKER, last_name="Invitee", email=address
    )
    assert member.invitation_state == InvitationState.NOT_INVITED

    result = await club.members.invite(member.id)
    assert (result.invited, result.not_invited) == (1, 0)
    invited = await club.members.get(member.id)
    assert invited.invitation_state == InvitationState.INVITED
    assert invited.invited_at is not None

    await club.members.revoke_invitation(member.id)
    revoked = await club.members.get(member.id)
    assert revoked.invitation_state == InvitationState.REVOKED


async def test_join_requests_can_be_read(demo_club: ClubClient) -> None:
    assert isinstance(await demo_club.members.join_requests(), list)
