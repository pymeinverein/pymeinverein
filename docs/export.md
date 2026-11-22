# Exporting members

`club.members.export()` returns members as JSON or CSV text and optionally
writes a file. It accepts the same filters as
[`club.members.list()`](members.md#filters).

```python
# Minimal JSON of everyone, returned as text
text = await club.members.export()

# CSV file of the active members (format taken from the file extension)
await club.members.export("active.csv", type="member", status="active")

# One department with contact details
await club.members.export("damen.json", department="1. Mannschaft - Damen", fields="contact")
```

The minimal JSON looks like this:

```json
[
  {
    "memberId": "2",
    "firstName": "Erika",
    "lastName": "Beispiel",
    "email": "erika.beispiel@example.org"
  }
]
```

and the minimal CSV like this:

```text
memberId,firstName,lastName,email
2,Erika,Beispiel,erika.beispiel@example.org
```

## Choosing fields

`fields` is one of:

- a **field set**: `"minimal"` (default), `"contact"` or `"full"`,
- a **list of fields**,
- a **mapping** `header -> field` to choose your own column names.

| Field set | Fields |
| --- | --- |
| `minimal` | `memberId`, `firstName`, `lastName`, `email` |
| `contact` | minimal + `phone`, `mobilePhone`, `address.addressLine1`, `address.zip`, `address.city`, `address.country` |
| `full` | id, number, type, status, names, gender, birthday, e-mail addresses, phones, address, membership dates, departments, roles, notes |

A field is a dotted path using the API's names (`lastName`, `address.city`);
`snake_case` works as well (`last_name`). Computed fields:

| Field | Value |
| --- | --- |
| `fullName` | first and last name |
| `departments` | names of the member's departments |
| `roles` | names of the member's permission roles |
| `typeName`, `statusName`, `genderName` | the numeric codes as words (`member`, `active`, `female`) |
| `custom.<name>` | value of the custom field with that name, e.g. `custom.Position` (or `custom.<id>`) |

```python
await club.members.export(
    "liste.csv",
    delimiter=";",                       # what a German Excel expects
    encoding="utf-8-sig",                # with BOM, so Excel detects UTF-8
    fields={
        "Nr": "memberId",
        "Name": "fullName",
        "Abteilung": "departments",
        "Position": "custom.Position",
    },
)
```

## Formatting rules

- `birthday`, `membershipBeginAt` and `membershipEndAt` are written as
  `YYYY-MM-DD`; other timestamps as ISO 8601.
- JSON keeps lists as lists and missing values as `null`. With
  `omit_empty=True` empty values are left out.
- CSV writes missing values as empty cells, booleans as `true`/`false` and
  joins lists with `"; "`. Cells are quoted where needed.

## Using the pieces directly

The export functions also work on members you already have:

```python
from pymeinverein.export import member_records, to_csv, to_json

members = await club.members.list(status="active")
records = member_records(members, ["memberId", "fullName", "email"])
print(to_json(records))
print(to_csv(records))
```
