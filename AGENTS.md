# AGENTS.md

Guidance for AI coding agents (and humans) working on this repository.

## What this is

`pymeinverein` is an async Python client for the private, undocumented web API
behind WISO MeinVerein Web (`api.meinverein.de`). Everything known about the API
was learned by watching the web application and trying calls against a demo
club. There is no specification: when in doubt, the observed behaviour of the
real service wins, and it is written down in `docs/`.

- Python 3.14+, async only (`aiohttp`), models with Pydantic v2.
- License GPL-3.0-or-later.
- `uv` for environments, `hatchling` + `hatch-vcs` for builds (version from git tags).

## Commands

```console
uv sync                         # dev environment
uv run black --check .          # formatting (line length 88)
uv run mypy                     # strict type checking
uv run pytest                   # tests against the bundled mock server
uv run pytest -m live           # opt-in tests against the real service
uv sync --group docs && uv run mkdocs build --strict
```

All four of black, mypy, pytest and the strict docs build must pass before a
commit.

## Layout

```
src/pymeinverein/
  client.py        MeinVereinClient (login, token, club access)
  auth.py          Buhl account login (SSO, two-factor hook)
  _transport.py    HTTP helper, x-api-version, error mapping
  exceptions.py    every error derives from MeinVereinError
  api/             one module per API area; ClubClient in api/clubs.py
  models/          pydantic models, one module per area (base: models/base.py)
  testing/         mock server: server.py, state.py, seed.py, routes/<area>.py
tests/             mock-based tests, one file per area
tests/live/        opt-in live tests (marker `live`)
scripts/probe.py   raw requests against the demo club for API discovery
scripts/meinverein.py  command line tool (docs/cli.md, tests/test_cli.py)
docs/              mkdocs site; docs/endpoints.md tracks coverage
```

## How a feature is added

1. Find the calls the web application makes (method, path, body,
   `x-api-version`). See `docs/api-discovery.md`.
2. Read the endpoints live on the demo club with `scripts/probe.py`; record the
   shapes.
3. Try writes on throwaway objects and look for silent side effects (fields that
   get cleared, ids that "succeed" although they don't exist).
4. Then, in one commit:
   - model(s) in `models/<area>.py`, API group in `api/<area>.py`, exports in
     `__init__.py`, attach it to `ClubClient` if club scoped;
   - mock routes in `testing/routes/<area>.py` and seed data that mirror the
     observed quirks;
   - `tests/test_<area>.py` (mock) and `tests/live/test_<area>.py` (live);
   - `docs/<area>.md`, nav entry in `mkdocs.yml`, rows in `docs/endpoints.md`,
     a line under *Unreleased* in `CHANGELOG.md`, README status table.
5. Anything that cannot be verified live is still implemented and mock-tested,
   but marked *unverified* in `docs/endpoints.md`.

## Conventions

- Each public method's docstring names the HTTP call behind it
  (``GET /protected/...``).
- Payloads are built with `to_payload` / `camel` and answers read with `unwrap`
  (`api/_util.py`); models derive from `ApiModel` and use snake_case fields.
- Raise the specific exceptions from `exceptions.py`; never return error dicts.
- Uploads use `aiohttp.FormData(quote_fields=False)`; the API rejects
  percent-encoded file names.
- Keep commits focused, one feature per commit.
- GitHub Actions are pinned to a full commit id with the version in a comment
  (`uses: owner/action@<sha> # vX.Y.Z`); never use a tag or branch. Dependabot
  (`.github/dependabot.yml`) keeps the pins and `uv.lock` current.

## API behaviour that bites

- A partial member update clears the fields it leaves out, so updates load,
  merge and send the whole object.
- Delete answers success for ids that don't exist; check first.
- A "Request Rejected" HTML page with status 200 means a firewall block or a
  server error; it becomes `RequestRejectedError`.
- Two URL families exist (`/protected/club/{id}` and
  `/protected/mv365/clubs/{id}`) and `x-api-version` changes the answer shape.
- The session token has no expiry and logout does not revoke it.

More in `todo.md` and the area pages under `docs/`.

## Safety rules for the real service

These are hard rules, not suggestions:

- **Live writes only in a demo club** (`isDemo: true`). The live fixture
  refuses anything else; never bypass it, never write to a real club.
- Name every test object `pymeinverein-test…` and remove it in a `finally`.
- **E-mail**: never send invitations or mailings except to an address the
  maintainer has explicitly named for testing.
- **Never** implement or call SEPA debit runs, bank transfers, online-banking
  setup, subscription/purchase calls, or club deletion.
- No credentials or tokens in the repository. Credentials come from
  `MEINVEREIN_EMAIL` / `MEINVEREIN_PASSWORD` or `MEINVEREIN_TOKEN`. The `har/`
  folder (recorded browser traffic) is git-ignored and must stay so.
- Don't push, tag or release unless asked.

## AI attribution

This project uses an [AI Attribution](https://aiattribution.github.io/)
statement (v1.0):

[AIA PAI Nc Hin Nr Claude Opus v1.0](https://aiattribution.github.io/statements/AIA-PAI-Nc-Hin-Nr-?model=Claude%20Opus-v1.0)

Full statement: *AIA Primarily AI, New content, Human-initiated, No human
review, Claude Opus v1.0*

| Code | Meaning |
| --- | --- |
| `AIA` | AI attribution statement |
| `PAI` | Primarily AI: the work was primarily AI-generated |
| `Nc` | New content: AI created the code, tests, mock server and docs |
| `Hin` | Human-initiated: AI was prompted for its contributions |
| `Nr` | No human review: the AI-generated content was not reviewed |
| `Claude Opus` | Model used (through Claude Code) |
| `v1.0` | Version of the statement format |

Keep the statement in `README.md` and here in step with how the project is
made. If a human reviews the code, change `Nr` to `R`; if another model
contributes, add it to the model part. Agents also add a `Co-Authored-By:`
trailer naming the model to every commit they make.
