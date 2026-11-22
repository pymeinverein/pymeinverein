"""JSON and CSV export of members."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from pymeinverein import LookupFailedError
from pymeinverein.api.clubs import ClubClient
from pymeinverein.export import (
    FIELD_SETS,
    export_members,
    member_records,
    resolve_fields,
    to_csv,
    to_json,
)
from pymeinverein.models import Member


def _rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


async def test_minimal_json_export(club: ClubClient) -> None:
    text = await club.members.export(status="former")
    assert json.loads(text) == [
        {
            "memberId": "6",
            "firstName": "Greta",
            "lastName": "Vorlage",
            "email": "greta.vorlage@example.org",
        },
        {
            "memberId": "7",
            "firstName": "Paul",
            "lastName": "Entwurf",
            "email": "paul.entwurf@example.org",
        },
    ]


async def test_minimal_csv_export(club: ClubClient) -> None:
    text = await club.members.export(format="csv", type="contact")
    assert text == (
        "memberId,firstName,lastName,email\n"
        "9,Hans,Kontakt,hans.kontakt@example.org\n"
        "10,,Sporthaus Beispiel GmbH,info@sporthaus.example\n"
    )


async def test_export_to_file_infers_format(club: ClubClient, tmp_path: Path) -> None:
    csv_file = tmp_path / "members.csv"
    text = await club.members.export(csv_file, from_list="Vorstand")
    assert csv_file.read_text(encoding="utf-8") == text
    assert _rows(text)[1:] == [
        ["1", "Demo", "User", "demo@example.org"],
        ["2", "Erika", "Beispiel", "erika.beispiel@example.org"],
    ]

    json_file = tmp_path / "members.json"
    await club.members.export(json_file, search="erika")
    assert json.loads(json_file.read_text(encoding="utf-8"))[0]["firstName"] == "Erika"

    with pytest.raises(ValueError, match="format="):
        await club.members.export(tmp_path / "members.txt")


async def test_export_selected_and_computed_fields(club: ClubClient) -> None:
    text = await club.members.export(
        format="json",
        search="erika",
        fields=[
            "full_name",
            "typeName",
            "statusName",
            "genderName",
            "birthday",
            "membership_begin_at",
            "address.city",
            "address.country",
            "departments",
            "roles",
            "custom.Position",
            "custom.Spielberechtigt",
            f"custom.{3002}",
        ],
    )
    assert json.loads(text) == [
        {
            "full_name": "Erika Beispiel",
            "typeName": "member",
            "statusName": "active",
            "genderName": "female",
            "birthday": "1988-04-12",
            "membership_begin_at": "2015-03-01",
            "address.city": "Berlin",
            "address.country": "Deutschland",
            "departments": ["1. Mannschaft - Damen"],
            "roles": ["Finanzverwalter"],
            "custom.Position": "Tor",
            "custom.Spielberechtigt": "true",
            "custom.3002": "Tor",
        }
    ]


async def test_export_with_custom_headers_and_delimiter(club: ClubClient) -> None:
    text = await club.members.export(
        format="csv",
        delimiter=";",
        department="1. Mannschaft - Herren",
        fields={
            "Nr": "memberId",
            "Name": "fullName",
            "Abteilung": "departments",
            "Position": "custom.Position",
        },
    )
    assert _rows(text.replace(";", ",")) == [
        ["Nr", "Name", "Abteilung", "Position"],
        ["3", "Max Muster", "1. Mannschaft - Herren", "Sturm"],
        ["5", "Jonas Test", "1. Mannschaft - Herren", ""],
    ]


async def test_export_omit_empty(club: ClubClient) -> None:
    text = await club.members.export(search="Jonas", omit_empty=True)
    assert json.loads(text) == [
        {"memberId": "5", "firstName": "Jonas", "lastName": "Test"}
    ]


async def test_export_unknown_custom_field(club: ClubClient) -> None:
    with pytest.raises(LookupFailedError, match="'Position'"):
        await club.members.export(fields=["custom.Schuhgröße"])


async def test_full_field_set(club: ClubClient) -> None:
    text = await club.members.export(format="csv", fields="full")
    rows = _rows(text)
    assert rows[0] == list(FIELD_SETS["full"])
    assert len(rows) == 11
    erika = dict(zip(rows[0], rows[2]))
    assert erika["typeName"] == "member"
    assert erika["address.zip"] == "10115"
    assert erika["departments"] == "1. Mannschaft - Damen"


def test_resolve_fields() -> None:
    assert resolve_fields("minimal")[0] == ("memberId", "memberId")
    assert resolve_fields(["a", "b.c"]) == [("a", "a"), ("b.c", "b.c")]
    assert resolve_fields({"Name": "lastName"}) == [("Name", "lastName")]
    with pytest.raises(ValueError, match="contact, full, minimal"):
        resolve_fields("everything")


def test_csv_quoting_and_value_formatting() -> None:
    records = [{"a": 'He said "hi", twice', "b": None, "c": True, "d": ["x", "y"]}]
    assert to_csv(records) == 'a,b,c,d\n"He said ""hi"", twice",,true,x; y\n'
    assert to_csv([], ["a"]) == "a\n"
    assert to_json([{"ä": 1}], indent=None) == '[{"ä": 1}]\n'


def test_records_from_models_without_server() -> None:
    members = [
        Member.model_validate(
            {"id": 1, "memberId": 7, "lastName": "Solo", "type": 3, "state": 9}
        )
    ]
    records = member_records(members, ["memberId", "typeName", "statusName", "nope.x"])
    assert records == [
        {"memberId": "7", "typeName": "company", "statusName": None, "nope.x": None}
    ]
    with pytest.raises(ValueError, match="json"):
        export_members(members, "xml")  # type: ignore[arg-type]
