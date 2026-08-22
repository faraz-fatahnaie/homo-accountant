import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { FundingEventOut } from "@/lib/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  usePathname: () => "/funding",
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { role: "accountant" }, loading: false, isWriter: true, isOwner: false, canDraft: true, refetch: vi.fn(), logout: vi.fn() }),
}));

const queryState: {
  data: FundingEventOut[] | undefined;
  mappings: { funding_type: string; account_code: string }[];
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} = { data: [], mappings: [], isLoading: false, isError: false, error: null };

vi.mock("@tanstack/react-query", () => ({
  useQuery: (opts: { queryKey: string[] }) => {
    if (opts.queryKey[0] === "funding-mappings") return { data: queryState.mappings, isLoading: false, isError: false, error: null, refetch: vi.fn() };
    return { data: queryState.data, isLoading: queryState.isLoading, isError: queryState.isError, error: queryState.error, refetch: vi.fn() };
  },
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

import FundingPage from "./page";

const base: FundingEventOut = {
  id: 1,
  number: "FDG-1405-0001",
  funding_type: "investment",
  contact_id: 2,
  contact_name: "شرکت سرمایه‌گذاری امید",
  project_id: null,
  event_date: "2026-08-10",
  amount: 100_000_000,
  method: "bank",
  agreement_ref: "قرارداد ۱۴۰۵-۰۱",
  maturity_date: null,
  notes: null,
  status: "posted",
  journal_entry_id: 5,
  created_at: "2026-08-10T09:00:00Z",
};

describe("funding page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryState.data = [];
    queryState.mappings = [];
    queryState.isLoading = false;
    queryState.isError = false;
  });

  it("shows loading state", () => {
    queryState.isLoading = true;
    render(<FundingPage />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows empty state", () => {
    render(<FundingPage />);
    expect(screen.getByText("هنوز رویداد تأمین مالی ثبت نشده است.")).toBeInTheDocument();
  });

  it("renders funding rows with Persian amounts and type", () => {
    queryState.data = [base];
    render(<FundingPage />);
    expect(screen.getByText("FDG-1405-0001")).toBeInTheDocument();
    expect(screen.getByText("شرکت سرمایه‌گذاری امید")).toBeInTheDocument();
    expect(screen.getAllByText("۱۰۰٬۰۰۰٬۰۰۰").length).toBeGreaterThan(0);
    expect(screen.getAllByText("سرمایه‌گذاری").length).toBeGreaterThan(0);
  });

  it("shows mapping summary", () => {
    queryState.mappings = [
      { funding_type: "investment", account_code: "301" },
      { funding_type: "loan", account_code: "205" },
    ];
    render(<FundingPage />);
    expect(screen.getByText("نگاشت حساب‌ها:")).toBeInTheDocument();
  });
});
