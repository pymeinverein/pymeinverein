"""Reports and the user profile against the mock server."""

from __future__ import annotations

from datetime import date

import pytest

from pymeinverein import BadRequestError, LookupFailedError, MeinVereinClient
from pymeinverein.api.clubs import ClubClient
from pymeinverein.testing import DEMO_EMAIL, MockServer


async def test_profile(client: MeinVereinClient) -> None:
    profile = await client.account.profile()
    assert (profile.email, profile.first_name, profile.last_name) == (
        DEMO_EMAIL,
        "Demo",
        "User",
    )


async def test_report_definitions(club: ClubClient) -> None:
    reports = await club.reports.all()
    assert [r.id for r in reports] == [
        "report-income-expense",
        "report-member-association-a",
    ]
    income = await club.reports.get("report-income-expense")
    assert income.export_types == ["excel", "pdf"]
    assert [(f.name, f.required, f.default_value) for f in income.fields] == [
        ("date", True, None),
        ("observationPeriod", False, "monthly"),
        ("layoutStyle", False, "tabular"),
    ]
    with pytest.raises(LookupFailedError, match="report-income-expense"):
        await club.reports.get("report-nope")


async def test_run_fills_defaults(server: MockServer, club: ClubClient) -> None:
    report = await club.reports.run(
        "report-income-expense", date=(date(2026, 1, 1), date(2026, 12, 31))
    )
    assert report.report_id == "report-income-expense"
    assert report.row_count == 10 and report.expired_at is not None
    pdf = await club.reports.download(report, "pdf")
    assert pdf == b"report-income-expense as pdf"
    # Without a format the report's default is used.
    assert await club.reports.download(report) == b"report-income-expense as excel"


async def test_export_in_one_step(club: ClubClient) -> None:
    csv = await club.reports.export(
        "report-member-association-a", "csv", cut_off_date=date(2026, 11, 10)
    )
    assert csv == b"report-member-association-a as csv"


async def test_required_inputs(club: ClubClient) -> None:
    with pytest.raises(BadRequestError, match="cutOffDate: REQUIRED"):
        await club.reports.run("report-member-association-a")
    report = await club.reports.run(
        "report-member-association-a", cut_off_date=date(2026, 11, 10)
    )
    with pytest.raises(BadRequestError):
        await club.reports.download(report, "pdf")  # not offered by this report
