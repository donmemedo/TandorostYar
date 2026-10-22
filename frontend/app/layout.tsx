import "@fontsource-variable/vazirmatn";
import "@fontsource-variable/inter";
import "./globals.css";
import type { Metadata, Viewport } from "next";
import { cookies, headers } from "next/headers";
import Shell from "@/components/Shell";
import { AuthProvider } from "@/lib/auth";
import { LangProvider, type Lang } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "فیت‌پیمان · FitPeyman",
  description: "Commit to your health goals with real stakes. Keep your pact, share the pool.",
  appleWebApp: { capable: true, title: "FitPeyman", statusBarStyle: "black-translucent" },
  robots: { index: false }, // account pages: nothing here should be indexed
};

export const viewport: Viewport = {
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f5f7" },
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
  ],
};

// Set theme before paint to avoid a flash
const themeScript = `try{var t=localStorage.theme;document.documentElement.dataset.theme=t||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')}catch(e){document.documentElement.dataset.theme='light'}`;

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const lang: Lang = (await cookies()).get("lang")?.value === "en" ? "en" : "fa";
  const nonce = (await headers()).get("x-nonce") ?? undefined; // minted per request in proxy.ts; lets this one inline script run under the CSP
  return (
    <html lang={lang} dir={lang === "fa" ? "rtl" : "ltr"} suppressHydrationWarning>
      <head>
        <script nonce={nonce} dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <LangProvider initial={lang}>
          <AuthProvider>
            <Shell>{children}</Shell>
          </AuthProvider>
        </LangProvider>
      </body>
    </html>
  );
}
