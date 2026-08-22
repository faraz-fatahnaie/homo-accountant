"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError, authApi, clearLegacyTokens } from "@/lib/api";

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
      await authApi.login(email.trim(), password);
      clearLegacyTokens();
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
      </div>
    </main>
  );
}
