import type { Config } from "tailwindcss";

/**
 * Tailwind maps to the classic design tokens (see src/styles/tokens.css),
 * the single source of truth. Colors use CSS variables so light/dark themes
 * switch automatically via [data-theme] on <html>.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        text: "var(--text)",
        muted: "var(--muted)",
        border: "var(--border)",
        "border-strong": "var(--border-strong)",
        primary: "var(--primary)",
        "primary-strong": "var(--primary-strong)",
        "on-primary": "var(--on-primary)",
        "primary-soft": "var(--primary-soft)",
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
        "success-soft": "var(--success-soft)",
        "warning-soft": "var(--warning-soft)",
        "danger-soft": "var(--danger-soft)",
        "danger-strong": "var(--danger-strong)",
        "success-strong": "var(--success-strong)",
        "warning-strong": "var(--warning-strong)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
      },
      fontSize: {
        xs: "var(--fs-xs)",
        sm: "var(--fs-sm)",
        base: "var(--fs-base)",
        md: "var(--fs-md)",
        lg: "var(--fs-lg)",
        xl: "var(--fs-xl)",
      },
    },
  },
  plugins: [],
};

export default config;
