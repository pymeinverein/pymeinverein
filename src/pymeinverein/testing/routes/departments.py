"""Departments ("sub areas") and the levels they belong to.

Observed on the real API: deleting an entry also deletes everything below it;
membership periods that pointed to a deleted entry keep existing without a
department. Copying appends " - Kopie" to the name and copies the children.
"""

from __future__ import annotations

from aiohttp import web

from .._responses import bad_request, not_found
from ..state import Json
from ._base import OLD, RouteGroup, json_body


class DepartmentRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        router.add_post(f"{OLD}/subareas", self.create)
        router.add_patch(f"{OLD}/subareas/{{sub_id}}", self.update)
        router.add_delete(f"{OLD}/subareas/{{sub_id}}", self.delete)
        router.add_post(f"{OLD}/subareas-copy/{{sub_id}}", self.copy)
        router.add_patch(f"{OLD}/areas/{{area_id}}", self.rename_level)

    def _sub(self, request: web.Request) -> tuple[int, Json] | None:
        club_id = self._club_id(request)
        raw = request.match_info["sub_id"]
        if club_id is None or not raw.isdecimal():
            return None
        for sub in self.state.sub_areas[club_id]:
            if sub["id"] == int(raw):
                return club_id, sub
        return None

    def _children(self, club_id: int, sub_id: int) -> list[Json]:
        direct = [s for s in self.state.sub_areas[club_id] if s["parentId"] == sub_id]
        return direct + [
            below for child in direct for below in self._children(club_id, child["id"])
        ]

    def _tree(self, club_id: int) -> web.Response:
        return web.json_response({"clubAreas": self.state.club_areas(club_id)})

    async def create(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not name.strip():
            return bad_request("name")
        area_ids = {area["id"] for area in self.state.areas[club_id]}
        if body.get("areaId") not in area_ids:
            return bad_request("areaId")
        sub: Json = {
            "id": self.state.next_id(),
            "name": name,
            "areaId": body["areaId"],
            "level": body.get("level", 1),
            "clubId": club_id,
            "parentId": body.get("parentId"),
            "alias": None,
        }
        self.state.sub_areas[club_id].append(sub)
        return web.json_response({"clubSubArea": sub})

    async def update(self, request: web.Request) -> web.Response:
        found = self._sub(request)
        if found is None:
            return not_found()
        _, sub = found
        body = await json_body(request)
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not name.strip():
            return bad_request("name")
        sub["name"] = name
        if "alias" in body:
            sub["alias"] = body["alias"]
        return web.json_response({"clubSubArea": sub})

    async def delete(self, request: web.Request) -> web.Response:
        found = self._sub(request)
        if found is None:
            return not_found()
        club_id, sub = found
        gone = {sub["id"]} | {
            child["id"] for child in self._children(club_id, sub["id"])
        }
        self.state.sub_areas[club_id] = [
            item for item in self.state.sub_areas[club_id] if item["id"] not in gone
        ]
        for member in self.state.members[club_id].values():
            for period in member.get("histories", []):
                if period.get("subAreaId") in gone:
                    period["subAreaId"] = None
        return self._tree(club_id)

    def _copy(
        self, club_id: int, sub: Json, parent_id: int | None, suffix: str
    ) -> None:
        clone = {
            **sub,
            "id": self.state.next_id(),
            "name": sub["name"] + suffix,
            "parentId": parent_id,
        }
        children = [
            item
            for item in self.state.sub_areas[club_id]
            if item["parentId"] == sub["id"]
        ]
        self.state.sub_areas[club_id].append(clone)
        for child in children:
            self._copy(club_id, child, clone["id"], "")

    async def copy(self, request: web.Request) -> web.Response:
        found = self._sub(request)
        if found is None:
            return not_found()
        club_id, sub = found
        self._copy(club_id, sub, sub["parentId"], " - Kopie")
        return self._tree(club_id)

    async def rename_level(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not name.strip():
            return bad_request("name")
        for area in self.state.areas[club_id]:
            if str(area["id"]) == request.match_info["area_id"]:
                area["name"] = name
                return web.json_response({"clubArea": area})
        return not_found()
