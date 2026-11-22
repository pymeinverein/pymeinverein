# Events and calendar

`club.events` reads and manages the club calendar ("Termine").

```python
from datetime import date, datetime, UTC

events = await club.events.list(date(2026, 11, 1), date(2026, 12, 31))
for event in events:
    print(event.start_date, event.title, event.description)

party = await club.events.create(
    "Sommerfest",
    datetime(2027, 7, 3, 14, 0, tzinfo=UTC),
    datetime(2027, 7, 3, 22, 0, tzinfo=UTC),
    location="Sportplatz",
    notes="Grill mitbringen",
)
await club.events.update(party.id, title="Sommerfest 2027")
await club.events.delete(party.id)
```

## Things to know

- **Times are UTC.** Pass timezone-aware datetimes; a plain `date` means
  midnight UTC. Use `full_day=True` for all-day events.
- **`location`** is stored in the event's `description` field - that is what the
  web application shows as place. Free text goes into `notes`.
- **Every event needs a category.** `create()` uses the club's standard
  category unless you pass `category=` (id, name or `EventCategory`).
- **Birthdays** of members appear as automatic all-day entries without id.
  `list()` leaves them out unless you pass `birthdays=True`.
- **No participants, no notifications.** Adding participants makes MeinVerein
  send invitations by e-mail, so this library does not manage participants.
  The write calls tell the service to skip notifications; pass `notify=True`
  if you want an existing event's participants informed about a change.
- **Recurring events** can be read; `delete()` removes the whole series.

## Categories

```python
for category in await club.events.categories():
    print(category.id, category.name, category.color, category.type)

tournaments = await club.events.create_category("Turniere", "#00aa00")
await club.events.list(date(2027, 1, 1), date(2027, 12, 31), categories=[tournaments])
await club.events.delete_category(tournaments)
```

## Calls behind the methods

| Method | HTTP call |
| --- | --- |
| `list` | `GET /protected/mv365/clubs/{club}/events?body={...}` (filter as JSON text; needs `categoryIds`) |
| `get` | `GET /protected/mv365/clubs/{club}/events/{id}` |
| `search` | `GET /protected/club/{club}/calendar/search?searchTerm=...` |
| `create` | `POST /protected/club/{club}/calendar/create` |
| `update` | `POST /protected/club/{club}/event/{id}` |
| `delete` | `POST /protected/club/{club}/calendar/delete` |
| `categories`, `create_category` | `GET`, `POST /protected/mv365/clubs/{club}/event-categories` |
| `delete_category` | `DELETE /protected/club/{club}/event-categories/{id}` |

All verified against the demo club.
