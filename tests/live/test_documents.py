"""Live test for the document storage."""

from __future__ import annotations

import pytest

from pymeinverein import BadRequestError
from pymeinverein.api.clubs import ClubClient

from .conftest import MARKER

pytestmark = pytest.mark.live


async def test_document_lifecycle(demo_club: ClubClient) -> None:
    club = demo_club
    try:
        folder = await club.documents.create_directory(f"{MARKER} dir")
        sub = await club.documents.create_directory(f"{MARKER} sub", parent=folder)
        assert sub.parent_id == folder.id

        document = await club.documents.upload(
            folder, b"hello pymeinverein\n", name=f"{MARKER}.txt"
        )
        assert (document.name, document.document_type, document.size) == (
            MARKER,
            "txt",
            19,
        )
        assert await club.documents.download(document.id) == b"hello pymeinverein\n"

        listed = await club.documents.list(f"{MARKER} dir")
        assert {(e.name, e.is_directory) for e in listed} == {
            (f"{MARKER} sub", True),
            (MARKER, False),
        }

        await club.documents.rename_document(document.id, f"{MARKER} renamed")
        await club.documents.rename_directory(sub, f"{MARKER} sub2")
        moved = await club.documents.move(
            [document.id], source=folder, target=f"{MARKER} dir/{MARKER} sub2"
        )
        assert moved.moved_document_ids == [document.id]
        in_sub = await club.documents.list(sub.id)
        assert [e.name for e in in_sub] == [f"{MARKER} renamed"]

        spaced = await club.documents.upload(
            folder, b"another small text file\n", name=f"{MARKER} Größe 1.txt"
        )
        assert spaced.name == f"{MARKER} Größe 1"

        await club.documents.delete_document(document.id)
        await club.documents.delete_directory(folder)
        with pytest.raises(BadRequestError) as excinfo:
            await club.documents.list(sub.id)  # deleted with its parent
        assert excinfo.value.name == "DIRECTORY_DOES_NOT_EXIST"
    finally:
        for entry in await club.documents.list():
            if MARKER in entry.name:
                await club.documents.delete_directory(entry.id)
