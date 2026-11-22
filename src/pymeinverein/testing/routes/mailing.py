"""Mailings: templates, drafts, previews, sent items and sending.

Observed on the real API:

* Templates and drafts are listed through ``/list/template`` and
  ``/list/draft``; other types answer ``400`` with a plain ``{"error": ...}``.
* Drafts have ``state`` 2, templates ``state`` 5. Both are deleted together
  with ``DELETE .../mailingDispatch`` and ``{"ids": [...]}``.
* A club with ``sendEmailEnabled: false`` cannot send: ``sendDirect`` answers
  with the "Request Rejected" page.

Nothing is e-mailed by the mock; sent messages are recorded in
``state.sent_items``.
"""

from __future__ import annotations

from aiohttp import web

from .._responses import bad_request, not_found, rejected
from ..state import Json, now_iso
from ._base import RouteGroup, json_body

_BASE = "/protected/clubs/{club_id}/mailingDispatch"
DRAFT, TEMPLATE = 2, 5


class MailingRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get(f"{_BASE}/list/items/{{box}}", self.items)
        router.add_get(f"{_BASE}/list/{{kind}}", self.listing)
        router.add_post(f"{_BASE}/template", self.create_template)
        router.add_get(f"{_BASE}/template/{{dispatch_id}}", self.get_template)
        router.add_put(f"{_BASE}/template/{{dispatch_id}}", self.update_template)
        router.add_post(f"{_BASE}/dispatch", self.create_draft)
        router.add_get(f"{_BASE}/dispatch/{{dispatch_id}}", self.get_draft)
        router.add_patch(f"{_BASE}/dispatch/{{dispatch_id}}", self.update_draft)
        router.add_delete(_BASE, self.delete)
        router.add_post(f"{_BASE}/emailPreview", self.preview)
        router.add_post(f"{_BASE}/sendDirect", self.send)

    def _store(self, request: web.Request) -> dict[int, Json] | None:
        club_id = self._club_id(request)
        return None if club_id is None else self.state.dispatches[club_id]

    def _find(self, request: web.Request, state: int) -> Json | None:
        store = self._store(request)
        raw = request.match_info["dispatch_id"]
        if store is None or not raw.isdecimal():
            return None
        item = store.get(int(raw))
        return item if item is not None and item["state"] == state else None

    def _receivers(self, request: web.Request, body: Json) -> list[Json] | None:
        club_id = self._club_id(request)
        assert club_id is not None
        receivers = []
        for entry in body.get("recipients") or []:
            member = self.state.members[club_id].get(entry.get("id"))
            if member is None:
                return None
            receivers.append(
                {
                    "id": member["id"],
                    "email": entry.get("email") or member["email"],
                    "firstName": member["firstName"],
                    "lastName": member["lastName"],
                    "communicationChannel": entry.get("communicationChannel", 0),
                }
            )
        return receivers

    @staticmethod
    def _valid(body: object) -> bool:
        return isinstance(body, dict) and isinstance(body.get("subject"), str)

    async def listing(self, request: web.Request) -> web.Response:
        store = self._store(request)
        if store is None:
            return not_found()
        kind = request.match_info["kind"]
        if kind not in ("draft", "template"):
            return web.json_response(
                {"error": "Invalid dispatch type. Valid types: draft, template"},
                status=400,
            )
        state, key = (
            (DRAFT, "dispatches") if kind == "draft" else (TEMPLATE, "templates")
        )
        return web.json_response(
            {"data": {key: [i for i in store.values() if i["state"] == state]}}
        )

    def _new(self, request: web.Request, body: Json, state: int) -> Json:
        store = self._store(request)
        assert store is not None
        timestamp = now_iso()
        item: Json = {
            "id": self.state.next_id(),
            "clubId": int(request.match_info["club_id"]),
            "name": body.get("name") or "",
            "subject": body["subject"],
            "html": body.get("html") or "",
            "state": state,
            "dispatchNumber": f"SE-{len(store) + 1}" if state == DRAFT else None,
            "receiver": [],
            "attachments": [],
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        store[item["id"]] = item
        return item

    async def create_template(self, request: web.Request) -> web.Response:
        body = await json_body(request)
        if self._store(request) is None:
            return not_found()
        if not self._valid(body):
            return bad_request("subject")
        return web.json_response({"template": self._new(request, body, TEMPLATE)})

    async def get_template(self, request: web.Request) -> web.Response:
        item = self._find(request, TEMPLATE)
        return not_found() if item is None else web.json_response({"data": item})

    async def update_template(self, request: web.Request) -> web.Response:
        item = self._find(request, TEMPLATE)
        if item is None:
            return not_found()
        body = await json_body(request)
        if not self._valid(body):
            return bad_request("subject")
        for key in ("name", "subject", "html"):
            item[key] = body.get(key, item[key])
        item["updatedAt"] = now_iso()
        return web.json_response({"success": True})

    async def create_draft(self, request: web.Request) -> web.Response:
        body = await json_body(request)
        if self._store(request) is None:
            return not_found()
        if not self._valid(body):
            return bad_request("subject")
        receivers = self._receivers(request, body)
        if receivers is None:
            return bad_request("recipients")
        item = self._new(request, body, DRAFT)
        item["receiver"] = receivers
        return web.json_response({"dispatch": item})

    async def get_draft(self, request: web.Request) -> web.Response:
        item = self._find(request, DRAFT)
        return not_found() if item is None else web.json_response({"data": item})

    async def update_draft(self, request: web.Request) -> web.Response:
        item = self._find(request, DRAFT)
        if item is None:
            return not_found()
        body = await json_body(request)
        if not self._valid(body):
            return bad_request("subject")
        receivers = self._receivers(request, body)
        if receivers is None:
            return bad_request("recipients")
        for key in ("name", "subject", "html"):
            item[key] = body.get(key, item[key])
        item["receiver"] = receivers
        item["updatedAt"] = now_iso()
        return web.json_response({"success": True})

    async def delete(self, request: web.Request) -> web.Response:
        store = self._store(request)
        if store is None:
            return not_found()
        body = await json_body(request)
        ids = body.get("ids") if isinstance(body, dict) else None
        if not isinstance(ids, list):
            return bad_request("ids")
        deleted = sum(store.pop(i, None) is not None for i in ids)
        return web.json_response({"deletedCount": deleted, "totalRequested": len(ids)})

    async def preview(self, request: web.Request) -> web.Response:
        body = await json_body(request)
        if self._store(request) is None:
            return not_found()
        if not self._valid(body):
            return bad_request("subject")
        receivers = self._receivers(request, body) or []
        return web.json_response(
            {
                "text": body.get("html") or "",
                "sender": "noreply@meinverein.de",
                "recipientEmail": receivers[0]["email"] if receivers else None,
                "attachments": [],
            }
        )

    async def items(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        box = request.match_info["box"]
        if box not in ("outbox", "sent", "deleted"):
            return not_found()
        found = self.state.sent_items[club_id] if box == "sent" else []
        return web.json_response(
            {"data": found, "totalCount": len(found), "page": 1, "pageSize": None}
        )

    async def send(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        if not self.state.clubs[club_id].get("sendEmailEnabled"):
            return rejected()
        body = await json_body(request)
        if not self._valid(body):
            return bad_request("subject")
        receivers = self._receivers(request, body)
        if receivers is None:
            return bad_request("recipients")
        for receiver in receivers:
            self.state.sent_items[club_id].append(
                {
                    "id": self.state.next_id(),
                    "clubId": club_id,
                    "address": receiver["email"],
                    "email": receiver["email"],
                    "name": body.get("name") or "",
                    "subject": body["subject"],
                    "communicationChannel": receiver["communicationChannel"],
                    "dispatchItemState": 1,
                    "type": "Sendung",
                    "lastAttemptAt": now_iso(),
                    "failureReason": None,
                    "failureCount": 0,
                    "receiver": {
                        "id": receiver["id"],
                        "fullName": f"{receiver['firstName']} {receiver['lastName']}",
                    },
                }
            )
        return web.json_response({"sentCount": len(receivers), "failedCount": 0})
