import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
}));

import LoginPage from "./page";

describe("login page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("renders the form with Persian labels", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("ایمیل")).toBeInTheDocument();
    expect(screen.getByLabelText("رمز عبور")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ورود" })).toBeInTheDocument();
  });

  it("shows validation error when fields are empty", () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: "ورود" }));
    expect(screen.getByRole("alert")).toHaveTextContent("ایمیل و رمز عبور الزامی است");
  });

  it("shows server error on 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ error: { code: "invalid_credentials", message: "ایمیل یا رمز عبور نادرست است" } }),
          { status: 401, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText("ایمیل"), { target: { value: "a@example.com" } });
    fireEvent.change(screen.getByLabelText("رمز عبور"), { target: { value: "wrong-pass-123" } });
    fireEvent.click(screen.getByRole("button", { name: "ورود" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("ایمیل یا رمز عبور نادرست است");
  });

  it("stores tokens and navigates on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ access_token: "acc", refresh_token: "ref", token_type: "bearer", expires_in: 1800 }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText("ایمیل"), { target: { value: "a@example.com" } });
    fireEvent.change(screen.getByLabelText("رمز عبور"), { target: { value: "correct-pass-1" } });
    fireEvent.click(screen.getByRole("button", { name: "ورود" }));
    await vi.waitFor(() => {
      expect(window.localStorage.getItem("homo-accountant-access-token")).toBe("acc");
      expect(push).toHaveBeenCalledWith("/dashboard");
    });
  });
});
