import { describe, expect, it } from "vitest";
import {
  faDigits,
  formatJalali,
  formatJalaliLong,
  formatRials,
  gregorianToJalali,
  jalaliToGregorian,
  parseJalaliInput,
} from "./format";

describe("Persian formatting", () => {
  it("converts digits to Persian", () => {
    expect(faDigits(1405)).toBe("۱۴۰۵");
    expect(faDigits("12")).toBe("۱۲");
  });

  it("groups rials with Persian separators + digits", () => {
    expect(formatRials(48_500_000)).toBe("۴۸٬۵۰۰٬۰۰۰");
    expect(formatRials(0)).toBe("۰");
  });
});

describe("Solar Hijri conversion (mirrors backend anchors)", () => {
  const cases: Array<[string, [number, number, number]]> = [
    ["2026-03-21", [1405, 1, 1]], // Nowruz 1405
    ["2026-08-13", [1405, 5, 22]], // today
    ["2025-03-21", [1404, 1, 1]],
    ["2025-03-20", [1403, 12, 30]], // leap Esfand 1403 (30 days)
    ["2026-03-20", [1404, 12, 29]], // 1404 not leap -> 29
  ];

  for (const [iso, jalali] of cases) {
    it(`2026 anchors: ${iso} -> ${jalali.join("/")}`, () => {
      const [y, m, d] = iso.split("-").map(Number);
      expect(gregorianToJalali(new Date(y as number, (m as number) - 1, d as number))).toEqual(jalali);
    });
  }

  it("round-trips", () => {
    const dates = ["2026-01-01", "2026-08-13", "2025-03-20", "2027-03-21", "2024-12-31"];
    for (const iso of dates) {
      const [y, m, d] = iso.split("-").map(Number);
      const date = new Date(y as number, (m as number) - 1, d as number);
      const [jy, jm, jd] = gregorianToJalali(date);
      const back = jalaliToGregorian(jy, jm, jd);
      expect(back.getFullYear()).toBe(y as number);
      expect(back.getMonth() + 1).toBe(m as number);
      expect(back.getDate()).toBe(d as number);
    }
  });

  it("matches backend formatting", () => {
    expect(formatJalali(new Date(2026, 7, 13))).toBe("۱۴۰۵/۰۵/۲۲");
    expect(formatJalaliLong(new Date(2026, 7, 13))).toBe("۲۲ مرداد ۱۴۰۵");
  });

  it("parses jalali input (ASCII + Persian digits)", () => {
    expect(parseJalaliInput("1405/05/22")?.toISOString().slice(0, 10)).toBe("2026-08-13");
    expect(parseJalaliInput("۱۴۰۵/۰۵/۲۲")?.toISOString().slice(0, 10)).toBe("2026-08-13");
    expect(parseJalaliInput("1405/13/01")).toBeNull();
    expect(parseJalaliInput("1405/12/30")).toBeNull(); // 1405 not leap
    expect(parseJalaliInput("abc")).toBeNull();
  });
});
