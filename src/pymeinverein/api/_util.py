"""Helpers shared by the API groups."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from ..exceptions import UnexpectedResponseError
from ..models.base import ApiModel


def camel(name: str) -> str:
    """Convert ``snake_case`` to the API's ``camelCase``; other names pass through."""
    head, *rest = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def to_payload(value: Any) -> Any:
    """Convert Python values into what the API expects in a JSON body.

    * dict keys are converted from ``snake_case`` to ``camelCase`` (recursively)
    * models are dumped with their API field names (only the fields that were set)
    * enums become their value, dates ``YYYY-MM-DD``, datetimes ISO 8601 in UTC
    """
    if isinstance(value, ApiModel):
        return value.model_dump(mode="json", by_alias=True, exclude_unset=True)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        text = value.astimezone(UTC).isoformat(timespec="milliseconds")
        return text.replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {camel(str(key)): to_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_payload(item) for item in value]
    return value


def unwrap(payload: Any, key: str, call: str) -> Any:
    """Return ``payload[key]`` or raise if the answer has an unexpected shape."""
    if not isinstance(payload, dict) or key not in payload:
        raise UnexpectedResponseError(f"{call}: the answer has no {key!r} field")
    return payload[key]
