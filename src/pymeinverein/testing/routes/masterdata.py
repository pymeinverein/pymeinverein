"""Master data: salutations, titles, departments, custom fields, roles."""

from __future__ import annotations

from aiohttp import web

from .. import seed
from .._responses import bad_request, data, not_found
from ._base import NEW, OLD, RouteGroup, json_body


class MasterDataRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get(f"{OLD}/data", self.master_data)
        router.add_get(f"{OLD}/areas", self.areas)
        router.add_get(f"{NEW}/list/individual-field", self.individual_fields)
        router.add_post(f"{NEW}/list/individual-field", self.create_field)
        router.add_put(f"{NEW}/list/individual-field/{{field_id}}", self.update_field)
        router.add_delete(
            f"{NEW}/list/individual-field/{{field_id}}", self.delete_field
        )
        router.add_get("/mv365/all_countries", self.countries)

    async def master_data(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        return web.json_response(self.state.master_data(club_id))

    async def areas(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        return web.json_response({"clubAreas": self.state.club_areas(club_id)})

    async def individual_fields(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        return data(self.state.individual_fields[club_id])

    async def countries(self, request: web.Request) -> web.Response:
        return web.json_response({"countries": seed.COUNTRIES})

    # ------------------------------------------------------------- custom fields

    async def create_field(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not name.strip():
            return bad_request("name")
        # Like the real service, the mock accepts duplicate names.
        field = {
            "id": self.state.next_id(),
            "clubId": club_id,
            "listId": body.get("listId"),
            "name": name,
            "type": body.get("type", 0),
            "options": body.get("options") or [],
            "suffix": body.get("suffix"),
            "area": body.get("area", 0),
        }
        self.state.individual_fields[club_id].append(field)
        return data(field)

    async def update_field(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        for field in self.state.individual_fields[club_id]:
            if str(field["id"]) == request.match_info["field_id"]:
                if not isinstance(body, dict) or not body.get("name"):
                    return bad_request("name")
                for key in ("name", "type", "options", "suffix", "area"):
                    if key in body:
                        field[key] = body[key]
                return data(field)
        return not_found()

    async def delete_field(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        fields = self.state.individual_fields[club_id]
        kept = [f for f in fields if str(f["id"]) != request.match_info["field_id"]]
        if len(kept) == len(fields):
            return not_found()
        gone = {f["id"] for f in fields} - {f["id"] for f in kept}
        self.state.individual_fields[club_id] = kept
        for member in self.state.members[club_id].values():
            member["memberIndividualFieldData"] = [
                item
                for item in member.get("memberIndividualFieldData", [])
                if item["individualFieldId"] not in gone
            ]
        return web.Response(status=200)
