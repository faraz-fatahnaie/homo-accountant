import { defineConfig, devices } from "@playwright/test";

/**
 * E2E against the REAL stack (docker compose up): real PostgreSQL, real API,
 * real browser. Core accounting journeys must not be mocked.
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 60_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    ...(process.env.E2E_CHROMIUM_EXECUTABLE
      ? { launchOptions: { executablePath: process.env.E2E_CHROMIUM_EXECUTABLE } }
      : {}),
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: process.env.E2E_DISABLE_VIDEO ? "off" : "retain-on-failure",
    locale: "fa-IR",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 960 } } },
    // Responsive web app: mobile width verified in Chromium with a mobile UA/touch.
    {
      name: "mobile",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
        deviceScaleFactor: 2,
        userAgent:
          "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
      },
    },
  ],
});
