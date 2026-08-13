import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/reports",
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { role: "accountant" },
    loading: false,
    isWriter: true,
    isOwner: false,
    canDraft: true,
    refetch: vi.fn(),
    logout: vi.fn(),
  }),
}));

const queryState: {
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  checks: { key: string; label: string; ok: boolean; detail: string }[];
} = {
  isLoading: false,
  isError: false,
  error: null,
  checks: [],
};

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({
    data: {
      as_of: "2026-08-13",
      checks: queryState.checks,
      all_ok: queryState.checks.every((c) => c.ok),
    },
    isLoading: queryState.isLoading,
    isError: queryState.isError,
    error: queryState.error,
    refetch: vi.fn(),
  }),
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

import ReportsPage from "./page";
import { ReconciliationPanel } from "./_hub-client";

describe("reports hub", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.checks = [
      {
        key: "trial_balance",
        label: "تراز آزمایشی (جمع بدهکار = جمع بستانکار)",
        ok: true,
        detail: "بدهکار 500 / بستانکار 500",
      },
      {
        key: "balance_sheet",
        label: "ترازنامه (داراییها = بدهیها + حقوق صاحبان سهام)",
        ok: false,
        detail: "دارایی 300 / بدهی+سرمایه 200",
      },
    ];
  });

  it("lists all eight report cards with links", () => {
    render(<ReportsPage />);
    expect(screen.getByText("گزارشهای مالی")).toBeInTheDocument();
    for (const title of [
      "تراز آزمایشی",
      "ترازنامه",
      "صورت سود و زیان",
      "صورت جریان وجوه نقد",
      "دفتر کل",
      "سررسید دریافتنی و پرداختنی",
      "بودجه و عملکرد پروژهها",
      "خلاصه تأمین مالی",
    ]) {
      expect(screen.getByText(title)).toBeInTheDocument();
    }
    const tbLink = screen.getByRole("link", { name: /تراز آزمایشی/ });
    expect(tbLink.getAttribute("href")).toBe("/reports/trial-balance");
  });

  it("shows reconciliation checks with ok/fail states", () => {
    render(<ReconciliationPanel />);
    expect(screen.getByText("تطبیق گزارشها با دفتر کل")).toBeInTheDocument();
    expect(screen.getByText("برخی بررسیها ناموفقاند — برای جزئیات به زیر مراجعه کنید")).toBeInTheDocument();
    expect(screen.getByText("تراز آزمایشی (جمع بدهکار = جمع بستانکار)")).toBeInTheDocument();
  });

  it("reports all checks passing when ledger is consistent", () => {
    queryState.checks = queryState.checks.map((c) => ({ ...c, ok: true }));
    render(<ReconciliationPanel />);
    expect(screen.getByText("همه بررسیها موفق — ارقام با دفتر کل منطبقاند")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    queryState.isLoading = true;
    render(<ReconciliationPanel />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
