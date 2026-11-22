# pymeinverein

Async Python client for the web API behind [WISO MeinVerein Web](https://www.meinverein.de/).

> **Unofficial.** MeinVerein has no documented public API. This library talks to
> the private API that the web application itself uses. It was built by
> observing that application and can break whenever Buhl changes it. It is not
> affiliated with or endorsed by Buhl Data Service GmbH.

## Status

| Area | State |
| --- | --- |
| Login through the Buhl account (incl. two-factor hook) | implemented |
| Account and clubs | implemented |
| Members and contacts: create, read, update, delete | implemented |
| Member lists, filters, JSON/CSV export | implemented |
| Membership periods, custom field values, pictures, bulk edits | implemented |
| Dynamic lists with rules, custom field definitions | implemented |
| Departments | implemented |
| Roles and permissions | implemented |
| Club settings (details, logo, titles, numbering) | implemented, partly unverified |
| Contribution rates and their assignment | implemented |
| Calendar events and categories (without participants) | implemented |
| Finance: accounts, bookings, invoices (read), cash box bookings, dashboard | implemented |
| Documents: folders, upload, download, move | implemented |
| Mailings: templates, drafts, sent items (sending unverified) | implemented |
| Reports (PDF, Excel, CSV downloads) | implemented |
| Invoice creation, event participants | planned |

[docs/endpoints.md](docs/endpoints.md) tracks which of the discovered endpoints
are covered.

## Installation

```console
pip install pymeinverein
```

Requires Python 3.14 or newer.

## Quick start

```python
import asyncio
from datetime import date

from pymeinverein import MeinVereinClient


async def main() -> None:
    # Credentials default to the environment variables
    # MEINVEREIN_EMAIL and MEINVEREIN_PASSWORD.
    async with MeinVereinClient() as mv:
        club = await mv.clubs.get(name="Demoverein")

        # Add, change and delete a member
        member = await club.members.create(
            first_name="Ada", last_name="Lovelace", birthday=date(1815, 12, 10)
        )
        await club.members.update(member.id, email="ada@example.org")
        await club.members.delete(member.id)

        # Filtered lists
        active = await club.members.list(type="member", status="active")
        print(len(active), "active members")

        # Exports: minimal JSON as text, CSV to a file
        print(await club.members.export(status="former"))
        await club.members.export("members.csv", type="member", fields="contact")


asyncio.run(main())
```

## Command line

`scripts/meinverein.py` wraps the most common tasks (run it from a checkout):

```console
export MEINVEREIN_TOKEN=$(uv run scripts/meinverein.py token)
uv run scripts/meinverein.py --club Demoverein members list --status active
uv run scripts/meinverein.py members export -o members.csv --fields contact
uv run scripts/meinverein.py members update 1234 --set phone="0123 456"
```

See [Command line](docs/cli.md).

## Testing without the real service

The package ships a mock server that imitates the login and the API:

```python
from pymeinverein import MeinVereinClient
from pymeinverein.testing import DEMO_EMAIL, DEMO_PASSWORD, MockServer

async with MockServer() as server:
    async with MeinVereinClient(DEMO_EMAIL, DEMO_PASSWORD, **server.client_kwargs()) as mv:
        ...
```

Run it standalone with `python -m pymeinverein.testing`.

## Documentation

The `docs/` folder explains how the library works and how the API was explored:

- [Getting started](docs/getting-started.md)
- [Authentication](docs/authentication.md)
- [Members and contacts](docs/members.md)
- [Exporting members](docs/export.md)
- [Lists and custom fields](docs/lists-and-fields.md)
- [Departments](docs/departments.md)
- [Roles and permissions](docs/roles.md)
- [Club settings](docs/settings.md)
- [Contributions](docs/contributions.md)
- [Events and calendar](docs/events.md)
- [Finance and dashboard](docs/finance.md)
- [Documents](docs/documents.md)
- [Mailings](docs/mailing.md)
- [Reports](docs/reports.md)
- [Command line](docs/cli.md)
- [Mock server](docs/mock-server.md)
- [How the API was discovered](docs/api-discovery.md)
- [Endpoint coverage](docs/endpoints.md)
- [Development](docs/development.md)
- [Releasing](docs/releasing.md)

## AI attribution

[AIA PAI Nc Hin Nr Claude Opus v1.0](https://aiattribution.github.io/statements/AIA-PAI-Nc-Hin-Nr-?model=Claude%20Opus-v1.0)

This project was written primarily by AI: the code, tests, mock server and
documentation were produced by an AI coding agent (Claude Code with Anthropic's
Claude Opus models), directed by the maintainer, who set the goals and made the
design decisions. The API was explored by that agent against a demo club.

**The code has not been reviewed by a human.** It is checked by the automated
test suite, strict type checking and opt-in live tests against a demo club,
but nothing more. Read it before you rely on it, and be especially careful
before pointing it at a real club's data.

Agents working on the repository should read [AGENTS.md](AGENTS.md).

## License

GPL-3.0-or-later, see [LICENSE](LICENSE).
