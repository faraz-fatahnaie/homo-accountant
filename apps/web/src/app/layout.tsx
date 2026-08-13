import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { ThemeProvider, initialThemeScript } from "@/lib/theme";

export const metadata: Metadata = {
  title: {
    default: "آریا تجارت — سامانه حسابداری",
    template: "%s | آریا تجارت",
  },
  description:
    "سامانه حسابداری دوطرفه فارسی برای شرکتهای کوچک — هزینهها، صورتحسابها، پرداختها، پروژهها و گزارشهای مالی",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: initialThemeScript }} />
      </head>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
