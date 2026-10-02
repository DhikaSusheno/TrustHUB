import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import BackendStatusBanner from "@/components/shared/BackendStatusBanner";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import { ThemeProvider } from "@/lib/theme/ThemeProvider";

const inter = localFont({ src: "../public/fonts/InterVariable.woff2", variable: "--font-inter" });

export const metadata: Metadata = {
  title: "TrustHUB — Manufacturing Knowledge Hub",
  description:
    "Document-grounded answers with a trust badge, cited sources, and measured refusals. CALIBER 2026 Case 1, LLDPE unit Set 01.",
};

// Runs before the browser paints anything below it, which is what stops a
// returning light-theme visitor from seeing a dark frame first. A plain inline
// script rather than next/script: it has to be in the document before the rest
// of the body, and it must not wait for hydration. It mirrors the fallback
// order in ThemeProvider, and defaults to dark, which is what globals.css
// declares on :root.
const themeBootstrap = `(function(){try{var s=window.localStorage.getItem("trusthub.theme");document.documentElement.setAttribute("data-theme",(s==="light"||s==="dark")?s:"dark");}catch(e){document.documentElement.setAttribute("data-theme","dark");}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // lang stays "en" on the server and LocaleProvider corrects it after
    // mount. Rendering the stored locale here would make the server and the
    // client disagree on the first paint. The same applies to the theme, except
    // that here the attribute is resolved by the bootstrap script below before
    // first paint, so it is correct even on the server-rendered frame.
    //
    // The old `dark` class is gone. Nothing in the app used a `dark:` variant,
    // because every colour was a fixed hex or a Tailwind shade that now resolves
    // through a theme variable. What decides the palette is data-theme.
    <html lang="en">
      {/* No bg-* here on purpose. The surface colour, the grain and the
          vignette are owned by globals.css; a second declaration of the base
          colour in the tree is one more place to forget when it changes. */}
      <body className={`${inter.variable} h-screen overflow-hidden text-slate-100 antialiased`}>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
        {/* Banner sits in flow, not fixed, so it can never cover the page
            header underneath. Children get the remaining height. */}
        <div className="flex h-full flex-col">
          <BackendStatusBanner />
          <div className="min-h-0 flex-1">
            <ThemeProvider>
              <LocaleProvider>{children}</LocaleProvider>
            </ThemeProvider>
          </div>
        </div>
      </body>
    </html>
  );
}