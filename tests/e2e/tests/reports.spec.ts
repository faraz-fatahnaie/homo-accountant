import { expect, test, type Page } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

async function loginAs(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function seedLedger(request: import("@playwright/test").APIRequestContext) {
  /** Post the canonical scenario so reports have real figures to show. */
  const login = await request.post(`${API}/auth/login`, {
    data: { email: "accountant@example.com", password: "acct-homo-1405" },
  });
  const token = (await login.json()).access_token as string;
  const H = { Authorization: `Bearer ${token}` };

  await request.post(`${API}/journal-entries`, {
    headers: H,
    data: {
      entry_date: "2026-08-01",
      memo: "سرمایهگذاری مالک (گزارش)",
      lines: [
        { account_code: "102", debit: 400_000_000, credit: 0 },
        { account_code: "301", debit: 0, credit: 400_000_000 },
      ],
    },
  });
  const entries = (await (await request.get(`${API}/journal-entries`, { headers: H })).json()) as {
    id: number;
    status: string;
  }[];
  for (const e of entries.filter((e) => e.status === "draft")) {
    await request.post(`${API}/journal-entries/${e.id}/post`, { headers: H });
  }
  await request.post(`${API}/expenses`, {
    headers: H,
    data: {
      entry_date: "2026-08-13",
      account_code: "603",
      amount: 48_500_000,
      payment_method: "bank",
      description: "هزینه مواد اولیه (گزارش)",
    },
  });
  const expenses = (await (await request.get(`${API}/expenses`, { headers: H })).json()) as {
    id: number;
    status: string;
  }[];
  for (const e of expenses.filter((e) => e.status === "draft")) {
    await request.post(`${API}/expenses/${e.id}/post`, { headers: H });
  }
}

test.describe("reports journeys (slice 8, verified in slice 9)", () => {
  test.beforeAll(async ({ request }) => {
    await seedLedger(request);
  });

  test("dashboard KPIs are real ledger figures and link to reports", async ({ page }) => {
    await loginAs(page, "accountant@example.com", "acct-homo-1405");
    await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible();
    // KPI cards derived from the ledger (not sample values)
    await expect(page.getByText("موجودی نقد و بانک")).toBeVisible();
    await expect(page.getByText("نتیجه خالص")).toBeVisible();
    // drill through the cash/bank KPI to the cash-flow report
    await page.getByRole("link", { name: /موجودی نقد و بانک/ }).click();
    await page.waitForURL("**/reports/cash-flow", { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "صورت جریان وجوه نقد" })).toBeVisible();
  });

  test("trial balance renders and reconciles", async ({ page }) => {
    await loginAs(page, "accountant@example.com", "acct-homo-1405");
    await page.goto("/reports/trial-balance");
    await expect(page.getByRole("heading", { name: "تراز آزمایشی" })).toBeVisible();
    // posted expense + investment must appear
    await expect(page.getByText("سرمایه مالک")).toBeVisible();
    await expect(page.getByText("مواد اولیه و کالا")).toBeVisible();
    await expect(page.getByText("جمع بدهکار", { exact: true })).toBeVisible();
    await expect(page.getByText("جمع بستانکار", { exact: true })).toBeVisible();
    // balanced badge (reconciled == true)
    await expect(page.getByText("تراز است")).toBeVisible();
  });

  test("balance sheet drill-down opens the general ledger for an account", async ({ page }) => {
    await loginAs(page, "accountant@example.com", "acct-homo-1405");
    await page.goto("/reports/balance-sheet");
    await expect(page.getByRole("heading", { name: "ترازنامه" })).toBeVisible();
    // assets section with bank
    await expect(page.getByText("بانک — حساب جاری")).toBeVisible();
    // drill into the bank account's GL
    await page.getByRole("link", { name: /بانک — حساب جاری/ }).click();
    await page.waitForURL("**/reports/general-ledger?account_code=102", { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "دفتر کل" })).toBeVisible();
    // running-balance rows rendered (investment memo)
    await expect(page.getByText("سرمایهگذاری مالک (گزارش)").first()).toBeVisible();
  });

  test("aging report reconciles receivable/payable to the ledger", async ({ page }) => {
    await loginAs(page, "accountant@example.com", "acct-homo-1405");
    await page.goto("/reports/aging");
    await expect(page.getByRole("heading", { name: "سررسید دریافتنی و پرداختنی" })).toBeVisible();
    await expect(page.getByText(/تطبیق شد/).first()).toBeVisible();
    // bucket chips exist
    await expect(page.getByText(/بیش از ۹۰ روز/).first()).toBeVisible();
  });

  test("reports hub shows all checks passing", async ({ page }) => {
    await loginAs(page, "owner@example.com", "owner-homo-1405");
    await page.goto("/reports");
    await expect(page.getByRole("heading", { name: "گزارشهای مالی" })).toBeVisible();
    await expect(page.getByText(/همه بررسیها موفق/)).toBeVisible();
    // each report card links somewhere
    await expect(page.getByRole("link", { name: /تراز آزمایشی/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /صورت سود و زیان/ })).toBeVisible();
  });
});
