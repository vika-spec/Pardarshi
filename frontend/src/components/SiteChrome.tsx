"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { OFFLINE_EVENT } from "@/lib/api";
import { useLang } from "@/lib/i18n";

export function Header() {
  const { t, lang, setLang, large, setLarge } = useLang();
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const on = () => setOffline(true);
    window.addEventListener(OFFLINE_EVENT, on);
    return () => window.removeEventListener(OFFLINE_EVENT, on);
  }, []);

  return (
    <>
      <a href="#main" className="skip-link">{t.skip}</a>
      {offline && (
        <div className="banner" role="status">
          <div className="wrap">{t.offline_banner}</div>
        </div>
      )}
      <header style={{ borderBottom: "1px solid var(--rule)" }}>
        <div className="wrap row between gap-16" style={{ paddingTop: 18, paddingBottom: 18 }}>
          <Link href="/" className="row gap-8" style={{ textDecoration: "none", color: "var(--ink)", alignItems: "baseline" }} aria-label="Pardarshi home">
            <span className="display" style={{ fontSize: 30, lineHeight: 1, fontFamily: '"Instrument Serif", Georgia, serif' }}>Pardarshi</span>
            <span lang="hi" style={{ fontFamily: '"Tiro Devanagari Hindi", serif', fontSize: 18, color: "var(--red)" }}>पारदर्शी</span>
          </Link>
          <nav aria-label="Main" className="row gap-16" style={{ fontSize: 15 }}>
            <Link href="/guide" style={{ color: "var(--ink)", textDecoration: "none" }}>{t.nav_guide}</Link>
            <Link href="/glossary" style={{ color: "var(--ink)", textDecoration: "none" }}>{t.nav_glossary}</Link>
            <Link href="/cases" style={{ color: "var(--ink)", textDecoration: "none" }}>{t.nav_cases}</Link>
            <Link href="/methodology" style={{ color: "var(--ink)", textDecoration: "none" }}>{t.nav_method}</Link>
            <Link href="/privacy" style={{ color: "var(--ink)", textDecoration: "none" }}>{t.nav_privacy}</Link>
            <button className="pill" aria-pressed={large} onClick={() => setLarge(!large)} title={t.text_size}>
              <span aria-hidden="true" style={{ fontWeight: 600 }}>A<span style={{ fontSize: "1.2em" }}>A</span></span>
              <span className="sr-only">{t.text_size}</span>
            </button>
            <button className="pill" onClick={() => setLang(lang === "en" ? "hi" : "en")} aria-label={t.lang_toggle_label} lang={lang === "en" ? "hi" : "en"}>
              {t.lang_toggle}
            </button>
          </nav>
        </div>
      </header>
    </>
  );
}

const REPO = (process.env.NEXT_PUBLIC_REPO_URL || "https://github.com").replace(/\/$/, "");

export function Footer() {
  const { t } = useLang();
  return (
    <footer className="rule-top" style={{ marginTop: 40 }}>
      <div className="wrap row between gap-16 muted" style={{ paddingTop: 26, paddingBottom: 30, fontSize: 14 }}>
        <span style={{ maxWidth: 640 }}>{t.footer_note}</span>
        <span className="row gap-12">
          <Link href="/cases">{t.nav_cases}</Link>
          <Link href="/methodology">{t.nav_method}</Link>
          <a href={REPO} rel="noreferrer">{t.open_source}</a>
          <a href={`${REPO}/issues/new?title=Wrong%20flag&labels=wrong-flag`} rel="noreferrer">{t.report_wrong}</a>
        </span>
      </div>
    </footer>
  );
}
