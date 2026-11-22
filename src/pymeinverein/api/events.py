"""Calendar events ("Termine") and their categories.

Participants are not managed here: inviting participants makes MeinVerein
send e-mails. Every write call below tells the service to skip notifications
unless ``notify=True`` is passed.
"""

from __future__ import annotations

import builtins
import json
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from .._transport import Transport
from ..exceptions import LookupFailedError, MeinVereinError
from ..models.events import Event, EventCategory
from ._util import to_payload, unwrap

#: A category: id, exact name or model.
type CategoryRef = int | str | EventCategory


def _moment(value: date | datetime | str) -> str:
    """Events use full timestamps; a plain date means midnight UTC."""
    if isinstance(value, datetime) or isinstance(value, str):
        return str(to_payload(value))
    return datetime(value.year, value.month, value.day).isoformat() + ".000Z"


class EventsAPI:
    """Read and manage the calendar of one club."""

    def __init__(self, transport: Transport, club_id: int) -> None:
        self._transport = transport
        self._base = f"/protected/club/{club_id}"
        self._legacy = f"/protected/mv365/clubs/{club_id}"

    # --------------------------------------------------------------- categories

    async def categories(self) -> builtins.list[EventCategory]:
        """Return the calendar categories, including the automatic birthday ones.

        ``GET /protected/mv365/clubs/{clubId}/event-categories``
        """
        path = f"{self._legacy}/event-categories"
        payload = await self._transport.get(path)
        return [
            EventCategory.model_validate(item)
            for item in unwrap(payload, "categories", f"GET {path}")
        ]

    async def _category_id(self, ref: CategoryRef | None) -> int:
        if isinstance(ref, EventCategory):
            return ref.id
        if isinstance(ref, int):
            return ref
        categories = await self.categories()
        if ref is None:
            matches = [item for item in categories if item.type == "default"]
        else:
            matches = [item for item in categories if item.name == ref]
        if len(matches) != 1:
            names = ", ".join(repr(item.name) for item in categories)
            raise LookupFailedError(
                f"Expected exactly one event category for {ref!r}, found "
                f"{len(matches)}. Known categories: {names or 'none'}"
            )
        return matches[0].id

    async def create_category(self, name: str, color: str = "#1b7bf1") -> EventCategory:
        """Create a calendar category; ``color`` is hex text like ``#1b7bf1``.

        ``POST /protected/mv365/clubs/{clubId}/event-categories``
        """
        path = f"{self._legacy}/event-categories"
        payload = await self._transport.post(path, {"name": name, "color": color})
        return EventCategory.model_validate(unwrap(payload, "category", f"POST {path}"))

    async def delete_category(self, ref: CategoryRef) -> None:
        """Delete a calendar category.

        ``DELETE /protected/club/{clubId}/event-categories/{id}``
        """
        category_id = await self._category_id(ref)
        await self._transport.delete(f"{self._base}/event-categories/{category_id}")

    # ------------------------------------------------------------------ reading

    async def get(self, event_id: int) -> Event:
        """Return one event.

        ``GET /protected/mv365/clubs/{clubId}/events/{eventId}``
        """
        path = f"{self._legacy}/events/{event_id}"
        payload = await self._transport.get(path)
        return Event.model_validate(unwrap(payload, "event", f"GET {path}"))

    async def search(self, term: str) -> builtins.list[Event]:
        """Return the events whose title contains ``term``.

        ``GET /protected/club/{clubId}/calendar/search?searchTerm=...``
        """
        path = f"{self._base}/calendar/search"
        payload = await self._transport.get(path, params={"searchTerm": term})
        return [
            Event.model_validate(item)
            for item in unwrap(payload, "data", f"GET {path}") or []
        ]

    async def list(
        self,
        start: date | datetime,
        end: date | datetime,
        *,
        categories: Iterable[CategoryRef] | None = None,
        search: str | None = None,
        birthdays: bool = False,
    ) -> builtins.list[Event]:
        """Return the events between ``start`` and ``end``.

        ``categories`` limits the result to some categories (default: all).
        MeinVerein adds members' birthdays as automatic entries; they are left
        out unless ``birthdays=True``.

        ``GET /protected/mv365/clubs/{clubId}/events?body={...}`` - the filter
        travels as JSON text in the query parameter ``body``, and the API only
        returns events of the categories named there.
        """
        if categories is None:
            category_ids = [item.id for item in await self.categories()]
        else:
            category_ids = [await self._category_id(item) for item in categories]
        body = {
            "startDate": _moment(start),
            "endDate": _moment(end),
            "searchText": search,
            "categoryIds": category_ids,
        }
        path = f"{self._legacy}/events"
        payload = await self._transport.get(path, params={"body": json.dumps(body)})
        events = [
            Event.model_validate(item)
            for item in unwrap(payload, "events", f"GET {path}")
        ]
        return [event for event in events if birthdays or not event.is_birthday]

    # ------------------------------------------------------------------ writing

    async def create(
        self,
        title: str,
        start: date | datetime,
        end: date | datetime,
        *,
        category: CategoryRef | None = None,
        full_day: bool = False,
        location: str | None = None,
        notes: str | None = None,
        notify: bool = False,
    ) -> Event:
        """Create an event without participants.

        ``category`` defaults to the club's standard category (the API requires
        one). ``location`` is the place shown in the calendar.
        ``POST /protected/club/{clubId}/calendar/create``
        """
        event = {
            "title": title,
            "startDate": _moment(start),
            "endDate": _moment(end),
            "fullDay": full_day,
            "description": location,
            "notes": notes,
            "isRecurringEvent": False,
            "participants": None,
            "categoryId": await self._category_id(category),
        }
        path = f"{self._base}/calendar/create"
        payload = await self._transport.post(
            path,
            {
                "event": event,
                "skipEmailNotifications": not notify,
                "receiveParticipantResponsePushNotification": False,
            },
        )
        return Event.model_validate(unwrap(payload, "data", f"POST {path}"))

    async def update(
        self, event_id: int, *, notify: bool = False, **changes: Any
    ) -> Event:
        """Change an event, e.g. ``update(42, title="Neu", start_date=...)``.

        Fields use the event's names (``title``, ``start_date``, ``end_date``,
        ``full_day``, ``description``, ``notes``, ``category_id``). The event is
        loaded, changed and sent back as a whole.
        ``GET .../events/{eventId}`` + ``POST /protected/club/{clubId}/event/{eventId}``
        """
        path = f"{self._legacy}/events/{event_id}"
        current = unwrap(await self._transport.get(path), "event", f"GET {path}")
        body = {key: value for key, value in current.items() if key != "_links"}
        body.update(to_payload(changes))
        body["skipEmailNotifications"] = not notify
        body["resetSeries"] = False
        path = f"{self._base}/event/{event_id}"
        payload = await self._transport.post(path, body)
        return Event.model_validate(unwrap(payload, "event", f"POST {path}"))

    async def delete(self, event_id: int, *, notify: bool = False) -> None:
        """Delete an event (for a recurring event: the whole series).

        ``POST /protected/club/{clubId}/calendar/delete``
        """
        path = f"{self._legacy}/events/{event_id}"
        current = unwrap(await self._transport.get(path), "event", f"GET {path}")
        event = {key: value for key, value in current.items() if key != "_links"}
        if event.get("id") is None:
            raise MeinVereinError("Automatic birthday entries cannot be deleted")
        await self._transport.post(
            f"{self._base}/calendar/delete",
            {
                "event": event,
                "skipEmailNotifications": not notify,
                "onlySingleEvent": False,
                # Observed: with False the service answers 404 even for a
                # single, non-recurring event.
                "wholeSeries": True,
            },
        )
