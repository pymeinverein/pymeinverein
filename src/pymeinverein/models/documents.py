"""Models for the document storage ("Dokumente")."""

from __future__ import annotations

from datetime import datetime

from .base import ApiModel


class DocumentEntry(ApiModel):
    """A folder or a file. Ids are UUID text, not numbers."""

    id: str
    name: str
    parent_id: str | None = None
    #: ``directory`` or ``document``.
    type: str | None = None
    #: File kind such as ``pdf`` or ``txt``; ``directory`` for folders.
    document_type: str | None = None
    mime_type: str | None = None
    #: Size in bytes.
    size: int | None = None
    #: Folders MeinVerein manages itself; they cannot be changed.
    is_system: bool | None = None
    updated_at: datetime | None = None

    @property
    def is_directory(self) -> bool:
        return self.type == "directory" or self.document_type == "directory"


class DirectoryNode(ApiModel):
    """A folder in the folder tree."""

    id: str
    name: str
    children: list[DirectoryNode] = []


class MoveResult(ApiModel):
    """Answer when documents are moved to another folder."""

    moved_document_ids: list[str] = []
    failed_document_ids: list[str] = []
    skipped_document_ids: list[str] = []
