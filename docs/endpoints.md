# Endpoint coverage

The web application can call roughly 400 endpoints (see
[How the API was discovered](api-discovery.md)). This page tracks what the
library covers.

Legend: **verified** = implemented and tested against the real demo club;
**unverified** = implemented from the web application's code only;
**known** = discovered, not implemented yet.

## Implemented

| Area | Endpoint | Library | State |
| --- | --- | --- | --- |
| Login | `POST www.buhl.de/mein-buhlkonto/wp-json/api/v1/login` | `auth.login` | verified |
| Login | same, with `TwoFactorToken` | `auth.login(two_factor=)` | unverified |
| Login | `POST /auth/buhlkonto/token` | `auth.login` | verified |
| Session | `GET /protected/accounts` | `account.get`, `clubs.list`, `clubs.get` | verified |
| Session | `GET /protected/auth/buhlkonto/keepalive` | `account.keepalive` | verified |
| Session | `GET /protected/mv365/accounts/logout` | `logout` | verified |
| Club | `POST /protected/mv365/clubs/{club}/selected` | `club.select` | verified |
| Members | `GET /protected/club/{club}/members/{id}` | `members.get` | verified |
| Members | `POST /protected/mv365/clubs/{club}/members` | `members.create` | verified |
| Members | `GET`, `PATCH /protected/mv365/clubs/{club}/members/{id}` | `members.update`, `set_membership`, `set_memberships`, `end_membership` | verified |
| Members | `POST /protected/club/{club}/members/delete` | `members.delete` | verified |
| Members | `POST /protected/club/{club}/list/all-members` | `members.query` | verified |
| Members | `GET /protected/mv365/clubs/{club}/members/next-number/{type}` | `members.next_number` | verified |
| Members | `GET /mv365/clubs/{club}/members/{id}/image` | `members.picture` | verified |
| Members | `GET /protected/club/{club}/user/exists` | `members.user_exists` | verified |
| Members | `PUT`, `DELETE /protected/club/{club}/list/individual-field-data` | `members.set_custom_field`, `clear_custom_field` | verified |
| Members | `POST`, `DELETE /protected/mv365/clubs/{club}/members/{id}/images` | `members.set_picture`, `delete_picture` | verified |
| Members | `PUT /protected/club/{club}/members/bulk-edit/individual-field-data` | `members.bulk.set_custom_fields` | verified |
| Members | `PUT /protected/club/{club}/members/bulk-edit/communication-type` | `members.bulk.set_communication_channel` | verified |
| Members | `PUT /protected/club/{club}/members/bulk-edit/payment-types` | `members.bulk.set_payment_method` | verified |
| Members | `POST`, `PUT /protected/club/{club}/members/bulk-edit/memberships` | `members.bulk.add_membership`, `update_membership` | verified |
| Invitations | `POST /protected/club/{club}/members/invite` | `members.invite` | verified |
| Invitations | `POST /protected/mv365/clubs/{club}/members/{id}/invite/revoke` | `members.revoke_invitation` | verified |
| Join requests | `GET /protected/club/{club}/requested-members` | `members.join_requests` | verified |
| Join requests | `POST /protected/club/{club}/members/{id}/join/accept`, `.../join/reject` | `members.accept_join_request`, `reject_join_request` | unverified |
| Lists | `GET /protected/club/{club}/list/all` | `lists.all`, `lists.get` | verified |
| Lists | `POST /protected/club/{club}/list/{list}` | `lists.members`, `members.list`, `members.export` | verified |
| Lists | `GET /protected/club/{club}/list/criteria/{list}` | `lists.criteria` | verified |
| Lists | `POST /protected/club/{club}/list/create` | `lists.create` | verified |
| Lists | `PUT`, `DELETE /protected/club/{club}/list/{list}` | `lists.rename`, `lists.delete` | verified |
| Lists | `POST /protected/club/{club}/list/assign-members/{list}` | `lists.add_members` | verified |
| Lists | `POST /protected/club/{club}/list/remove-members/{list}` | `lists.remove_members` | verified |
| Departments | `POST /protected/mv365/clubs/{club}/subareas` | `departments.create` | verified |
| Departments | `PATCH`, `DELETE /protected/mv365/clubs/{club}/subareas/{id}` | `departments.update`, `delete` | verified |
| Departments | `POST /protected/mv365/clubs/{club}/subareas-copy/{id}` | `departments.copy` | verified |
| Departments | `PATCH /protected/mv365/clubs/{club}/areas/{id}` | `departments.rename_level` | verified |
| Lists | `POST /protected/club/{club}/list/criteria/{list}`, `DELETE .../list/criteria` | `lists.set_criteria`, `lists.create(criteria=)` | verified |
| Lists | `GET`, `DELETE /protected/club/{club}/list/individual-field-criteria/{list}`, `POST .../individual-field-criteria/` | `lists.field_criteria`, `lists.set_criteria` | verified |
| Lists | `POST /protected/club/{club}/list/{list}/copy` | `lists.copy` | verified |
| Lists | `POST`, `DELETE /protected/club/{club}/list/favorites/{list}` | `lists.set_favourite` | verified |
| Custom fields | `POST /protected/club/{club}/list/individual-field` | `custom_fields.create` | verified |
| Custom fields | `PUT`, `DELETE /protected/club/{club}/list/individual-field/{id}` | `custom_fields.update`, `delete` | verified |
| Roles | `GET /protected/club/{club}/auth/club-roles` | `roles.all`, `roles.get`, `master_data.roles` | verified |
| Roles | `POST /protected/club/{club}/auth/club-role/create` | `roles.create` | verified |
| Roles | `PUT /protected/club/{club}/auth/club-role/{role}/update`, `DELETE .../club-role/{role}` | `roles.update`, `roles.delete` | verified |
| Roles | `GET /protected/club/{club}/auth/club-role/{role}/permissions/all` | `roles.permissions`, `permission_states` | verified |
| Roles | `PUT /protected/club/{club}/auth/club-role/{role}/permission-key` | `roles.set_permission` | verified |
| Roles | `PUT /protected/club/{club}/auth/club-members/{member}/assign/club-roles` | `roles.set_member_roles` | verified |
| Roles | `POST`, `PUT /protected/club/{club}/auth/club-role/{role}/assign/club-members` | `roles.add_members`, `set_members` | verified |
| Settings | `GET /protected/mv365/clubs/{club}` | `settings.details` | verified |
| Settings | `PATCH /protected/mv365/clubs/{club}` | `settings.update` | unverified |
| Settings | `GET /protected/mv365/club-categories` | `settings.categories` | verified |
| Settings | `GET /mv365/clubs/{club}/logo`, `POST`, `DELETE /protected/mv365/clubs/{club}/logo` | `settings.logo`, `set_logo`, `delete_logo` | verified |
| Settings | `GET /protected/club/{club}/formsOfAddress` | `settings.salutations` | verified |
| Settings | `GET /protected/club/{club}/titles`, `PUT .../titles/{id}` | `settings.titles`, `update_title` | verified |
| Settings | `POST /protected/club/{club}/titles` | `settings.create_title` | unverified |
| Settings | `GET /protected/club/{club}/settings/numeration/{kind}`, `.../next` | `settings.numbering`, `next_number` | verified |
| Contributions | `GET`, `POST /protected/mv365/club/{club}/contribution/rates` | `contributions.rates`, `create` | verified |
| Contributions | `GET`, `PATCH`, `DELETE /protected/mv365/club/{club}/contribution/rate/{id}` | `contributions.update`, `delete` | verified |
| Contributions | `POST`, `DELETE /protected/club/{club}/members/bulk-edit/contributions` | `contributions.assign`, `unassign` | verified |
| Events | `GET /protected/mv365/clubs/{club}/events`, `.../events/{id}` | `events.list`, `events.get` | verified |
| Events | `GET /protected/club/{club}/calendar/search` | `events.search` | verified |
| Events | `POST /protected/club/{club}/calendar/create`, `.../calendar/delete` | `events.create`, `events.delete` | verified |
| Events | `POST /protected/club/{club}/event/{id}` | `events.update` | verified |
| Events | `GET`, `POST /protected/mv365/clubs/{club}/event-categories`, `DELETE /protected/club/{club}/event-categories/{id}` | `events.categories`, `create_category`, `delete_category` | verified |
| Finance | `GET /protected/club/{club}/banking/account` | `finance.accounts`, `account`, `total_balance` | verified |
| Finance | `GET /protected/club/{club}/banking/account/{id}/turnover` | `finance.bookings` | verified |
| Finance | `GET`, `DELETE /protected/club/{club}/banking/booking/{id}` | `finance.booking`, `delete_booking` | verified |
| Finance | `POST /protected/club/{club}/banking/cashjournal/{account}/booking` | `finance.create_cash_booking` | verified |
| Finance | `GET /protected/club/{club}/businesstransactions`, `.../invoice/{id}` | `finance.transactions`, `finance.invoice` | verified |
| Dashboard | `GET /protected/club/{club}/dashboard/{memberStatistics,financeStatistics,financeComparison}` | `dashboard.*` | verified |
| Documents | `GET /protected/club/{club}/dms/directories/tree`, `.../dms/directories[/{id}]` | `documents.tree`, `documents.list` | verified |
| Documents | `POST`, `PATCH`, `DELETE /protected/club/{club}/dms/directories[/{id}]` | `documents.create_directory`, `rename_directory`, `delete_directory` | verified |
| Documents | `POST /protected/club/{club}/dms/documents/{folder}`, `GET .../documents/{id}/download` | `documents.upload`, `download` | verified |
| Documents | `PATCH`, `DELETE /protected/club/{club}/dms/documents/{id}`, `POST .../documents/move` | `documents.rename_document`, `delete_document`, `move` | verified |
| Mailing | `GET /protected/clubs/{club}/mailingDispatch/list/{draft,template}` | `mailing.drafts`, `templates` | verified |
| Mailing | `GET`, `POST`, `PUT .../mailingDispatch/template[/{id}]` | `mailing.template`, `create_template`, `update_template` | verified |
| Mailing | `GET`, `POST`, `PATCH .../mailingDispatch/dispatch[/{id}]` | `mailing.draft`, `create_draft`, `update_draft` | verified |
| Mailing | `DELETE .../mailingDispatch` | `mailing.delete` | verified |
| Mailing | `POST .../mailingDispatch/emailPreview` | `mailing.preview` | verified |
| Mailing | `GET .../mailingDispatch/list/items/{outbox,sent,deleted}` | `mailing.outbox`, `sent`, `deleted` | verified |
| Mailing | `POST .../mailingDispatch/sendDirect` | `mailing.send` | unverified |
| Reports | `GET`, `POST /protected/club/{club}/reports` | `reports.all`, `get`, `run` | verified |
| Reports | `GET /protected/club/{club}/reports/{processId}/download` | `reports.download`, `export` | verified |
| Account | `GET /protected/accounts/profile` | `account.profile` | verified |
| Master data | `GET /protected/mv365/clubs/{club}/data` | `master_data.get` | verified |
| Master data | `GET /protected/mv365/clubs/{club}/areas` | `master_data.areas` | verified |
| Master data | `GET /protected/club/{club}/list/individual-field` | `master_data.individual_fields` | verified |
| Master data | `GET /mv365/all_countries` | `master_data.countries` | verified |

## Known, not implemented yet

Grouped by area, with the paths found in the web application. `{club}` paths
are below `/protected/club/{club}` unless they start with `mv365`.

| Area | Examples |
| --- | --- |
| Invitations: user side | `GET /protected/user/invitations`, `POST /protected/user/invitations/accept`, `.../revoke` (invitations the logged-in user received) |
| Members: other edits | `PUT .../members/inline-edit/{id}/{field}` (works for some fields only), `POST /protected/clubMember/document` |
| Members: profile changes | `GET .../updated-members`, `POST mv365 .../members/{id}/updateMember`, `.../compare_data` |
| Members: import | `POST mv365 .../import-upload`, `.../import-finalize`, `GET .../import-info` |
| Lists: column settings | `GET`, `PUT`, `DELETE .../listUserSettings/{list}`, `GET .../columns` |
| Lists: free lists | `GET`, `POST`, `PUT`, `DELETE .../list/free-list-field/{list}`, `.../list/free-list-data/{list}` |
| Roles: rest | `PUT .../auth/club-role/{id}/permissions/update` (bulk), `GET`, `PUT .../auth/club-role/{id}/field-permissions`, `GET .../auth/club-role/permissions/{type}`, `GET .../auth/club-user/permission-actions/allowed` |
| Departments: rest | `POST`, `DELETE mv365 .../areas` (levels), `DELETE .../subareas-clear/{id}`, `.../subareas-clear-functions/{id}`, `.../areas-clear/{id}` |
| Club settings: rest | `PUT .../formsOfAddress`, `POST .../settings/numeration/{kind}`, `.../settings/email`, `.../settings/text-templates`, `PATCH .../clubApplicationSettings`, `.../club-profile-settings` |
| Contributions: billing (out of scope) | `POST .../contribution/{preview,generate,start,finish,retry}`, `PUT .../members/bulk-edit/contributions` |
| Invoices: writing | `POST`, `PUT .../invoice`, `.../invoice/{id}/{close,credit,document}`, `DELETE .../invoice/{id}`, `.../settings/invoiceLayout`, `.../e-invoice/*`, expenses (`.../banking/expense`) |
| Banking: rest | assignments of bookings to invoices (`.../booking/{id}/assignments`), rebooking, initial balance, account setup, `.../chart-of-account/*`, `.../tax/category`; **out of scope:** `.../debit/*`, bank transfers, online banking setup |
| Donations | `GET`, `POST`, `PUT`, `DELETE .../club-donations`, `.../donations/courses` |
| Events: participants and rest | `POST .../events/{id}/participants/{reinvitation,reminder}`, participant responses, attachments, `PUT .../calendar/edit`, `PUT .../event-categories` |
| Mailing: rest | `POST .../items`, `.../sendItems`, `.../send-batch`, `.../resend`, `PATCH .../items/{id}`, `.../items/restore`, `.../letterPreview`, `GET .../items/{id}/letter`, attachments (`.../attachment/upload`) |
| Documents: rest | `POST .../dms/bulk-delete`, `GET .../dms/documents/{id}/metadata`, folder permissions (`PUT .../auth/update-directory-permissions/directories/{id}`), member documents (`POST /protected/clubMember/document`) |
| Reports: background jobs | `GET`, `POST .../async-jobs`, `GET .../async-jobs/{id}/download` (booking journal / DATEV export) |
| Dashboard: rest | `GET .../dashboard/{birthdayStatistics,anniversaryStatistics,onboarding,webinars}` |
| Account: rest | `PATCH /protected/accounts`, `.../signature`, `GET`, `POST .../clubUser/profile` |
| Subscription | `GET .../subscription`, `POST .../subscription/{sync,assign,useClubAccount}` |
