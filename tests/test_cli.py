"""The command line interface in scripts/meinverein.py, run against the mock."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import ModuleType

import pytest

from pymeinverein.testing import DEMO_EMAIL, DEMO_PASSWORD, MockServer

SCRIPT = Path(__file__).parent.parent / "scripts" / "meinverein.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("meinverein_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli = _load()

type Run = Callable[..., Awaitable[tuple[int, str, str]]]


@pytest.fixture
def run(
    server: MockServer,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> Run:
    monkeypatch.setenv("MEINVEREIN_EMAIL", DEMO_EMAIL)
    monkeypatch.setenv("MEINVEREIN_PASSWORD", DEMO_PASSWORD)
    monkeypatch.delenv("MEINVEREIN_CLUB", raising=False)

    async def invoke(*argv: str) -> tuple[int, str, str]:
        capsys.readouterr()
        code = await cli.amain(
            [
                "--api-url",
                server.api_url,
                "--login-url",
                server.login_url,
                "--club",
                "Demoverein",
                *argv,
            ]
        )
        out, err = capsys.readouterr()
        return code, out, err

    return invoke


async def test_clubs_as_json(run: Run) -> None:
    code, out, _ = await run("clubs", "--json")
    assert code == 0
    assert "Demoverein" in {club["name"] for club in json.loads(out)}


async def test_whoami(run: Run) -> None:
    code, out, _ = await run("whoami")
    assert code == 0
    assert "@" in out


async def test_token_can_be_reused(run: Run, server: MockServer) -> None:
    code, token, _ = await run("token")
    assert code == 0 and token.strip()
    code = await cli.amain(
        ["--api-url", server.api_url, "--token", f"Bearer {token.strip()}", "clubs"]
    )
    assert code == 0


async def test_members_list_table(run: Run) -> None:
    code, out, err = await run("members", "list", "--status", "former")
    assert code == 0
    lines = out.splitlines()
    assert lines[0].split() == ["memberId", "firstName", "lastName", "email"]
    assert "Greta" in out and "Paul" in out
    assert "2 entries" in err


async def test_members_export_csv_to_file(run: Run, tmp_path: Path) -> None:
    target = tmp_path / "members.csv"
    code, _, err = await run(
        "members",
        "export",
        "-o",
        str(target),
        "--fields",
        "firstName,lastName",
        "--status",
        "former",
        "--delimiter",
        ";",
    )
    assert code == 0, err
    rows = list(csv.reader(io.StringIO(target.read_text()), delimiter=";"))
    assert rows == [
        ["firstName", "lastName"],
        ["Greta", "Vorlage"],
        ["Paul", "Entwurf"],
    ]


async def test_members_export_json_to_stdout(run: Run) -> None:
    code, out, _ = await run(
        "members", "export", "--fields", "minimal", "--status", "former", "--omit-empty"
    )
    assert code == 0
    assert [row["firstName"] for row in json.loads(out)] == ["Greta", "Paul"]


async def test_create_update_show_delete(run: Run) -> None:
    code, out, err = await run(
        "members",
        "create",
        "--json",
        "--last-name",
        "Lovelace",
        "--first-name",
        "Ada",
        "--email",
        "ada@example.org",
        "--birthday",
        "1815-12-10",
        "--set",
        "address.city=London",
    )
    assert code == 0, err
    member_id = json.loads(out)["id"]

    code, out, err = await run(
        "members", "update", str(member_id), "--set", "phone=0123 456"
    )
    assert code == 0, err
    assert "Updated Ada Lovelace" in out

    code, out, _ = await run("members", "show", str(member_id))
    shown = json.loads(out)
    assert shown["phone"] == "0123 456"
    assert shown["email"] == "ada@example.org"
    assert shown["address"]["city"] == "London"

    code, out, _ = await run("members", "delete", str(member_id), "--yes")
    assert code == 0
    assert "Deleted 1" in out
    code, _, err = await run("members", "show", str(member_id))
    assert code == 1 and "404" in err


async def test_delete_needs_confirmation_without_terminal(run: Run) -> None:
    code, out, _ = await run("members", "create", "--json", "--last-name", "Keep")
    member_id = str(json.loads(out)["id"])
    code, _, err = await run("members", "delete", member_id)
    assert code == 2
    assert "--yes" in err
    code, _, _ = await run("members", "show", member_id)
    assert code == 0


async def test_update_without_changes_is_an_error(run: Run) -> None:
    code, _, err = await run("members", "update", "1")
    assert code == 2
    assert "--set" in err


async def test_errors_are_reported_not_raised(run: Run) -> None:
    code, _, err = await run("members", "show", "999999")
    assert code == 1
    assert err.startswith("meinverein: ")


@pytest.mark.parametrize(
    "command",
    [
        ["lists"],
        ["departments"],
        ["roles"],
        ["fields"],
        ["rates"],
        ["events", "--from", "2020-01-01", "--days", "3650"],
        ["accounts"],
        ["documents"],
        ["reports"],
    ],
)
async def test_read_commands(run: Run, command: list[str]) -> None:
    code, out, err = await run(*command)
    assert code == 0, err
    assert out.strip()
    code, out, err = await run(*command, "--json")
    assert code == 0, err
    assert isinstance(json.loads(out), list)


def test_parse_assignments() -> None:
    assert cli.parse_assignments(
        ["a=1", "b=text", "c.d=true", "c.e=null", "f=[1, 2]"]
    ) == {"a": 1, "b": "text", "c": {"d": True, "e": None}, "f": [1, 2]}
    with pytest.raises(cli.UsageError):
        cli.parse_assignments(["novalue"])


def test_report_inputs() -> None:
    from datetime import date

    assert cli.parse_report_input("2026-01-01..2026-12-31") == (
        date(2026, 1, 1),
        date(2026, 12, 31),
    )
    assert cli.parse_report_input("3") == 3
