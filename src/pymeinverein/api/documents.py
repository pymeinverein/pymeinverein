"""Document storage ("Dokumente"): folders and files of a club."""

from __future__ import annotations

import asyncio
import builtins
import mimetypes
import re
from collections.abc import Iterable
from pathlib import Path

import aiohttp

from .._transport import Transport
from ..exceptions import LookupFailedError
from ..models.documents import DirectoryNode, DocumentEntry, MoveResult
from ._util import unwrap

#: A folder: its id, a path like ``"Protokolle/2026"`` or a model.
type DirectoryRef = str | DocumentEntry | DirectoryNode

_UUID = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.IGNORECASE)


class DocumentsAPI:
    """Manage the folders and files of one club.

    Files live in folders; the top level only holds folders. Folders are
    referred to by id, by path from the top (``"Protokolle/2026"``) or by a
    model object. Documents are referred to by id.
    """

    def __init__(self, transport: Transport, club_id: int) -> None:
        self._transport = transport
        self._base = f"/protected/club/{club_id}/dms"

    # ------------------------------------------------------------------ reading

    async def tree(self) -> builtins.list[DirectoryNode]:
        """Return the folder tree (folders only).

        ``GET /protected/club/{clubId}/dms/directories/tree``
        """
        path = f"{self._base}/directories/tree"
        payload = await self._transport.get(path)
        return [
            DirectoryNode.model_validate(node)
            for node in unwrap(payload, "data", f"GET {path}")
        ]

    async def _directory_id(self, ref: DirectoryRef | None) -> str | None:
        if ref is None:
            return None
        if not isinstance(ref, str):
            return ref.id
        if _UUID.match(ref):
            return ref
        nodes = await self.tree()
        found: DirectoryNode | None = None
        for part in [piece.strip() for piece in ref.split("/") if piece.strip()]:
            matches = [node for node in nodes if node.name == part]
            if len(matches) != 1:
                names = ", ".join(repr(node.name) for node in nodes)
                raise LookupFailedError(
                    f"Expected exactly one folder {part!r} in path {ref!r}, found "
                    f"{len(matches)}. Folders at that level: {names or 'none'}"
                )
            found = matches[0]
            nodes = found.children
        if found is None:
            raise LookupFailedError(f"{ref!r} is not a folder path")
        return found.id

    async def list(
        self, directory: DirectoryRef | None = None
    ) -> builtins.list[DocumentEntry]:
        """Return the folders and files in a folder (default: the top level).

        ``GET /protected/club/{clubId}/dms/directories/{directoryId}`` with
        ``offset`` and ``limit``; all pages are fetched.
        """
        directory_id = await self._directory_id(directory)
        path = f"{self._base}/directories"
        if directory_id is not None:
            path += f"/{directory_id}"
        entries: builtins.list[DocumentEntry] = []
        while True:
            payload = await self._transport.get(
                path, params={"offset": len(entries), "limit": 40}
            )
            page = unwrap(payload, "data", f"GET {path}")
            entries.extend(DocumentEntry.model_validate(item) for item in page)
            pagination = (payload.get("meta") or {}).get("pagination") or {}
            if not page or not pagination.get("hasNextPage"):
                return entries

    async def download(self, document_id: str) -> bytes:
        """Return the content of a file.

        ``GET /protected/club/{clubId}/dms/documents/{documentId}/download``
        """
        return await self._transport.request_bytes(
            "GET", f"{self._base}/documents/{document_id}/download"
        )

    # ------------------------------------------------------------------ folders

    async def create_directory(
        self, name: str, parent: DirectoryRef | None = None
    ) -> DocumentEntry:
        """Create a folder, at the top level or inside ``parent``.

        ``POST /protected/club/{clubId}/dms/directories``
        """
        path = f"{self._base}/directories"
        payload = await self._transport.post(
            path, {"name": name, "parentId": await self._directory_id(parent)}
        )
        data = dict(unwrap(payload, "data", f"POST {path}"))
        data.setdefault("type", "directory")
        return DocumentEntry.model_validate(data)

    async def rename_directory(self, directory: DirectoryRef, name: str) -> None:
        """Rename a folder.

        ``PATCH /protected/club/{clubId}/dms/directories/{directoryId}``
        """
        directory_id = await self._directory_id(directory)
        await self._transport.patch(
            f"{self._base}/directories/{directory_id}", {"name": name}
        )

    async def delete_directory(self, directory: DirectoryRef) -> None:
        """Delete a folder **with everything in it**.

        ``DELETE /protected/club/{clubId}/dms/directories/{directoryId}``
        """
        directory_id = await self._directory_id(directory)
        await self._transport.delete(f"{self._base}/directories/{directory_id}")

    # -------------------------------------------------------------------- files

    async def upload(
        self,
        directory: DirectoryRef,
        file: str | Path | bytes,
        *,
        name: str | None = None,
        content_type: str | None = None,
    ) -> DocumentEntry:
        """Upload a file into a folder.

        ``file`` is a path or the content as bytes; with bytes a ``name``
        (including the extension) is required. MeinVerein shows the name
        without extension and keeps the kind of file separately.
        ``POST /protected/club/{clubId}/dms/documents/{directoryId}``
        (multipart, field ``file``)
        """
        if isinstance(file, bytes):
            if not name:
                raise ValueError("name is required when the file is given as bytes")
            content = file
        else:
            source = Path(file)
            content = await asyncio.to_thread(source.read_bytes)
            name = name or source.name
        if content_type is None:
            content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        # quote_fields=False: otherwise aiohttp percent-encodes the file name
        # ("Satzung%202026.pdf") and MeinVerein stores it like that.
        form = aiohttp.FormData(quote_fields=False)
        form.add_field("file", content, filename=name, content_type=content_type)
        path = f"{self._base}/documents/{await self._directory_id(directory)}"
        payload = await self._transport.post_form(path, form)
        return DocumentEntry.model_validate(unwrap(payload, "data", f"POST {path}"))

    async def rename_document(self, document_id: str, name: str) -> None:
        """Rename a file.

        ``PATCH /protected/club/{clubId}/dms/documents/{documentId}``
        """
        await self._transport.patch(
            f"{self._base}/documents/{document_id}", {"name": name}
        )

    async def move(
        self,
        document_ids: Iterable[str],
        *,
        source: DirectoryRef,
        target: DirectoryRef,
    ) -> MoveResult:
        """Move files from one folder to another.

        ``POST /protected/club/{clubId}/dms/documents/move``
        """
        path = f"{self._base}/documents/move"
        payload = await self._transport.post(
            path,
            {
                "documentIds": builtins.list(document_ids),
                "targetDirectoryId": await self._directory_id(target),
                "sourceDirectoryId": await self._directory_id(source),
            },
        )
        return MoveResult.model_validate(unwrap(payload, "data", f"POST {path}"))

    async def delete_document(self, document_id: str) -> None:
        """Delete a file.

        ``DELETE /protected/club/{clubId}/dms/documents/{documentId}``
        """
        await self._transport.delete(f"{self._base}/documents/{document_id}")
