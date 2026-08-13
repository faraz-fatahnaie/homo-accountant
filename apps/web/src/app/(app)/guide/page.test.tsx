import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import GuidePage from "./page";

/** Heading matcher that ignores ZWNJ differences. */
function heading(name: string) {
  return (content: string) => content.replace(/\u200c/g, "") === name.replace(/\u200c/g, "");
}

function textIncludes(snippet: string) {
  return (_: unknown, node: Element | null) =>
    !!node?.textContent && node.textContent.replace(/\u200c/g, "").includes(snippet.replace(/\u200c/g, ""));
}

describe("guide page", () => {
  it("renders the header and table of contents", () => {
    render(<GuidePage />);
    expect(
      screen.getByRole("heading", { name: "راهنمای استفاده از سامانه" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "فهرست مطالب" })).toBeInTheDocument();
  });

  it("covers quick start, roles, journeys, FAQ and roadmap", () => {
    render(<GuidePage />);
    const headings = screen.getAllByRole("heading", { level: 2 });
    const titles = headings.map((h) => (h.textContent ?? "").replace(/\u200c/g, ""));
    for (const expected of [
      "۱) شروع سریع — در پنج قدم",
      "۲) نقشها و دسترسیها",
      "۳) مفاهیم پایه (به زبان ساده)",
      "۴) مسیر کاربری: ثبت یک سند (قدمبهقدم)",
      "۵) مسیر کاربری: برگشت سند (اصلاح اشتباه)",
      "۶) دورههای حسابداری",
      "۷) نکتهها و میانبرها",
      "۸) سوالات پرتکرار",
      "۹) وضعیت امکانات و چه چیزهایی در راه است",
    ]) {
      expect(titles.some((t) => t === expected)).toBe(true);
    }
  });

  it("explains the four roles", () => {
    render(<GuidePage />);
    expect(screen.getByText(heading("مدیر (Owner)"))).toBeInTheDocument();
    expect(screen.getAllByText(heading("حسابدار")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(heading("کارمند")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(heading("بیننده")).length).toBeGreaterThan(0);
  });

  it("explains double-entry in simple words", () => {
    render(<GuidePage />);
    expect(screen.getByText(heading("سند حسابداری چیست؟"))).toBeInTheDocument();
    expect(
      screen.getAllByText(textIncludes("جمع بدهکار همیشه باید با جمع بستانکار برابر باشد")).length,
    ).toBeGreaterThan(0);
  });

  it("lists honest future features", () => {
    render(<GuidePage />);
    expect(screen.getAllByText(textIncludes("گزارشها (تراز، سود و زیان")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(textIncludes("پرسوجوی فارسی امن و خروجی CSV/Excel")).length).toBeGreaterThan(0);
  });
});
