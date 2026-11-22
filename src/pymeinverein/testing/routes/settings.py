"""Club settings: details, logo, salutations, titles, numbering.

Observed on the real API: ``PATCH`` of the club needs (among others) ``name``
and a valid ``categoryId`` and answers ``400`` otherwise; a missing logo is an
empty ``200`` answer; the next invoice number is the year plus a six digit
counter.
"""

from __future__ import annotations

from aiohttp import web

from .. import seed
from .._responses import api_error, bad_request, data, not_found
from ._base import NEW, OLD, RouteGroup, json_body


class SettingsRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get("/protected/mv365/club-categories", self.categories)
        router.add_get(OLD, self.club)
        router.add_patch(OLD, self.update_club)
        router.add_get("/mv365/clubs/{club_id}/logo", self.logo)
        router.add_post(f"{OLD}/logo", self.set_logo)
        router.add_delete(f"{OLD}/logo", self.delete_logo)
        router.add_get(f"{NEW}/formsOfAddress", self.salutations)
        router.add_get(f"{NEW}/titles", self.titles)
        router.add_post(f"{NEW}/titles", self.create_title)
        router.add_put(f"{NEW}/titles/{{title_id}}", self.update_title)
        router.add_get(f"{NEW}/settings/numeration/{{kind}}", self.numbering)
        router.add_get(f"{NEW}/settings/numeration/{{kind}}/next", self.next_number)

    async def categories(self, request: web.Request) -> web.Response:
        return web.json_response({"data": seed.CLUB_CATEGORIES})

    async def club(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        return web.json_response({"club": self.state.clubs[club_id]})

    async def update_club(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        errors = []
        if not isinstance(body, dict) or not isinstance(body.get("name"), str):
            errors.append("name")
        if not isinstance(body, dict) or not isinstance(body.get("categoryId"), int):
            errors.append("categoryId")
        if errors:
            return api_error(
                400,
                "BadRequestError",
                [
                    {"location": "body", "param": param, "msg": "Invalid value"}
                    for param in errors
                ],
            )
        club = self.state.clubs[club_id]
        for key, value in body.items():
            if key not in ("id", "isDemo", "createdAt", "creator"):
                club[key] = value
        return web.json_response({"club": club})

    async def logo(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        return web.Response(
            body=self.state.logos.get(club_id, b""), content_type="image/jpeg"
        )

    async def set_logo(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        upload = (await request.post()).get("clubLogo")
        if not isinstance(upload, web.FileField):
            return bad_request("clubLogo")
        self.state.logos[club_id] = upload.file.read()
        return web.json_response({})

    async def delete_logo(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        self.state.logos.pop(club_id, None)
        return web.Response(status=200)

    async def salutations(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        master = self.state.master[club_id]
        return data(
            {
                "formsOfAddress": master["formOfAddresses"],
                "letterSalutationType": 1,
            }
        )

    async def titles(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        return data(self.state.master[club_id]["titles"])

    async def create_title(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        label = body.get("label") if isinstance(body, dict) else None
        if not isinstance(label, str) or not label.strip():
            return bad_request("label")
        title = {
            "id": self.state.next_id(),
            "clubId": club_id,
            "label": label,
            "isDefault": False,
            "isFavorite": False,
        }
        self.state.master[club_id]["titles"].append(title)
        return data(title)

    async def update_title(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        for title in self.state.master[club_id]["titles"]:
            if str(title["id"]) == request.match_info["title_id"]:
                if not isinstance(body, dict) or not body.get("label"):
                    return bad_request("label")
                title["label"] = body["label"]
                title["isFavorite"] = bool(body.get("isFavorite"))
                return data(title)
        return not_found()

    async def numbering(self, request: web.Request) -> web.Response:
        if self._club_id(request) is None:
            return not_found()
        if request.match_info["kind"] != "invoice":
            return bad_request("type")
        return web.json_response(
            {
                "data": {
                    "prefix": "",
                    "suffix": "",
                    "length": 6,
                    "datePartType": "YYYY",
                    "currentValue": "33",
                    "startValue": "1",
                    "id": 9001,
                }
            }
        )

    async def next_number(self, request: web.Request) -> web.Response:
        if self._club_id(request) is None:
            return not_found()
        if request.match_info["kind"] != "invoice":
            return bad_request("type")
        return web.json_response({"data": "2026000033"})
