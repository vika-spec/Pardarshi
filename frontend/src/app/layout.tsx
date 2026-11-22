import type { Metadata, Viewport } from "next";
import "./globals.css";
import { LangProvider } from "@/lib/i18n";
import { Footer, Header } from "@/components/SiteChrome";

export const metadata: Metadata = {
  title: "Pardarshi · Read your portfolio like an auditor",
  description:
    "See what your mutual funds really own, what hidden commissions cost you, and which companies inside carry warning signs, with the page number for every claim.",
  applicationName: "Pardarshi",
};

export const viewport: Viewport = { themeColor: "#fbf8f1", width: "device-width", initialScale: 1 };

const FONTS =
  "https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Sans+Devanagari:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Tiro+Devanagari+Hindi&display=swap";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link rel="stylesheet" href={FONTS} />
      </head>
      <body>
        <LangProvider>
          <Header />
          <main id="main">{children}</main>
          <Footer />
        </LangProvider>
      </body>
    </html>
  );
}
