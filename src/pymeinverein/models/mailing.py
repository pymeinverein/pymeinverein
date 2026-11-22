"""Models for mailings ("Korrespondenz")."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from .base import ApiModel


class Dispatch(ApiModel):
    """A mailing draft or template: subject, HTML text and recipients."""

    id: int
    name: str | None = None
    subject: str | None = None
    html: str | None = None
    #: 2 for drafts, 5 for templates (as observed).
    state: int | None = None
    dispatch_number: str | None = None
    #: The recipients, as the API sends them (only filled for drafts).
    receiver: list[dict[str, Any]] = []
    attachments: list[dict[str, Any]] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DispatchReceiver(ApiModel):
    id: int | None = None
    full_name: str | None = None


class DispatchItem(ApiModel):
    """One message to one recipient in the outbox, the sent or deleted items."""

    id: int
    name: str | None = None
    subject: str | None = None
    #: Where the message goes: an e-mail address or a postal address.
    address: str | None = None
    email: str | None = None
    #: 0 = e-mail, 1 = letter (see ``CommunicationChannel``).
    communication_channel: int | None = None
    dispatch_item_state: int | None = None
    #: For example ``Sendung``.
    item_type: str | None = Field(default=None, alias="type")
    last_attempt_at: datetime | None = None
    failure_reason: str | None = None
    failure_count: int | None = None
    receiver: DispatchReceiver | None = None


class MailPreview(ApiModel):
    """How an e-mail would look for its first recipient."""

    text: str | None = None
    sender: str | None = None
    recipient_email: str | None = None
