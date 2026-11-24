# Members and contacts

MeinVerein keeps members, contacts and companies in one place and tells them
apart by `type`. The API calls all of them "club members"; so does this
library. Everything below hangs off a club client:

```python
async with MeinVereinClient() as mv:
    club = await mv.clubs.get(name="Demoverein")
    members = club.members
```

## Read

```python
member = await club.members.get(23430459)        # all details of one member
print(member.full_name, member.email, member.address.city)

everyone = await club.members.list()             # members, former members, contacts
active = await club.members.list(type="member", status="active")
women = await club.members.list(department="1. Mannschaft - Damen")
board = await club.members.list(from_list="Vorstand")
no_mail = await club.members.list(type="member", where=lambda m: not m.email)
```

### Filters

| Argument | Meaning |
| --- | --- |
| `from_list` | Read this list (id, exact name or `DefaultListType`) instead of the list of everyone |
| `type` | `"member"`, `"contact"`, `"company"` or a `MemberType` |
| `status` | `"active"`, `"former"`, `"passive"` or a `MemberState` |
| `department` | Name or id of a department (or of a function inside one) |
| `role` | Name or id of a permission role |
| `search` | Text contained in name, e-mail address or member number (case-insensitive) |
| `where` | Any function `Member -> bool` |

All given conditions must hold. `from_list` is evaluated by the server; the
other filters run in Python on the rows of that list (`MemberFilter`).

`list()` returns *list rows*: they contain department names (`member.departments`),
roles and custom field values, but not every field. `get()` returns the full
record.

For server-side selection with the criteria that dynamic lists use there is
`query()`:

```python
former = await club.members.query([("type", "=", 1), ("state", "=", 1)])
```

### Codes

The API stores several properties as numbers. The enums in
`pymeinverein.models` name them:

| Field | Enum | Values |
| --- | --- | --- |
| `type` | `MemberType` | `MEMBER=1`, `CONTACT=2`, `COMPANY=3` |
| `state` | `MemberState` | `ACTIVE=0`, `FORMER=1`, `PASSIVE=2` |
| `gender` | `Gender` | `MALE=0`, `FEMALE=1`, `NOT_SPECIFIED=2`, `DIVERSE=3` |
| `marital_status` | `MaritalStatus` | `LIKE_MARRIAGE=0` ... `WIDOWED=6` |
| `invitation_state` | `InvitationState` | `ACCEPTED=0` ... `REJECTED=5` |
| `payment_type.type` | `PaymentMethod` | `SEPA_DEBIT=0`, `INVOICE=1`, `THIRD_PARTY=2` |

Model fields hold the plain numbers (so new values do not break parsing);
compare them with the enums: `member.type == MemberType.CONTACT`.

## Create

```python
from datetime import date

member = await club.members.create(
    first_name="Ada",
    last_name="Lovelace",                 # the only required field
    email="ada@example.org",
    birthday=date(1815, 12, 10),
    membership_begin_at=date(2024, 1, 1),
    address={"address_line1": "Main St 1", "zip": "12345", "city": "Berlin", "country_id": 2},
)

contact = await club.members.create(last_name="Miller", type=MemberType.CONTACT)
company = await club.members.create(last_name="ACME GmbH", type=MemberType.COMPANY)
```

Fields are passed by name in `snake_case` (or the API's `camelCase`). Dates,
enums and models such as `Address` are converted for you. The member number is
assigned by MeinVerein unless you pass `member_id`.

Things observed on the real service:

- The country is not defaulted: pass `country_id` (2 is Germany; see
  `club.master_data.countries()`).
- Several members may share an e-mail address.
- Some harmless looking values make the service answer with its "Request
  Rejected" page (a member number of `T-1` was refused, `900` was fine). This
  surfaces as `RequestRejectedError`.

## Change

```python
await club.members.update(member.id, phone="030 123", notes="prefers e-mail")
await club.members.update(member.id, address={"city": "Potsdam"})   # keeps the street
await club.members.update(member.id, birthday=date(1990, 5, 17), gender=Gender.FEMALE)
```

`update()` loads the member, applies your changes and sends the whole object
back. That is deliberate: the API accepts partial updates but **silently clears
some fields that are missing** (the e-mail address, for example) and replaces
nested objects like the address as a whole. Sending everything is what the web
application does too.

## Delete

```python
result = await club.members.delete(member.id)
result = await club.members.delete(101, 102, 103)
```

Deleting is permanent. The API reports success even for ids that do not exist,
so `delete()` first checks every id and raises `NotFoundError` before deleting
anything. Pass `missing_ok=True` to skip that check. Members who pay for other
members are skipped by the API (`result.skipped_count`) unless you pass
`force_payers=True`.

## Membership periods and status

MeinVerein records membership as *periods* (the API calls them `histories`):
one per department or function, each with a start, an optional end and a
status. A member's overall `state` is **derived** from the periods - sending
`state` or `membership_end_at` in `update()` has no effect.

```python
from datetime import date
from pymeinverein import MemberState

# Join a department (or a function inside one, given as a path)
await club.members.set_membership(member.id, "1. Mannschaft - Damen", start=date(2025, 1, 1))
await club.members.set_membership(member.id, "1. Mannschaft - Damen/Spieler")

# Change an existing period
await club.members.set_membership(member.id, "1. Mannschaft - Damen", status=MemberState.PASSIVE)

# The member leaves the club
await club.members.end_membership(member.id, date(2026, 12, 31))
```

To set several periods at once - with exact start and end dates, in a single
update - describe each one with a `MembershipPeriod`:

```python
from pymeinverein import MembershipPeriod

await club.members.set_memberships(member.id, [
    MembershipPeriod("Aktivitas/aF", date(2009, 1, 1), date(2009, 12, 31)),
    MembershipPeriod("Aktivitas/aB", date(2010, 1, 1)),          # open
])
```

A `MembershipPeriod` is the complete wanted state of its period: `end=None`
leaves it open and removes an end date it had. The status defaults to
`FORMER` for periods that ended before today and to `ACTIVE` otherwise.
Periods for departments that are not mentioned are kept; pass `replace=True`
to remove them.

A department is given by id, by a unique name, or as `Department/Function`
when the name alone is ambiguous. `department=None` means the club as a whole.
A member created without periods is active and has `histories == []`.

## Custom field values

```python
await club.members.set_custom_field(member.id, "Position", "Tor")
await club.members.set_custom_field(member.id, "Spielberechtigt", True)
await club.members.clear_custom_field(member.id, "Position")
```

The field is given by name or id. Values are stored as text (`True` becomes
`"true"`, lists stay lists).

!!! warning "Multiple choice fields drop unknown values"
    A multiple choice field stores `null` for every value that is not one of
    its options - the call succeeds, but the value is lost. Reading leaves
    these `null`s out. Add the option first (`club.custom_fields.update`).
    Observed with the bulk edit call; other field types were not seen to
    check their options.

## Pictures

```python
await club.members.set_picture(member.id, "portrait.jpg")     # path or bytes
jpeg = await club.members.picture(member.id, "small")         # small, medium, large
await club.members.delete_picture(member.id)
```

## Bulk edits

`club.members.bulk` changes many members with one call. Each method returns a
`BulkResult`; `result.skips` lists the members the API left untouched and why.

```python
from pymeinverein.models import CommunicationChannel, PaymentMethod

ids = [m.id for m in await club.members.list(department="1. Mannschaft - Herren")]

await club.members.bulk.set_custom_fields(ids, {"Position": "Sturm"}, notes="U23")
await club.members.bulk.set_communication_channel(ids, CommunicationChannel.LETTER)
await club.members.bulk.add_membership(ids, "2. Mannschaft - Herren", start=date(2026, 1, 1))
await club.members.bulk.update_membership(
    ids, "1. Mannschaft - Herren", end=date(2025, 12, 31), status=MemberState.FORMER
)

result = await club.members.bulk.set_payment_method(ids, PaymentMethod.SEPA_DEBIT)
for skip in result.skips:
    print(skip.club_member_id, skip.reason)        # e.g. NO_SEPA_MANDATE
```

## Invitations

Inviting a member gives them access to the club's MeinVerein portal.

!!! warning "This sends e-mails"
    `invite()` makes MeinVerein send an e-mail to every invited member.

```python
result = await club.members.invite(101, 102, 103)
print(result.invited, result.not_invited)

await club.members.invite(104, roles=[await club.roles.get("Verwalter")])
await club.members.revoke_invitation(101)      # as long as it was not accepted
```

- `roles` are the roles the member gets on accepting; by default the built-in
  member role ("Mitglied").
- Members without e-mail address or with an existing account are not invited
  and counted in `not_invited`.
- `member.invitation_state` shows the progress (`InvitationState`):
  `NOT_INVITED` → `INVITED` → `ACCEPTED`, or `REVOKED`.

Only members with an account can hold [roles](roles.md).

## Join requests

People can ask to join a club through its public profile.

```python
for request in await club.members.join_requests():
    print(request.full_name, request.email)

await club.members.accept_join_request(request.id)
await club.members.reject_join_request(request.id)
```

!!! note "Partly unverified"
    Reading the requests was verified. Accepting and rejecting are implemented
    from the web application's code; the demo club has no requests to try them
    on.

## Other calls

```python
await club.members.next_number()             # the number MeinVerein would assign next
await club.members.picture(member.id)        # JPEG bytes
await club.members.user_exists("a@b.org")    # is there a MeinVerein *login* with this address?
```

## Lists

Member lists, dynamic lists with rules and custom field definitions are
described in [Lists and custom fields](lists-and-fields.md).

## Master data

Ids in member data refer to the club's master data:

```python
master = await club.master_data.get()            # salutations, titles, departments, rates, custom fields
await club.master_data.areas()                   # department structure
await club.master_data.individual_fields()       # custom field definitions
await club.master_data.roles()                   # permission roles
await club.master_data.countries()               # country ids for addresses
```

## Calls behind the methods

| Method | HTTP call |
| --- | --- |
| `members.get` | `GET /protected/club/{club}/members/{id}` |
| `members.list`, `lists.members` | `POST /protected/club/{club}/list/{list}` with `x-api-version: v3` |
| `members.query` | `POST /protected/club/{club}/list/all-members` |
| `members.create` | `POST /protected/mv365/clubs/{club}/members` |
| `members.update` | `GET` + `PATCH /protected/mv365/clubs/{club}/members/{id}` with `x-api-version: v2` |
| `members.delete` | `POST /protected/club/{club}/members/delete` |
| `members.set_membership`, `members.set_memberships`, `members.end_membership` | `GET` + `PATCH /protected/mv365/clubs/{club}/members/{id}` (field `histories`) |
| `members.set_custom_field` / `clear_custom_field` | `PUT` / `DELETE /protected/club/{club}/list/individual-field-data` |
| `members.set_picture` / `delete_picture` | `POST` / `DELETE /protected/mv365/clubs/{club}/members/{id}/images` |
| `members.bulk.*` | `PUT` or `POST /protected/club/{club}/members/bulk-edit/{communication-type, payment-types, individual-field-data, memberships}` |
| `members.invite` | `POST /protected/club/{club}/members/invite` |
| `members.revoke_invitation` | `POST /protected/mv365/clubs/{club}/members/{id}/invite/revoke` |
| `members.join_requests` | `GET /protected/club/{club}/requested-members` |
| `members.accept_join_request` / `reject_join_request` | `POST /protected/club/{club}/members/{id}/join/accept` / `.../join/reject` (unverified) |
| `members.next_number` | `GET /protected/mv365/clubs/{club}/members/next-number/{type}` |
| `members.picture` | `GET /mv365/clubs/{club}/members/{id}/image?type=...` |
| `members.user_exists` | `GET /protected/club/{club}/user/exists?email=...` |
| `lists.all` | `GET /protected/club/{club}/list/all` |
| `lists.criteria` | `GET /protected/club/{club}/list/criteria/{list}` |
| `lists.create` | `POST /protected/club/{club}/list/create` |
| `lists.rename` / `lists.delete` | `PUT` / `DELETE /protected/club/{club}/list/{list}` |
| `lists.add_members` / `lists.remove_members` | `POST /protected/club/{club}/list/assign-members/{list}` / `.../remove-members/{list}` |
| `master_data.get` / `areas` | `GET /protected/mv365/clubs/{club}/data` / `.../areas` |
| `master_data.individual_fields` | `GET /protected/club/{club}/list/individual-field` |
| `master_data.roles` | `GET /protected/club/{club}/auth/club-roles` |
| `master_data.countries` | `GET /mv365/all_countries` |

Unless marked otherwise, all of these were verified against the demo club of
the real service.
