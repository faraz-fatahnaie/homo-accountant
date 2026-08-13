"""Solar Hijri (تقویم شمسی) date helpers.

UI dates use the Solar Hijri calendar; canonical storage uses ISO Gregorian
dates and UTC instants. Conversions are delegated to `jdatetime` (the reference
implementation) and covered by round-trip + Tehran timezone-boundary tests.

Note: Iran uses UTC+3:30 year-round (no DST since 2022).
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import jdatetime

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
FA_MONTHS = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]

JalaliDate = tuple[int, int, int]


def fa_digits(value: int | str) -> str:
    return "".join(FA_DIGITS[int(ch)] if ch.isdigit() else ch for ch in str(value))


def gregorian_to_jalali(d: dt.date) -> JalaliDate:
    jd = jdatetime.date.fromgregorian(date=d)
    return (jd.year, jd.month, jd.day)


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> dt.date:
    """Convert a Jalali date to Gregorian; raises ValueError on invalid dates."""
    try:
        j = jdatetime.date(jy, jm, jd)
    except ValueError:
        raise
    gregorian = j.togregorian()
    return dt.date(gregorian.year, gregorian.month, gregorian.day)


def utc_instant_to_jalali(instant: dt.datetime) -> JalaliDate:
    """Map a UTC instant to the Solar Hijri date as seen in Tehran."""
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=dt.UTC)
    local = instant.astimezone(TEHRAN_TZ)
    return gregorian_to_jalali(local.date())


def format_jalali(jalali: JalaliDate, with_month_name: bool = False) -> str:
    jy, jm, jd = jalali
    if with_month_name:
        return f"{fa_digits(jd)} {FA_MONTHS[jm - 1]} {fa_digits(jy)}"
    # Pad in ASCII first, then convert to Persian digits ("۰۵", not "0۵").
    return f"{fa_digits(f'{jy:04d}')}/{fa_digits(f'{jm:02d}')}/{fa_digits(f'{jd:02d}')}"


def entry_period(entry_date: dt.date) -> tuple[int, int]:
    """Return the (jalali_year, jalali_month) period for an entry date."""
    jy, jm, _ = gregorian_to_jalali(entry_date)
    return (jy, jm)
