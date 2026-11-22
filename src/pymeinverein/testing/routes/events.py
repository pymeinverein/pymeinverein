"""Calendar events and categories.

Observed on the real API:

* The list filter travels as JSON text in the query parameter ``body``; only
  events of the categories named in ``categoryIds`` are returned (none without).
* Members' birthdays are added as automatic all-day entries without ``id``.
* Creating an event needs ``categoryId``.
* Deleting with ``wholeSeries: false`` answers ``404``, also for single events.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from aiohttp import web

from .._responses import api_error, bad_request, not_found
from ..state import Json, now_iso
from ._base import NEW, OLD, RouteGroup, json_body


def _parse(value: str) -> datetime:
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class EventRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get(f"{OLD}/event-categories", self.categories)
        router.add_post(f"{OLD}/event-categories", self.create_category)
        router.add_delete(
            f"{NEW}/event-categories/{{category_id}}", self.delete_category
        )
        router.add_get(f"{OLD}/events", self.events)
        router.add_get(f"{OLD}/events/{{event_id}}", self.event)
        router.add_get(f"{NEW}/calendar/search", self.search)
        router.add_post(f"{NEW}/calendar/create", self.create)
        router.add_post(f"{NEW}/calendar/delete", self.delete)
        router.add_post(f"{NEW}/event/{{event_id}}", self.update)

    def _event(self, request: web.Request) -> tuple[int, Json] | None:
        club_id = self._club_id(request)
        raw = request.match_info["event_id"]
        if club_id is None or not raw.isdecimal():
            return None
        event = self.state.events[club_id].get(int(raw))
        return None if event is None else (club_id, event)

    def _with_category(self, club_id: int, event: Json) -> Json:
        category = next(
            (
                item
                for item in self.state.event_categories[club_id]
                if item["id"] == event.get("categoryId")
            ),
            None,
        )
        return {**event, "category": category}

    # --------------------------------------------------------------- categories

    async def categories(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        return web.json_response({"categories": self.state.event_categories[club_id]})

    async def create_category(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        missing = [
            {"param": key, "msg": ""}
            for key in ("name", "color")
            if not isinstance(body, dict) or not body.get(key)
        ]
        if missing:
            return api_error(400, "BadRequestError", missing)
        category = {
            "id": self.state.next_id(),
            "clubId": club_id,
            "name": body["name"],
            "color": body["color"],
            "type": "custom",
            "checked": True,
        }
        self.state.event_categories[club_id].append(category)
        return web.json_response({"category": category})

    async def delete_category(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        categories = self.state.event_categories[club_id]
        kept = [
            item
            for item in categories
            if str(item["id"]) != request.match_info["category_id"]
        ]
        if len(kept) == len(categories):
            return not_found()
        self.state.event_categories[club_id] = kept
        return web.Response(status=200)

    # ------------------------------------------------------------------- events

    def _birthdays(self, club_id: int, start: datetime, end: datetime) -> list[Json]:
        category = next(
            (
                item
                for item in self.state.event_categories[club_id]
                if item["type"] == "birthday"
            ),
            None,
        )
        entries: list[Json] = []
        if category is None:
            return entries
        for member in self.state.members[club_id].values():
            if not member.get("birthday") or member["state"] == 1:
                continue
            born = _parse(member["birthday"])
            for year in range(start.year, end.year + 1):
                day = datetime(year, born.month, born.day, tzinfo=UTC)
                if start <= day <= end:
                    name = f"{member['firstName']} {member['lastName']}"
                    entries.append(
                        {
                            "title": f"{name} hat Geburtstag",
                            "startDate": day.isoformat().replace("+00:00", ".000Z"),
                            "endDate": (day + timedelta(days=1))
                            .isoformat()
                            .replace("+00:00", ".000Z"),
                            "eventLength": 0,
                            "fullDay": True,
                            "category": category,
                            "clubId": club_id,
                            "participants": [],
                        }
                    )
        return entries

    async def events(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        try:
            body = json.loads(request.query.get("body", ""))
        except ValueError:
            return bad_request("body", "REQUIRED", "REQUIRED")
        if not body.get("startDate") or not body.get("endDate"):
            return api_error(
                400,
                "BadRequestError",
                [
                    {"param": key, "value": "", "msg": ""}
                    for key in ("startDate", "endDate")
                ],
            )
        start, end = _parse(body["startDate"]), _parse(body["endDate"])
        category_ids = body.get("categoryIds") or []
        search = (body.get("searchText") or "").casefold()
        found = [
            self._with_category(club_id, event)
            for event in self.state.events[club_id].values()
            if event["categoryId"] in category_ids
            and _parse(event["startDate"]) <= end
            and _parse(event["endDate"]) >= start
            and search in event["title"].casefold()
        ]
        birthdays = [
            entry
            for entry in self._birthdays(club_id, start, end)
            if entry["category"]["id"] in category_ids
        ]
        return web.json_response({"events": birthdays + found})

    async def event(self, request: web.Request) -> web.Response:
        found = self._event(request)
        if found is None:
            return not_found()
        return web.json_response({"event": found[1]})

    async def search(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        term = request.query.get("searchTerm", "").casefold()
        return web.json_response(
            {
                "data": [
                    event
                    for event in self.state.events[club_id].values()
                    if term in event["title"].casefold()
                ]
            }
        )

    async def create(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        event = body.get("event") if isinstance(body, dict) else None
        if not isinstance(event, dict) or not event.get("title"):
            return bad_request("title", "REQUIRED", "REQUIRED")
        known = {item["id"] for item in self.state.event_categories[club_id]}
        if event.get("categoryId") not in known:
            return bad_request("categoryId", "REQUIRED", "REQUIRED")
        timestamp = now_iso()
        length = _parse(event["endDate"]) - _parse(event["startDate"])
        stored: Json = {
            **event,
            "id": self.state.next_id(),
            "clubId": club_id,
            "participants": event.get("participants") or [],
            "eventLength": int(length.total_seconds()),
            "recType": None,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        self.state.events[club_id][stored["id"]] = stored
        return web.json_response({"data": stored})

    async def update(self, request: web.Request) -> web.Response:
        found = self._event(request)
        if found is None:
            return not_found()
        _, event = found
        body = await json_body(request)
        if not isinstance(body, dict) or not body.get("title"):
            return bad_request("title", "REQUIRED", "REQUIRED")
        for key, value in body.items():
            if key not in ("id", "clubId", "skipEmailNotifications", "resetSeries"):
                event[key] = value
        event["updatedAt"] = now_iso()
        return web.json_response({"event": event})

    async def delete(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        event = body.get("event") if isinstance(body, dict) else None
        event_id = event.get("id") if isinstance(event, dict) else None
        if event_id not in self.state.events[club_id] or not body.get("wholeSeries"):
            return not_found()
        return web.json_response({"data": self.state.events[club_id].pop(event_id)})
