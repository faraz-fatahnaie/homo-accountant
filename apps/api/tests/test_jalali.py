"""Unit tests: Solar Hijri calendar helpers (round-trips + Tehran boundary)."""

from __future__ import annotations

import datetime as dt

import pytest

from app.core.jalali import (
    entry_period,
    fa_digits,
    format_jalali,
    gregorian_to_jalali,
    jalali_to_gregorian,
    utc_instant_to_jalali,
)


class TestKnownDates:
    @pytest.mark.parametrize(
        "greg, jalali",
        [
            (dt.date(2026, 3, 21), (1405, 1, 1)),  # Nowruz 1405
            (dt.date(2026, 8, 13), (1405, 5, 22)),  # today
            (dt.date(2025, 3, 21), (1404, 1, 1)),
            (dt.date(2025, 3, 20), (1403, 12, 30)),  # leap Esfand 1403 has 30 days
            (dt.date(2026, 3, 20), (1404, 12, 29)),  # 1404 not leap -> 29 days
        ],
    )
    def test_gregorian_to_jalali(self, greg: dt.date, jalali: tuple[int, int, int]) -> None:
        assert gregorian_to_jalali(greg) == jalali

    def test_jalali_to_gregorian(self) -> None:
        assert jalali_to_gregorian(1405, 1, 1) == dt.date(2026, 3, 21)
        assert jalali_to_gregorian(1405, 5, 22) == dt.date(2026, 8, 13)

    def test_round_trip(self) -> None:
        for d in [
            dt.date(2026, 1, 1),
            dt.date(2026, 8, 13),
            dt.date(2025, 3, 20),
            dt.date(2027, 3, 21),
            dt.date(2024, 12, 31),
        ]:
            assert jalali_to_gregorian(*gregorian_to_jalali(d)) == d

    def test_invalid_date_rejected(self) -> None:
        with pytest.raises(ValueError):
            jalali_to_gregorian(1405, 12, 30)  # 1405 is not leap


class TestTehranBoundary:
    """UTC instants must map to the Tehran-local Solar Hijri date."""

    def test_midnight_tehran_boundary(self) -> None:
        # Tehran is UTC+3:30 year-round. 2026-08-13T20:30Z == 2026-08-14 00:00 Tehran.
        before = dt.datetime(2026, 8, 13, 20, 29, 59, tzinfo=dt.UTC)
        at = dt.datetime(2026, 8, 13, 20, 30, 0, tzinfo=dt.UTC)
        assert utc_instant_to_jalali(before) == (1405, 5, 22)
        assert utc_instant_to_jalali(at) == (1405, 5, 23)

    def test_naive_input_treated_as_utc(self) -> None:
        naive = dt.datetime(2026, 8, 13, 12, 0, 0)
        assert utc_instant_to_jalali(naive) == (1405, 5, 22)


class TestFormatting:
    def test_fa_digits(self) -> None:
        assert fa_digits(1405) == "۱۴۰۵"
        assert fa_digits("12") == "۱۲"

    def test_format_jalali(self) -> None:
        assert format_jalali((1405, 5, 22)) == "۱۴۰۵/۰۵/۲۲"
        assert format_jalali((1405, 5, 22), with_month_name=True) == "۲۲ مرداد ۱۴۰۵"

    def test_entry_period(self) -> None:
        assert entry_period(dt.date(2026, 8, 13)) == (1405, 5)
        assert entry_period(dt.date(2026, 3, 21)) == (1405, 1)
