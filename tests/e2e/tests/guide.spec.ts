import { expect, test, type Page } from "@playwright/test";

const USERS = [
  { label: "مدیر", email: "owner@example.com", password: "owner-homo-1405" },
  { label: "حسابدار", email: "accountant@example.com", password: "acct-homo-1405" },
  { label: "کارمند", email: "staff@example.com", password: "staff-homo-1405" },
  { label: "بیننده", email: "viewer@example.com", password: "viewer-homo-1405" },
] as const;

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test.describe("user guide", () => {
  for (const user of USERS) {
    test(`guide is reachable and renders for ${user.label}`, async ({ page }) => {
      await login(page, user.email, user.password);
      // sidebar nav link exists for every role
      await page.getByRole("link", { name: "راهنمای استفاده" }).click();
      await page.waitForURL("**/guide", { timeout: 15_000 });
      await expect(
        page.getByRole("heading", { name: "راهنمای استفاده از سامانه" }),
      ).toBeVisible();
      // quick start + roles + FAQ sections are present
      // (regexes tolerate ZWNJ (نیمفاصله) differences in Persian strings)
      await expect(page.getByRole("heading", { name: /۱\) شروع سریع/ })).toBeVisible();
      await expect(page.getByRole("heading", { name: /نقش.*دسترسی/ })).toBeVisible();
      await expect(page.getByRole("heading", { name: /۸\) سوالات پرتکرار/ })).toBeVisible();
    });
  }

  test("guide FAQ collapses and expands without JS errors", async ({ page }) => {
    await login(page, "accountant@example.com", "acct-homo-1405");
    await page.goto("/guide");
    const summary = page.getByText(/سند حسابداری چیست\?/);
    await summary.click();
    await expect(page.getByText(/جمع بدهکار همیشه باید با جمع بستانکار برابر باشد/)).toBeVisible();
    // TOC anchors jump to sections
    await page.getByRole("link", { name: /برگشت سند/ }).click();
    await expect(
      page.getByRole("heading", { name: /۵\) مسیر کاربری: برگشت سند/ }),
    ).toBeVisible();
  });
});
