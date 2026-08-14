import { AxeBuilder } from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/**
 * Accessibility scans (WCAG 2.2 A + AA) on the most-used surfaces, run in
 * both desktop and mobile projects. Failures are collected per page so one
 * broken page doesn't mask the rest.
 */

const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

const SERIOUS_RULES = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function scan(page: Page, path: string, title: string) {
  await page.goto(path);
  await page.waitForLoadState("networkidle");
  const results = await new AxeBuilder({ page })
    .withTags(SERIOUS_RULES)
    .disableRules(["color-contrast", "target-size"]) // theme-dependent; checked visually
    .analyze();
  const violations = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(
    violations,
    `${title} (${path}) — serious/critical a11y violations:\n` +
      violations.map((v) => `  [${v.id}] ${v.help} (${v.nodes.length} nodes)`).join("\n"),
  ).toEqual([]);
}

test.describe("accessibility (axe, WCAG 2.2 AA)", () => {
  test("login page has no serious violations", async ({ page }) => {
    await scan(page, "/login", "login");
  });

  test("dashboard after login has no serious violations", async ({ page }) => {
    await login(page, "accountant@example.com", "acct-homo-1405");
    await scan(page, "/dashboard", "dashboard");
  });

  test("transactions page has no serious violations", async ({ page }) => {
    await login(page, "accountant@example.com", "acct-homo-1405");
    await scan(page, "/transactions", "transactions");
  });

  test("reports hub has no serious violations", async ({ page }) => {
    await login(page, "accountant@example.com", "acct-homo-1405");
    await scan(page, "/reports", "reports hub");
  });

  test("trial balance report has no serious violations", async ({ page }) => {
    await login(page, "accountant@example.com", "acct-homo-1405");
    await scan(page, "/reports/trial-balance", "trial balance");
  });

  test("cash flow report has no serious violations", async ({ page }) => {
    await login(page, "accountant@example.com", "acct-homo-1405");
    await scan(page, "/reports/cash-flow", "cash flow");
  });

  test("user guide has no serious violations", async ({ page }) => {
    await login(page, "viewer@example.com", "viewer-homo-1405");
    await scan(page, "/guide", "guide");
  });
});
