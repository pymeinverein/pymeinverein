# Lists and custom fields

## Lists

`club.lists` reads and manages member lists. A list can be given as id, exact
name, `DefaultListType` or `MemberList`.

```python
from pymeinverein import DefaultListType

for item in await club.lists.all():
    print(item.id, item.name)

former = await club.lists.members(DefaultListType.FORMER_MEMBERS)
```

There are two kinds of lists you create yourself:

**Static lists** hold the members you put on them.

```python
helpers = await club.lists.create("Helfer")
await club.lists.add_members(helpers, [101, 102])
await club.lists.remove_members(helpers, [102])
```

**Dynamic lists** select their members by rules and follow the data.

```python
keepers = await club.lists.create(
    "Torhüter",
    criteria=[("type", "=", 1), ("state", "=", 0), ("state", "=", 2)],
    field_criteria=[("Position", "=", "Tor")],
)
await club.lists.set_criteria(keepers, [("type", "=", 1)])     # replace all rules
```

### How rules combine

- `criteria` are rules on member columns (`type`, `state`, `lastName`,
  `birthday`, ...), `field_criteria` rules on custom fields (by name or id).
- Rules on **different** columns must all hold.
- Several rules on the **same** column or field are alternatives. The example
  above selects members that are active *or* passive.
- Values are compared as text. Verified operators: `=` and `!=`; `!=` with the
  value `None` means "is filled in".

`club.lists.criteria(list)` and `club.lists.field_criteria(list)` return the
current rules. The default lists are dynamic lists too; reading their rules
shows how MeinVerein defines "current members" and so on.

### Other list calls

```python
await club.lists.rename(helpers, "Helferteam")
copy = await club.lists.copy(keepers, "Torhüter 2")     # rules (or members) are copied
await club.lists.set_favourite(keepers)                # for the logged-in user
await club.lists.delete(helpers)                       # members stay
```

## Custom fields

`club.custom_fields` manages the definitions of custom fields
("individuelle Felder") for members and contacts.

```python
from pymeinverein.models import IndividualFieldType

size = await club.custom_fields.create(
    "Trikotgröße", IndividualFieldType.SELECT, options=["S", "M", "L"]
)
await club.custom_fields.update(size, options=["S", "M", "L", "XL"])
await club.custom_fields.delete(size)      # also removes the members' values
```

Field types: `TEXT`, `SELECT`, `MULTISELECT`, `DATE`, `NUMBER`, `BOOLEAN`,
`PERSON`. The API allows several fields with the same name; refer to such
fields by id.

Values are set per member with
[`members.set_custom_field`](members.md#custom-field-values) or for many
members with `members.bulk.set_custom_fields`, and exported with the field
`custom.<name>`.

## Calls behind the methods

| Method | HTTP call |
| --- | --- |
| `lists.all`, `lists.get` | `GET /protected/club/{club}/list/all` |
| `lists.members` | `POST /protected/club/{club}/list/{list}` with `x-api-version: v3` |
| `lists.create` | `POST /protected/club/{club}/list/create` |
| `lists.rename` / `lists.delete` | `PUT` / `DELETE /protected/club/{club}/list/{list}` |
| `lists.copy` | `POST /protected/club/{club}/list/{list}/copy` |
| `lists.set_favourite` | `POST` / `DELETE /protected/club/{club}/list/favorites/{list}` |
| `lists.add_members` / `remove_members` | `POST /protected/club/{club}/list/assign-members/{list}` / `.../remove-members/{list}` |
| `lists.criteria` | `GET /protected/club/{club}/list/criteria/{list}` |
| `lists.field_criteria` | `GET /protected/club/{club}/list/individual-field-criteria/{list}` |
| `lists.set_criteria` | `DELETE /protected/club/{club}/list/criteria`, `POST .../list/criteria/{list}`, `DELETE .../list/individual-field-criteria/{list}`, `POST .../list/individual-field-criteria/` |
| `custom_fields.all`, `get` | `GET /protected/club/{club}/list/individual-field` |
| `custom_fields.create` | `POST /protected/club/{club}/list/individual-field` |
| `custom_fields.update` / `delete` | `PUT` / `DELETE /protected/club/{club}/list/individual-field/{id}` |

All verified against the demo club.
