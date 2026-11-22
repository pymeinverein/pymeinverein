"""Models for the logged-in user and the clubs they can access."""

from __future__ import annotations

from datetime import datetime

from .base import ApiModel


class User(ApiModel):
    """The logged-in Buhl account as MeinVerein sees it."""

    id: int
    email: str
    first_name: str | None = None
    last_name: str | None = None
    approved: bool | None = None
    last_login: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Club(ApiModel):
    """A club ("Verein") the logged-in user belongs to."""

    id: int
    name: str
    name2: str | None = None
    #: ``True`` for the demo club that MeinVerein fills with sample data.
    is_demo: bool = False
    number: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    member_count: int | None = None
    #: Whether the club may send e-mail mailings (``False`` for demo clubs).
    send_email_enabled: bool | None = None
    category_id: int | None = None
    club_owner_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Account(ApiModel):
    """Answer of ``GET /protected/accounts``: the user and their clubs."""

    user: User
    clubs: list[Club] = []
    #: Id of the club that is currently selected in the web application.
    selected_club_id: int | None = None


class Profile(ApiModel):
    """The logged-in user's personal profile."""

    id: int
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
