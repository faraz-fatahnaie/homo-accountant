import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider, initialThemeScript, useTheme } from "./theme";

function wrapper({ children }: { children: ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>;
}

describe("theme provider", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false })));
  });

  it("loads and persists a stored theme", async () => {
    window.localStorage.setItem("homo-accountant-theme", "dark");
    const { result } = renderHook(() => useTheme(), { wrapper });
    await waitFor(() => expect(result.current.theme).toBe("dark"));
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });

  it("toggles the active theme", async () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    await waitFor(() => expect(result.current.theme).toBe("light"));
    act(() => result.current.toggleTheme());
    expect(result.current.theme).toBe("dark");
    expect(window.localStorage.getItem("homo-accountant-theme")).toBe("dark");
  });

  it("provides a pre-hydration script to avoid a theme flash", () => {
    expect(initialThemeScript).toContain("data-theme");
    expect(initialThemeScript).toContain("prefers-color-scheme: dark");
  });
});
