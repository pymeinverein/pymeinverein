# pymeinverein — status and to-do

$ claude --resume 6540339e-3388-4cd2-93c1-60ec50dd3f5c


Status after the second round (2026-11-11). `pymeinverein` covers members
(including membership periods, custom fields, pictures, bulk edits and
invitations), lists with rules, custom field definitions, departments, roles
and permissions, club settings, contributions, events, finance (read plus cash
box bookings), dashboard, documents, mailings and reports, each with a mock
server counterpart and docs. 157 mock-based tests, strict mypy, black and the
docs build pass; the 24 opt-in live tests pass against the Demoverein demo
club and leave nothing behind (one is skipped unless an invitation address is
given).

See `docs/endpoints.md` for every implemented endpoint and its state
(verified or unverified) and for the known endpoints that are still missing.

## API behaviour worth knowing

- **Updates send the whole member.** A partial update is accepted but silently
  clears fields that are left out (the e-mail address, for one), so `update()`
  loads, merges and sends everything back.
- **Delete reports success for ids that don't exist.** `delete()` therefore
  checks every id first and raises before deleting anything.
- **Logout does not revoke the token**, and the token has no expiry. Treat it
  like a password.
- **The "Request Rejected" page** appears for blocked requests and, apparently,
  for server errors (`T-1` as member number, roles for members without account,
  mailings from a club that may not send). It surfaces as `RequestRejectedError`.
- **A member's status is derived** from the membership periods; use
  `set_membership` / `end_membership`.
- **Demo clubs may not send mailings** (`sendEmailEnabled: false`), so
  `mailing.send` is unverified.
- **The country is not defaulted** on create; pass `country_id` (2 is Germany).

## Where things stand in git

- Work is on branch `initial-library` (17 commits); `main` still only has the
  gitignore commit. Merge it when you're happy.
- `v0.1.0` is tagged locally on the round-1 commit. Round 2 is collected under
  *Unreleased* in `CHANGELOG.md`, ready for `v0.2.0`. Nothing is pushed.

## To do: needs the maintainer

- [ ] Merge `initial-library` into `main`.
- [ ] Create the GitHub repository and push (no remote exists; `gh` is not
      installed).
- [ ] Register the PyPI trusted publisher and create a `pypi` environment on
      GitHub; `docs/releasing.md` has the exact values.
- [ ] Add the repository URL to `pyproject.toml` (`[project.urls]`).
- [ ] Decide on the first release (`v0.1.0` exists; `v0.2.0` would include round 2) and push the tag.

## To do: next milestones

`docs/endpoints.md` lists the remaining known endpoints by area. Deliberately
out of scope: SEPA debit runs, bank transfers, online banking setup,
subscription and purchase calls, club deletion.

- [x] Roles and permissions (create/update/delete roles, permissions, assign to members)
- [x] Member invitations (verified once with a test address) and revoking
- [x] Member bulk edit, pictures, custom field values, membership periods
- [ ] Member documents
- [x] Join requests (reading verified; accept/reject unverified)
- [ ] Member import from files
- [x] Departments (create, update, copy, delete, rename levels)
- [x] List criteria (dynamic lists), copy, favourites, custom field definitions
- [ ] List column settings, free lists
- [x] Club settings (details, logo, salutations, titles, numbering)
- [ ] Club settings: e-mail, text templates, saving salutations and numbering
- [x] Contribution rates and assignment (billing runs stay out of scope)
- [x] Invoices and other business transactions (read-only)
- [ ] Invoices: create, close, credit notes, expenses
- [x] Accounts, bookings, cash box bookings
- [ ] Assigning bookings to invoices, chart of accounts
- [ ] Donations
- [x] Events and calendar (without participants)
- [ ] Event participants, attachments, recurring series
- [x] Mailing: templates, drafts, preview, sent items
- [ ] Mailing: verify `send` with a club that may send e-mail; outbox actions, attachments
- [x] Documents (folders, upload, download, rename, move, delete)
- [x] Reports, dashboard, account profile (read)
- [ ] Booking journal export (background jobs), changing the account profile
- [ ] Verify the two-factor login against an account that has it enabled
