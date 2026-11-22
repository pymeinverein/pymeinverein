# Authentication

MeinVerein has no login form of its own. It uses the Buhl account
("buhl:Konto") as single sign-on. `pymeinverein.auth.login()` replays what the
browser does:

| Step | Request | Result |
| --- | --- | --- |
| 1 | `GET https://www.buhl.de/mein-buhlkonto/?buhlparam=1050105` | Opens a session (cookies). `buhlparam` tells Buhl the login is for MeinVerein Web. |
| 2 | `POST https://www.buhl.de/mein-buhlkonto/wp-json/api/v1/login` with the form fields `action=LoginUser`, `eml-user`, `psw-user`, `rdr-buhlparam` | JSON. On success the field `redirection` contains an HTML form with a one-time `BuhlTicket`. |
| 3 | `POST https://api.meinverein.de/auth/buhlkonto/token?eml=...&eml_extra=...` with the `BuhlTicket` | `302` redirect to `https://web.meinverein.de/login?token=<JWT>` |

The token from step 3 is sent with every API call as
`Authorization: Bearer <JWT>`.

Safety check: the form in step 2 names the URL the ticket is posted to. The
library only posts it if that URL is on the configured API host.

## Login failures

Step 2 reports failures in the JSON field `code`:

| `code` | Exception |
| --- | --- |
| `invalid-user-credential` | `AuthenticationError` |
| `wrong-password-wait`, `wrong-twofactor-token-wait` | `LoginThrottledError` (`wait_seconds` from `waitTime`) |
| `twofactorauthentication-failed` | `TwoFactorRequiredError` if no code was supplied |

## Two-factor authentication

Pass `two_factor=` to the client: a string, or a sync or async callable that
returns the current code.

```python
async with MeinVereinClient(email, password, two_factor=lambda: input("Code: ")) as mv:
    ...
```

!!! note "Not verified against the real service"
    The two-factor flow was implemented from the JavaScript of the login page
    (the code is sent as `TwoFactorToken` together with the `InvalidTicket` of
    the first answer). The test account has no second factor, so this path has
    only been tested against the mock server.

## The token

Observed properties of the token:

- It is a JWT **without an expiry date**.
- The web application calls `GET /protected/auth/buhlkonto/keepalive` every few
  minutes; `await mv.account.keepalive()` does the same.
- `GET /protected/mv365/accounts/logout` answers `{}` but does **not** revoke
  the token - it keeps working after logout.

Treat the token like a password.

## Using a token instead of logging in

Pass a token and the login is skipped entirely - no credentials needed:

```python
async with MeinVereinClient(token=saved_token) as mv:
    ...
```

or set it in the environment:

```console
export MEINVEREIN_TOKEN='eyJhbGciOi...'
```

- Where to get one: `mv.token` after a login, or the browser. In the web
  application open the developer tools, pick any request to
  `api.meinverein.de` and copy its `Authorization` header. A leading `Bearer `
  is removed, as are surrounding blanks.
- An explicit `token=` wins over `MEINVEREIN_TOKEN`; a token wins over e-mail
  and password, which are then ignored.
- The token is not checked when the client starts. A wrong or foreign token
  shows up as `AuthenticationError` (HTTP 401) on the first call; call
  `await mv.account.keepalive()` to check it right away.

`await mv.logout()` notifies the server and removes the token from the client.
Leaving the `async with` block only closes the HTTP session.
