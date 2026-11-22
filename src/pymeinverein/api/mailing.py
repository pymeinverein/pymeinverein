"""Mailings ("Korrespondenz"): templates, drafts and sending.

Sending is guarded: :meth:`MailingAPI.send` checks first that the club may send
e-mail at all. Demo clubs may not, so the sending call itself could not be
verified against the real service.
"""

from __future__ import annotations

import builtins
from collections.abc import Iterable
from typing import Any

from .._transport import Transport
from ..exceptions import MeinVereinError
from ..models.mailing import Dispatch, DispatchItem, MailPreview
from ..models.member import Member
from ._util import unwrap


class SendingDisabledError(MeinVereinError):
    """The club is not allowed to send e-mail mailings (``sendEmailEnabled``)."""


class MailingAPI:
    """Write, keep and send mailings of one club."""

    def __init__(self, transport: Transport, club_id: int) -> None:
        self._transport = transport
        self._club_id = club_id
        self._base = f"/protected/clubs/{club_id}/mailingDispatch"

    # ------------------------------------------------------------- recipients

    async def _recipients(
        self, member_ids: Iterable[int]
    ) -> builtins.list[dict[str, Any]]:
        """Build the recipient entries the API expects from member ids."""
        recipients = []
        for member_id in member_ids:
            path = f"/protected/club/{self._club_id}/members/{member_id}"
            member = Member.model_validate(
                unwrap(await self._transport.get(path), "data", f"GET {path}")
            )
            recipients.append(
                {
                    "id": member.id,
                    "email": member.email or "",
                    "communicationChannel": member.communication_channel or 0,
                }
            )
        return recipients

    async def _payload(
        self,
        name: str,
        subject: str,
        html: str,
        recipients: Iterable[int],
    ) -> dict[str, Any]:
        return {
            "recipients": await self._recipients(recipients),
            "copyRecipients": [],
            "subject": subject,
            "name": name,
            "html": html,
            "attachments": [],
            "attachmentIds": [],
        }

    # ---------------------------------------------------------------- templates

    async def templates(self) -> builtins.list[Dispatch]:
        """Return the saved mailing templates.

        ``GET /protected/clubs/{clubId}/mailingDispatch/list/template``
        """
        path = f"{self._base}/list/template"
        data = unwrap(await self._transport.get(path), "data", f"GET {path}")
        return [
            Dispatch.model_validate(item)
            for item in unwrap(data, "templates", f"GET {path}")
        ]

    async def template(self, template_id: int) -> Dispatch:
        """Return one template.

        ``GET /protected/clubs/{clubId}/mailingDispatch/template/{id}``
        """
        path = f"{self._base}/template/{template_id}"
        return Dispatch.model_validate(
            unwrap(await self._transport.get(path), "data", f"GET {path}")
        )

    async def create_template(self, name: str, subject: str, html: str) -> Dispatch:
        """Save a reusable template; ``html`` is the message body as HTML.

        ``POST /protected/clubs/{clubId}/mailingDispatch/template``
        """
        path = f"{self._base}/template"
        payload = await self._transport.post(
            path,
            {
                "name": name,
                "subject": subject,
                "html": html,
                "attachments": [],
                "attachmentIds": [],
            },
        )
        return Dispatch.model_validate(unwrap(payload, "template", f"POST {path}"))

    async def update_template(
        self,
        template_id: int,
        *,
        name: str | None = None,
        subject: str | None = None,
        html: str | None = None,
    ) -> Dispatch:
        """Change a template.

        ``PUT /protected/clubs/{clubId}/mailingDispatch/template/{id}``
        """
        current = await self.template(template_id)
        await self._transport.put(
            f"{self._base}/template/{template_id}",
            {
                "id": template_id,
                "name": current.name if name is None else name,
                "subject": current.subject if subject is None else subject,
                "html": current.html if html is None else html,
                "attachments": [],
                "attachmentIds": [],
            },
        )
        return await self.template(template_id)

    # ------------------------------------------------------------------- drafts

    async def drafts(self) -> builtins.list[Dispatch]:
        """Return the mailing drafts.

        ``GET /protected/clubs/{clubId}/mailingDispatch/list/draft``
        """
        path = f"{self._base}/list/draft"
        data = unwrap(await self._transport.get(path), "data", f"GET {path}")
        return [
            Dispatch.model_validate(item)
            for item in unwrap(data, "dispatches", f"GET {path}")
        ]

    async def draft(self, draft_id: int) -> Dispatch:
        """Return one draft with its recipients.

        ``GET /protected/clubs/{clubId}/mailingDispatch/dispatch/{id}``
        """
        path = f"{self._base}/dispatch/{draft_id}"
        return Dispatch.model_validate(
            unwrap(await self._transport.get(path), "data", f"GET {path}")
        )

    async def create_draft(
        self,
        name: str,
        subject: str,
        html: str,
        *,
        recipients: Iterable[int] = (),
    ) -> Dispatch:
        """Save a mailing draft for the given members. Nothing is sent.

        ``POST /protected/clubs/{clubId}/mailingDispatch/dispatch``
        """
        path = f"{self._base}/dispatch"
        payload = await self._transport.post(
            path, await self._payload(name, subject, html, recipients)
        )
        created = unwrap(payload, "dispatch", f"POST {path}")
        return await self.draft(int(unwrap(created, "id", f"POST {path}")))

    async def update_draft(
        self,
        draft_id: int,
        *,
        name: str | None = None,
        subject: str | None = None,
        html: str | None = None,
        recipients: Iterable[int] | None = None,
    ) -> Dispatch:
        """Change a draft; ``recipients`` replaces the recipient list.

        ``PATCH /protected/clubs/{clubId}/mailingDispatch/dispatch/{id}``
        """
        current = await self.draft(draft_id)
        member_ids = (
            [int(entry["id"]) for entry in current.receiver if entry.get("id")]
            if recipients is None
            else recipients
        )
        body = await self._payload(
            current.name or "" if name is None else name,
            current.subject or "" if subject is None else subject,
            current.html or "" if html is None else html,
            member_ids,
        )
        body["id"] = draft_id
        await self._transport.patch(f"{self._base}/dispatch/{draft_id}", body)
        return await self.draft(draft_id)

    async def delete(self, *ids: int) -> int:
        """Delete drafts and/or templates; returns how many were deleted.

        ``DELETE /protected/clubs/{clubId}/mailingDispatch`` with ``{"ids": [...]}``
        """
        if not ids:
            return 0
        payload = await self._transport.delete(self._base, {"ids": list(ids)})
        return int(unwrap(payload, "deletedCount", f"DELETE {self._base}"))

    async def preview(
        self, subject: str, html: str, *, recipients: Iterable[int]
    ) -> MailPreview:
        """Show how the e-mail would look for the first recipient. Nothing is sent.

        ``POST /protected/clubs/{clubId}/mailingDispatch/emailPreview``
        """
        path = f"{self._base}/emailPreview"
        payload = await self._transport.post(
            path, await self._payload("", subject, html, recipients)
        )
        return MailPreview.model_validate(payload)

    # -------------------------------------------------------------------- items

    async def _items(self, box: str) -> builtins.list[DispatchItem]:
        path = f"{self._base}/list/items/{box}"
        payload = await self._transport.get(path)
        return [
            DispatchItem.model_validate(item)
            for item in unwrap(payload, "data", f"GET {path}")
        ]

    async def outbox(self) -> builtins.list[DispatchItem]:
        """Return messages that wait to be sent (or printed, for letters).

        ``GET /protected/clubs/{clubId}/mailingDispatch/list/items/outbox``
        """
        return await self._items("outbox")

    async def sent(self) -> builtins.list[DispatchItem]:
        """Return the messages that were sent.

        ``GET /protected/clubs/{clubId}/mailingDispatch/list/items/sent``
        """
        return await self._items("sent")

    async def deleted(self) -> builtins.list[DispatchItem]:
        """Return deleted messages.

        ``GET /protected/clubs/{clubId}/mailingDispatch/list/items/deleted``
        """
        return await self._items("deleted")

    # ------------------------------------------------------------------ sending

    async def sending_enabled(self) -> bool:
        """Tell whether the club may send e-mail mailings.

        ``GET /protected/mv365/clubs/{clubId}`` (field ``sendEmailEnabled``)
        """
        path = f"/protected/mv365/clubs/{self._club_id}"
        club = unwrap(await self._transport.get(path), "club", f"GET {path}")
        return bool(club.get("sendEmailEnabled"))

    async def send(
        self,
        subject: str,
        html: str,
        *,
        recipients: Iterable[int],
        name: str = "",
    ) -> dict[str, Any]:
        """Send an e-mail to members right away. **Sends e-mails.**

        Raises :class:`SendingDisabledError` before sending anything if the club
        may not send e-mail (demo clubs, clubs without the feature).

        Not verified against the real service: the only club available for
        tests is a demo club, which may not send.
        ``POST /protected/clubs/{clubId}/mailingDispatch/sendDirect``
        """
        if not await self.sending_enabled():
            raise SendingDisabledError(
                "This club may not send e-mail mailings (sendEmailEnabled is false)"
            )
        path = f"{self._base}/sendDirect"
        payload = await self._transport.post(
            path, await self._payload(name, subject, html, recipients)
        )
        return payload if isinstance(payload, dict) else {}
