"""Models for permission roles."""

from __future__ import annotations

from enum import IntEnum

from .base import ApiModel


class RoleType(IntEnum):
    """Kind of role (field ``type``): the four built-in roles or a custom one."""

    CUSTOM = 0
    ADMINISTRATOR = 1
    FINANCE_MANAGER = 2
    MANAGER = 3
    MEMBER = 4


class PermissionState(IntEnum):
    """What a role may do with one area of MeinVerein."""

    LOCKED = 0
    READ = 1
    UPDATE = 2
    UPDATE_AND_DELETE = 3


class RoleMember(ApiModel):
    """A member that holds a role."""

    id: int
    first_name: str | None = None
    last_name: str | None = None
    member_id: str | None = None


class ClubRole(ApiModel):
    """A permission role of the club ("Rolle")."""

    id: int
    name: str
    description: str | None = None
    #: See :class:`RoleType`.
    type: int | None = None
    is_system_role: bool | None = None
    #: The role new members get automatically.
    is_default: bool | None = None
    member_count: int | None = None
    #: Only filled when the roles were requested with their members.
    members: list[RoleMember] = []


class PermissionValue(ApiModel):
    """The state of a permission: as stored and as currently effective."""

    original: int | None = None
    current: int | None = None


class Permission(ApiModel):
    """One node of a role's permission tree.

    Containers (``state`` is ``None``) group the actual permissions in
    ``children``. See :class:`PermissionState` for the values.
    """

    key: str
    name: str | None = None
    disabled: bool | None = None
    state: PermissionValue | None = None
    children: list[Permission] = []
