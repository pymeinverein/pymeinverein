"""Custom fields ("individuelle Felder") for members and contacts.

This module manages the field *definitions*. The values of a member are set
with ``club.members.set_custom_field``.
"""

from __future__ import annotations

from collections.abc import Sequence

from .._transport import Transport
from ..exceptions import LookupFailedError
from ..models.masterdata import IndividualField, IndividualFieldType
from ._util import unwrap
from .masterdata import MasterDataAPI

#: A custom field: id, exact name or model.
type FieldRef = int | str | IndividualField

#: The API's code for "field for members and contacts".
_AREA_MEMBERS = 0


class CustomFieldsAPI:
    """Create, change and delete custom field definitions of one club."""

    def __init__(
        self, transport: Transport, club_id: int, master_data: MasterDataAPI
    ) -> None:
        self._transport = transport
        self._master_data = master_data
        self._base = f"/protected/club/{club_id}/list/individual-field"

    async def all(self) -> list[IndividualField]:
        """Return the custom fields for members and contacts.

        ``GET /protected/club/{clubId}/list/individual-field``
        """
        return await self._master_data.individual_fields()

    async def get(self, ref: FieldRef) -> IndividualField:
        """Look up a custom field by id or exact name."""
        field_id = await self._master_data.resolve_individual_field(ref)
        for field in await self.all():
            if field.id == field_id:
                return field
        raise LookupFailedError(f"There is no custom field {ref!r}")

    async def create(
        self,
        name: str,
        type: IndividualFieldType = IndividualFieldType.TEXT,
        *,
        options: Sequence[str] = (),
        suffix: str | None = None,
    ) -> IndividualField:
        """Create a custom field.

        ``options`` are the choices of a ``SELECT`` or ``MULTISELECT`` field;
        ``suffix`` is a unit shown after the value (for example ``"cm"``). The
        API allows several fields with the same name.
        ``POST /protected/club/{clubId}/list/individual-field``
        """
        payload = await self._transport.post(
            self._base,
            {
                "name": name,
                "type": int(type),
                "options": list(options),
                "suffix": suffix,
                "area": _AREA_MEMBERS,
            },
        )
        return IndividualField.model_validate(
            unwrap(payload, "data", f"POST {self._base}")
        )

    async def update(
        self,
        ref: FieldRef,
        *,
        name: str | None = None,
        options: Sequence[str] | None = None,
        suffix: str | None = None,
    ) -> IndividualField:
        """Rename a custom field or change its options or suffix.

        ``PUT /protected/club/{clubId}/list/individual-field/{id}``
        """
        current = await self.get(ref)
        path = f"{self._base}/{current.id}"
        payload = await self._transport.put(
            path,
            {
                "name": current.name if name is None else name,
                "type": current.type,
                "options": current.options if options is None else list(options),
                "suffix": current.suffix if suffix is None else suffix,
                "area": _AREA_MEMBERS,
            },
        )
        return IndividualField.model_validate(unwrap(payload, "data", f"PUT {path}"))

    async def delete(self, ref: FieldRef) -> None:
        """Delete a custom field together with the values members have for it.

        ``DELETE /protected/club/{clubId}/list/individual-field/{id}``
        """
        field_id = await self._master_data.resolve_individual_field(ref)
        await self._transport.delete(f"{self._base}/{field_id}")
