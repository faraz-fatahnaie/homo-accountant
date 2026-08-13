"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError, authApi, storeTokens } from "@/lib/api";

const DEMO_USERS = [
  { role: "مدیر", email: "owner@example.com", password: "owner-homo-1405" },
  { role: "حسابدار", email: "accountant@example.com", password: "acct-homo-1405" },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError("ایمیل و رمز عبور الزامی است");
      return;
    }
    setLoading(true);
    try {
      const pair = await authApi.login(email.trim(), password);
      storeTokens(pair.access_token, pair.refresh_token);
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "ارتباط با سرور برقرار نشد؛ دوباره تلاش کنید",
      );
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4" dir="rtl">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-md bg-primary text-2xl font-extrabold text-on-primary">
            آ
          </div>
          <h1 className="text-xl font-extrabold">آریا تجارت</h1>
          <p className="mt-1 text-sm text-muted">سامانه حسابداری — ورود به حساب کاربری</p>
        </div>

        <form onSubmit={onSubmit} noValidate className="card p-6">
          <div className="mb-4">
            <label htmlFor="email" className="label">
              ایمیل
            </label>
            <input
              id="email"
              type="email"
              dir="ltr"
              autoComplete="username"
              className="input"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="mb-4">
            <label htmlFor="password" className="label">
              رمز عبور
            </label>
            <input
              id="password"
              type="password"
              dir="ltr"
              autoComplete="current-password"
              className="input"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error ? (
            <p role="alert" className="error mb-4">
              {error}
            </p>
          ) : null}

          <button type="submit" disabled={loading} className="btn btn-primary w-full justify-center">
            {loading ? "در حال ورود…" : "ورود"}
          </button>
        </form>

        <div className="card mt-4 p-4 text-xs text-muted">
          <p className="mb-2 font-bold text-text">کاربران آزمایشی (فقط محیط توسعه)</p>
          <ul className="space-y-1">
            {DEMO_USERS.map((u) => (
              <li key={u.email} className="flex items-center justify-between gap-2">
                <span>{u.role}</span>
                <button
                  type="button"
                  className="font-mono text-primary-strong underline"
                  onClick={() => {
                    setEmail(u.email);
                    setPassword(u.password);
                    setError(null);
                  }}
                >
                  <span dir="ltr">{u.email}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </main>
  );
}
