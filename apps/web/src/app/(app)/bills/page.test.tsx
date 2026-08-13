import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { BillOut } from "@/lib/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  usePathname: () => "/bills",
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { role: "accountant" }, loading: false, isWriter: true, isOwner: false, canDraft: true, refetch: vi.fn(), logout: vi.fn() }),
}));

const queryState: { data: BillOut[] | undefined; isLoading: boolean; isError: boolean; error: Error | null } = {
  data: [],
  isLoading: false,
  isError: false,
  error: null,
};
vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: queryState.data, isLoading: queryState.isLoading, isError: queryState.isError, error: queryState.error, refetch: vi.fn() }),
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

import BillsPage from "./page";

const base: BillOut = {
  id: 1,
  number: "BIL-1405-0001",
  vendor_id: 2,
  vendor_name: "فولاد البرز",
  project_id: null,
  account_code: "603",
  account_name: "مواد اولیه و کالا",
  issue_date: "2026-08-10",
  due_date: "2026-09-10",
  bill_number: "F-88712",
  status: "open",
  memo: "خرید ورق فولادی ۲ تن",
  total: 48_500_000,
  paid_total: 20_000_000,
  balance: 28_500_000,
  is_overdue: false,
  journal_entry_id: 5,
  created_at: "2026-08-10T09:00:00Z",
  payments: [],
};

describe("bills page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryState.data = [];
    queryState.isLoading = false;
    queryState.isError = false;
  });

  it("shows loading state", () => {
    queryState.isLoading = true;
    render(<BillsPage />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows empty state", () => {
    render(<BillsPage />);
    expect(screen.getByText("فاکتور خریدی در این وضعیت یافت نشد.")).toBeInTheDocument();
  });

  it("renders bill rows with Persian amounts and status", () => {
    queryState.data = [base];
    render(<BillsPage />);
    expect(screen.getByText("BIL-1405-0001")).toBeInTheDocument();
    expect(screen.getByText("فولاد البرز")).toBeInTheDocument();
    expect(screen.getAllByText("۴۸٬۵۰۰٬۰۰۰").length).toBeGreaterThan(0);
    expect(screen.getAllByText("باز").length).toBeGreaterThan(0);
  });

  it("marks overdue bills", () => {
    queryState.data = [{ ...base, is_overdue: true }];
    render(<BillsPage />);
    expect(screen.getAllByText("معوق").length).toBeGreaterThan(0);
  });
});
