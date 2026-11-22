"""Client-side filters for members.

The API can only filter through lists. To keep filtering simple and uniform,
pymeinverein loads a list and applies these filters in Python.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import IntEnum

from .models.member import Member, MemberState, MemberType


def _code[E: IntEnum](value: E | str | int, enum: type[E], what: str) -> int:
    """Accept an enum member, its name (any case) or the raw integer."""
    if isinstance(value, str):
        try:
            return int(enum[value.strip().upper()])
        except KeyError:
            names = ", ".join(member.name.lower() for member in enum)
            raise ValueError(f"Unknown {what} {value!r}; use one of: {names}") from None
    return int(value)


@dataclass(frozen=True, kw_only=True)
class MemberFilter:
    """Conditions a member has to meet; all given conditions must hold.

    ``type``
        ``"member"``, ``"contact"`` or ``"company"`` (or a :class:`MemberType`).
    ``status``
        ``"active"``, ``"former"`` or ``"passive"`` (or a :class:`MemberState`).
    ``department``
        Name or id of a department or function the member belongs to.
    ``role``
        Name or id of a permission role the member has.
    ``search``
        Text that must occur in the name, e-mail address or member number
        (case-insensitive).
    ``where``
        Any function that takes a :class:`Member` and returns ``True`` to keep it.
    """

    type: MemberType | str | int | None = None
    status: MemberState | str | int | None = None
    department: str | int | None = None
    role: str | int | None = None
    search: str | None = None
    where: Callable[[Member], bool] | None = None

    def __post_init__(self) -> None:
        # Fail early on misspelled names instead of silently matching nothing.
        if self.type is not None:
            _code(self.type, MemberType, "member type")
        if self.status is not None:
            _code(self.status, MemberState, "status")

    def matches(self, member: Member) -> bool:
        if self.type is not None:
            if member.type != _code(self.type, MemberType, "member type"):
                return False
        if self.status is not None:
            if member.state != _code(self.status, MemberState, "status"):
                return False
        if self.department is not None and not self._in_department(member):
            return False
        if self.role is not None:
            if isinstance(self.role, int):
                if all(role.id != self.role for role in member.roles):
                    return False
            elif all(role.name != self.role for role in member.roles):
                return False
        if self.search:
            needle = self.search.casefold()
            haystack = " ".join(
                text
                for text in (
                    member.first_name,
                    member.last_name,
                    member.email,
                    member.member_id,
                )
                if text
            ).casefold()
            if needle not in haystack:
                return False
        if self.where is not None and not self.where(member):
            return False
        return True

    def _in_department(self, member: Member) -> bool:
        if isinstance(self.department, int):
            ids = {area.id for area in member.club_sub_areas}
            ids |= {h.sub_area_id for h in member.histories if h.sub_area_id}
            return self.department in ids
        return any(area.name == self.department for area in member.club_sub_areas)

    def apply(self, members: Iterable[Member]) -> list[Member]:
        """Return the members that match, in their original order."""
        return [member for member in members if self.matches(member)]
