"""Mailings against the mock server (nothing is e-mailed)."""

from __future__ import annotations

import pytest

from pymeinverein import MeinVereinClient, NotFoundError, SendingDisabledError
from pymeinverein.api.clubs import ClubClient
from pymeinverein.testing import REGULAR_CLUB_ID, MockServer

ERIKA, MAX = 7002, 7003


async def test_template_lifecycle(club: ClubClient) -> None:
    assert await club.mailing.templates() == []
    created = await club.mailing.create_template(
        "Einladung", "Einladung zur Versammlung", "<p>Hallo</p>"
    )
    assert (created.name, created.subject, created.state) == (
        "Einladung",
        "Einladung zur Versammlung",
        5,
    )
    updated = await club.mailing.update_template(created.id, html="<p>Hallo 2</p>")
    assert (updated.subject, updated.html) == (
        "Einladung zur Versammlung",
        "<p>Hallo 2</p>",
    )
    assert [t.id for t in await club.mailing.templates()] == [created.id]
    assert await club.mailing.delete(created.id) == 1
    assert await club.mailing.templates() == []
    with pytest.raises(NotFoundError):
        await club.mailing.template(created.id)


async def test_draft_lifecycle(club: ClubClient) -> None:
    draft = await club.mailing.create_draft(
        "Rundmail",
        "Training fällt aus",
        "<p>Heute kein Training.</p>",
        recipients=[ERIKA],
    )
    assert draft.state == 2 and draft.dispatch_number == "SE-1"
    assert [r["email"] for r in draft.receiver] == ["erika.beispiel@example.org"]

    changed = await club.mailing.update_draft(draft.id, subject="Training fällt aus!")
    assert changed.subject == "Training fällt aus!"
    assert [r["id"] for r in changed.receiver] == [ERIKA]  # recipients kept

    both = await club.mailing.update_draft(draft.id, recipients=[ERIKA, MAX])
    assert [r["id"] for r in both.receiver] == [ERIKA, MAX]
    assert [d.id for d in await club.mailing.drafts()] == [draft.id]

    template = await club.mailing.create_template("T", "S", "<p>x</p>")
    assert await club.mailing.delete(draft.id, template.id) == 2
    assert await club.mailing.delete() == 0


async def test_preview(club: ClubClient) -> None:
    preview = await club.mailing.preview("Betreff", "<p>Text</p>", recipients=[MAX])
    assert (preview.text, preview.recipient_email) == (
        "<p>Text</p>",
        "max.muster@example.org",
    )


async def test_demo_club_cannot_send(server: MockServer, club: ClubClient) -> None:
    assert await club.mailing.sending_enabled() is False
    server.state.requests.clear()
    with pytest.raises(SendingDisabledError):
        await club.mailing.send("Betreff", "<p>Text</p>", recipients=[ERIKA])
    assert not any(path.endswith("/sendDirect") for _, path in server.state.requests)


async def test_send_and_sent_items(
    server: MockServer, client: MeinVereinClient
) -> None:
    regular = await client.clubs.get(REGULAR_CLUB_ID)
    assert await regular.mailing.sending_enabled() is True
    result = await regular.mailing.send(
        "Willkommen", "<p>Hallo</p>", recipients=[8002], name="Begrüßung"
    )
    assert result == {"sentCount": 1, "failedCount": 0}
    sent = await regular.mailing.sent()
    assert [(i.email, i.subject, i.item_type) for i in sent] == [
        ("clara.echt@example.org", "Willkommen", "Sendung")
    ]
    assert sent[0].receiver is not None and sent[0].receiver.full_name == "Clara Echt"
    assert await regular.mailing.outbox() == []
    assert await regular.mailing.deleted() == []
