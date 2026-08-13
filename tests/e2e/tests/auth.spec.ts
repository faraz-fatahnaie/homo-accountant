import { expect, test, type Page } from "@playwright/test";

const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

const USERS = [
  { role: "مدیر", email: "owner@example.com", password: "owner-homo-1405", label: "مدیر" },
  { role: "حسابدار", email: "accountant@example.com", password: "acct-homo-1405", label: "حسابدار" },
  { role: "کارمند", email: "staff@example.com", password: "staff-homo-1405", label: "کارمند" },
  { role: "بیننده", email: "viewer@example.com", password: "viewer-homo-1405", label: "بیننده" },
] as const;

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

/** The role label lives in the sidebar (desktop) or the topbar chip (mobile). */
async function expectRoleLabelVisible(page: Page, label: string) {
  const width = page.viewportSize()?.width ?? 0;
  const scope = width >= 1024 ? "complementary" : "banner";
  await expect(page.getByRole(scope).getByText(label, { exact: true })).toBeVisible();
}

test.describe("authentication", () => {
  for (const user of USERS) {
    test(`each role can log in and lands on the dashboard (${user.role})`, async ({ page }) => {
      await login(page, user.email, user.password);
      await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible();
      await expectRoleLabelVisible(page, user.label);
    });
  }

  test("wrong password shows a Persian error and stays on login", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#email", "accountant@example.com");
    await page.fill("#password", "wrong-pass-999");
    await page.click('button[type="submit"]');
    await expect(page.getByText("ایمیل یا رمز عبور نادرست است")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("theme toggle switches light/dark and persists", async ({ page }) => {
    await login(page, USERS[1].email, USERS[1].password);
    const html = page.locator("html");
    const initial = await html.getAttribute("data-theme");
    await page.getByRole("button", { name: "حالت تیره" }).click();
    await expect(html).toHaveAttribute("data-theme", "dark");
    await page.reload();
    await expect(html).toHaveAttribute("data-theme", "dark");
    await page.getByRole("button", { name: "حالت روشن" }).click();
    await expect(html).toHaveAttribute("data-theme", initial === "dark" ? "light" : "light");
  });
});

test.describe("RBAC is enforced by the API (direct calls without UI)", () => {
  test("accountant cannot list users (403)", async ({ request }) => {
    const login = await request.post(`${API}/auth/login`, {
      data: { email: "accountant@example.com", password: "acct-homo-1405" },
    });
    expect(login.ok()).toBeTruthy();
    const { access_token } = await login.json();
    const users = await request.get(`${API}/users`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(users.status()).toBe(403);
  });

  test("owner can list users (200)", async ({ request }) => {
    const login = await request.post(`${API}/auth/login`, {
      data: { email: "owner@example.com", password: "owner-homo-1405" },
    });
    const { access_token } = await login.json();
    const users = await request.get(`${API}/users`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(users.status()).toBe(200);
    expect(Array.isArray(await users.json())).toBeTruthy();
  });
});
