# Contributions

`club.contributions` manages contribution rates ("Beitragssätze") and which
members have them.

!!! note "Nothing is billed"
    These calls define what members owe. Creating contribution invoices and
    starting SEPA direct debits is deliberately not part of this library.

```python
from datetime import date
from pymeinverein.models import RateInterval

for rate in await club.contributions.rates():
    print(rate.name, rate.amount, RateInterval(rate.interval).name)

youth = await club.contributions.create("Jugend", 60, interval=RateInterval.YEARLY)
await club.contributions.update(youth, amount=65)
await club.contributions.delete(youth)
```

A rate is given by id, exact name or `ContributionRate` object.

| `RateInterval` | | `RateType` | |
| --- | --- | --- | --- |
| `MONTHLY` | 0 | `REGULAR` | 0 |
| `QUARTERLY` | 1 | `DEPENDS_ON_AGE` | 1 |
| `HALF_YEARLY` | 2 | `DEPENDS_ON_MEMBERSHIP_DURATION` | 2 |
| `YEARLY` | 3 | `ADDITIONAL` | 3 |
| `ONCE` | 4 | `DONATION` | 4 |

Amounts come back as decimal text (`"60.00"`). The API only accepts them as
numbers, so the library converts when it sends a rate.

## Assigning rates to members

```python
ids = [m.id for m in await club.members.list(department="Jugend")]

await club.contributions.assign(ids, "Jugend", next_due=date(2027, 1, 1))
await club.contributions.unassign(ids, ["Jugend"])
```

- `next_due` is the first due date; `last_due` ends the contribution.
- `overwrite=True` replaces the members' existing contributions instead of
  adding to them.
- Both calls return a `BulkResult` naming skipped members.
- A member's contributions are in `member.club_member_contribution_rates`
  (from `club.members.get()`), as the API sends them.

## Calls behind the methods

| Method | HTTP call |
| --- | --- |
| `rates`, `get` | `GET /protected/mv365/club/{club}/contribution/rates` |
| `create` | `POST /protected/mv365/club/{club}/contribution/rates` |
| `update` | `GET` + `PATCH /protected/mv365/club/{club}/contribution/rate/{id}` |
| `delete` | `DELETE /protected/mv365/club/{club}/contribution/rate/{id}` |
| `assign` / `unassign` | `POST` / `DELETE /protected/club/{club}/members/bulk-edit/contributions` |

All verified against the demo club.
