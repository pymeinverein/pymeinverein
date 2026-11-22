# Mailings

`club.mailing` handles the club's mailings ("Korrespondenz"): templates,
drafts, previews, sent items and sending.

```python
template = await club.mailing.create_template(
    "Einladung", "Einladung zur Mitgliederversammlung", "<p>Liebe Mitglieder, ...</p>"
)

ids = [m.id for m in await club.members.list(type="member", status="active")]
draft = await club.mailing.create_draft(
    "Versammlung 2027", template.subject, template.html, recipients=ids
)
preview = await club.mailing.preview(draft.subject, draft.html, recipients=ids[:1])
print(preview.recipient_email, preview.text)

await club.mailing.delete(draft.id, template.id)       # drafts and templates alike
```

Recipients are member ids; the library looks up each member's e-mail address
and communication channel. The message body is HTML.

## Sending

!!! warning "This sends e-mails"
    `send()` e-mails every recipient right away.

```python
if await club.mailing.sending_enabled():
    await club.mailing.send("Training fällt aus", "<p>Heute kein Training.</p>", recipients=ids)
```

MeinVerein only lets some clubs send e-mail (field `sendEmailEnabled` of the
club). Demo clubs may not. `send()` checks this first and raises
`SendingDisabledError` without contacting the send endpoint. Without that check
the service answers with its "Request Rejected" page.

!!! note "Unverified"
    Sending is implemented from the web application's code and tested against
    the mock server. The only club available for live tests is a demo club,
    which may not send, so `send()` has not been tried on the real service.

## Sent items and outbox

```python
for item in await club.mailing.sent():
    print(item.last_attempt_at, item.email, item.subject, item.failure_reason)

waiting = await club.mailing.outbox()       # e.g. letters still to be printed
removed = await club.mailing.deleted()
```

## Calls behind the methods

All paths below `/protected/clubs/{club}/mailingDispatch`.

| Method | HTTP call | State |
| --- | --- | --- |
| `templates` / `drafts` | `GET /list/template` / `GET /list/draft` | verified |
| `template`, `create_template`, `update_template` | `GET`, `POST`, `PUT /template[/{id}]` | verified |
| `draft`, `create_draft`, `update_draft` | `GET`, `POST`, `PATCH /dispatch[/{id}]` | verified |
| `delete` | `DELETE` (body `{"ids": [...]}`) | verified |
| `preview` | `POST /emailPreview` | verified |
| `outbox`, `sent`, `deleted` | `GET /list/items/{outbox,sent,deleted}` | verified |
| `sending_enabled` | `GET /protected/mv365/clubs/{club}` (field `sendEmailEnabled`) | verified |
| `send` | `POST /sendDirect` | unverified |
