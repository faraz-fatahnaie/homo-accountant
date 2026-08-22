import { expect, test, type Page } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

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
    test(`guide is reachable and renders for ${user.label}`, async ({ page }, testInfo) => {
      await login(page, user.email, user.password);
      // Secondary destinations are intentionally grouped under «More» on mobile.
      if (testInfo.project.name === "mobile") {
        const moreButton = page.getByRole("button", { name: "بیشتر" });
        // Exercise the accessible control path. This also avoids a Chromium/Chrome
        // touch-emulation hit-test mismatch seen only with the local Chrome fallback.
        await moreButton.focus();
        await expect(moreButton).toBeFocused();
        await page.keyboard.press("Enter");
        await expect(moreButton).toHaveAttribute("aria-expanded", "true");
      }
      const guideLink = page.getByRole(
        testInfo.project.name === "mobile" ? "menuitem" : "link",
        { name: "راهنمای استفاده" },
      );
      await expect(guideLink).toBeVisible();
      await guideLink.click();
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
    // seed the session via API to avoid login-flow redirect races on this page
    const loginResp = await page.request.post(`${API}/auth/login`, {
      data: { email: "accountant@example.com", password: "acct-homo-1405" },
    });
    expect(loginResp.ok()).toBeTruthy();
    await page.goto("/guide");
    // NB: the question mark is the Arabic ؟ (U+061F) — never escape it as \?
    // (\? would match ASCII ? and never find the text)
    const summary = page.getByText(/سند حسابداری چیست؟/);
    await expect(summary).toBeVisible({ timeout: 20_000 });
    await summary.click();
    await expect(page.getByText(/جمع بدهکار همیشه باید با جمع بستانکار برابر باشد/)).toBeVisible();
    // TOC anchors jump to sections
    await page.getByRole("link", { name: /برگشت سند/ }).click();
    await expect(
      page.getByRole("heading", { name: /۵\) مسیر کاربری: برگشت سند/ }),
    ).toBeVisible();
  });
});
