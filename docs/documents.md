# Documents

`club.documents` manages the club's document storage ("Dokumente"): folders
and the files in them.

```python
minutes = await club.documents.create_directory("Protokolle")
year = await club.documents.create_directory("2026", parent=minutes)

document = await club.documents.upload("Protokolle/2026", "Sitzung 2026-03.pdf")
content = await club.documents.download(document.id)

for entry in await club.documents.list("Protokolle/2026"):
    print(entry.name, entry.document_type, entry.size, entry.is_directory)

await club.documents.rename_document(document.id, "Vorstandssitzung März")
await club.documents.move([document.id], source="Protokolle/2026", target="Allgemeines")
await club.documents.delete_document(document.id)
await club.documents.delete_directory(minutes)        # with everything in it
```

## Things to know

- **Folders** are given by id, by path from the top level (`"Protokolle/2026"`)
  or as an object returned by another call. **Files** are given by id. Ids are
  UUID text.
- The **top level only holds folders**; upload into a folder.
- `upload()` takes a path, or bytes plus `name=` (with extension). MeinVerein
  lists a file **without its extension** and keeps the kind of file in
  `document_type`.
- The service **checks the content against the extension** and rejects a
  mismatch with `BadRequestError` ("Der Dateityp stimmt nicht mit der
  Dateiendung überein").
- `tree()` returns the folder hierarchy without the folders MeinVerein manages
  itself; `list()` shows those too (`is_system`).
- **Deleting a folder deletes its content.** There is no trash.
- Errors of this part of the API carry a `code` (for example
  `DIRECTORY_DOES_NOT_EXIST`), available as `error.name`.

## Calls behind the methods

| Method | HTTP call |
| --- | --- |
| `tree` | `GET /protected/club/{club}/dms/directories/tree` |
| `list` | `GET /protected/club/{club}/dms/directories[/{folder}]?offset=..&limit=..` |
| `create_directory` | `POST /protected/club/{club}/dms/directories` |
| `rename_directory` / `delete_directory` | `PATCH` / `DELETE /protected/club/{club}/dms/directories/{folder}` |
| `upload` | `POST /protected/club/{club}/dms/documents/{folder}` (multipart, field `file`) |
| `download` | `GET /protected/club/{club}/dms/documents/{id}/download` |
| `rename_document` / `delete_document` | `PATCH` / `DELETE /protected/club/{club}/dms/documents/{id}` |
| `move` | `POST /protected/club/{club}/dms/documents/move` |

All verified against the demo club.
