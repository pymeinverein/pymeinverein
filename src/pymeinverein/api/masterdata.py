"""Master data of a club: salutations, titles, departments, custom fields, roles."""

from __future__ import annotations

from .._transport import Transport
from ..exceptions import LookupFailedError
from ..models.masterdata import (
    ClubArea,
    ClubRole,
    Country,
    IndividualField,
    MasterData,
)
from ..models.member import SubArea
from ._util import unwrap


class MasterDataAPI:
    """Read-only lookups that other data refers to by id."""

    def __init__(self, transport: Transport, club_id: int) -> None:
        self._transport = transport
        self._club_id = club_id

    async def get(self) -> MasterData:
        """Return salutations, titles, departments, rates and custom fields.

        ``GET /protected/mv365/clubs/{clubId}/data``
        """
        payload = await self._transport.get(
            f"/protected/mv365/clubs/{self._club_id}/data"
        )
        return MasterData.model_validate(payload)

    async def areas(self) -> list[ClubArea]:
        """Return the department structure.

        ``GET /protected/mv365/clubs/{clubId}/areas``
        """
        path = f"/protected/mv365/clubs/{self._club_id}/areas"
        payload = await self._transport.get(path)
        areas = unwrap(payload, "clubAreas", f"GET {path}")
        return [ClubArea.model_validate(area) for area in areas]

    async def individual_fields(self) -> list[IndividualField]:
        """Return the custom fields defined for members and contacts.

        ``GET /protected/club/{clubId}/list/individual-field``
        """
        path = f"/protected/club/{self._club_id}/list/individual-field"
        payload = await self._transport.get(path)
        fields = unwrap(payload, "data", f"GET {path}")
        return [IndividualField.model_validate(field) for field in fields]

    async def roles(self) -> list[ClubRole]:
        """Return the permission roles of the club.

        ``GET /protected/club/{clubId}/auth/club-roles?withClubUsersCount=true``
        """
        path = f"/protected/club/{self._club_id}/auth/club-roles"
        payload = await self._transport.get(path, params={"withClubUsersCount": "true"})
        roles = unwrap(payload, "data", f"GET {path}")
        return [ClubRole.model_validate(role) for role in roles]

    async def countries(self) -> list[Country]:
        """Return all countries with the ids used in addresses.

        ``GET /mv365/all_countries``
        """
        payload = await self._transport.get("/mv365/all_countries")
        countries = unwrap(payload, "countries", "GET /mv365/all_countries")
        return [Country.model_validate(country) for country in countries]

    async def resolve_sub_area(self, ref: int | str | SubArea) -> int:
        """Return the id of a department or function given by id, name or path.

        A name must be unique among all departments and functions. Functions
        usually are not ("Spieler" exists in every team), so they can be given
        as a path: ``"1. Mannschaft - Damen/Spieler"``.
        """
        if isinstance(ref, SubArea):
            return ref.id
        if isinstance(ref, int):
            return ref
        subs = [sub for area in await self.areas() for sub in area.sub_areas]
        parts = [part.strip() for part in ref.split("/")]
        candidates = [sub for sub in subs if sub.name == ref]
        if not candidates and len(parts) > 1:
            parents: list[int | None] = [None]
            for index, part in enumerate(parts):
                found = [
                    sub
                    for sub in subs
                    if sub.name == part
                    and (index == 0 or sub.parent_id in parents)
                    and (index > 0 or sub.parent_id is None)
                ]
                parents = [sub.id for sub in found]
                candidates = found
        if len(candidates) != 1:
            names = ", ".join(sorted({repr(sub.name) for sub in subs}))
            raise LookupFailedError(
                f"Expected exactly one department or function for {ref!r}, found "
                f"{len(candidates)}. Use an id or a path like 'Department/Function'. "
                f"Known names: {names or 'none'}"
            )
        return candidates[0].id

    async def resolve_individual_field(self, ref: int | str | IndividualField) -> int:
        """Return the id of a custom field given by id or exact name."""
        if isinstance(ref, IndividualField):
            return ref.id
        if isinstance(ref, int):
            return ref
        fields = await self.individual_fields()
        matches = [field for field in fields if field.name == ref]
        if len(matches) != 1:
            names = ", ".join(repr(field.name) for field in fields)
            raise LookupFailedError(
                f"Expected exactly one custom field named {ref!r}, found "
                f"{len(matches)}. Known fields: {names or 'none'}"
            )
        return matches[0].id
