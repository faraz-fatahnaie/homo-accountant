import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { InvoiceOut } from "@/lib/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  usePathname: () => "/invoices",
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { role: "accountant" }, loading: false, isWriter: true, isOwner: false, canDraft: true, refetch: vi.fn(), logout: vi.fn() }),
}));

const queryState: { data: InvoiceOut[] | undefined; isLoading: boolean; isError: boolean; error: Error | null } = {
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

import InvoicesPage from "./page";

const base: InvoiceOut = {
  id: 1,
  number: "INV-1405-0001",
  customer_id: 2,
  customer_name: "بازرگانی خلیجفارس",
  project_id: null,
  issue_date: "2026-08-10",
  due_date: "2026-09-10",
  status: "issued",
  notes: null,
  payment_instructions: null,
  total: 6_500_000,
  paid_total: 2_000_000,
  balance: 4_500_000,
  is_overdue: false,
  journal_entry_id: 5,
  created_at: "2026-08-10T09:00:00Z",
  items: [],
  payments: [],
};

describe("invoices page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryState.data = [];
    queryState.isLoading = false;
    queryState.isError = false;
  });

  it("shows loading state", () => {
    queryState.isLoading = true;
    render(<InvoicesPage />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows empty state", () => {
    render(<InvoicesPage />);
    expect(screen.getByText("صورت‌حسابی در این وضعیت یافت نشد.")).toBeInTheDocument();
  });

  it("renders invoice rows with Persian amounts and status", () => {
    queryState.data = [base];
    render(<InvoicesPage />);
    expect(screen.getByText("INV-1405-0001")).toBeInTheDocument();
    expect(screen.getByText("بازرگانی خلیجفارس")).toBeInTheDocument();
    expect(screen.getAllByText("۶٬۵۰۰٬۰۰۰").length).toBeGreaterThan(0);
    // status appears in the row (and as a filter chip)
    expect(screen.getAllByText("صادرشده").length).toBeGreaterThan(0);
  });

  it("marks overdue invoices", () => {
    queryState.data = [{ ...base, is_overdue: true }];
    render(<InvoicesPage />);
    expect(screen.getAllByText("معوق").length).toBeGreaterThan(0);
  });
});
