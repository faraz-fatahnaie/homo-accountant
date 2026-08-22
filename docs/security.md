# امنیت

این سند کنترل‌های امنیتی نسخهٔ فعلی برنامهٔ حسابداری «آریا تجارت» را خلاصه می‌کند. یکپارچگی دفتر کل، محرمانگی اسناد مالی و امکان بازیابی داده‌ها مهم‌ترین دارایی‌ها هستند.

## احراز هویت و دسترسی

- رمز عبور با PBKDF2-HMAC-SHA256، salt اختصاصی و ۶۰۰٬۰۰۰ دور نگهداری می‌شود.
- نشست مرورگر با cookieهای `HttpOnly` و `SameSite=Lax` کار می‌کند؛ در production ویژگی `Secure` نیز فعال است. access token کوتاه‌عمر است و refresh token پس از هر استفاده می‌چرخد.
- استفادهٔ مجدد از refresh token، کل خانوادهٔ آن نشست را باطل می‌کند. خروج نیز refresh token را باطل و cookieها را پاک می‌کند.
- API clientهای غیرمرورگری همچنان می‌توانند از Bearer token استفاده کنند.
- نقش، دسترسی و محدودهٔ شرکت در backend کنترل می‌شود؛ مخفی‌کردن دکمه در UI کنترل امنیتی محسوب نمی‌شود.
- endpoint ورود هم در API و هم در nginx محدودیت نرخ دارد.

## دفتر کل و داده‌های مالی

- ثبت نهایی فقط برای سند متوازن و در یک تراکنش پایگاه داده انجام می‌شود.
- سند ثبت‌شده تغییرناپذیر است و اصلاح آن فقط با سند معکوس انجام می‌شود.
- هر سند فقط یک‌بار می‌تواند معکوس شود؛ این قاعده در service و پایگاه داده enforce می‌شود.
- همهٔ mutationها و گزارش‌ها به شرکت کاربر محدودند و گزارش‌ها از خطوط ثبت‌شدهٔ دفتر کل ساخته می‌شوند.
- query builder فقط AST مجاز، پارامتری و read-only را کامپایل می‌کند و SQL خام نمی‌پذیرد.

## فایل و خروجی

- فایل ضمیمه فقط JPG، PNG یا PDF و حداکثر ۵ MiB است؛ نوع واقعی فایل با magic bytes بررسی می‌شود.
- route حداکثر `MAX_UPLOAD_BYTES + 1` را می‌خواند، فایل را در `finally` می‌بندد و nginx درخواست را در ۶ MiB محدود می‌کند.
- نام فایل download پیش از ساخت `Content-Disposition` پاک‌سازی و با RFC 5987 encode می‌شود.
- خروجی CSV در برابر spreadsheet formula injection محافظت می‌شود.

## production و شبکه

- production با JWT secret پیش‌فرض/کوتاه، رمز پیش‌فرض DB یا CORS wildcard بالا نمی‌آید.
- secretها فقط از environment یا فایل `.env` خارج از Git تأمین می‌شوند.
- API docs در production غیرفعال است و پاسخ‌ها هدرهای امنیتی و `X-Request-ID` دارند.
- TLS در proxy بیرونی خاتمه می‌یابد و VM فقط پورت ۸۰ را منتشر می‌کند. nginx مقدار `X-Forwarded-For` را از `$remote_addr` می‌سازد تا header ساختگی client زنجیره نشود.
- اگر proxy بیرونی IP اصلی را در header می‌فرستد، فقط IP همان proxy باید با `set_real_ip_from` trusted شود.
- CSP، frame protection، content-type protection و policyهای browser در لایهٔ web/nginx فعال‌اند.

## عملیات و بازیابی

- startup ابتدا migrationها و سپس bootstrap idempotent حساب‌های سیستمی را اجرا می‌کند؛ bootstrap حساب موجود را بازنویسی نمی‌کند.
- backup روزانه شامل dump پایگاه داده و فایل‌هاست. gzip، catalog بازیابی PostgreSQL و manifest SHA-256 هنگام backup بررسی می‌شوند؛ restore نیز checksum را پیش از تغییر داده کنترل می‌کند.
- Sentry اختیاری است و فقط با DSN فعال می‌شود؛ PII ارسال نمی‌شود. release و sampling از environment قابل تنظیم‌اند.
- تغییر رمز production با `python -m app.scripts.rotate_password` و secretهای environment انجام می‌شود؛ فرمان رمز را چاپ نمی‌کند و نشست‌های قبلی را باطل می‌کند.

## اعتبارسنجی و ریسک باقی‌مانده

اسکن استاندارد Codex Security روی snapshot مبنا دو یافتهٔ کم‌خطر پیدا کرد: پذیرش JWT secret شناخته‌شده و خواندن نامحدود upload پیش از کنترل اندازه. هر دو در working tree رفع و برایشان regression test افزوده شده است. گزارش نهایی باید همراه نتایج واقعی CI، تست integration/E2E، dependency audit و آزمون deployment خوانده شود.

محدودیت نرخ ورود در حافظهٔ یک process نگهداری می‌شود؛ برای همین استقرار تک‌process فعلی مناسب است، اما پیش از scale-out باید به storage مشترک مانند Redis منتقل شود. CSP فعلی به‌دلیل bootstrap درون‌خطی Next.js شامل `script-src 'unsafe-inline'` است؛ سایر directiveها دامنهٔ اثر را محدود می‌کنند و این تصمیم هنگام ارتقای معماری rendering باید دوباره بررسی شود.
