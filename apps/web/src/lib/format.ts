/**
 * Persian formatting + Solar Hijri (تقویم شمسی) conversion.
 *
 * Mirrors the backend (apps/api/app/core/jalali.py): same anchors, same
 * algorithm, so the UI and the ledger agree on dates. Covered by round-trip
 * tests with the same known dates as the backend suite.
 */

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
export const FA_MONTHS = [
  "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];

export function faDigits(value: number | string): string {
  return String(value).replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)] ?? d);
}

/** Format an integer with Persian thousands separators + Persian digits. */
export function formatRials(amount: number): string {
  const grouped = Math.trunc(amount)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, "٬");
  return faDigits(grouped);
}

const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";

/**
 * Normalize a user-entered amount: Persian/Arabic digits → ASCII, and strip
 * thousands separators (٬ , _) and spaces. "۴۸٬۵۰۰٬۰۰۰" → "48500000".
 */
export function normalizeAmountInput(value: string): string {
  return value
    .replace(/[۰-۹]/g, (d) => String(FA_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(ARABIC_DIGITS.indexOf(d)))
    .replace(/[٬,\s_]/g, "");
}

/**
 * Parse a user-entered amount into an integer. Accepts Persian or ASCII
 * digits, with or without separators. Returns NaN for invalid input.
 */
export function parseAmount(value: string): number {
  const cleaned = normalizeAmountInput(value);
  if (!/^\d+$/.test(cleaned)) return NaN;
  return Number(cleaned);
}

export function gregorianToJalali(d: Date): [number, number, number] {
  let gy = d.getFullYear();
  const gm = d.getMonth() + 1;
  const gd = d.getDate();
  const gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  let jy = gy > 1600 ? 979 : 0;
  if (gy > 1600) gy -= 1600;
  else gy -= 621;
  const gy2 = gm > 2 ? gy + 1 : gy;
  let days =
    365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) +
    Math.floor((gy2 + 399) / 400) - 80 + gd + (gdm[gm - 1] ?? 0);
  jy += 33 * Math.floor(days / 12053);
  days %= 12053;
  jy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    jy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }
  const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
  const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
  return [jy, jm, jd];
}

const LEAP_OFFSETS = [1, 5, 9, 13, 17, 22, 26, 30];

function isJalaliLeap(jy: number): boolean {
  return LEAP_OFFSETS.includes(((jy % 33) + 33) % 33);
}

/** Days from 1 Farvardin to the 1st of month jm (months 1–6 = 31 days, 7–12 = 30). */
function monthOffset(jm: number): number {
  return jm <= 7 ? (jm - 1) * 31 : 186 + (jm - 7) * 30;
}

/** Gregorian date of 1 Farvardin for jalali year jy (anchored at 1405 → 2026-03-21). */
function nowruz(jy: number): Date {
  const anchorJy = 1405;
  const anchorDate = new Date(2026, 2, 21);
  let daysOffset = 0;
  if (jy > anchorJy) {
    for (let y = anchorJy; y < jy; y += 1) daysOffset += isJalaliLeap(y) ? 366 : 365;
  } else if (jy < anchorJy) {
    for (let y = anchorJy - 1; y >= jy; y -= 1) daysOffset -= isJalaliLeap(y) ? 366 : 365;
  }
  return new Date(anchorDate.getFullYear(), anchorDate.getMonth(), anchorDate.getDate() + daysOffset);
}

export function jalaliToGregorian(jy: number, jm: number, jd: number): Date {
  if (jm < 1 || jm > 12) throw new Error("ماه نامعتبر است");
  const lastDay = jm <= 6 ? 31 : jm <= 11 ? 30 : isJalaliLeap(jy) ? 30 : 29;
  if (jd < 1 || jd > lastDay) throw new Error("روز نامعتبر است");
  const base = nowruz(jy);
  return new Date(base.getFullYear(), base.getMonth(), base.getDate() + monthOffset(jm) + jd - 1);
}

/** Parse "1405/05/22" (ASCII or Persian digits) into a Date (local noon). */
export function parseJalaliInput(input: string): Date | null {
  const normalized = input.replace(/[۰-۹]/g, (d) => String(FA_DIGITS.indexOf(d)));
  const parts = normalized.trim().split(/[/\-،,]/).map((p) => Number(p));
  if (parts.length !== 3 || parts.some((p) => !Number.isInteger(p))) return null;
  const [jy, jm, jd] = parts;
  try {
    return jalaliToGregorian(jy as number, jm as number, jd as number);
  } catch {
    return null;
  }
}

export function formatJalali(d: Date): string {
  const [jy, jm, jd] = gregorianToJalali(d);
  return `${faDigits(jy)}/${faDigits(String(jm).padStart(2, "0"))}/${faDigits(String(jd).padStart(2, "0"))}`;
}

export function formatJalaliLong(d: Date): string {
  const [jy, jm, jd] = gregorianToJalali(d);
  return `${faDigits(jd)} ${FA_MONTHS[jm - 1] ?? ""} ${faDigits(jy)}`;
}

export function todayJalali(): [number, number, number] {
  return gregorianToJalali(new Date());
}
