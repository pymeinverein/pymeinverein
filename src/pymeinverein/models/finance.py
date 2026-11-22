"""Models for accounts, bookings, business transactions and statistics."""

from __future__ import annotations

from datetime import datetime

from .base import ApiModel


class BankAccount(ApiModel):
    """A cash box or bank account of the club."""

    id: int
    account_name: str | None = None
    #: ``cash`` for a cash box, ``offlineBankAccount`` for a manually kept
    #: bank account; online accounts have other values.
    account_type: str | None = None
    account_currency: str | None = None
    account_holder: str | None = None
    account_iban: str | None = None
    bic_code: str | None = None
    bank_name: str | None = None
    account_balance: float | None = None
    account_balance_date: datetime | None = None
    #: Balance computed from the bookings.
    calculated_balance: float | None = None
    account_active: bool | None = None
    has_bookings: bool | None = None

    @property
    def is_cash(self) -> bool:
        return self.account_type == "cash"


class Booking(ApiModel):
    """A movement on an account ("Buchung")."""

    id: int
    bank_account_id: int | None = None
    bank_account_name: str | None = None
    booking_date: datetime | None = None
    valuta_date: datetime | None = None
    #: Who paid or was paid.
    booking_contact_name: str | None = None
    purpose_description: str | None = None
    #: Positive for income, negative for expenses.
    booking_amount: float | None = None
    #: Part of the amount not yet matched with invoices or receipts.
    booking_open_amount: float | None = None
    #: ``notAssigned``, ``partlyAssigned`` or ``fullyAssigned``.
    assignment_state: str | None = None
    is_initial_balance: bool | None = None


class BusinessTransaction(ApiModel):
    """An invoice, expense, donation, credit note or cancellation."""

    id: int
    #: Id that is unique across all kinds, e.g. ``INV_22001291``.
    unified_id: str | None = None
    #: ``invoice``, ``expense``, ``donation``, ``credit``, ``contribution``
    #: or ``cancellation``.
    type: str | None = None
    #: ``Open``, ``Paid`` or ``Cancelled``.
    state: str | None = None
    closing_state: str | None = None
    number: str | None = None
    date: datetime | None = None
    receiver: str | None = None
    receiver_id: str | None = None
    total_gross: float | None = None
    payment_open_amount: float | None = None
    payment_paid_amount: float | None = None
    payment_due_date: datetime | None = None
    notes: str | None = None


class MemberStatistics(ApiModel):
    """Member counts for the club as a whole or for one department."""

    name: str
    member_count: int = 0
    active_count: int = 0
    passive_count: int = 0
    contact_count: int = 0
    average_age: float | None = None


class FinanceStatisticsEntry(ApiModel):
    account_name: str
    balance: float = 0
    last_update: datetime | None = None
    #: 0 = account, 1 = open receivables, 2 = upcoming payments.
    type: int | None = None


class FinanceStatistics(ApiModel):
    """Balances shown on the dashboard, with their sum."""

    data: list[FinanceStatisticsEntry] = []
    sum: float = 0


class MonthlyFinance(ApiModel):
    """Income and expenses of one month (``key`` is ``YYYY-MM``)."""

    key: str
    income_sum: float = 0
    expenses_sum: float = 0
