"""Common base class of all API models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Base class for objects returned by the MeinVerein API.

    * Python attributes use ``snake_case``; the API uses ``camelCase``. Both
      spellings are accepted when a model is created.
    * The API is undocumented and changes without notice, so unknown fields are
      kept (``extra="allow"``) instead of raising. They stay reachable through
      :attr:`model_extra` and are part of :meth:`to_api`.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="allow",
        coerce_numbers_to_str=True,
    )

    def to_api(self, *, exclude_none: bool = False) -> dict[str, Any]:
        """Return the model as a JSON-ready dict with the API's field names."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=exclude_none)
