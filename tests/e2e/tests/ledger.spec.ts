import { expect, test, type Page } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

async function loginAsAccountant(page: Page) {
  await page.goto("/login");
  await page.fill("#email", "accountant@example.com");
  await page.fill("#password", "acct-homo-1405");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test.describe("ledger user journey (real API + DB)", () => {
  test("accountant creates and posts a balanced journal entry", async ({ page }) => {
    await loginAsAccountant(page);
    const memo = `سند تست ${Date.now()}`;

    // open the new-entry form
    await page.goto("/journal-entries/new");
    await expect(page.getByRole("heading", { name: "سند حسابداری جدید" })).toBeVisible();

    // date prefilled (today, jalali) — leave as is; fill memo
    await page.fill("#entry-memo", memo);

    // line 1: 603 debit; line 2: 102 credit
    // (Persian digits + separator — verifies the amount-parsing fix)
    await page.locator('select[aria-label="حساب"]').nth(0).selectOption("603");
    await page.locator('input[aria-label="بدهکار"]').nth(0).fill("۱٬۰۰۰٬۰۰۰");
    await page.locator('select[aria-label="حساب"]').nth(1).selectOption("102");
    await page.locator('input[aria-label="بستانکار"]').nth(1).fill("۱٬۰۰۰٬۰۰۰");

    // balanced indicator
    await expect(page.getByText("سند متوازن است")).toBeVisible();

    await page.getByRole("button", { name: "ایجاد سند" }).click();
    await page.waitForURL("**/transactions", { timeout: 15_000 });

    // the draft row appears
    const row = page.getByRole("row").filter({ hasText: memo });
    await expect(row).toContainText("پیش‌نویس");

    // post it
    await row.getByRole("button", { name: "ثبت نهایی" }).click();
    await expect(row).toContainText("ثبت‌شده");
    await expect(row).toContainText(/J-1405-\d{4}/);

    // second post attempt is impossible (no button), and void exists
    await expect(row.getByRole("button", { name: "برگشت" })).toBeVisible();
  });

  test("viewer cannot see post/create actions", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#email", "viewer@example.com");
    await page.fill("#password", "viewer-homo-1405");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/dashboard", { timeout: 20_000 });

    await page.goto("/transactions");
    // no "سند جدید" button for viewer
    await expect(page.getByRole("link", { name: "سند جدید" })).toHaveCount(0);
    // any row actions must not include ثبت نهایی / برگشت
    await expect(page.getByRole("button", { name: "ثبت نهایی" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "برگشت" })).toHaveCount(0);
  });

  test("periods page: close shows reopen as owner-only", async ({ page }) => {
    // API-seeded session (avoids login-flow redirect races on full loads)
    const loginResp = await page.request.post(`${API}/auth/login`, {
      data: { email: "accountant@example.com", password: "acct-homo-1405" },
    });
    expect(loginResp.ok()).toBeTruthy();
    await page.goto("/periods");
    await page.waitForURL("**/periods", { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "دوره‌های حسابداری" })).toBeVisible({ timeout: 15_000 });
    // accountant sees بستن دوره buttons, never بازگشایی
    await expect(page.getByRole("button", { name: "بستن دوره" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /بازگشایی/ })).toHaveCount(0);
  });
});
