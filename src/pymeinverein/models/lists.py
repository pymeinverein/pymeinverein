"""Models for member lists."""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum

from .base import ApiModel


class ListType(IntEnum):
    """Kind of list (field ``listType``)."""

    #: Members are assigned by hand.
    STATIC = 0
    #: Members are selected by filter criteria.
    DYNAMIC = 1
    FINANCE = 2
    #: A free table that is not tied to members.
    FREE = 3


class DefaultListType(IntEnum):
    """Identifies the lists MeinVerein creates for every club."""

    BIRTHDAY_MEMBERS = 0
    BIRTHDAY = 1
    ANNIVERSARY = 2
    DEPARTMENT = 3
    ACTIVE_MEMBERS = 4
    #: Everyone: members, former members and contacts.
    ALL_CONTACTS = 5
    ALL_MEMBERS = 6
    ALL_PERSONS = 7
    FORMER_MEMBERS = 8


class MemberList(ApiModel):
    """A list of members ("Liste")."""

    id: int
    name: str
    club_id: int | None = None
    #: See :class:`ListType`.
    list_type: int | None = None
    is_default_list: bool = False
    #: See :class:`DefaultListType`; ``None`` for lists created by users.
    default_list_type: int | None = None
    #: Sub area id for the automatic department lists.
    department_id: int | None = None
    is_favourite: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListCriterion(ApiModel):
    """One filter rule of a dynamic list, e.g. ``state = 0``.

    ``value`` is text (numbers are sent as text too); ``None`` together with the
    operator ``!=`` means "is filled in".
    """

    column_name: str
    operator: str = "="
    value: str | None = None
    id: int | None = None
    list_id: int | None = None


class FieldCriterion(ApiModel):
    """A filter rule on a custom field, e.g. ``Position = Tor``."""

    individual_field_id: int
    operator: str = "="
    value: str | None = None
    id: int | None = None
    list_id: int | None = None


class RemoveResult(ApiModel):
    """Answer when members are removed from a list."""

    removed_count: int = 0
    skipped_count: int = 0
