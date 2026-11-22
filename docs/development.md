# Development

The project uses [uv](https://docs.astral.sh/uv/) for environments and builds.

```console
git clone <repository url>
cd pymeinverein
uv sync                 # creates .venv with runtime and dev dependencies
```

## Checks

```console
uv run black --check .  # formatting
uv run mypy             # static types (strict)
uv run pytest           # tests, run against the mock server
```

CI (`.github/workflows/ci.yml`) runs the same commands on every push and pull
request.

The workflows pin every action to a full commit id, with the version as a
comment (`actions/checkout@3d3c42e… # v7.0.1`), so a moved or hijacked tag
cannot change what runs. Checkouts use `persist-credentials: false`.
Dependabot (`.github/dependabot.yml`) opens weekly pull requests that bump
those pins and the Python dependencies in `uv.lock`, grouped into one pull
request for actions, one for runtime and one for development dependencies.
When you add an action by hand, pin it the same way:

```console
git ls-remote https://github.com/OWNER/ACTION.git 'refs/tags/vX.Y.Z^{}' 'refs/tags/vX.Y.Z'
```

## Live tests

Tests in `tests/live/` talk to the real service and are skipped by default:

```console
export MEINVEREIN_EMAIL=... MEINVEREIN_PASSWORD=...
uv run pytest -m live
```

They only ever write to a club with `isDemo: true` and refuse to run otherwise.
Everything they create is named `pymeinverein-test...` and removed afterwards.

The invitation test would send a real e-mail, so it is skipped unless you name
the recipient:

```console
MEINVEREIN_TEST_INVITE_EMAIL=you@example.org uv run pytest -m live tests/live/test_invitations.py
```

## Exploring endpoints

`scripts/probe.py` sends one raw request to the real API and prints the shape
of the answer. `{club}` stands for the demo club; other clubs are refused.

```console
uv run python scripts/probe.py GET '/protected/club/{club}/list/all'
uv run python scripts/probe.py POST '/protected/club/{club}/list/1234' --api-version v3
```

See [How the API was discovered](api-discovery.md) for the method.

## Layout

```
src/pymeinverein/
  client.py        MeinVereinClient
  auth.py          Buhl account login
  _transport.py    HTTP helper and error mapping
  exceptions.py
  filters.py       client-side member filters
  export.py        JSON and CSV export
  api/             one module per API area
  models/          pydantic models, one module per area
  testing/         mock server
    server.py      login, session and the HTTP server itself
    routes/        one module per API area
    state.py       in-memory data
    seed.py        invented sample data
tests/             pytest suite against the mock server
tests/live/        opt-in tests against the real service
scripts/probe.py   raw requests for exploring the API
scripts/meinverein.py  command line tool (docs/cli.md)
docs/              this documentation (mkdocs)
```

## Documentation

```console
uv sync --group docs
uv run mkdocs serve
```
