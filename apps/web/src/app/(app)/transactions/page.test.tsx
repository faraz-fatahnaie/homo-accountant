import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { JournalEntryOut } from "@/lib/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  usePathname: () => "/transactions",
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { role: "accountant" },
    loading: false,
    isWriter: true,
    isOwner: false,
    refetch: vi.fn(),
    logout: vi.fn(),
  }),
}));

// Fully mock react-query so each test controls useQuery output.
const queryState: {
  data: JournalEntryOut[] | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} = { data: [], isLoading: false, isError: false, error: null };

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({
    data: queryState.data,
    isLoading: queryState.isLoading,
    isError: queryState.isError,
    error: queryState.error,
    refetch: vi.fn(),
  }),
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

import TransactionsPage from "./page";

describe("transactions page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryState.data = [];
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.error = null;
  });

  it("shows loading state", () => {
    queryState.isLoading = true;
    render(<TransactionsPage />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows empty state when no entries", () => {
    render(<TransactionsPage />);
    expect(screen.getByText("سندی در این دوره یافت نشد")).toBeInTheDocument();
  });

  it("renders posted entries with reference and amount", () => {
    queryState.data = [
      {
        id: 1,
        entry_date: "2026-08-13",
        reference: "J-1405-0001",
        memo: "خرید ورق فولادی",
        status: "posted",
        reversal_of_id: null,
        created_at: "2026-08-13T09:00:00Z",
        posted_at: "2026-08-13T09:01:00Z",
        lines: [
          { id: 1, account_code: "603", account_name: "مواد اولیه و کالا", debit: 48_500_000, credit: 0 },
          { id: 2, account_code: "102", account_name: "بانک — حساب جاری", debit: 0, credit: 48_500_000 },
        ],
      },
    ];
    render(<TransactionsPage />);
    expect(screen.getByText("خرید ورق فولادی")).toBeInTheDocument();
    expect(screen.getByText("J-1405-0001")).toBeInTheDocument();
    expect(screen.getAllByText("۴۸٬۵۰۰٬۰۰۰").length).toBeGreaterThan(0);
    expect(screen.getByText("ثبتشده")).toBeInTheDocument();
  });
});
