# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Command line tool `scripts/meinverein.py`: list, export, show, create,
  update and delete members; overviews of clubs, lists, departments, roles,
  custom fields, rates, events, accounts, bookings, documents and reports;
  document and report downloads.
- Members: `set_memberships` sets several membership periods (with exact
  start and end, removing end dates) in one update; `MembershipPeriod`.
- Members: membership periods (`set_membership`, `end_membership`), custom
  field values, picture upload and removal, bulk edits (`members.bulk`).
- Departments: `club.departments` with create, update, copy, delete and
  renaming of levels.
- Lists: dynamic lists with rules (`create(criteria=...)`, `set_criteria`,
  `field_criteria`), `copy`, `set_favourite`.
- Custom field definitions: `club.custom_fields` with create, update, delete.
- Roles and permissions: `club.roles` with create, update, delete,
  permission tree, `set_permission` and role assignment; `NoAccountError`.
- Invitations (`members.invite`, `revoke_invitation`) and join requests.
- Club settings: `club.settings` with details, logo, salutations, titles and
  numbering.
- Contributions: `club.contributions` with rates (create, update, delete)
  and assignment to members.
- Events: `club.events` with list, search, create, update, delete and
  calendar categories.
- Finance: `club.finance` with accounts, bookings, cash box bookings and
  business transactions (read); `club.dashboard` statistics.
- Documents: `club.documents` with folders, upload, download, rename, move
  and delete.
- Mailings: `club.mailing` with templates, drafts, preview, sent items and a
  guarded `send` (`SendingDisabledError`).
- Reports: `club.reports` with run, download and export; `account.profile`.
- `scripts/probe.py` for exploring endpoints on the demo club.
- `MEINVEREIN_TOKEN` environment variable to skip the login; tokens copied
  with a `Bearer ` prefix are accepted.

### Security

- GitHub workflows pin every action to a commit id (checkout v7.0.1,
  setup-uv v10.3.3, upload-artifact v7.0.2, download-artifact v8.0.2,
  pypi-publish v1.14.3) and don't keep the checkout credentials.
- Dependabot updates the actions and the Python dependencies weekly.

### Fixed

- File names in uploads are no longer percent-encoded (a space became `%20`).
- Reading a member no longer fails when a multiple choice field holds `null`
  values. The real service stores `null` for values that are not among the
  field's options; they are now left out, and the docs no longer claim that
  options are not checked. The mock server mirrors the behaviour.

### Changed

- The mock server's routes are split into one module per area.

## [0.1.0] - 2026-11-09

First release.

### Added

- `MeinVereinClient` with login through the Buhl account, including a hook for
  two-factor codes.
- Account and club lookup.
- Members and contacts: `get`, `list` with filters, `query`, `create`,
  `update`, `delete`, `next_number`, `picture`.
- Member export as JSON or CSV with field sets, custom columns and custom
  fields.
- Member lists: read, create, rename, delete, add and remove members.
- Master data: salutations, titles, departments, custom fields, roles,
  countries.
- Mock server (`pymeinverein.testing`) for tests without the real service.
- CI and release workflows (PyPI trusted publishing).
