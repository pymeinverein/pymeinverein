"""Models for club settings."""

from __future__ import annotations

from .base import ApiModel


class Numbering(ApiModel):
    """How consecutive numbers (for example invoice numbers) are built."""

    id: int | None = None
    prefix: str | None = None
    suffix: str | None = None
    #: Number of digits of the counter.
    length: int | None = None
    #: Date part put in front of the counter, e.g. ``YYYY``.
    date_part_type: str | None = None
    current_value: str | None = None
    start_value: str | None = None


class ClubCategory(ApiModel):
    """A kind of club ("Sportverein" > "Fußball") from MeinVerein's catalogue."""

    id: int
    name: str
    children: list[ClubCategory] | None = None
