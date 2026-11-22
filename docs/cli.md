# Command line

`scripts/meinverein.py` is a small command line tool on top of the library. It
lives in the repository, not in the installed package, and runs from a
checkout:

```console
uv run scripts/meinverein.py --help
uv run scripts/meinverein.py members list --help
```

It covers the everyday member tasks (list, export, show, create, update,
delete) and read-only overviews of the other areas. For anything else, use the
library directly.

## Logging in and choosing the club

The tool logs in the same way as the library:

| Source | Meaning |
| --- | --- |
| `--token` or `MEINVEREIN_TOKEN` | session token; no login |
| `--email` or `MEINVEREIN_EMAIL` | Buhl account e-mail address |
| `MEINVEREIN_PASSWORD` | password; asked for interactively if missing |
| `--club` or `MEINVEREIN_CLUB` | club id or exact name; default: the club selected in the web application |

Every run without a token logs in again. Log in once and keep the token for the
session:

```console
export MEINVEREIN_EMAIL=you@example.org
export MEINVEREIN_TOKEN=$(uv run scripts/meinverein.py token)
export MEINVEREIN_CLUB=Demoverein
```

The token does not expire and is not revoked by a logout, so treat it like the
password (see [Authentication](authentication.md)).

## Members

```console
# table of active members (fields: memberId, firstName, lastName, email)
uv run scripts/meinverein.py members list --status active

# filters can be combined; all must match
uv run scripts/meinverein.py members list --type member --department "1. Mannschaft - Damen"
uv run scripts/meinverein.py members list --list Vorstand --search mahler

# exports: the format follows the file extension, or --format
uv run scripts/meinverein.py members export -o members.csv --fields contact
uv run scripts/meinverein.py members export --status former --omit-empty > former.json
uv run scripts/meinverein.py members export -o excel.csv --delimiter ";" --encoding utf-8-sig \
    --fields "firstName,lastName,address.city,custom.Position"

# one member with all details (by internal id, shown as "id" in --json output)
uv run scripts/meinverein.py members show 23451612
```

`members list` prints a table by default; `members export` prints JSON (field
set `contact`). Both accept `--format table|json|csv`, `--fields` (a field set
`minimal`, `contact`, `full`, or a comma separated list, see
[Exporting members](export.md)) and `-o FILE`.

### Creating, changing and deleting

```console
uv run scripts/meinverein.py members create --last-name Lovelace --first-name Ada \
    --email ada@example.org --birthday 1815-12-10 \
    --set country_id=2 --set address.city=London

uv run scripts/meinverein.py members update 23451612 --set phone="0123 456" --set address.zip=12345

uv run scripts/meinverein.py members delete 23451612 23451613
```

`--set KEY=VALUE` takes any member field, in `snake_case` or `camelCase`; a dot
reaches into nested objects (`address.city`). Values are read as JSON when
possible (`2`, `true`, `null`, `[1, 2]`) and as text otherwise. Updates go
through `members.update()`, so fields you don't name are kept.

`delete` shows the entries and asks before deleting. Without a terminal (in
scripts) it refuses unless `--yes` is given. Members who pay for other members
are skipped unless `--force-payers` is given.

These commands change the club you chose. Unlike `scripts/probe.py`, the tool
has no demo-club guard.

## Overviews

| Command | Shows |
| --- | --- |
| `clubs` | clubs of the account |
| `whoami` | the logged-in user |
| `lists` | member lists |
| `departments` | departments and functions |
| `roles` | permission roles |
| `fields` | custom field definitions |
| `rates` | contribution rates |
| `events [--from DATE] [--to DATE] [--days N] [--search TEXT] [--birthdays]` | calendar events, by default the next 90 days |
| `accounts` | cash boxes and bank accounts |
| `bookings ACCOUNT [--limit N] [--search TEXT]` | bookings of an account (id or name), newest first |
| `documents [FOLDER]` | files and folders |
| `download DOCUMENT_ID -o FILE` | download a file |
| `reports` | available reports with their inputs |
| `report REPORT_ID -o FILE [--format F] [--input NAME=VALUE]...` | run a report and save it |

All of them accept `--json` for the full data instead of a table:

```console
uv run scripts/meinverein.py report report-income-expense -o eur.pdf --format pdf \
    --input date=2026-01-01..2026-12-31
```

## Exit codes

`0` success, `1` an error from the API or the file system (the message is
printed), `2` wrong usage, `130` interrupted.

## Tests

`tests/test_cli.py` runs every command against the mock server; the CLI has
hidden `--api-url` and `--login-url` options for that.
