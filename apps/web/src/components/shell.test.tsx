import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/dashboard" }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { full_name: "کاربر آزمون", role: "accountant" },
    loading: false,
    logout: vi.fn(),
  }),
}));
vi.mock("@/lib/theme", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: vi.fn() }),
}));

import Shell from "./shell";

describe("application shell", () => {
  it("links the top search affordance to the real query builder", () => {
    render(<Shell>محتوا</Shell>);
    expect(screen.getByRole("link", { name: "رفتن به پرس‌وجو و جست‌وجو" })).toHaveAttribute(
      "href",
      "/query-builder",
    );
  });

  it("exposes secondary destinations through the mobile More menu", () => {
    render(<Shell>محتوا</Shell>);
    const more = screen.getByRole("button", { name: "بیشتر" });
    expect(more).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(more);
    expect(more).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menu", { name: "سایر بخش‌ها" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "هزینه‌ها" })).toHaveAttribute(
      "href",
      "/expenses",
    );
  });
});
