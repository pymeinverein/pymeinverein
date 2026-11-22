"""Permission roles: what the users of a club may see and do."""

from __future__ import annotations

from collections.abc import Iterable

from .._transport import Transport
from ..exceptions import LookupFailedError, NoAccountError
from ..models.member import Member
from ..models.roles import ClubRole, Permission, PermissionState
from ._util import unwrap

#: A role: id, exact name or model.
type RoleRef = int | str | ClubRole


class RolesAPI:
    """Manage the roles of one club and who holds them.

    Every club has four built-in roles (Administrator, Finanzverwalter,
    Verwalter, Mitglied); further roles can be created. Roles belong to *user
    accounts*: only a member who was invited and has an account can hold one.
    """

    def __init__(self, transport: Transport, club_id: int) -> None:
        self._transport = transport
        self._club_base = f"/protected/club/{club_id}"
        self._base = f"/protected/club/{club_id}/auth"

    async def all(self, *, with_members: bool = False) -> list[ClubRole]:
        """Return the roles, optionally with the members that hold them.

        ``GET /protected/club/{clubId}/auth/club-roles``
        """
        params = {"withClubUsersCount": "true"}
        if with_members:
            params["withClubUsers"] = "true"
        path = f"{self._base}/club-roles"
        payload = await self._transport.get(path, params=params)
        return [
            ClubRole.model_validate(role)
            for role in unwrap(payload, "data", f"GET {path}")
        ]

    async def get(self, ref: RoleRef, *, with_members: bool = False) -> ClubRole:
        """Look up a role by id or exact name."""
        roles = await self.all(with_members=with_members)
        if isinstance(ref, ClubRole):
            ref = ref.id
        matches = [
            role
            for role in roles
            if (role.id == ref if isinstance(ref, int) else role.name == ref)
        ]
        if len(matches) != 1:
            names = ", ".join(repr(role.name) for role in roles)
            raise LookupFailedError(
                f"Expected exactly one role for {ref!r}, found {len(matches)}. "
                f"Known roles: {names or 'none'}"
            )
        return matches[0]

    async def _id(self, ref: RoleRef) -> int:
        if isinstance(ref, ClubRole):
            return ref.id
        if isinstance(ref, int):
            return ref
        return (await self.get(ref)).id

    async def create(self, name: str, description: str = "") -> ClubRole:
        """Create a custom role.

        It starts with the service's default permissions (most areas locked);
        adjust them with :meth:`set_permission`.

        ``POST /protected/club/{clubId}/auth/club-role/create``
        """
        path = f"{self._base}/club-role/create"
        payload = await self._transport.post(
            path, {"name": name, "description": description}
        )
        return ClubRole.model_validate(unwrap(payload, "data", f"POST {path}"))

    async def update(
        self,
        ref: RoleRef,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> ClubRole:
        """Change the name and/or description of a role.

        ``PUT /protected/club/{clubId}/auth/club-role/{roleId}/update``
        """
        current = await self.get(ref)
        await self._transport.put(
            f"{self._base}/club-role/{current.id}/update",
            {
                "name": current.name if name is None else name,
                "description": (
                    current.description if description is None else description
                ),
            },
        )
        return await self.get(current.id)

    async def delete(self, ref: RoleRef) -> None:
        """Delete a role. Members that hold it simply lose it.

        ``DELETE /protected/club/{clubId}/auth/club-role/{roleId}``
        """
        role = await self.get(ref)  # an unknown id makes the service fail
        await self._transport.delete(f"{self._base}/club-role/{role.id}")

    # --------------------------------------------------------------- permissions

    async def permissions(self, ref: RoleRef) -> list[Permission]:
        """Return the permission tree of a role.

        ``GET /protected/club/{clubId}/auth/club-role/{roleId}/permissions/all``
        """
        path = f"{self._base}/club-role/{await self._id(ref)}/permissions/all"
        payload = await self._transport.get(path)
        return [
            Permission.model_validate(node)
            for node in unwrap(payload, "data", f"GET {path}")
        ]

    async def permission_states(self, ref: RoleRef) -> dict[str, int]:
        """Return ``{permission key: current state}`` for all permissions of a role."""
        states: dict[str, int] = {}

        def collect(nodes: list[Permission]) -> None:
            for node in nodes:
                if node.state is not None and node.state.current is not None:
                    states[node.key] = node.state.current
                collect(node.children)

        collect(await self.permissions(ref))
        return states

    async def set_permission(
        self, ref: RoleRef, key: str, state: PermissionState
    ) -> None:
        """Set one permission of a role, e.g. ``calendar_events_module`` to ``READ``.

        Keys come from :meth:`permissions` / :meth:`permission_states`.
        ``PUT /protected/club/{clubId}/auth/club-role/{roleId}/permission-key``
        """
        await self._transport.put(
            f"{self._base}/club-role/{await self._id(ref)}/permission-key",
            {"key": key, "state": int(state)},
        )

    # ---------------------------------------------------------------- assignment

    async def _require_account(self, member_id: int) -> None:
        path = f"{self._club_base}/members/{member_id}"
        payload = await self._transport.get(path)
        member = Member.model_validate(unwrap(payload, "data", f"GET {path}"))
        if member.user_id is None:
            raise NoAccountError(
                f"Member {member_id} ({member.full_name}) has no MeinVerein account. "
                "Roles can only be given to members who accepted an invitation."
            )

    async def set_member_roles(self, member_id: int, roles: Iterable[RoleRef]) -> None:
        """Replace the roles of one member with the given ones.

        Raises :class:`~pymeinverein.exceptions.NoAccountError` if the member has
        no user account (the service fails without a useful message then).
        ``PUT /protected/club/{clubId}/auth/club-members/{memberId}/assign/club-roles``
        """
        role_ids = [await self._id(role) for role in roles]
        await self._require_account(member_id)
        await self._transport.put(
            f"{self._base}/club-members/{member_id}/assign/club-roles",
            {"clubRoleIds": role_ids},
        )

    async def add_members(self, ref: RoleRef, member_ids: Iterable[int]) -> list[int]:
        """Give a role to members in addition to the roles they have.

        Returns the ids of the members that received the role. Members without
        a user account are silently skipped by the API and missing from it.
        ``POST /protected/club/{clubId}/auth/club-role/{roleId}/assign/club-members``
        """
        path = f"{self._base}/club-role/{await self._id(ref)}/assign/club-members"
        payload = await self._transport.post(path, {"clubMemberIds": list(member_ids)})
        assigned = unwrap(payload, "data", f"POST {path}")
        return [int(item["clubMemberId"]) for item in assigned]

    async def set_members(self, ref: RoleRef, member_ids: Iterable[int]) -> None:
        """Make exactly these members the holders of a role.

        ``PUT /protected/club/{clubId}/auth/club-role/{roleId}/assign/club-members``
        """
        await self._transport.put(
            f"{self._base}/club-role/{await self._id(ref)}/assign/club-members",
            {"clubMemberIds": list(member_ids)},
        )
