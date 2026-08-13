import type { Metadata } from "next";

export const metadata: Metadata = { title: "داشبورد" };

const KPIS = [
  { label: "موجودی نقد و بانک", value: "۱۸۴٬۶۲۰٬۰۰۰", delta: "+۴٬۲۱۰٬۰۰۰ نسبت به تیر", up: true },
  { label: "درآمد دوره", value: "۹۶٬۸۵۰٬۰۰۰", delta: "۱۲٪ نسبت به سه ماه قبل", up: true },
  { label: "هزینههای دوره", value: "۶۱٬۳۴۰٬۰۰۰", delta: "۳٪ کاهش نسبت به سه ماه قبل", up: true },
  { label: "نتیجه خالص", value: "۳۵٬۵۱۰٬۰۰۰", delta: "سودآور", up: true },
];

export default function DashboardPage() {
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold">داشبورد</h1>
          <p className="mt-0.5 text-xs text-muted">نمای کلی مالی — ۱ فروردین تا ۲۲ مرداد ۱۴۰۵</p>
        </div>
        <button className="btn btn-primary" disabled title="در نسخههای بعدی">
          + ثبت هزینه جدید
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {KPIS.map((kpi) => (
          <div key={kpi.label} className="card relative overflow-hidden p-4">
            <span className="absolute inset-y-3 right-0 w-0.5 rounded bg-primary" aria-hidden="true" />
            <div className="text-xs font-semibold text-muted">{kpi.label}</div>
            <div className="mt-2 text-base font-extrabold tabular-nums">
              {kpi.value}
              <span className="mr-1 text-[11px] font-semibold text-muted">ریال</span>
            </div>
            <div className="mt-2 inline-flex items-center gap-1 rounded-full border border-border bg-success-soft px-2 py-0.5 text-[11px] font-bold text-success-strong">
              {kpi.delta}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <section className="card">
          <div className="card-head">
            <h2 className="text-sm font-extrabold">نیاز به توجه</h2>
          </div>
          <div className="divide-y divide-dashed divide-border px-4 py-2 text-sm">
            <div className="flex items-center justify-between gap-2 py-2.5">
              <span>فاکتور فروش INV-1405-0041 سررسید گذشته</span>
              <span className="font-bold tabular-nums">۸٬۴۰۰٬۰۰۰</span>
            </div>
            <div className="flex items-center justify-between gap-2 py-2.5">
              <span>فاکتور خرید PR-1405-0112 نزدیک سررسید</span>
              <span className="font-bold tabular-nums">۲۱٬۰۰۰٬۰۰۰</span>
            </div>
            <div className="flex items-center justify-between gap-2 py-2.5">
              <span>پیشنویس هزینه «خرید ملزومات اداری»</span>
              <span className="font-bold tabular-nums">۱٬۸۵۰٬۰۰۰</span>
            </div>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h2 className="text-sm font-extrabold">آخرین فعالیت</h2>
          </div>
          <div className="divide-y divide-dashed divide-border px-4 py-2 text-sm text-muted">
            <div className="py-2.5">ثبت پرداخت ۵۰٬۰۰۰٬۰۰۰ ریال — ۲۲ مرداد، ۰۸:۴۱</div>
            <div className="py-2.5">ایجاد پیشنویس هزینه «سوخت کامیون» — ۲۲ مرداد، ۰۷:۵۸</div>
            <div className="py-2.5">صدور صورتحساب INV-1405-0042 — ۲۱ مرداد، ۱۶:۱۲</div>
          </div>
        </section>
      </div>

      <p className="mt-6 rounded-md border border-dashed border-border-strong bg-surface-2 px-4 py-3 text-xs leading-6 text-muted">
        <b className="text-text">یادداشت نسخه:</b> مقادیر بالا نمونه داده طراحی هستند. از اسلایس ۸
        (داشبورد و گزارشها) همه اعداد مستقیماً از دفتر کل ثبتشده محاسبه و با گزارشها تطبیق داده
        میشوند. نمودارها، بودجه پروژهها و تأمین مالی نیز در اسلایسهای بعدی افزوده میشوند.
      </p>
    </div>
  );
}
