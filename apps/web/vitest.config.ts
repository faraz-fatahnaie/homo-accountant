import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    globals: true,
    coverage: {
      provider: "v8",
      include: [
        "src/lib/{api,auth,format,theme}.tsx",
        "src/lib/{api,auth,format,theme}.ts",
        "src/components/{shell,ui}.tsx",
      ],
      thresholds: {
        statements: 75,
        lines: 75,
        branches: 70,
      },
    },
  },
});
