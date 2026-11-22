"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChatDrawer } from "@/components/ChatDrawer";
import { EvidenceDrawer } from "@/components/Evidence";
import { Chat } from "@/components/icons";
import { CostSection, LookInto, ModeToggle, OverlapSection, OwnSection, RiskSection, SummaryLedger } from "@/components/ReportSections";
import { analyzeManual, ApiError, getSample } from "@/lib/api";
import { rupees } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { saveReport, useStoredReport } from "@/lib/session";

export default function ReportPage() {
  const { t } = useLang();
  const stored = useStoredReport();
  const [err, setErr] = useState("");
  const [evidence, setEvidence] = useState<string | null>(null);
  const [chat, setChat] = useState(false);
  const [age, setAge] = useState("");
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const r = stored;
  const [wantSample] = useState(() => typeof window !== "undefined" && new URLSearchParams(window.location.search).has("sample"));
  const needSample = !stored || wantSample;
  useEffect(() => {
    if (!needSample) return;
    let alive = true;
    getSample()
      .then((s) => alive && saveReport(s))
      .catch((e) => alive && setErr(e.message));
    return () => {
      alive = false;
    };
  }, [needSample]);

  // Recalculate costs for a new age, re-using the anonymous holdings already on screen.
  const onAge = useCallback((a: string) => {
    setAge(a);
    if (timer.current) clearTimeout(timer.current);
    const n = parseInt(a, 10);
    if (!r || !(n >= 16 && n <= 90)) return;
    timer.current = setTimeout(async () => {
      setBusy(true);
      try {
        const next = await analyzeManual(r.funds.map((f) => ({ scheme_id: f.scheme_id, plan: f.plan, value: f.value })), n);
        const merged = { ...next, label: r.label, statement: r.statement, direct_stocks: r.direct_stocks, unmatched: r.unmatched };
        saveReport(merged);
      } catch (e) {
        setErr(e instanceof ApiError ? e.message : "Couldn't recalculate.");
      } finally {
        setBusy(false);
      }
    }, 450);
  }, [r]);

  if (err && !r) return <div className="wrap section"><p className="error" role="alert">{err}</p><Link className="btn" href="/">{t.start_over}</Link></div>;
  if (!r) return <div className="wrap section"><div className="skeleton" style={{ height: 320 }} /><span className="sr-only">{t.loading}</span></div>;

  const isDemo = r.dataset?.dataset === "demo";

  return (
    <>
      {isDemo && <div className="banner" role="note"><div className="wrap">{t.demo_banner}</div></div>}
      <div className="wrap">
        <section className="section row gap-32" style={{ alignItems: "center", paddingBottom: 24 }}>
          <div style={{ flex: "1 1 420px", minWidth: 0 }}>
            <p className="eyebrow">{r.label ? t.sample_label : t.report_label}</p>
            <h1 className="display h1" style={{ marginTop: 14 }}>{t.r_title}</h1>
            {r.statement && <p className="hint" style={{ marginTop: 10 }}>{r.statement.type}{r.statement.as_of ? ` · as of ${r.statement.as_of}` : ""}</p>}
            <div className="row gap-12 no-print" style={{ marginTop: 22 }}>
              <button className="btn btn-primary" onClick={() => setChat(true)}><Chat /> {t.ask_open}</button>
              <button className="btn" onClick={() => window.print()}>{t.print}</button>
              <Link className="link-btn" href="/#start" style={{ alignSelf: "center" }}>{t.start_over}</Link>
            </div>
            {err && <p className="error" role="alert" style={{ marginTop: 14 }}>{err}</p>}
          </div>
          <div style={{ flex: "1 1 380px", minWidth: 0 }}>
            <SummaryLedger r={r} />
          </div>
        </section>

        <ModeToggle />
        <div style={{ height: 18 }} />
        <LookInto r={r} />
        <RiskSection r={r} onOpen={setEvidence} />
        <OwnSection r={r} />
        <OverlapSection r={r} />
        <CostSection r={r} age={age} onAge={onAge} busy={busy} />

        {(r.unmatched.length > 0 || r.direct_stocks.length > 0) && (
          <section className="section rule-top row gap-32" style={{ alignItems: "flex-start" }}>
            {r.unmatched.length > 0 && (
              <div style={{ flex: "1 1 320px" }}>
                <h2 className="h3">{t.unmatched_title}</h2>
                <p className="hint">{t.unmatched_sub}</p>
                <ul style={{ paddingLeft: 18 }}>{r.unmatched.map((u) => <li key={u.name}>{u.name} · <span className="mono">{rupees(u.value)}</span></li>)}</ul>
              </div>
            )}
            {r.direct_stocks.length > 0 && (
              <div style={{ flex: "1 1 320px" }}>
                <h2 className="h3">{t.direct_stocks}</h2>
                <ul style={{ paddingLeft: 18 }}>
                  {r.direct_stocks.map((s) => (
                    <li key={s.isin}>{s.name} · <span className="mono">{rupees(s.value)}</span>{s.has_scorecard && <> · <button className="link-btn" onClick={() => setEvidence(s.isin)}>{t.open_evidence}</button></>}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </div>

      <button className="btn btn-primary no-print" onClick={() => setChat(true)} style={{ position: "fixed", right: 18, bottom: 18, zIndex: 30, borderRadius: 26, boxShadow: "0 6px 18px rgba(31,42,68,.18)" }}>
        <Chat /> {t.ask_open}
      </button>

      {evidence && <EvidenceDrawer isin={evidence} trust={r.risk.trust} onClose={() => setEvidence(null)} />}
      {chat && <ChatDrawer report={r} onClose={() => setChat(false)} onOpenEvidence={(isin) => { setChat(false); setEvidence(isin); }} />}
    </>
  );
}
