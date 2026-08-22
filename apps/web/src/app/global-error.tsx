"use client";

import { useEffect } from "react";
import * as Sentry from "@sentry/nextjs";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="fa" dir="rtl">
      <body className="grid min-h-screen place-items-center bg-bg p-6 text-text">
        <main className="card max-w-md p-6 text-center">
          <h1 className="text-lg font-extrabold">خطای پیش‌بینی‌نشده</h1>
          <p className="mt-2 text-sm text-muted">
            اجرای این بخش با مشکل روبه‌رو شد. دوباره تلاش کنید؛ اگر مشکل ادامه داشت، آن را به مدیر
            سامانه اطلاع دهید.
          </p>
          <button className="btn btn-primary mt-5" type="button" onClick={reset}>
            تلاش دوباره
          </button>
        </main>
      </body>
    </html>
  );
}
