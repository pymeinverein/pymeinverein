# pymeinverein

`pymeinverein` is an async Python client for the web API behind
[WISO MeinVerein Web](https://www.meinverein.de/), built on
[aiohttp](https://docs.aiohttp.org/) and [pydantic](https://docs.pydantic.dev/).

!!! warning "Unofficial"
    MeinVerein has no documented public API. This library uses the private API
    of the web application. It was built by observing that application, is not
    affiliated with Buhl Data Service GmbH and can stop working whenever the
    service changes.

## How the library is organised

| Piece | Module | Purpose |
| --- | --- | --- |
| Client | `pymeinverein.client` | `MeinVereinClient`: owns the HTTP session, logs in, gives access to the API groups |
| Login | `pymeinverein.auth` | The Buhl account single sign-on that produces the session token |
| Transport | `pymeinverein._transport` | Adds the token, decodes JSON, turns error answers into exceptions |
| API groups | `pymeinverein.api.*` | One module per area (account, clubs, members, ...) |
| Models | `pymeinverein.models.*` | Pydantic models of the returned objects |
| Filters | `pymeinverein.filters` | Client-side member filters |
| Export | `pymeinverein.export` | Members to flat records, JSON and CSV |
| Mock server | `pymeinverein.testing` | An in-memory imitation of the service for tests |

Every method's docstring names the HTTP call it makes, so the mapping between
the Python API and the web API stays visible.

## Where to go next

- [Getting started](getting-started.md) - install and make the first calls.
- [Authentication](authentication.md) - how the login works, tokens, two-factor.
- [Members and contacts](members.md) - read, create, change, delete; lists and master data.
- [Exporting members](export.md) - filtered JSON and CSV exports.
- [Lists and custom fields](lists-and-fields.md) - static and dynamic lists, field definitions.
- [Departments](departments.md) - the department tree.
- [Roles and permissions](roles.md) - roles, their permissions and who holds them.
- [Club settings](settings.md) - club details, logo, salutations, titles, numbering.
- [Contributions](contributions.md) - contribution rates and their assignment.
- [Events and calendar](events.md) - calendar entries and categories.
- [Finance and dashboard](finance.md) - accounts, bookings, invoices (read), statistics.
- [Documents](documents.md) - folders and files.
- [Mailings](mailing.md) - templates, drafts, sent items, sending.
- [Reports](reports.md) - finance and member association reports as files.
- [Mock server](mock-server.md) - test your own code without the real service.
- [How the API was discovered](api-discovery.md) - the method behind the endpoint list.
- [Endpoint coverage](endpoints.md) - what is implemented and what is known but missing.
- [Development](development.md) - set up a checkout, run the checks.
- [Releasing](releasing.md) - how a version gets to PyPI.
