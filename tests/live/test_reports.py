"""Live test for reports and the user profile (read-only)."""

from __future__ import annotations

from datetime import date

import pytest

from pymeinverein import MeinVereinClient
from pymeinverein.api.clubs import ClubClient

pytestmark = pytest.mark.live


async def test_profile() -> None:
    async with MeinVereinClient() as mv:
        profile = await mv.account.profile()
        assert profile.email and profile.id


async def test_reports(demo_club: ClubClient) -> None:
    club = demo_club
    ids = {report.id for report in await club.reports.all()}
    assert {"report-income-expense", "report-member-association-a"} <= ids

    year = date.today().year
    report = await club.reports.run(
        "report-income-expense", date=(date(year, 1, 1), date(year, 12, 31))
    )
    assert report.report_process_id
    assert (await club.reports.download(report, "pdf")).startswith(b"%PDF")
    assert (await club.reports.download(report, "excel")).startswith(b"PK")

    csv = await club.reports.export(
        "report-member-association-a", "csv", cut_off_date=date.today()
    )
    assert b";" in csv
