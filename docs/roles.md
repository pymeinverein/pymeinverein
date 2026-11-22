# Roles and permissions

`club.roles` manages the permission roles of a club: what its users may see
and do in MeinVerein.

Every club has four built-in roles - Administrator, Finanzverwalter, Verwalter
and Mitglied - and can define its own.

```python
from pymeinverein.models import PermissionState

for role in await club.roles.all(with_members=True):
    print(role.name, role.member_count, [m.last_name for m in role.members])

trainer = await club.roles.create("Trainer", "Darf Termine pflegen")
await club.roles.update(trainer, name="Übungsleiter")
await club.roles.delete(trainer)          # members that hold it lose it
```

A role is given by id, exact name or `ClubRole` object.

## Permissions

A role's permissions form a tree: containers (for example "Kalender") with the
actual permissions below them. Each permission has one of four states:

| `PermissionState` | Meaning |
| --- | --- |
| `LOCKED` (0) | no access |
| `READ` (1) | may view |
| `UPDATE` (2) | may view and change |
| `UPDATE_AND_DELETE` (3) | may view, change and delete |

```python
tree = await club.roles.permissions(trainer)               # the full tree
states = await club.roles.permission_states(trainer)       # {"calendar_events_module": 0, ...}

await club.roles.set_permission(trainer, "calendar_events_module", PermissionState.UPDATE)
```

A new role starts with the service's default permissions (most areas locked).
The keys are defined by MeinVerein; read them from `permission_states()`.

## Who holds a role

Roles belong to **user accounts**. Only a member who was invited and has a
MeinVerein account can hold one.

```python
await club.roles.set_member_roles(member_id, ["Verwalter", "Mitglied"])   # replace the member's roles
await club.roles.add_members("Verwalter", [101, 102])                     # add holders, returns who got it
await club.roles.set_members("Verwalter", [101])                          # exactly these holders
```

- `set_member_roles` raises `NoAccountError` for a member without account.
  (The service itself fails on that request without a useful message.)
- `add_members` returns the ids that received the role; members without
  account are skipped by the API and missing from the result.

`club.members.list(role="Verwalter")` lists the holders of a role.

## Calls behind the methods

| Method | HTTP call |
| --- | --- |
| `all`, `get` | `GET /protected/club/{club}/auth/club-roles` |
| `create` | `POST /protected/club/{club}/auth/club-role/create` |
| `update` | `PUT /protected/club/{club}/auth/club-role/{role}/update` |
| `delete` | `DELETE /protected/club/{club}/auth/club-role/{role}` |
| `permissions`, `permission_states` | `GET /protected/club/{club}/auth/club-role/{role}/permissions/all` |
| `set_permission` | `PUT /protected/club/{club}/auth/club-role/{role}/permission-key` |
| `set_member_roles` | `PUT /protected/club/{club}/auth/club-members/{member}/assign/club-roles` |
| `add_members` / `set_members` | `POST` / `PUT /protected/club/{club}/auth/club-role/{role}/assign/club-members` |

All verified against the demo club.
