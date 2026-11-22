"""Club settings: details, logo, salutations, titles and numbering."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import aiohttp

from .._transport import Transport
from ..exceptions import LookupFailedError
from ..models.account import Club
from ..models.masterdata import FormOfAddress, Title
from ..models.settings import ClubCategory, Numbering
from ._util import to_payload, unwrap


class ClubSettingsAPI:
    """Read and change the settings of one club."""

    def __init__(self, transport: Transport, club_id: int) -> None:
        self._transport = transport
        self._club_id = club_id
        self._base = f"/protected/club/{club_id}"
        self._legacy = f"/protected/mv365/clubs/{club_id}"

    # ------------------------------------------------------------------ details

    async def details(self) -> Club:
        """Return the club's details (name, contact data, profile settings).

        ``GET /protected/mv365/clubs/{clubId}``
        """
        payload = await self._transport.get(self._legacy)
        return Club.model_validate(unwrap(payload, "club", f"GET {self._legacy}"))

    async def update(self, **changes: Any) -> Club:
        """Change club details such as ``name2``, ``phone`` or ``website``.

        The club is loaded, the changes are applied and the whole object is
        sent back. The API requires a club category (``category_id``, see
        :meth:`categories`) in that object and answers ``400`` without one.

        Not verified against the real service: the demo club has no category,
        and setting one cannot be undone.
        ``PATCH /protected/mv365/clubs/{clubId}``
        """
        payload = await self._transport.get(self._legacy)
        body = dict(unwrap(payload, "club", f"GET {self._legacy}"))
        body.pop("_links", None)
        body.update(to_payload(changes))
        answer = await self._transport.patch(self._legacy, body)
        return Club.model_validate(unwrap(answer, "club", f"PATCH {self._legacy}"))

    async def categories(self) -> list[ClubCategory]:
        """Return MeinVerein's catalogue of club categories.

        ``GET /protected/mv365/club-categories``
        """
        path = "/protected/mv365/club-categories"
        payload = await self._transport.get(path)
        return [
            ClubCategory.model_validate(item)
            for item in unwrap(payload, "data", f"GET {path}")
        ]

    # --------------------------------------------------------------------- logo

    async def logo(self, size: str = "medium") -> bytes:
        """Return the club logo (JPEG); empty bytes if the club has none.

        ``size`` is ``small``, ``medium`` or ``large``.
        ``GET /mv365/clubs/{clubId}/logo?size=...``
        """
        return await self._transport.request_bytes(
            "GET", f"/mv365/clubs/{self._club_id}/logo", params={"size": size}
        )

    async def set_logo(
        self, image: bytes | str | Path, *, content_type: str = "image/jpeg"
    ) -> None:
        """Upload the club logo, given as bytes or as path of an image file.

        ``POST /protected/mv365/clubs/{clubId}/logo`` (multipart, field ``clubLogo``)
        """
        if not isinstance(image, bytes):
            image = await asyncio.to_thread(Path(image).read_bytes)
        form = aiohttp.FormData(quote_fields=False)
        form.add_field("clubLogo", image, filename="logo", content_type=content_type)
        await self._transport.post_form(f"{self._legacy}/logo", form)

    async def delete_logo(self) -> None:
        """Remove the club logo.

        ``DELETE /protected/mv365/clubs/{clubId}/logo``
        """
        await self._transport.delete(f"{self._legacy}/logo")

    # ------------------------------------------------------ salutations, titles

    async def salutations(self) -> list[FormOfAddress]:
        """Return the salutations with their letter opening templates.

        ``GET /protected/club/{clubId}/formsOfAddress``
        """
        path = f"{self._base}/formsOfAddress"
        data = unwrap(await self._transport.get(path), "data", f"GET {path}")
        return [
            FormOfAddress.model_validate(item)
            for item in unwrap(data, "formsOfAddress", f"GET {path}")
        ]

    async def titles(self) -> list[Title]:
        """Return the titles ("Dr.", "Prof.", ...) members can have.

        ``GET /protected/club/{clubId}/titles``
        """
        path = f"{self._base}/titles"
        payload = await self._transport.get(path)
        return [
            Title.model_validate(item)
            for item in unwrap(payload, "data", f"GET {path}")
        ]

    async def create_title(self, label: str) -> Title:
        """Add a title.

        Not verified against the real service: there is no call to delete a
        title again, so it was not tried on the demo club.
        ``POST /protected/club/{clubId}/titles``
        """
        path = f"{self._base}/titles"
        payload = await self._transport.post(path, {"label": label})
        return Title.model_validate(unwrap(payload, "data", f"POST {path}"))

    async def update_title(
        self,
        title_id: int,
        *,
        label: str | None = None,
        favorite: bool | None = None,
    ) -> Title:
        """Rename a title or mark it as favourite (shown first in selections).

        ``PUT /protected/club/{clubId}/titles/{titleId}``
        """
        current = next((t for t in await self.titles() if t.id == title_id), None)
        if current is None:
            raise LookupFailedError(f"There is no title with id {title_id}")
        body = current.to_api()
        if label is not None:
            body["label"] = label
        if favorite is not None:
            body["isFavorite"] = favorite
        path = f"{self._base}/titles/{title_id}"
        payload = await self._transport.put(path, body)
        return Title.model_validate(unwrap(payload, "data", f"PUT {path}"))

    # ---------------------------------------------------------------- numbering

    async def numbering(self, kind: str = "invoice") -> Numbering:
        """Return how consecutive numbers are built; ``kind`` is ``"invoice"``.

        ``GET /protected/club/{clubId}/settings/numeration/{kind}``
        """
        path = f"{self._base}/settings/numeration/{kind}"
        payload = await self._transport.get(path)
        return Numbering.model_validate(unwrap(payload, "data", f"GET {path}"))

    async def next_number(self, kind: str = "invoice") -> str:
        """Return the next number MeinVerein would assign, e.g. ``2026000033``.

        ``GET /protected/club/{clubId}/settings/numeration/{kind}/next``
        """
        path = f"{self._base}/settings/numeration/{kind}/next"
        return str(unwrap(await self._transport.get(path), "data", f"GET {path}"))
