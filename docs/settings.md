# Club settings

`club.settings` covers the club's own data.

```python
details = await club.settings.details()
print(details.name, details.email, details.phone)

logo = await club.settings.logo("large")          # JPEG bytes, b"" if there is none
await club.settings.set_logo("logo.png", content_type="image/png")
await club.settings.delete_logo()

for salutation in await club.settings.salutations():
    print(salutation.label, salutation.address)

for title in await club.settings.titles():
    print(title.id, title.label)
await club.settings.update_title(title.id, favorite=True)

numbering = await club.settings.numbering()         # invoice numbers
print(await club.settings.next_number())            # e.g. 2026000033
```

## Changing club details

```python
await club.settings.update(name2="seit 1900", website="example.org")
```

`update()` loads the club, applies the changes and sends the whole object
back. The API insists on a club category in that object; a club without one
gets `BadRequestError` until you pass `category_id` (see
`club.settings.categories()`).

!!! note "Unverified"
    `update()` and `create_title()` are implemented from the web application's
    code and tested against the mock only. The demo club has no category and
    setting one cannot be undone; titles cannot be deleted through the API.

## Calls behind the methods

| Method | HTTP call | State |
| --- | --- | --- |
| `details` | `GET /protected/mv365/clubs/{club}` | verified |
| `update` | `PATCH /protected/mv365/clubs/{club}` | unverified |
| `categories` | `GET /protected/mv365/club-categories` | verified |
| `logo` | `GET /mv365/clubs/{club}/logo?size=...` | verified |
| `set_logo` / `delete_logo` | `POST` / `DELETE /protected/mv365/clubs/{club}/logo` | verified |
| `salutations` | `GET /protected/club/{club}/formsOfAddress` | verified |
| `titles` | `GET /protected/club/{club}/titles` | verified |
| `create_title` | `POST /protected/club/{club}/titles` | unverified |
| `update_title` | `PUT /protected/club/{club}/titles/{id}` | verified |
| `numbering` / `next_number` | `GET /protected/club/{club}/settings/numeration/{kind}` / `.../next` | verified |
