"""Document storage: folders and files.

Observed on the real API:

* Ids are UUIDs. The top level only holds folders.
* An uploaded file is listed without its extension; the kind of file is kept
  in ``documentType``. The upload answers ``201``.
* Deleting a folder deletes everything in it.
* Errors of this service look different: ``{"code": ..., "message": ...}``.
"""

from __future__ import annotations

import uuid
from pathlib import PurePath

from aiohttp import web

from .. import seed
from .._responses import data, not_found
from ..state import Json, now_iso
from ._base import NEW, RouteGroup, json_body


def _missing(directory_id: str) -> web.Response:
    return web.json_response(
        {
            "code": "DIRECTORY_DOES_NOT_EXIST",
            "message": "Das Verzeichnis existiert nicht.",
            "details": {"directoryId": directory_id},
        },
        status=400,
    )


class DocumentRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        dms = f"{NEW}/dms"
        router.add_get(f"{dms}/directories/tree", self.tree)
        router.add_get(f"{dms}/directories", self.listing)
        router.add_post(f"{dms}/directories", self.create_directory)
        router.add_get(f"{dms}/directories/{{entry_id}}", self.listing)
        router.add_patch(f"{dms}/directories/{{entry_id}}", self.rename)
        router.add_delete(f"{dms}/directories/{{entry_id}}", self.delete)
        router.add_post(f"{dms}/documents/move", self.move)
        router.add_post(f"{dms}/documents/{{entry_id}}", self.upload)
        router.add_get(f"{dms}/documents/{{entry_id}}/download", self.download)
        router.add_patch(f"{dms}/documents/{{entry_id}}", self.rename)
        router.add_delete(f"{dms}/documents/{{entry_id}}", self.delete)

    def _entries(self, request: web.Request) -> dict[str, Json] | None:
        club_id = self._club_id(request)
        return None if club_id is None else self.state.documents[club_id]

    def _children(self, entries: dict[str, Json], parent: str | None) -> list[Json]:
        return [entry for entry in entries.values() if entry["parentId"] == parent]

    def _node(self, entries: dict[str, Json], entry: Json) -> Json:
        return {
            "id": entry["id"],
            "isCurrentDirectory": False,
            "name": entry["name"],
            "children": [
                self._node(entries, child)
                for child in self._children(entries, entry["id"])
                if child["type"] == "directory"
            ],
        }

    async def tree(self, request: web.Request) -> web.Response:
        entries = self._entries(request)
        if entries is None:
            return not_found()
        return data(
            [
                self._node(entries, entry)
                for entry in self._children(entries, None)
                if not entry["isSystem"]
            ]
        )

    async def listing(self, request: web.Request) -> web.Response:
        entries = self._entries(request)
        if entries is None:
            return not_found()
        directory_id = request.match_info.get("entry_id")
        if directory_id is not None and directory_id not in entries:
            return _missing(directory_id)
        children = self._children(entries, directory_id)
        offset = int(request.query.get("offset", 0))
        limit = int(request.query.get("limit", 40))
        page = children[offset : offset + limit]
        return data(
            page,
            {
                "pagination": {
                    "offset": offset,
                    "limit": limit,
                    "totalItems": len(children),
                    "hasNextPage": offset + limit < len(children),
                },
                "capabilities": {
                    "canCreateDirectoryHere": True,
                    "canUploadDocumentHere": directory_id is not None,
                },
            },
        )

    async def create_directory(self, request: web.Request) -> web.Response:
        entries = self._entries(request)
        if entries is None:
            return not_found()
        body = await json_body(request)
        name = body.get("name") if isinstance(body, dict) else None
        parent = body.get("parentId") if isinstance(body, dict) else None
        if not isinstance(name, str) or not name.strip():
            return web.json_response({"code": "INVALID_NAME"}, status=400)
        if parent is not None and parent not in entries:
            return _missing(str(parent))
        created = seed.folder(str(uuid.uuid4()), name, parent)
        created["updatedAt"] = now_iso()
        entries[created["id"]] = created
        return data(created)

    async def upload(self, request: web.Request) -> web.Response:
        entries = self._entries(request)
        if entries is None:
            return not_found()
        directory_id = request.match_info["entry_id"]
        if directory_id not in entries:
            return _missing(directory_id)
        upload = (await request.post()).get("file")
        if not isinstance(upload, web.FileField):
            return web.json_response({"code": "FILE_REQUIRED"}, status=400)
        content = upload.file.read()
        filename = PurePath(upload.filename)
        document: Json = {
            "id": str(uuid.uuid4()),
            "name": filename.stem,
            "parentId": directory_id,
            "type": "document",
            "documentType": filename.suffix.lstrip(".").lower(),
            "mimeType": upload.content_type,
            "size": len(content),
            "isSystem": False,
            "updatedAt": now_iso(),
        }
        entries[document["id"]] = document
        self.state.document_files[document["id"]] = content
        return web.json_response({"meta": {}, "data": document}, status=201)

    async def download(self, request: web.Request) -> web.Response:
        entries = self._entries(request)
        entry_id = request.match_info["entry_id"]
        if entries is None or entry_id not in self.state.document_files:
            return not_found()
        return web.Response(
            body=self.state.document_files[entry_id],
            content_type=entries[entry_id]["mimeType"] or "application/octet-stream",
        )

    async def rename(self, request: web.Request) -> web.Response:
        entries = self._entries(request)
        entry_id = request.match_info["entry_id"]
        if entries is None or entry_id not in entries:
            return not_found()
        body = await json_body(request)
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not name.strip():
            return web.json_response({"code": "INVALID_NAME"}, status=400)
        entries[entry_id]["name"] = name
        return data(entries[entry_id])

    def _remove(self, entries: dict[str, Json], entry_id: str) -> None:
        for child in self._children(entries, entry_id):
            self._remove(entries, child["id"])
        entries.pop(entry_id, None)
        self.state.document_files.pop(entry_id, None)

    async def delete(self, request: web.Request) -> web.Response:
        entries = self._entries(request)
        entry_id = request.match_info["entry_id"]
        if entries is None or entry_id not in entries:
            return not_found()
        self._remove(entries, entry_id)
        return data({"deleted": True})

    async def move(self, request: web.Request) -> web.Response:
        entries = self._entries(request)
        if entries is None:
            return not_found()
        body = await json_body(request)
        target = body.get("targetDirectoryId") if isinstance(body, dict) else None
        if target not in entries:
            return _missing(str(target))
        moved, failed = [], []
        for document_id in body.get("documentIds", []):
            if document_id in entries and entries[document_id]["type"] == "document":
                entries[document_id]["parentId"] = target
                moved.append(document_id)
            else:
                failed.append(document_id)
        return data(
            {
                "movedDocumentIds": moved,
                "failedDocumentIds": failed,
                "skippedDocumentIds": [],
                "skips": [],
            }
        )
