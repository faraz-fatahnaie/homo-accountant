import { expect, test } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

test.describe("query builder user journey (real API + DB)", () => {
  test("accountant runs a template and exports CSV", async ({ page, request }) => {
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

    // seed a customer + invoice via API so the query has data
    const c = await request.post(`${API}/contacts`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: "مشتری پرسوجو", roles: ["customer"] },
    });
    const cid = (await c.json()).id as number;
    await request.post(`${API}/invoices`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        customer_id: cid,
        issue_date: "2026-08-01",
        due_date: "2026-09-01",
        items: [{ description: "کالا", quantity: 1, unit_price: 6500000 }],
      },
    });

    await page.goto("/query-builder");
    await expect(page.getByRole("heading", { name: "پرسوجو و جستجو" })).toBeVisible({ timeout: 25_000 });

    // apply the overdue template, then run
    await page.getByRole("button", { name: "فاکتورهای فروش معوق" }).click();
    await page.getByRole("button", { name: "اجرای پرسوجو" }).click();
    await expect(page.getByText("خلاصه:")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/ردیف/)).toBeVisible({ timeout: 20_000 });

    // export CSV (download event) — scroll into view + force on mobile
    const csvBtn = page.getByRole("button", { name: "خروجی CSV" });
    await csvBtn.scrollIntoViewIfNeeded();
    const downloadPromise = page.waitForEvent("download", { timeout: 40_000 });
    await csvBtn.click({ force: true });
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.csv$/);
  });

  test("viewer can open the query builder (read-only)", async ({ page, request }) => {
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
    await page.goto("/query-builder");
    await expect(page.getByRole("heading", { name: "پرسوجو و جستجو" })).toBeVisible({ timeout: 25_000 });
    await expect(page.getByRole("button", { name: "اجرای پرسوجو" })).toBeVisible();
  });
});
