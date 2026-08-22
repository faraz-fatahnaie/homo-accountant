import { expect, test } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

test.describe("bills user journey (real API + DB)", () => {
  test("accountant creates, posts and partially pays a supplier bill", async ({ page, request }) => {
    const loginResp = await request.post(`${API}/auth/login`, {
      data: { email: "accountant@example.com", password: "acct-homo-1405" },
    });
    expect(loginResp.ok()).toBeTruthy();
    const token = (await loginResp.json()).access_token as string;
    await page.addInitScript(
      (access) => {
        window.localStorage.setItem("homo-accountant-access-token", access);
        window.localStorage.setItem("homo-accountant-refresh-token", "seed");
      },
      token,
    );
    const vendor = `تأمین‌کننده تست ${Date.now()}`;
    const memo = `خرید ورق فولادی ${Date.now()}`;

    const v = await request.post(`${API}/contacts`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: vendor, roles: ["vendor"] },
    });
    expect(v.ok()).toBeTruthy();

    // build the bill in the UI
    await page.goto("/bills/new");
    await expect(page.getByRole("heading", { name: "فاکتور خرید جدید" })).toBeVisible({ timeout: 25_000 });
    await page.locator("#b-vendor").selectOption({ label: vendor });
    await page.locator("#b-account").selectOption("603");
    await page.locator("#b-total").fill("۱٬۰۰۰٬۰۰۰"); // Persian digits
    await page.fill("#b-memo", memo);
    // post immediately (default checked)
    await page.getByRole("button", { name: "ایجاد فاکتور خرید" }).click();
    await page.waitForURL("**/bills", { timeout: 25_000 });

    const row = page.getByRole("row").filter({ hasText: memo });
    await expect(row).toContainText(/BIL-1405-\d{4}/);
    await expect(row).toContainText("باز");

    // open the detail and pay partially
    await row.getByRole("link", { name: "مشاهده" }).click();
    await page.waitForURL(/\/bills\/\d+/, { timeout: 20_000 });
    await page.getByLabel("مبلغ پرداخت").fill("400000");
    await page.getByRole("button", { name: "ثبت پرداخت" }).click();
    await expect(page.getByText("جزئی پرداخت‌شده")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("listitem").getByText("۴۰۰٬۰۰۰")).toBeVisible();
  });

  test("viewer can read bills but has no create/post actions", async ({ page, request }) => {
    const loginResp = await request.post(`${API}/auth/login`, {
      data: { email: "viewer@example.com", password: "viewer-homo-1405" },
    });
    const token = (await loginResp.json()).access_token as string;
    await page.addInitScript(
      (access) => {
        window.localStorage.setItem("homo-accountant-access-token", access);
        window.localStorage.setItem("homo-accountant-refresh-token", "seed");
      },
      token,
    );
    await page.goto("/bills");
    await expect(page.getByRole("heading", { name: /فاکتورهای خرید/ })).toBeVisible({ timeout: 25_000 });
    await expect(page.getByRole("link", { name: "+ فاکتور خرید جدید" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "ثبت نهایی" })).toHaveCount(0);
  });
});
