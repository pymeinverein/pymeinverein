"""Departments: the tree of "Abteilungen" and the functions inside them.

MeinVerein models the structure with three fixed *levels* (the API calls them
"areas", e.g. "Mannschaften" > "Rollen" > "Ebene 3"). The entries of a level
are "sub areas": a level 1 entry is a department, entries of level 2 and 3
hang below an entry of the level above.
"""

from __future__ import annotations

from .._transport import Transport
from ..exceptions import LookupFailedError, UnexpectedResponseError
from ..models.masterdata import ClubArea
from ..models.member import SubArea
from ._util import unwrap
from .masterdata import MasterDataAPI

#: A department or function: id, unique name, ``"Department/Function"`` path or model.
type DepartmentRef = int | str | SubArea


class DepartmentsAPI:
    """Read and change the department structure of one club."""

    def __init__(
        self, transport: Transport, club_id: int, master_data: MasterDataAPI
    ) -> None:
        self._transport = transport
        self._master_data = master_data
        self._base = f"/protected/mv365/clubs/{club_id}"

    async def tree(self) -> list[ClubArea]:
        """Return the levels with their entries.

        ``GET /protected/mv365/clubs/{clubId}/areas``
        """
        return await self._master_data.areas()

    async def all(self) -> list[SubArea]:
        """Return all departments and functions as one flat list."""
        return [sub for area in await self.tree() for sub in area.sub_areas]

    async def get(self, ref: DepartmentRef) -> SubArea:
        """Look up a department or function by id, unique name or path."""
        sub_area_id = await self._master_data.resolve_sub_area(ref)
        for sub in await self.all():
            if sub.id == sub_area_id:
                return sub
        raise LookupFailedError(f"There is no department or function {ref!r}")

    async def create(
        self,
        name: str,
        *,
        parent: DepartmentRef | None = None,
        alias: str | None = None,
    ) -> SubArea:
        """Create a department, or with ``parent`` a function below an entry.

        ``POST /protected/mv365/clubs/{clubId}/subareas``
        """
        levels = await self.tree()
        parent_area = None if parent is None else await self.get(parent)
        level = 1 if parent_area is None else (parent_area.level or 1) + 1
        area = next((item for item in levels if item.level == level), None)
        if area is None:
            raise LookupFailedError(
                f"The department structure has no level {level}; entries can be "
                f"nested {len(levels)} levels deep"
            )
        body: dict[str, object] = {"name": name, "areaId": area.id, "level": level}
        if parent_area is not None:
            body["parentId"] = parent_area.id
        path = f"{self._base}/subareas"
        payload = await self._transport.post(path, body)
        created = SubArea.model_validate(unwrap(payload, "clubSubArea", f"POST {path}"))
        if alias is not None:
            created = await self.update(created.id, alias=alias)
        return created

    async def update(
        self,
        ref: DepartmentRef,
        *,
        name: str | None = None,
        alias: str | None = None,
    ) -> SubArea:
        """Rename a department or function and/or set its short name (alias).

        ``PATCH /protected/mv365/clubs/{clubId}/subareas/{id}``
        """
        current = await self.get(ref)
        body = {
            "name": current.name if name is None else name,
            "alias": current.alias if alias is None else alias,
        }
        path = f"{self._base}/subareas/{current.id}"
        payload = await self._transport.patch(path, body)
        return SubArea.model_validate(unwrap(payload, "clubSubArea", f"PATCH {path}"))

    async def copy(self, ref: DepartmentRef) -> SubArea:
        """Duplicate an entry together with everything below it.

        The copy gets the name with " - Kopie" appended.
        ``POST /protected/mv365/clubs/{clubId}/subareas-copy/{id}``
        """
        source = await self.get(ref)
        before = {sub.id for sub in await self.all()}
        path = f"{self._base}/subareas-copy/{source.id}"
        payload = await self._transport.post(path)
        areas = unwrap(payload, "clubAreas", f"POST {path}")
        new = [
            sub
            for area in areas
            for sub in ClubArea.model_validate(area).sub_areas
            if sub.id not in before and sub.level == source.level
        ]
        if len(new) != 1:
            raise UnexpectedResponseError(
                f"POST {path}: expected one new entry, found {len(new)}"
            )
        return new[0]

    async def delete(self, ref: DepartmentRef) -> None:
        """Delete a department or function, including everything below it.

        Members are not deleted. Their membership period in the deleted entry
        stays but loses its department.
        ``DELETE /protected/mv365/clubs/{clubId}/subareas/{id}``
        """
        sub_area_id = await self._master_data.resolve_sub_area(ref)
        await self._transport.delete(f"{self._base}/subareas/{sub_area_id}")

    async def rename_level(self, level: int, name: str) -> ClubArea:
        """Rename one of the three levels (for example "Mannschaften").

        ``PATCH /protected/mv365/clubs/{clubId}/areas/{id}``
        """
        area = next((item for item in await self.tree() if item.level == level), None)
        if area is None:
            raise LookupFailedError(f"The department structure has no level {level}")
        path = f"{self._base}/areas/{area.id}"
        payload = await self._transport.patch(path, {"name": name})
        return ClubArea.model_validate(unwrap(payload, "clubArea", f"PATCH {path}"))
