# How the API was discovered

There is no official API documentation. Everything in this library comes from
three sources, in this order of trust:

1. **Live requests** against the demo club ("Demoverein") that every account
   can create. Behaviour marked as *verified* in these docs was seen there.
2. **A HAR capture** of a browser session (login, dashboard, member list,
   editing a member). HAR files contain session tokens and personal data, so
   the `har/` folder is git-ignored and never published.
3. **The JavaScript bundles of the web application** (`https://web.meinverein.de`).
   They are public and contain every URL the application can call. Searching
   them for `this.http.get(`, `.post(`, ... yields about 400 endpoints.

## Findings that shape the library

**Two URL families.** Club data lives under `/protected/club/{clubId}/...`
(newer endpoints) and `/protected/mv365/clubs/{clubId}/...` (older ones). Both
are in use; a feature often needs calls from both.

**Bearer token.** Every call below `/protected/` needs
`Authorization: Bearer <token>`; see [Authentication](authentication.md).

**Errors.** The API uses three styles:

- JSON: `{"errorInfo": {"name": "BadRequestError", "message": ..., "statusCode": 400, "errors": [{"param": ..., "msg": ...}]}}`
- an empty body with status `401` (no or bad token) or `404` (unknown id or path)
- a firewall in front of the API that answers **`200 OK` with an HTML page**
  ("Request Rejected"). The library turns this into `RequestRejectedError`.

**HATEOAS links are unreliable.** Many answers contain `_links` with URLs for
follow-up actions. Several of them return `404` today, so the library uses
fixed paths taken from the web application instead of following links.

**Whole-object updates.** The web application loads an object, changes it and
sends the complete object back with `PATCH`. This is not just a habit: a
partial `PATCH` of a member is accepted, but fields that are left out can be
cleared (seen with the e-mail address) and nested objects such as the address
are replaced as a whole.

**Versioned answers.** Some calls carry a header `x-api-version: v2` or `v3`.
The same URL answers with different data depending on it. Example: the content
of a list (`POST .../list/{id}`) has resolved custom field values only with
`v2`/`v3`, and `POST .../list/all-members` shrinks to nine fields per member
with `v2`. The library sends the versions the web application sends and names
them in the docstrings.

**Look-alike endpoints.** There are two calls that create a member.
`POST /protected/club/{id}/members` belongs to a quick "new contact" dialog
and stores only names, type, e-mail, phone and address - everything else is
dropped without an error. `POST /protected/mv365/clubs/{id}/members` is the one
behind the full form. Reading the web application's code alone would have
picked the wrong one; only testing showed the difference.

**Success for things that did not happen.** The bulk delete reports
`deletedCount: 1` for an id that never existed, and logout answers `{}` without
revoking the token. The library compensates where it can (it checks ids before
deleting) and documents the rest.

**Derived fields.** A member's `state` (active, former, passive) and
`membershipEndAt` cannot be written. They follow from the membership periods
(`histories`). A `PATCH` that sets `state` succeeds and changes nothing.

**Rules that look redundant.** The rules of a dynamic list are a flat array.
A default list has `state = 0` and `state = 2` side by side: rules on the same
column are alternatives, rules on different columns must all hold.

**Filters that silently return nothing.** The event list takes its filter as
JSON text in a query parameter (`?body={...}`) and only returns events of the
categories named there. Without category ids the answer is an empty list, not
an error.

**A fourth error style.** The document storage answers errors as
`{"code": "DIRECTORY_DOES_NOT_EXIST", "message": ..., "details": ...}` instead
of the `errorInfo` envelope. The library maps `code` to the error's `name`.

**Feature switches.** Some actions depend on per-club switches in the club
object. Demo clubs have `sendEmailEnabled: false`, and a mailing sent from them
gets the "Request Rejected" page. The library reads such switches first where
it knows them, so it can raise a specific error.

**The "Request Rejected" page.** Besides blocking unknown URLs, the page shows
up for requests the backend apparently cannot process: a bulk call without a
required object, deleting a role that does not exist, assigning roles to a
member without account, a member number of `T-1` (while `900` is fine). The
most plausible reading is that the firewall also replaces server errors with
this page. Either way there is no error message to learn from, so the library
reports `RequestRejectedError` and, where the cause is known, checks the
precondition first and raises a specific error (for example `NoAccountError`).

## Method for adding a new area

1. Find the endpoints in the web bundles and note method, path and how the
   request body is built.
2. Call the read endpoints on the demo club and record the answer's shape.
3. Try the write endpoints on throwaway objects in the demo club; clean up.
4. Write models, the API group, the mock server routes and tests.
5. Document the calls and mark anything that could not be verified.
