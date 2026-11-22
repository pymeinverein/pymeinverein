# Departments

`club.departments` manages the tree of departments ("Abteilungen") and the
functions inside them.

MeinVerein has three fixed *levels* (in the demo club: "Mannschaften" >
"Rollen" > "Ebene 3"). An entry of level 1 is a department; entries of level 2
and 3 hang below an entry of the level above. The API calls the levels "areas"
and the entries "sub areas".

```python
for level in await club.departments.tree():
    print(level.level, level.name, [entry.name for entry in level.sub_areas])

youth = await club.departments.create("Jugend", alias="JU")
trainers = await club.departments.create("Trainer", parent=youth)

await club.departments.update(youth, name="Jugendabteilung")
copy = await club.departments.copy(youth)          # "Jugendabteilung - Kopie", with its functions
await club.departments.delete(copy)

await club.departments.rename_level(1, "Teams")    # rename the level itself
```

## Referring to an entry

Wherever a department or function is expected you can pass

- its id,
- its name, if that name is unique among all entries,
- a path `"Department/Function"` (or three parts for level 3), or
- a `SubArea` object.

Functions usually share names ("Spieler" exists in every team), so they need
the path form. The same forms work in
[`members.set_membership`](members.md#membership-periods-and-status), the bulk
membership calls and the `department=` filter id.

## What deleting does

- Deleting an entry deletes everything below it.
- Members are never deleted. A membership period that pointed to the deleted
  entry stays, without a department.

## Calls behind the methods

| Method | HTTP call |
| --- | --- |
| `tree`, `all`, `get` | `GET /protected/mv365/clubs/{club}/areas` |
| `create` | `POST /protected/mv365/clubs/{club}/subareas` |
| `update` | `PATCH /protected/mv365/clubs/{club}/subareas/{id}` |
| `copy` | `POST /protected/mv365/clubs/{club}/subareas-copy/{id}` |
| `delete` | `DELETE /protected/mv365/clubs/{club}/subareas/{id}` |
| `rename_level` | `PATCH /protected/mv365/clubs/{club}/areas/{id}` |

All verified against the demo club.
