"""Live test for mailings: templates, drafts and preview. Nothing is sent."""

from __future__ import annotations

import pytest

from pymeinverein import SendingDisabledError
from pymeinverein.api.clubs import ClubClient

from .conftest import MARKER

pytestmark = pytest.mark.live


async def test_templates_drafts_preview(demo_club: ClubClient) -> None:
    club = demo_club
    try:
        template = await club.mailing.create_template(
            f"{MARKER} template", f"{MARKER} subject", "<p>Hallo</p>"
        )
        updated = await club.mailing.update_template(template.id, html="<p>Hallo 2</p>")
        assert (updated.subject, updated.html) == (
            f"{MARKER} subject",
            "<p>Hallo 2</p>",
        )

        member = await club.members.create(
            first_name=MARKER, last_name="Recipient", email="nobody@example.org"
        )
        draft = await club.mailing.create_draft(
            f"{MARKER} draft",
            f"{MARKER} subject",
            "<p>Entwurf</p>",
            recipients=[member.id],
        )
        assert [r["id"] for r in draft.receiver] == [member.id]
        changed = await club.mailing.update_draft(
            draft.id, subject=f"{MARKER} subject2"
        )
        assert changed.subject == f"{MARKER} subject2"
        assert [r["id"] for r in changed.receiver] == [member.id]

        preview = await club.mailing.preview(
            "Betreff", "<p>Text</p>", recipients=[member.id]
        )
        assert preview.recipient_email == "nobody@example.org"

        assert await club.mailing.delete(template.id, draft.id) == 2
    finally:
        leftovers = [
            item.id
            for item in await club.mailing.drafts() + await club.mailing.templates()
            if MARKER in (item.name or "")
        ]
        await club.mailing.delete(*leftovers)


async def test_sent_items_and_send_guard(demo_club: ClubClient) -> None:
    club = demo_club
    assert isinstance(await club.mailing.sent(), list)
    assert isinstance(await club.mailing.outbox(), list)
    # Demo clubs may not send; the library refuses before calling the API.
    assert await club.mailing.sending_enabled() is False
    with pytest.raises(SendingDisabledError):
        await club.mailing.send("x", "<p>x</p>", recipients=[])
