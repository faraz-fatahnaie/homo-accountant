import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { QueryDataset, QueryResult, QueryTemplate } from "@/lib/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  usePathname: () => "/query-builder",
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { role: "accountant" }, loading: false, isWriter: true, isOwner: false, canDraft: true, refetch: vi.fn(), logout: vi.fn() }),
}));

const datasets: QueryDataset[] = [
  {
    id: "invoices",
    label: "صورت‌حساب‌های فروش",
    columns: [
      { field: "number", label: "شماره", type: "string" },
      { field: "customer_name", label: "مشتری", type: "string" },
      { field: "total", label: "مبلغ", type: "amount", amount: true },
      { field: "status", label: "وضعیت", type: "enum", enum_options: ["issued"] },
    ],
  },
];
const templates: QueryTemplate[] = [
  { id: "invoices_overdue", name: "فاکتورهای فروش معوق", description: "معوق", ast: { dataset: "invoices", fields: ["number"] } },
];

const queryState: {
  datasets: QueryDataset[];
  templates: QueryTemplate[];
  saved: unknown[];
  result: QueryResult | null;
} = { datasets, templates, saved: [], result: null };

vi.mock("@tanstack/react-query", () => ({
  useQuery: (opts: { queryKey: string[] }) => {
    const key = opts.queryKey[0];
    if (key === "qb-datasets") return { data: queryState.datasets, isLoading: false, isError: false, error: null, refetch: vi.fn() };
    if (key === "qb-templates") return { data: queryState.templates, isLoading: false, isError: false, error: null, refetch: vi.fn() };
    if (key === "qb-saved") return { data: queryState.saved, isLoading: false, isError: false, error: null, refetch: vi.fn() };
    return { data: undefined, isLoading: false, isError: false, error: null, refetch: vi.fn() };
  },
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

import QueryBuilderPage from "./page";

describe("query builder page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryState.saved = [];
    queryState.result = null;
  });

  it("renders the builder with dataset + templates", () => {
    render(<QueryBuilderPage />);
    expect(screen.getByRole("heading", { name: "پرس‌وجو و جست‌وجو" })).toBeInTheDocument();
    expect(screen.getByText("قالب‌های آماده:")).toBeInTheDocument();
    expect(screen.getByText("فاکتورهای فروش معوق")).toBeInTheDocument();
    expect(screen.getByText("صورت‌حساب‌های فروش")).toBeInTheDocument();
  });

  it("shows a prompt before running", () => {
    render(<QueryBuilderPage />);
    expect(
      screen.getByText("یک قالب آماده انتخاب کنید یا پرس‌وجوی خود را بسازید و «اجرای پرس‌وجو» را بزنید."),
    ).toBeInTheDocument();
  });

  it("offers localized choices for enum filters", () => {
    render(<QueryBuilderPage />);
    const valueSelect = screen.getByRole("combobox", { name: "مقدار شرط" });
    expect(valueSelect).toHaveValue("issued");
    expect(screen.getByRole("option", { name: "صادرشده" })).toBeInTheDocument();
  });
});
