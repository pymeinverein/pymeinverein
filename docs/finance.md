# Finance and dashboard

`club.finance` reads the club's finances and keeps a cash box.

!!! warning "Deliberately limited"
    The library never starts SEPA direct debits, bank transfers or online
    banking, and it does not create invoices. Those calls move real money or
    produce legally relevant, numbered documents. They are listed as *known,
    not implemented* in [Endpoint coverage](endpoints.md).

## Accounts and bookings

```python
for account in await club.finance.accounts():
    print(account.account_name, account.account_type, account.account_balance)
print(await club.finance.total_balance())

bookings = await club.finance.bookings("Kasse", limit=20)       # newest first
found = await club.finance.bookings("Kasse", search="Getränke")
```

An account is given by id, exact name or `BankAccount`. `account_type` is
`cash` for a cash box and `offlineBankAccount` for a bank account kept by hand.

### Cash box bookings

```python
from datetime import date

booking = await club.finance.create_cash_booking(
    "Kasse", -12.50, on=date.today(), contact_name="Bäckerei", purpose="Brötchen"
)
await club.finance.delete_booking(booking.id)
```

Positive amounts are money received, negative amounts money spent. Bookings can
only be entered in cash boxes; for other accounts the call raises an error
before anything is sent.

## Invoices and other business transactions

```python
unpaid = await club.finance.transactions(type="invoice", state="Open")
for item in unpaid:
    print(item.number, item.receiver, item.payment_open_amount)

details = await club.finance.invoice(unpaid[0].id)      # full data as a dict
```

`transactions()` returns invoices, expenses, donations, credit notes,
contribution invoices and cancellations (`type`), each `Open`, `Paid` or
`Cancelled` (`state`). This part is read-only.

## Dashboard

```python
for row in await club.dashboard.member_statistics():      # club total first, then departments
    print(row.name, row.member_count, row.active_count)

finance = await club.dashboard.finance_statistics()       # balances, receivables, upcoming payments
months = await club.dashboard.finance_comparison()        # income and expenses, last six months
```

## Calls behind the methods

| Method | HTTP call |
| --- | --- |
| `finance.accounts`, `account`, `total_balance` | `GET /protected/club/{club}/banking/account` with `x-api-version: v2` |
| `finance.bookings` | `GET /protected/club/{club}/banking/account/{id}/turnover?offset=..&limit=..` |
| `finance.booking` / `delete_booking` | `GET` / `DELETE /protected/club/{club}/banking/booking/{id}` |
| `finance.create_cash_booking` | `POST /protected/club/{club}/banking/cashjournal/{account}/booking` |
| `finance.transactions` | `GET /protected/club/{club}/businesstransactions` |
| `finance.invoice` | `GET /protected/club/{club}/invoice/{id}` |
| `dashboard.member_statistics` | `GET /protected/club/{club}/dashboard/memberStatistics` |
| `dashboard.finance_statistics` | `GET /protected/club/{club}/dashboard/financeStatistics` |
| `dashboard.finance_comparison` | `GET /protected/club/{club}/dashboard/financeComparison?filter=1` |

All verified against the demo club.
