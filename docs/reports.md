# Reports

`club.reports` runs the club's reports ("Auswertungen") and downloads them as
files.

```python
from datetime import date
from pathlib import Path

for report in await club.reports.all():
    print(report.id, report.export_types, [field.name for field in report.fields])

pdf = await club.reports.export(
    "report-income-expense", "pdf", date=(date(2026, 1, 1), date(2026, 12, 31))
)
Path("einnahmen-ausgaben-2026.pdf").write_bytes(pdf)

csv = await club.reports.export("report-member-association-a", "csv", cut_off_date=date.today())
```

Reports available in the demo club:

| Id | Content | Formats | Required input |
| --- | --- | --- | --- |
| `report-income-expense` | income and expenses | `excel`, `pdf` | `date` (range) |
| `report-receipts` | receipts | `excel` | `date` (range) |
| `report-member-association-a`, `-b`, `-ab` | member association report ("Verbandsmeldung") | `csv`, `excel`, `xml` | `cut_off_date` |
| `report-booking-journal` | booking journal for the tax adviser | `csv` | `date` (range) - runs as a background job, not supported yet |

How it works:

- `run()` prepares a report on the server and returns a `Report` with a
  process id and the number of rows; `download(report, format)` fetches the
  file. `export()` does both.
- Inputs use the report's field names (`snake_case` works). A date range is a
  pair `(start, end)`.
- Inputs you leave out get the report's default value (for example
  `observationPeriod="monthly"`). The service insists on them even though they
  have defaults.
- A prepared run expires after a while (`report.expired_at`).

## The user profile

```python
profile = await mv.account.profile()
print(profile.first_name, profile.last_name, profile.email)
```

## Calls behind the methods

| Method | HTTP call |
| --- | --- |
| `reports.all`, `get` | `GET /protected/club/{club}/reports` |
| `reports.run` | `POST /protected/club/{club}/reports` |
| `reports.download` | `GET /protected/club/{club}/reports/{processId}/download?output-format=...` |
| `account.profile` | `GET /protected/accounts/profile` |

All verified against the demo club.
