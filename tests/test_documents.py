"""Document storage against the mock server."""

from __future__ import annotations

from pathlib import Path

import pytest

from pymeinverein import BadRequestError, LookupFailedError, NotFoundError
from pymeinverein.api.clubs import ClubClient
from pymeinverein.testing import seed


async def test_top_level_and_tree(club: ClubClient) -> None:
    top = await club.documents.list()
    assert [(e.name, e.is_directory, e.is_system) for e in top] == [
        ("Systemordner", True, True),
        ("Allgemeines", True, False),
    ]
    assert [node.name for node in await club.documents.tree()] == ["Allgemeines"]


async def test_folders_by_id_path_and_model(club: ClubClient) -> None:
    minutes = await club.documents.create_directory("Protokolle")
    assert minutes.is_directory and minutes.parent_id is None
    year = await club.documents.create_directory("2026", parent="Protokolle")
    assert year.parent_id == minutes.id
    await club.documents.create_directory("Q1", parent=year)

    tree = await club.documents.tree()
    assert [node.name for node in tree] == ["Allgemeines", "Protokolle"]
    assert tree[1].children[0].children[0].name == "Q1"

    assert [e.name for e in await club.documents.list("Protokolle/2026")] == ["Q1"]
    assert [e.name for e in await club.documents.list(minutes.id)] == ["2026"]

    await club.documents.rename_directory("Protokolle/2026", "2026 alt")
    assert [e.name for e in await club.documents.list(minutes)] == ["2026 alt"]
    with pytest.raises(LookupFailedError, match="'2026 alt'"):
        await club.documents.list("Protokolle/2026")


async def test_file_lifecycle(club: ClubClient, tmp_path: Path) -> None:
    source = tmp_path / "Satzung 2026.pdf"
    source.write_bytes(b"%PDF-fake")
    document = await club.documents.upload("Allgemeines", source)
    # Like the real service: the name is listed without extension.
    assert (document.name, document.document_type, document.size) == (
        "Satzung 2026",
        "pdf",
        9,
    )
    assert document.mime_type == "application/pdf" and not document.is_directory
    assert await club.documents.download(document.id) == b"%PDF-fake"

    await club.documents.rename_document(document.id, "Satzung")
    listed = await club.documents.list(seed.FOLDER_GENERAL)
    assert [e.name for e in listed] == ["Satzung"]

    archive = await club.documents.create_directory("Archiv")
    result = await club.documents.move(
        [document.id, "not-a-document"], source="Allgemeines", target=archive
    )
    assert result.moved_document_ids == [document.id]
    assert result.failed_document_ids == ["not-a-document"]
    assert await club.documents.list("Allgemeines") == []

    await club.documents.delete_document(document.id)
    assert await club.documents.list("Archiv") == []
    with pytest.raises(NotFoundError):
        await club.documents.download(document.id)


async def test_upload_bytes(club: ClubClient) -> None:
    note = await club.documents.upload("Allgemeines", b"hallo", name="notiz.txt")
    assert (note.name, note.document_type, note.mime_type) == (
        "notiz",
        "txt",
        "text/plain",
    )
    with pytest.raises(ValueError, match="name is required"):
        await club.documents.upload("Allgemeines", b"hallo")


async def test_deleting_a_folder_deletes_its_content(club: ClubClient) -> None:
    await club.documents.create_directory("Projekt")
    await club.documents.create_directory("Fotos", parent="Projekt")
    photo = await club.documents.upload("Projekt/Fotos", b"jpg", name="a.jpg")
    await club.documents.delete_directory("Projekt")
    assert [node.name for node in await club.documents.tree()] == ["Allgemeines"]
    with pytest.raises(NotFoundError):
        await club.documents.download(photo.id)


async def test_listing_is_paged(club: ClubClient) -> None:
    for number in range(45):
        await club.documents.upload("Allgemeines", b"x", name=f"datei-{number:02}.txt")
    entries = await club.documents.list("Allgemeines")
    assert len(entries) == 45 and len({e.id for e in entries}) == 45


async def test_document_service_errors(club: ClubClient) -> None:
    with pytest.raises(BadRequestError) as excinfo:
        await club.documents.list("00000000-0000-4000-8000-00000000ffff")
    assert excinfo.value.name == "DIRECTORY_DOES_NOT_EXIST"
    assert "existiert nicht" in str(excinfo.value)
