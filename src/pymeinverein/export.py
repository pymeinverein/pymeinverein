"""Turn members into flat records and write them as JSON or CSV.

A *field* is a dotted path into the member data using the API's field names,
for example ``lastName`` or ``address.city`` (``snake_case`` works too:
``last_name``). On top of the raw data there are computed fields:

``fullName``
    First and last name.
``departments``
    Names of the member's departments (list rows only).
``roles``
    Names of the member's permission roles (list rows only).
``typeName`` / ``statusName`` / ``genderName``
    The integer codes as words, e.g. ``member`` / ``active`` / ``female``.
``custom.<name>``
    Value of the custom field with that name (or ``custom.<id>``).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from enum import IntEnum
from typing import Any, Literal

from .api._util import camel
from .exceptions import LookupFailedError
from .models.masterdata import IndividualField
from .models.member import Gender, Member, MemberState, MemberType

type ExportFormat = Literal["json", "csv"]
#: The name of a field set, a list of fields, or a mapping ``header -> field``.
type FieldSpec = str | Sequence[str] | Mapping[str, str]

FIELD_SETS: dict[str, tuple[str, ...]] = {
    "minimal": ("memberId", "firstName", "lastName", "email"),
    "contact": (
        "memberId",
        "firstName",
        "lastName",
        "email",
        "phone",
        "mobilePhone",
        "address.addressLine1",
        "address.zip",
        "address.city",
        "address.country",
    ),
    "full": (
        "id",
        "memberId",
        "typeName",
        "statusName",
        "firstName",
        "lastName",
        "genderName",
        "birthday",
        "email",
        "additionalEmail",
        "phone",
        "phone2",
        "mobilePhone",
        "address.addressLine1",
        "address.addressLine2",
        "address.zip",
        "address.city",
        "address.country",
        "membershipBeginAt",
        "membershipEndAt",
        "departments",
        "roles",
        "notes",
    ),
}

#: Fields that hold a day rather than a point in time.
DATE_FIELDS = frozenset({"birthday", "membershipBeginAt", "membershipEndAt"})

_CUSTOM_PREFIX = "custom."


def resolve_fields(fields: FieldSpec) -> list[tuple[str, str]]:
    """Return ``(header, path)`` pairs for a field specification."""
    if isinstance(fields, str):
        try:
            names: Sequence[str] = FIELD_SETS[fields]
        except KeyError:
            known = ", ".join(sorted(FIELD_SETS))
            raise ValueError(
                f"Unknown field set {fields!r}; use one of {known} or a list of fields"
            ) from None
        return [(name, name) for name in names]
    if isinstance(fields, Mapping):
        return [(str(header), str(path)) for header, path in fields.items()]
    return [(name, name) for name in fields]


def _enum_name(value: Any, enum: type[IntEnum]) -> str | None:
    try:
        return enum(value).name.lower()
    except TypeError, ValueError:
        return None


def _custom_value(
    member: Member, key: str, individual_fields: Sequence[IndividualField]
) -> Any:
    values = member.custom_values
    if key.isdecimal():
        field_id = int(key)
    else:
        matches = [field.id for field in individual_fields if field.name == key]
        if not matches:
            known = ", ".join(repr(field.name) for field in individual_fields)
            raise LookupFailedError(
                f"No custom field named {key!r}. Known fields: {known or 'none'}"
            )
        # A name can exist several times (club wide and per list): take the
        # first one this member has a value for.
        field_id = next((fid for fid in matches if fid in values), matches[0])
    found = values.get(field_id, [])
    if len(found) == 1:
        return found[0]
    return found or None


def _lookup(record: Mapping[str, Any], path: str) -> Any:
    current: Any = record
    for part in path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(camel(part))
    return current


def _plain(value: Any, *, as_date: bool) -> Any:
    """Make a value JSON friendly."""
    if isinstance(value, datetime):
        return value.date().isoformat() if as_date else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, IntEnum):
        return int(value)
    if isinstance(value, Mapping):
        return {str(k): _plain(v, as_date=False) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item, as_date=False) for item in value]
    return value


def member_value(
    member: Member,
    path: str,
    *,
    individual_fields: Sequence[IndividualField] = (),
    record: Mapping[str, Any] | None = None,
) -> Any:
    """Return the value of one field for one member."""
    if path.startswith(_CUSTOM_PREFIX):
        return _custom_value(member, path[len(_CUSTOM_PREFIX) :], individual_fields)
    match camel(path):
        case "fullName":
            return member.full_name
        case "departments":
            return member.departments
        case "roles" if member.roles:
            return [role.name for role in member.roles]
        case "roles":
            return []
        case "typeName":
            return _enum_name(member.type, MemberType)
        case "statusName":
            return _enum_name(member.state, MemberState)
        case "genderName":
            return _enum_name(member.gender, Gender)
    data = record if record is not None else member.to_record()
    last = camel(path.rsplit(".", 1)[-1])
    return _plain(_lookup(data, path), as_date=last in DATE_FIELDS)


def member_records(
    members: Iterable[Member],
    fields: FieldSpec = "minimal",
    *,
    individual_fields: Sequence[IndividualField] = (),
    omit_empty: bool = False,
) -> list[dict[str, Any]]:
    """Convert members into flat dicts with one entry per requested field.

    With ``omit_empty`` entries that are ``None``, ``""`` or ``[]`` are left
    out (useful for compact JSON; do not use it for CSV).
    """
    columns = resolve_fields(fields)
    records: list[dict[str, Any]] = []
    for member in members:
        data = member.to_record()
        row: dict[str, Any] = {}
        for header, path in columns:
            value = member_value(
                member, path, individual_fields=individual_fields, record=data
            )
            if omit_empty and value in (None, "", []):
                continue
            row[header] = value
        records.append(row)
    return records


def to_json(records: Sequence[Mapping[str, Any]], *, indent: int | None = 2) -> str:
    """Serialize records as a JSON array."""
    return json.dumps(records, ensure_ascii=False, indent=indent) + "\n"


def _csv_cell(value: Any, list_separator: str) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return list_separator.join(_csv_cell(item, list_separator) for item in value)
    if isinstance(value, Mapping):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def to_csv(
    records: Sequence[Mapping[str, Any]],
    headers: Sequence[str] | None = None,
    *,
    delimiter: str = ",",
    list_separator: str = "; ",
) -> str:
    """Serialize records as CSV with a header row.

    ``headers`` fixes the columns and their order; by default they are taken
    from the records. Lists are joined with ``list_separator``.
    """
    if headers is None:
        seen: dict[str, None] = {}
        for record in records:
            seen.update(dict.fromkeys(record))
        headers = list(seen)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow(headers)
    for record in records:
        writer.writerow(
            [_csv_cell(record.get(header), list_separator) for header in headers]
        )
    return buffer.getvalue()


def export_members(
    members: Iterable[Member],
    format: ExportFormat = "json",
    *,
    fields: FieldSpec = "minimal",
    individual_fields: Sequence[IndividualField] = (),
    omit_empty: bool = False,
    delimiter: str = ",",
) -> str:
    """Return members as JSON or CSV text."""
    if format == "json":
        records = member_records(
            members, fields, individual_fields=individual_fields, omit_empty=omit_empty
        )
        return to_json(records)
    if format == "csv":
        records = member_records(members, fields, individual_fields=individual_fields)
        headers = [header for header, _ in resolve_fields(fields)]
        return to_csv(records, headers, delimiter=delimiter)
    raise ValueError(f"Unknown export format {format!r}; use 'json' or 'csv'")
