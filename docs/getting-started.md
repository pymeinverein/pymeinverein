# Getting started

## Install

```console
pip install pymeinverein
```

Python 3.14 or newer is required.

## Credentials

You log in with your Buhl account ("buhl:Konto"), the same e-mail address and
password you use at <https://web.meinverein.de>. Either pass them to the client
or set two environment variables:

```console
export MEINVEREIN_EMAIL='me@example.org'
export MEINVEREIN_PASSWORD='secret'
```

Do not put credentials into source files.

If you already have a session token, `MEINVEREIN_TOKEN` (or `token=`) skips
the login completely; see [Authentication](authentication.md#using-a-token-instead-of-logging-in).

## First calls

```python
import asyncio

from pymeinverein import MeinVereinClient


async def main() -> None:
    async with MeinVereinClient() as mv:          # logs in
        account = await mv.account.get()
        print("Logged in as", account.user.email)

        for club in await mv.clubs.list():
            print(club.id, club.name, "(demo)" if club.is_demo else "")

        club = await mv.clubs.get(name="Demoverein")   # a client for one club
        print(club.id, club.name)


asyncio.run(main())
```

`mv.clubs.get()` accepts a club id, `name=...`, or nothing - then the club that
is selected in the web application is used.

## Errors

All errors derive from `pymeinverein.MeinVereinError`:

| Exception | Raised when |
| --- | --- |
| `AuthenticationError` | wrong credentials, missing or rejected token |
| `TwoFactorRequiredError` | the account needs a two-factor code and none was given |
| `LoginThrottledError` | too many wrong passwords; has `wait_seconds` |
| `BadRequestError` | HTTP 400/422, the API rejected the data; `errors` lists the fields |
| `PermissionDeniedError` | HTTP 403 |
| `NotFoundError` | HTTP 404, unknown object or endpoint |
| `ServerError` | HTTP 5xx |
| `RequestRejectedError` | the service answered with its "Request Rejected" page: the request was blocked, or the server failed on it |
| `NoAccountError` | the action needs a member with a MeinVerein account (for example role assignment) |
| `UnexpectedResponseError` | the answer was not what the library expects |
| `LookupFailedError` | a lookup by name matched nothing or several objects |

## Models

API objects are pydantic models. Attributes use `snake_case`
(`club.is_demo`), the API uses `camelCase` (`isDemo`); `model.to_api()` returns
the API spelling. Because the API is undocumented, models keep fields they do
not know: they are available in `model.model_extra`.
