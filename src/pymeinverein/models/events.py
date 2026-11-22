"""Models for calendar events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import ApiModel


class EventCategory(ApiModel):
    """A calendar category with its colour."""

    id: int
    name: str
    #: Colour as hex text, e.g. ``#e33232``.
    color: str | None = None
    #: ``custom``, ``default`` or one of the automatic birthday categories.
    type: str | None = None


class Event(ApiModel):
    """A calendar entry.

    Birthdays show up as automatic all-day entries without ``id``; they
    cannot be changed or deleted.
    """

    id: int | None = None
    title: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    full_day: bool = False
    #: Shown as the place of the event in the web application.
    description: str | None = None
    notes: str | None = None
    category_id: int | None = None
    category: EventCategory | None = None
    #: Duration in seconds.
    event_length: int | None = None
    is_recurring_event: bool | None = None
    participants: list[dict[str, Any]] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_birthday(self) -> bool:
        """``True`` for the automatic birthday entries."""
        return self.id is None
