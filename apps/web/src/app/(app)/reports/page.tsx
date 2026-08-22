import Link from "next/link";
import type { Metadata } from "next";
import { ReconciliationPanel } from "./_hub-client";

export const metadata: Metadata = { title: "گزارش‌های مالی" };

const REPORT_CARDS = [
  {
    href: "/reports/trial-balance",
    title: "تراز آزمایشی",
    desc: "بدهکار و بستانکار هر حساب از دفتر کل؛ جمع دو طرف همواره برابر است.",
  },
  {
    href: "/reports/balance-sheet",
    title: "ترازنامه",
    desc: "دارایی‌ها در برابر بدهی‌ها و حقوق صاحبان سهام (شامل سود دوره).",
  },
  {
    href: "/reports/profit-loss",
    title: "صورت سود و زیان",
    desc: "درآمد و هزینه دوره با تفکیک حساب‌ها و نتیجه خالص.",
  },
  {
    href: "/reports/cash-flow",
    title: "صورت جریان وجوه نقد",
    desc: "روش مستقیم بر مبنای حساب‌های نقد و بانک؛ عملیاتی، تأمین مالی، سرمایه‌گذاری.",
  },
  {
    href: "/reports/general-ledger",
    title: "دفتر کل",
    desc: "گردش یک حساب با مانده تجمعی؛ جزئیات تا سطح سند.",
  },
  {
    href: "/reports/aging",
    title: "سررسید دریافتنی و پرداختنی",
    desc: "تفکیک سن مطالبات و بدهی‌ها (جاری، ۳۰، ۶۰، ۹۰+ روز).",
  },
  {
    href: "/reports/budget",
    title: "بودجه و عملکرد پروژه‌ها",
    desc: "مقایسه بودجه هر پروژه با هزینه‌های ثبت‌شده.",
  },
  {
    href: "/reports/funding",
    title: "خلاصه تأمین مالی",
    desc: "سرمایه، وام، کمک و درآمد با تطبیق سندهای دفتر کل.",
  },
];

export default function ReportsPage() {
  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-extrabold">گزارش‌های مالی</h1>
        <p className="mt-0.5 text-xs text-muted">
          همه ارقام مستقیماً از دفتر کل (سندهای ثبت‌شده) محاسبه می‌شوند — هر گزارش برچسب تطبیق دارد.
        </p>
      </div>

      <ReconciliationPanel />

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {REPORT_CARDS.map((c) => (
          <Link
            key={c.href}
            href={c.href}
            className="card group p-4 transition-colors hover:border-primary"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-extrabold group-hover:text-primary-strong">{c.title}</h2>
              <svg
                viewBox="0 0 24 24"
                className="h-4 w-4 text-muted transition-transform group-hover:-translate-x-0.5"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                aria-hidden="true"
              >
                <path d="M9 18l6-6-6-6" />
              </svg>
            </div>
            <p className="mt-1.5 text-xs leading-5 text-muted">{c.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
