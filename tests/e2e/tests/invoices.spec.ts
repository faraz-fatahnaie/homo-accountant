import { expect, test } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

/** API-login and pre-seed the browser session (avoids redirect races on full loads). */
test.describe("invoices user journey (real API + DB)", () => {
  test("accountant creates, issues, partially pays and downloads PDF", async ({ page }) => {
    const loginResp = await page.request.post(`${API}/auth/login`, {
      data: { email: "accountant@example.com", password: "acct-homo-1405" },
    });
    expect(loginResp.ok()).toBeTruthy();
    const customer = `مشتری تست ${Date.now()}`;
    const desc = `دستگاه تست ${Date.now()}`;

    // create the customer via API (the UI contact flow is covered elsewhere)
    const c = await page.request.post(`${API}/contacts`, {
      data: { name: customer, roles: ["customer"] },
    });
    expect(c.ok()).toBeTruthy();

    // build the invoice in the UI
    await page.goto("/invoices/new");
    await expect(page.getByRole("heading", { name: "صورت‌حساب جدید" })).toBeVisible({ timeout: 20_000 });
    await page.locator("#inv-customer").selectOption({ label: customer });
    const descInput = page.getByPlaceholder("شرح کالا / خدمت");
    await descInput.fill(desc);
    await page.locator('input[inputmode="numeric"]').nth(1).fill("1000000"); // unit price
    await page.getByRole("button", { name: "ایجاد صورت‌حساب" }).click();
    await page.waitForURL(/\/invoices\/\d+/, { timeout: 20_000 });

    // draft detail — issue it (dev-mode first compile of the route can stall the
    // first load; reload once if the page is still showing the loading block)
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const issueBtn = page.getByRole("button", { name: "صدور صورت‌حساب" });
      if (await issueBtn.count()) {
        await expect(issueBtn).toBeVisible({ timeout: 20_000 });
        break;
      }
      await page.waitForTimeout(2000);
      await page.reload().catch(() => undefined);
    }
    await expect(page.getByRole("button", { name: "صدور صورت‌حساب" })).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "صدور صورت‌حساب" }).click();
    await expect(page.getByText("صادرشده")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/INV-1405-\d{4}/)).toBeVisible();

    // partial payment
    await page.getByLabel("مبلغ پرداخت").fill("400000");
    await page.getByRole("button", { name: "ثبت پرداخت" }).click();
    await expect(page.getByText("جزئی پرداخت‌شده")).toBeVisible({ timeout: 15_000 });
    // payment appears in the payments list item
    await expect(page.getByRole("listitem").getByText("۴۰۰٬۰۰۰")).toBeVisible();

    // PDF download (authenticated fetch → blob → download)
    const downloadPromise = page.waitForEvent("download", { timeout: 30_000 });
    await page.getByRole("button", { name: "دانلود PDF" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  });

  test("viewer can read invoices but has no create/issue actions", async ({ page }) => {
    const vLogin = await page.request.post(`${API}/auth/login`, { data: { email: "viewer@example.com", password: "viewer-homo-1405" } });
    expect(vLogin.ok()).toBeTruthy();
    await page.goto("/invoices");
    await expect(page.getByRole("heading", { name: /صورت‌حساب/ })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("link", { name: "+ صورت‌حساب جدید" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "صدور" })).toHaveCount(0);
  });
});
