import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard", { timeout: 25_000 });
}

/** Navigate to an authed page; if the app bounces to /login, re-login and retry once. */
async function gotoApp(page: Page, path: string, email: string, password: string) {
  await page.goto(path);
  if (new URL(page.url()).pathname.startsWith("/login")) {
    await login(page, email, password);
    await page.goto(path);
  }
  await page.waitForURL(`**${path}`, { timeout: 25_000 });
}

test.describe("expenses user journey (real API + DB)", () => {
  test("accountant creates a contact and an expense, then posts it", async ({ page }) => {
    await login(page, "accountant@example.com", "acct-homo-1405");
    const contactName = `تأمینکننده تست ${Date.now()}`;
    const desc = `خرید کامپیوتر اداری ${Date.now()}`;

    // create contact
    await gotoApp(page, "/contacts", "accountant@example.com", "acct-homo-1405");
    await page.getByRole("button", { name: "+ طرف حساب جدید" }).click();
    await page.fill("#c-name", contactName);
    await page.fill("#c-phone", "021-12345678");
    await page.getByRole("button", { name: "ایجاد" }).click();
    await expect(page.getByText(contactName)).toBeVisible();

    // create expense
    await gotoApp(page, "/expenses/new", "accountant@example.com", "acct-homo-1405");
    await expect(page.getByRole("heading", { name: "ثبت هزینه جدید" })).toBeVisible();
    await page.fill("#ex-desc", desc);
    await page.fill("#ex-amount", "۵۸٬۵۰۰٬۰۰۰"); // Persian digits + separator
    await page.locator("#ex-account").selectOption("606");
    await page.locator("#ex-contact").selectOption({ label: contactName });
    await page.locator("#ex-pay").selectOption("cash");
    // post immediately
    await page.getByRole("button", { name: "ایجاد هزینه" }).click();
    await page.waitForURL("**/expenses", { timeout: 15_000 });

    // row shows posted + number EXP-...
    const row = page.getByRole("row").filter({ hasText: desc });
    await expect(row).toContainText("ثبتشده");
    await expect(row).toContainText(/EXP-1405-\d{4}/);
    await expect(row).toContainText("۵۸٬۵۰۰٬۰۰۰");
  });

  test("staff can create a draft but cannot post it", async ({ page }) => {
    await login(page, "staff@example.com", "staff-homo-1405");
    const desc = `پیشنویس کارمند ${Date.now()}`;

    await gotoApp(page, "/expenses/new", "staff@example.com", "staff-homo-1405");
    await expect(page.getByRole("heading", { name: "ثبت هزینه جدید" })).toBeVisible();
    await page.fill("#ex-desc", desc);
    await page.fill("#ex-amount", "2500000");
    await page.locator("#ex-account").selectOption("606");
    // leave "post immediately" unchecked (default is checked → uncheck)
    await page.getByRole("checkbox").uncheck();
    await page.getByRole("button", { name: "ایجاد هزینه" }).click();
    await page.waitForURL("**/expenses", { timeout: 15_000 });

    const row = page.getByRole("row").filter({ hasText: desc });
    await expect(row).toContainText("پیشنویس");
    // staff has no post button
    await expect(row.getByRole("button", { name: "ثبت نهایی" })).toHaveCount(0);
  });

  test("viewer can read expenses but sees no create action", async ({ page }) => {
    await login(page, "viewer@example.com", "viewer-homo-1405");
    await gotoApp(page, "/expenses", "viewer@example.com", "viewer-homo-1405");
    await expect(page.getByRole("heading", { name: /هزینه/ })).toBeVisible();
    await expect(page.getByRole("link", { name: "+ هزینه جدید" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "ثبت نهایی" })).toHaveCount(0);
  });
});
