#!/usr/bin/env python3
"""Command line interface for pymeinverein.

Run it from a checkout with ``uv run scripts/meinverein.py COMMAND ...``;
``--help`` after any command shows its options. Examples::

    export MEINVEREIN_EMAIL=... MEINVEREIN_PASSWORD=...
    export MEINVEREIN_TOKEN=$(uv run scripts/meinverein.py token)   # log in once

    uv run scripts/meinverein.py clubs
    uv run scripts/meinverein.py --club Demoverein members list --status active
    uv run scripts/meinverein.py members export -o members.csv --fields contact
    uv run scripts/meinverein.py members create --last-name Lovelace \\
        --first-name Ada --email ada@example.org --set address.city=London
    uv run scripts/meinverein.py members update 1234 --set phone="0123 456"
    uv run scripts/meinverein.py members delete 1234

Authentication follows the library: ``--token`` or ``MEINVEREIN_TOKEN`` skips
the login, otherwise ``--email`` / ``MEINVEREIN_EMAIL`` and
``MEINVEREIN_PASSWORD`` are used (the password is asked for when only the
e-mail address is known). The club is chosen with ``--club`` (id or name) or
``MEINVEREIN_CLUB``; by default the club selected in the web application.

Commands that change data act on whichever club is chosen - there is no demo
club guard here, unlike ``scripts/probe.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys
from collections.abc import Callable, Coroutine, Mapping, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from pymeinverein import MeinVereinClient, MeinVereinError, MemberType, __version__
from pymeinverein.api.clubs import ClubClient
from pymeinverein.export import FIELD_SETS, member_records, to_csv, to_json

ENV_CLUB = "MEINVEREIN_CLUB"

Handler = Callable[[argparse.Namespace, MeinVereinClient], Coroutine[Any, Any, int]]


class UsageError(Exception):
    """Wrong command line input that argparse cannot detect."""


# --------------------------------------------------------------------- output


def jsonable(value: Any) -> Any:
    """Turn models (and lists of them) into plain JSON data."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def print_json(value: Any) -> None:
    print(json.dumps(jsonable(value), indent=2, ensure_ascii=False))


def cell(value: Any, width: int = 40) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, datetime):
        local = value.astimezone() if value.tzinfo else value
        midnight = local.time() == datetime.min.time()
        return local.strftime("%Y-%m-%d" if midnight else "%Y-%m-%d %H:%M")
    if isinstance(value, (list, tuple)):
        value = ", ".join(cell(item, width) for item in value)
    text = str(value).replace("\n", " ")
    return text if len(text) <= width else text[: width - 1] + "…"


def print_table(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    """Print rows as aligned columns; ``columns`` are the keys to show."""
    if not rows:
        print("(nothing found)")
        return
    cells = [[cell(row.get(column)) for column in columns] for row in rows]
    widths = [
        max(len(column), *(len(line[i]) for line in cells))
        for i, column in enumerate(columns)
    ]
    print("  ".join(c.ljust(w) for c, w in zip(columns, widths)).rstrip())
    print("  ".join("-" * w for w in widths))
    for line in cells:
        print("  ".join(c.ljust(w) for c, w in zip(line, widths)).rstrip())


def show(
    args: argparse.Namespace,
    items: Sequence[BaseModel],
    columns: Sequence[str],
) -> int:
    """Print models as JSON (``--json``) or as a table of some attributes."""
    if args.json:
        print_json(list(items))
    else:
        rows = [
            {column: getattr(item, column, None) for column in columns}
            for item in items
        ]
        print_table(rows, columns)
    return 0


# ---------------------------------------------------------------- arguments


def parse_value(text: str) -> Any:
    """Read ``--set`` values: JSON (numbers, true, null, lists...) or text."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def parse_assignments(items: Sequence[str] | None) -> dict[str, Any]:
    """Turn ``key=value`` pairs into keyword arguments; ``a.b=v`` nests."""
    result: dict[str, Any] = {}
    for item in items or ():
        key, sep, raw = item.partition("=")
        if not sep or not key:
            raise UsageError(f"Expected KEY=VALUE, got {item!r}")
        target = result
        *parents, leaf = key.split(".")
        for parent in parents:
            target = target.setdefault(parent, {})
            if not isinstance(target, dict):
                raise UsageError(f"{key!r} conflicts with another --set")
        target[leaf] = parse_value(raw)
    return result


def parse_day(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date (YYYY-MM-DD): {text!r}")


def parse_report_input(text: str) -> Any:
    """Report inputs: ``2026-01-01..2026-12-31`` is a range, dates become dates."""
    if ".." in text:
        start, _, end = text.partition("..")
        return (parse_report_input(start), parse_report_input(end))
    try:
        return date.fromisoformat(text)
    except ValueError:
        return parse_value(text)


def ref(text: str) -> int | str:
    """An object given by id (digits) or by name."""
    return int(text) if text.isdigit() else text


def field_spec(text: str) -> str | list[str]:
    """``minimal``/``contact``/``full`` or a comma separated list of fields."""
    if text in FIELD_SETS:
        return text
    return [part.strip() for part in text.split(",") if part.strip()]


# ------------------------------------------------------------------- helpers


async def open_club(args: argparse.Namespace, mv: MeinVereinClient) -> ClubClient:
    choice = args.club or os.environ.get(ENV_CLUB)
    if not choice:
        return await mv.clubs.get()
    if choice.isdigit():
        return await mv.clubs.get(int(choice))
    return await mv.clubs.get(name=choice)


def confirm(question: str, args: argparse.Namespace) -> bool:
    if args.yes:
        return True
    if not sys.stdin.isatty():
        raise UsageError("Refusing to change data without a terminal; pass --yes")
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


# ------------------------------------------------------------------ commands


async def cmd_whoami(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    profile = await mv.account.profile()
    if args.json:
        print_json(profile)
    else:
        name = " ".join(p for p in (profile.first_name, profile.last_name) if p)
        print(f"{name} <{profile.email}> (id {profile.id})")
    return 0


async def cmd_token(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    print(mv.token)
    return 0


async def cmd_clubs(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    clubs = await mv.clubs.list()
    return show(args, clubs, ["id", "name", "member_count", "is_demo", "email"])


async def cmd_members_list(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    fields = field_spec(args.fields)
    output_format = args.format
    if output_format is None:
        suffix = Path(args.output).suffix.lower() if args.output else ""
        output_format = {".csv": "csv", ".json": "json"}.get(
            suffix, "table" if args.command_name == "list" else "json"
        )
    if args.json:
        output_format = "json"
    members = await club.members.list(
        from_list=ref(args.list) if args.list else None,
        type=args.type,
        status=args.status,
        department=ref(args.department) if args.department else None,
        role=ref(args.role) if args.role else None,
        search=args.search,
    )
    individual_fields = []
    columns = list(FIELD_SETS[fields]) if isinstance(fields, str) else list(fields)
    if any(column.startswith("custom.") for column in columns):
        individual_fields = await club.master_data.individual_fields()
    records = member_records(
        members,
        fields,
        individual_fields=individual_fields,
        omit_empty=args.omit_empty and output_format == "json",
    )
    if output_format == "table":
        print_table(records, columns)
        sys.stdout.flush()
        print(
            f"\n{len(records)} {'entry' if len(records) == 1 else 'entries'}",
            file=sys.stderr,
        )
        return 0
    if output_format == "csv":
        text = to_csv(records, columns, delimiter=args.delimiter)
    else:
        text = to_json(records) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding=args.encoding, newline="")
        print(f"Wrote {len(records)} entries to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


async def cmd_members_show(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    print_json(await club.members.get(args.member_id))
    return 0


async def cmd_members_create(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    fields = parse_assignments(args.set)
    for name in ("email", "member_id"):
        if getattr(args, name) is not None:
            fields[name] = getattr(args, name)
    if args.birthday is not None:
        fields["birthday"] = args.birthday
    member = await club.members.create(
        last_name=args.last_name,
        first_name=args.first_name,
        type=MemberType[args.type.upper()],
        **fields,
    )
    if args.json:
        print_json(member)
    else:
        print(
            f"Created {member.first_name or ''} {member.last_name} (id {member.id}, "
            f"number {member.member_id})".replace("  ", " ")
        )
    return 0


async def cmd_members_update(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    changes = parse_assignments(args.set)
    if not changes:
        raise UsageError("Nothing to change; pass at least one --set KEY=VALUE")
    club = await open_club(args, mv)
    member = await club.members.update(args.member_id, **changes)
    if args.json:
        print_json(member)
    else:
        print(
            f"Updated {member.first_name or ''} {member.last_name} (id {member.id})".replace(
                "  ", " "
            )
        )
    return 0


async def cmd_members_delete(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    members = [await club.members.get(member_id) for member_id in args.member_ids]
    for member in members:
        name = " ".join(p for p in (member.first_name, member.last_name) if p)
        print(f"  {member.id}  {member.member_id or '-'}  {name}")
    if not confirm(
        f"Permanently delete these {len(members)} entries from {club.name!r}?", args
    ):
        print("Nothing deleted.")
        return 1
    result = await club.members.delete(
        *args.member_ids, force_payers=args.force_payers, missing_ok=True
    )
    if args.json:
        print_json(result)
    elif result.skipped_count:
        print(
            f"Deleted {result.deleted_count}, skipped {result.skipped_count} "
            "(members who pay for others need --force-payers)"
        )
    else:
        print(f"Deleted {result.deleted_count}")
    return 0


async def cmd_lists(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    return show(
        args,
        await club.lists.all(),
        ["id", "name", "is_default_list", "is_favourite", "updated_at"],
    )


async def cmd_departments(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    return show(
        args, await club.departments.all(), ["id", "name", "level", "parent_id"]
    )


async def cmd_roles(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    return show(
        args,
        await club.roles.all(),
        ["id", "name", "member_count", "is_system_role", "description"],
    )


async def cmd_fields(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    return show(
        args,
        await club.master_data.individual_fields(),
        ["id", "name", "type", "options"],
    )


async def cmd_rates(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    return show(
        args,
        await club.contributions.rates(),
        ["id", "name", "amount", "interval", "type"],
    )


async def cmd_events(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    start = args.start or date.today()
    end = args.end or start + timedelta(days=args.days)
    events = await club.events.list(
        start, end, search=args.search, birthdays=args.birthdays
    )
    return show(args, events, ["id", "title", "start_date", "end_date", "full_day"])


async def cmd_accounts(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    return show(
        args,
        await club.finance.accounts(),
        ["id", "account_name", "account_type", "account_balance", "account_iban"],
    )


async def cmd_bookings(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    bookings = await club.finance.bookings(
        ref(args.account), search=args.search, limit=args.limit
    )
    return show(
        args,
        bookings,
        [
            "id",
            "booking_date",
            "booking_amount",
            "booking_contact_name",
            "purpose_description",
        ],
    )


async def cmd_documents(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    entries = await club.documents.list(args.folder)
    return show(args, entries, ["id", "name", "type", "size", "updated_at"])


async def cmd_download(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    data = await club.documents.download(args.document_id)
    Path(args.output).write_bytes(data)
    print(f"Wrote {len(data)} bytes to {args.output}", file=sys.stderr)
    return 0


async def cmd_reports(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    reports = await club.reports.all()
    if args.json:
        print_json(reports)
        return 0
    rows = [
        {
            "id": report.id,
            "formats": report.export_types,
            "inputs": [field.name for field in report.fields],
        }
        for report in reports
    ]
    print_table(rows, ["id", "formats", "inputs"])
    return 0


async def cmd_report(args: argparse.Namespace, mv: MeinVereinClient) -> int:
    club = await open_club(args, mv)
    values = {}
    for item in args.input or ():
        key, sep, raw = item.partition("=")
        if not sep:
            raise UsageError(f"Expected NAME=VALUE, got {item!r}")
        values[key] = parse_report_input(raw)
    data = await club.reports.export(args.report_id, args.format, **values)
    Path(args.output).write_bytes(data)
    print(f"Wrote {len(data)} bytes to {args.output}", file=sys.stderr)
    return 0


# --------------------------------------------------------------- the parser


def add_member_filters(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("filters (all must match)")
    group.add_argument("--list", help="read this list (id or name) instead of everyone")
    group.add_argument("--type", choices=["member", "contact", "company"])
    group.add_argument("--status", choices=["active", "former", "passive"])
    group.add_argument("--department", help="department or function (id or name)")
    group.add_argument("--role", help="permission role (id or name)")
    group.add_argument("--search", help="text in name, e-mail or member number")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print JSON")

    parser = argparse.ArgumentParser(
        prog="meinverein",
        description="Manage a WISO MeinVerein club from the command line.",
        epilog="Credentials: MEINVEREIN_TOKEN, or MEINVEREIN_EMAIL and "
        "MEINVEREIN_PASSWORD. Club: --club or MEINVEREIN_CLUB.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--club", help="club id or exact name")
    parser.add_argument("--token", help="session token (skips the login)")
    parser.add_argument(
        "--email", dest="login_email", help="Buhl account e-mail address"
    )
    # Only needed to point the CLI at the mock server.
    parser.add_argument("--api-url", help=argparse.SUPPRESS)
    parser.add_argument("--login-url", help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def command(
        sub: Any, name: str, handler: Handler, help: str, **kwargs: Any
    ) -> argparse.ArgumentParser:
        p: argparse.ArgumentParser = sub.add_parser(
            name, help=help, description=help, parents=[common], **kwargs
        )
        p.set_defaults(handler=handler, command_name=name)
        return p

    command(commands, "whoami", cmd_whoami, "show the logged-in user")
    command(commands, "token", cmd_token, "log in and print the session token")
    command(commands, "clubs", cmd_clubs, "list the clubs of the account")

    members = commands.add_parser("members", help="list, export and change members")
    msub = members.add_subparsers(dest="members_command", required=True)
    for name, help in (
        ("list", "show members as a table (or JSON/CSV)"),
        ("export", "export members as JSON or CSV"),
    ):
        p = command(msub, name, cmd_members_list, help)
        add_member_filters(p)
        p.add_argument("--format", choices=["table", "json", "csv"])
        p.add_argument(
            "--fields",
            default="minimal" if name == "list" else "contact",
            help="field set (minimal, contact, full) or comma separated fields, "
            "e.g. firstName,lastName,address.city,custom.Shirt size",
        )
        p.add_argument("-o", "--output", help="write to this file (.json or .csv)")
        p.add_argument("--delimiter", default=",", help="CSV delimiter")
        p.add_argument("--encoding", default="utf-8", help="file encoding")
        p.add_argument(
            "--omit-empty", action="store_true", help="JSON: skip empty fields"
        )

    p = command(msub, "show", cmd_members_show, "show all details of one member")
    p.add_argument("member_id", type=int, help="internal id (not the member number)")

    p = command(msub, "create", cmd_members_create, "create a member or contact")
    p.add_argument("--last-name", required=True, help="last name or company name")
    p.add_argument("--first-name")
    p.add_argument("--email")
    p.add_argument("--birthday", type=parse_day, help="YYYY-MM-DD")
    p.add_argument("--member-id", help="member number (default: next free one)")
    p.add_argument("--type", default="member", choices=["member", "contact", "company"])
    p.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        help="any other field, e.g. phone=0123, address.city=Berlin, country_id=2",
    )

    p = command(msub, "update", cmd_members_update, "change fields of a member")
    p.add_argument("member_id", type=int)
    p.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        help="field to change (repeatable); values are JSON or text",
    )

    p = command(msub, "delete", cmd_members_delete, "delete members permanently")
    p.add_argument("member_ids", type=int, nargs="+", metavar="MEMBER_ID")
    p.add_argument("-y", "--yes", action="store_true", help="do not ask")
    p.add_argument(
        "--force-payers",
        action="store_true",
        help="also delete members who pay for others",
    )

    command(commands, "lists", cmd_lists, "list the member lists")
    command(commands, "departments", cmd_departments, "list departments and functions")
    command(commands, "roles", cmd_roles, "list permission roles")
    command(commands, "fields", cmd_fields, "list custom field definitions")
    command(commands, "rates", cmd_rates, "list contribution rates")

    p = command(commands, "events", cmd_events, "list calendar events")
    p.add_argument("--from", dest="start", type=parse_day, help="default: today")
    p.add_argument("--to", dest="end", type=parse_day)
    p.add_argument("--days", type=int, default=90, help="range without --to")
    p.add_argument("--search")
    p.add_argument("--birthdays", action="store_true", help="include birthdays")

    command(commands, "accounts", cmd_accounts, "list cash boxes and bank accounts")
    p = command(commands, "bookings", cmd_bookings, "list the bookings of an account")
    p.add_argument("account", help="account id or name")
    p.add_argument("--search")
    p.add_argument("--limit", type=int, default=50)

    p = command(commands, "documents", cmd_documents, "list documents in a folder")
    p.add_argument("folder", nargs="?", help="folder id or name (default: top level)")
    p = command(commands, "download", cmd_download, "download a document")
    p.add_argument("document_id")
    p.add_argument("-o", "--output", required=True)

    command(commands, "reports", cmd_reports, "list the available reports")
    p = command(commands, "report", cmd_report, "run a report and save it")
    p.add_argument("report_id")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--format", help="pdf, excel, csv or xml (default: the report's)")
    p.add_argument(
        "--input",
        action="append",
        metavar="NAME=VALUE",
        help="report input; a date range is 2026-01-01..2026-12-31",
    )
    return parser


# --------------------------------------------------------------------- main


async def run(args: argparse.Namespace) -> int:
    password = os.environ.get("MEINVEREIN_PASSWORD")
    has_token = bool(args.token or os.environ.get("MEINVEREIN_TOKEN"))
    email = args.login_email or os.environ.get("MEINVEREIN_EMAIL")
    if not has_token and email and not password and sys.stdin.isatty():
        password = getpass.getpass(f"Password for {email}: ")
    kwargs: dict[str, Any] = {}
    if args.api_url:
        kwargs["api_url"] = args.api_url
    if args.login_url:
        kwargs["login_url"] = args.login_url
    async with MeinVereinClient(email, password, token=args.token, **kwargs) as mv:
        handler: Handler = args.handler
        return await handler(args, mv)


async def amain(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv`` and run the command; returns the exit code."""
    args = build_parser().parse_args(argv)
    try:
        return await run(args)
    except UsageError as error:
        print(f"meinverein: {error}", file=sys.stderr)
        return 2
    except (MeinVereinError, ValueError, OSError) as error:
        print(f"meinverein: {error}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return asyncio.run(amain(argv))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
