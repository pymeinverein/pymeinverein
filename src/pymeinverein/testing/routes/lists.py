"""Member lists.

Quirk copied from the real API: the content of a list depends on the
``x-api-version`` header - only ``v2`` and ``v3`` rows contain
``individualFieldData``.
"""

from __future__ import annotations

from aiohttp import web

from .._responses import bad_request, data, not_found
from ..state import Json, now_iso
from ._base import NEW, RouteGroup, json_body, public


class ListRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get(f"{NEW}/list/all", self.lists)
        router.add_post(f"{NEW}/list/all-members", self.all_members)
        router.add_post(f"{NEW}/list/create", self.create_list)
        router.add_get(f"{NEW}/list/criteria/{{list_id}}", self.list_criteria)
        router.add_post(f"{NEW}/list/criteria/{{list_id}}", self.add_criteria)
        router.add_delete(f"{NEW}/list/criteria", self.delete_criteria)
        field_criteria = f"{NEW}/list/individual-field-criteria"
        router.add_post(field_criteria + "/", self.add_field_criteria)
        router.add_get(field_criteria + "/{list_id}", self.list_field_criteria)
        router.add_delete(field_criteria + "/{list_id}", self.delete_field_criteria)
        router.add_post(f"{NEW}/list/favorites/{{list_id}}", self.favourite)
        router.add_delete(f"{NEW}/list/favorites/{{list_id}}", self.favourite)
        router.add_post(f"{NEW}/list/{{list_id}}/copy", self.copy_list)
        router.add_post(f"{NEW}/list/assign-members/{{list_id}}", self.assign_members)
        router.add_post(f"{NEW}/list/remove-members/{{list_id}}", self.remove_members)
        router.add_post(f"{NEW}/list/{{list_id}}", self.list_content)
        router.add_put(f"{NEW}/list/{{list_id}}", self.rename_list)
        router.add_delete(f"{NEW}/list/{{list_id}}", self.delete_list)

    async def lists(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        return data([public(item) for item in self.state.lists[club_id].values()])

    async def list_content(self, request: web.Request) -> web.Response:
        club_id, item = self._club_id(request), self._list(request)
        if club_id is None or item is None:
            return not_found()
        versioned = request.headers.get("x-api-version") in ("v2", "v3")
        rows = [
            self._row(club_id, member, versioned=versioned)
            for member in self._list_members(club_id, item)
        ]
        meta = {
            "listUserSettings": {"columnSettings": []},
            "criteriaList": self._criteria(item),
            "individualFieldCriteria": [],
            "clubRoles": [],
        }
        return data(rows, meta)

    @staticmethod
    def _criteria(item: Json) -> list[Json]:
        return [
            {"clubId": item["clubId"], "listId": item["id"], **rule}
            for rule in item["_criteria"]
        ]

    def _field_criteria(self, item: Json) -> list[Json]:
        fields = {f["id"]: f for f in self.state.individual_fields[item["clubId"]]}
        return [
            {
                "clubId": item["clubId"],
                "listId": item["id"],
                **rule,
                "individualField": fields.get(rule["individualFieldId"]),
            }
            for rule in item["_field_criteria"]
        ]

    async def list_criteria(self, request: web.Request) -> web.Response:
        item = self._list(request)
        if item is None:
            return not_found()
        return data(self._criteria(item))

    async def all_members(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        rules = body.get("criterias") if isinstance(body, dict) else None
        if not isinstance(rules, list):
            return bad_request("criterias")
        criteria: list[Json] = []
        for rule in rules:
            if not isinstance(rule, dict) or "columnName" not in rule:
                return bad_request("criterias")
            criteria.append(
                {
                    "columnName": str(rule["columnName"]),
                    "operator": str(rule.get("operator", "=")),
                    "value": rule.get("value"),
                }
            )
        members = self.state.members[club_id].values()
        return data([m for m in members if self._matches(m, criteria)])

    async def create_list(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not name.strip():
            return bad_request("name")
        timestamp = now_iso()
        item: Json = {
            "defaultListType": None,
            "id": self.state.next_id(),
            "clubId": club_id,
            "departmentId": None,
            "name": name,
            "listType": int(body.get("type") or 0),
            "isDefaultList": False,
            "updatedAt": timestamp,
            "createdAt": timestamp,
            "_criteria": [],
            "_field_criteria": [],
            "_member_ids": [],
        }
        self.state.lists[club_id][item["id"]] = item
        return data(public(item))

    async def rename_list(self, request: web.Request) -> web.Response:
        item = self._list(request)
        if item is None:
            return not_found()
        body = await json_body(request)
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not name.strip():
            return bad_request("name")
        item["name"] = name
        item["updatedAt"] = now_iso()
        return data([1])

    async def delete_list(self, request: web.Request) -> web.Response:
        club_id, item = self._club_id(request), self._list(request)
        if club_id is None or item is None:
            return not_found()
        del self.state.lists[club_id][item["id"]]
        return web.Response(status=200)

    async def assign_members(self, request: web.Request) -> web.Response:
        item = self._list(request)
        if item is None:
            return not_found()
        body = await json_body(request)
        ids = body.get("clubMemberIds") if isinstance(body, dict) else None
        if not isinstance(ids, list):
            return bad_request("clubMemberIds")
        for member_id in ids:
            if member_id not in item["_member_ids"]:
                item["_member_ids"].append(member_id)
        return data(public(item))

    async def remove_members(self, request: web.Request) -> web.Response:
        item = self._list(request)
        if item is None:
            return not_found()
        body = await json_body(request)
        ids = body.get("clubMemberIds") if isinstance(body, dict) else None
        if not isinstance(ids, list):
            return bad_request("clubMemberIds")
        removed = [i for i in ids if i in item["_member_ids"]]
        for member_id in removed:
            item["_member_ids"].remove(member_id)
        return data(
            {}, {"removedCount": len(removed), "skippedCount": len(ids) - len(removed)}
        )

    # ------------------------------------------------------------------ criteria

    async def add_criteria(self, request: web.Request) -> web.Response:
        item = self._list(request)
        if item is None:
            return not_found()
        body = await json_body(request)
        rules = body.get("criteria") if isinstance(body, dict) else None
        if not isinstance(rules, list):
            return bad_request("criteria")
        created = []
        for rule in rules:
            if not isinstance(rule, dict) or not rule.get("columnName"):
                return bad_request("criteria")
            entry = {
                "id": self.state.next_id(),
                "columnName": rule["columnName"],
                "operator": rule.get("operator", "="),
                "value": rule.get("value"),
            }
            item["_criteria"].append(entry)
            created.append({"clubId": item["clubId"], "listId": item["id"], **entry})
        return data(created)

    async def delete_criteria(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        ids = body.get("criteriaIds") if isinstance(body, dict) else None
        if not isinstance(ids, list):
            return bad_request("criteriaIds", ["REQUIRED", "NO_ARRAY"])
        for item in self.state.lists[club_id].values():
            item["_criteria"] = [r for r in item["_criteria"] if r["id"] not in ids]
        return web.Response(status=200)

    async def add_field_criteria(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        body = await json_body(request)
        if club_id is None or not isinstance(body, dict):
            return not_found()
        item = self.state.lists[club_id].get(body.get("listId", 0))
        rules = body.get("criteria")
        if item is None or not isinstance(rules, list):
            return bad_request("listId")
        for rule in rules:
            item["_field_criteria"].append(
                {
                    "id": self.state.next_id(),
                    "individualFieldId": rule["individualFieldId"],
                    "operator": rule.get("operator", "="),
                    "value": rule.get("value"),
                }
            )
        created = self._field_criteria(item)[-len(rules) :] if rules else []
        return data(
            [{k: v for k, v in c.items() if k != "individualField"} for c in created]
        )

    async def list_field_criteria(self, request: web.Request) -> web.Response:
        item = self._list(request)
        if item is None:
            return not_found()
        return data(self._field_criteria(item))

    async def delete_field_criteria(self, request: web.Request) -> web.Response:
        # Observed: the rules to delete are named in the body ("criteriaIds");
        # without it the real service answers 400.
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        ids = body.get("criteriaIds") if isinstance(body, dict) else None
        if not isinstance(ids, list):
            return bad_request("criteriaIds", ["REQUIRED", "NO_ARRAY"])
        for item in self.state.lists[club_id].values():
            item["_field_criteria"] = [
                r for r in item["_field_criteria"] if r["id"] not in ids
            ]
        return web.Response(status=200)

    # ------------------------------------------------------ copy and favourites

    async def copy_list(self, request: web.Request) -> web.Response:
        club_id, item = self._club_id(request), self._list(request)
        if club_id is None or item is None:
            return not_found()
        body = await json_body(request)
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not name.strip():
            return bad_request("name")
        timestamp = now_iso()
        clone: Json = {
            **item,
            "id": self.state.next_id(),
            "name": name,
            "isDefaultList": False,
            "defaultListType": None,
            "isFavourite": False,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "_criteria": [
                {**rule, "id": self.state.next_id()} for rule in item["_criteria"]
            ],
            "_field_criteria": [
                {**rule, "id": self.state.next_id()} for rule in item["_field_criteria"]
            ],
            "_member_ids": list(item["_member_ids"]),
        }
        self.state.lists[club_id][clone["id"]] = clone
        return data(public(clone))

    async def favourite(self, request: web.Request) -> web.Response:
        item = self._list(request)
        if item is None:
            return not_found()
        item["isFavourite"] = request.method == "POST"
        return web.Response(status=200)
