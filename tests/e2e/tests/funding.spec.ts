import { expect, test } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

test.describe("funding user journey (real API + DB)", () => {
  test("accountant records an investment and a loan", async ({ page }) => {
    const loginResp = await page.request.post(`${API}/auth/login`, {
      data: { email: "accountant@example.com", password: "acct-homo-1405" },
    });
    expect(loginResp.ok()).toBeTruthy();

    const investor = `سرمایه‌گذار تست ${Date.now()}`;
    const lender = `بانک تست ${Date.now()}`;
    const c1 = await page.request.post(`${API}/contacts`, {
      data: { name: investor, roles: ["investor"] },
    });
    const c2 = await page.request.post(`${API}/contacts`, {
      data: { name: lender, roles: ["lender"] },
    });
    expect(c1.ok() && c2.ok()).toBeTruthy();

    // investment via UI
    await page.goto("/funding/new");
    await expect(page.getByRole("heading", { name: "رویداد تأمین مالی جدید" })).toBeVisible({ timeout: 25_000 });
    await page.locator("#f-type").selectOption("investment");
    await page.locator("#f-contact").selectOption({ label: investor });
    await page.locator("#f-amount").fill("۵۰٬۰۰۰٬۰۰۰"); // Persian digits
    await page.getByRole("button", { name: "ثبت رویداد" }).click();
    await page.waitForURL("**/funding", { timeout: 25_000 });
    await expect(page.getByText(investor)).toBeVisible();
    await expect(page.getByText(/FDG-1405-\d{4}/).first()).toBeVisible();

    // loan (maturity required) via UI
    await page.goto("/funding/new");
    await page.locator("#f-type").selectOption("loan");
    await page.locator("#f-contact").selectOption({ label: lender });
    await page.locator("#f-amount").fill("20000000");
    await page.locator("#f-maturity").fill("1405/12/01");
    await page.getByRole("button", { name: "ثبت رویداد" }).click();
    await page.waitForURL("**/funding", { timeout: 25_000 });
    await expect(page.getByText(lender)).toBeVisible();

    // loan without maturity -> inline error (clear the field first by reloading)
    await page.goto("/funding/new");
    await page.locator("#f-type").selectOption("loan");
    await page.locator("#f-amount").fill("1000000");
    await page.getByRole("button", { name: "ثبت رویداد" }).click();
    await expect(page.getByText("برای وام، تاریخ سررسید الزامی است")).toBeVisible();
  });

  test("viewer can read funding but has no create action", async ({ page }) => {
    const loginResp = await page.request.post(`${API}/auth/login`, {
      data: { email: "viewer@example.com", password: "viewer-homo-1405" },
    });
    expect(loginResp.ok()).toBeTruthy();
    await page.goto("/funding");
    await expect(page.getByRole("heading", { name: "تأمین مالی" })).toBeVisible({ timeout: 25_000 });
    await expect(page.getByRole("link", { name: "+ رویداد تأمین مالی" })).toHaveCount(0);
  });
});
