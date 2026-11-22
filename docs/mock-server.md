# Mock server

`pymeinverein.testing` contains a mock of the service, built on `aiohttp.web`.
The library's own tests run against it, and it ships with the package so you
can test code that uses pymeinverein without network access or credentials.

One server plays both hosts: paths below `/mein-buhlkonto` imitate
`www.buhl.de` (the login), everything else imitates `api.meinverein.de`.

## In tests

```python
import pytest

from pymeinverein import MeinVereinClient
from pymeinverein.testing import DEMO_EMAIL, DEMO_PASSWORD, MockServer


@pytest.fixture
async def server():
    async with MockServer() as mock:
        yield mock


async def test_clubs(server):
    async with MeinVereinClient(DEMO_EMAIL, DEMO_PASSWORD, **server.client_kwargs()) as mv:
        assert [club.name for club in await mv.clubs.list()] == [
            "Musterverein e.V.",
            "Demoverein",
        ]
```

`server.client_kwargs()` returns the `api_url` and `login_url` arguments that
point the client at the mock.

## Standalone

```console
$ python -m pymeinverein.testing --port 8765
pymeinverein mock server listening on http://127.0.0.1:8765
```

## State

All data lives in `server.state` (`MockState`), plain Python objects that tests
may read and change:

| Attribute | Content |
| --- | --- |
| `users` | accounts that can log in, by e-mail (`MockUser`) |
| `clubs` | clubs by id, as API shaped dicts |
| `members` | members by club id and member id, shaped like the detail answer |
| `member_roles` | permission role ids by member id |
| `lists` | lists by club id and list id |
| `pictures` | member pictures by member id |
| `sent_invitations` | invitations the mock "sent", as `(member id, e-mail)`; nothing is e-mailed |
| `tokens` | valid session tokens |
| `requests` | every API request received, as `(method, path)` |
| `api_versions` | the `x-api-version` header of each of those requests |
| `rejected_paths` | paths the simulated firewall blocks |

`MockState.demo()` (the default) creates one user and two clubs: a regular club
(`REGULAR_CLUB_ID`) and a demo club (`DEMO_CLUB_ID`, `isDemo: true`). The demo
club has ten people (active, former and passive members, a contact and a
company), two departments, two custom fields, four roles and the default
lists; `pymeinverein.testing.seed` holds the ids. All sample data is invented;
only its shape follows the real API.

```python
server.state.add_member(DEMO_CLUB_ID, {"firstName": "Neu", "lastName": "Hier"})
```

## What is implemented

Every endpoint the library uses (see [Endpoint coverage](endpoints.md)):
login, account, clubs, members, lists and master data. Unknown paths answer
`404` like the real service.

## Simulating failures

```python
server.state.users[DEMO_EMAIL].two_factor_code = "123456"   # login asks for a code
server.state.users[DEMO_EMAIL].locked_ms = 30_000           # "wrong-password-wait"
server.state.rejected_paths.add("/protected/accounts")      # firewall page, HTTP 200
```

## Behaviour copied from the real service

- Missing or unknown token: empty `401`.
- Unknown object: empty `404`.
- Validation errors: `400` with
  `{"errorInfo": {"name": "BadRequestError", "errors": [{"param": ..., "msg": ...}]}}`.
- Firewall rejection: `200` with an HTML page titled "Request Rejected".
- Logout answers `{}` and leaves the token valid.
- A member `PATCH` needs `lastName`, replaces `address` as a whole and clears
  the e-mail address if the body has no `email`.
- The bulk delete counts unknown ids as deleted.
- The quick-create call (`POST /protected/club/{id}/members`) stores only a few
  fields.
- List rows contain `individualFieldData` only with `x-api-version: v2`/`v3`.
- A member's `state` follows from the membership periods; it cannot be set.
- Bulk edits answer with the skipped members and a reason code.
