"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { getPage, getScorecard, getTimeline, reportPdfUrl } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { CheckResult, Evidence, Report, Scorecard, Timeline } from "@/lib/types";
import { Drawer } from "./Drawer";
import { Check, External, StatusIcon, Warn } from "./icons";
import { LevelBadge, TrustStrip } from "./ReportSections";

const ORDER: Record<string, number> = { flagged: 0, disputed: 1, unverified: 2, not_found: 3, passed: 4, not_applicable: 5 };

type Trust = Report["risk"]["trust"];

export function EvidenceDrawer({ isin, onClose, trust }: { isin: string; onClose: () => void; trust?: Trust }) {
  const { t, lang } = useLang();
  const [card, setCard] = useState<Scorecard | null>(null);
  const [err, setErr] = useState("");
  const [page, setPage] = useState<{ ev: Evidence } | null>(null);

  useEffect(() => {
    getScorecard(isin).then(setCard).catch((e) => setErr(e.message));
  }, [isin]);

  const checks = useMemo(() => (card ? [...card.checks].sort((a, b) => ORDER[a.status] - ORDER[b.status]) : []), [card]);

  return (
    <Drawer
      title={card?.name ?? t.loading}
      sub={card ? `${card.fy ? `Annual report ${card.fy} · ` : ""}${t.checks_of(card.counts.flagged ?? 0, card.counts.passed ?? 0)}` : undefined}
      onClose={onClose}
    >
      {err && <p className="error">{err}</p>}
      {!card && !err && <div className="skeleton" style={{ height: 200 }} />}
      {card && !page && (
        <div className="stack gap-12">
          <TrustStrip trust={trust} />
          <p className="hint" style={{ margin: 0 }}>
            {t.report_source}{card.fy ? ` ${card.fy}` : ""}{card.report_date ? ` · ${t.published} ${card.report_date}` : ""} ·{" "}
            <a href={reportPdfUrl(isin)} target="_blank" rel="noreferrer">{t.open_report} <External /></a>
          </p>
          {card.old_report && <p className="badge badge-amber" style={{ margin: 0 }}>{t.old_report}: {t.old_report_hint}</p>}
          <p className="hint" style={{ margin: 0 }}>{t.not_proof}</p>
          <TimelineView isin={isin} lang={lang} />
          {checks.map((c) => <CheckBlock key={c.id} c={c} lang={lang} nPages={card.n_pages} onOpen={(ev) => setPage({ ev })} />)}
        </div>
      )}
      {card && page && <PageView isin={isin} ev={page.ev} onBack={() => setPage(null)} />}
    </Drawer>
  );
}

// ---------------------------------------------------------------- the numbers
const FIELD: Record<string, { en: string; hi: string; unit?: "cr" | "%" }> = {
  pledged_pct_of_promoter_holding: { en: "Promoter shares pledged", hi: "प्रमोटर शेयर गिरवी", unit: "%" },
  rpt_current: { en: "Related-party deals, this year", hi: "संबंधित पक्ष सौदे, इस साल", unit: "cr" },
  rpt_previous: { en: "Related-party deals, last year", hi: "संबंधित पक्ष सौदे, पिछले साल", unit: "cr" },
  revenue_current: { en: "Revenue, this year", hi: "आय, इस साल", unit: "cr" },
  revenue_previous: { en: "Revenue, last year", hi: "आय, पिछले साल", unit: "cr" },
  contingent_liabilities: { en: "Contingent liabilities", hi: "आकस्मिक देनदारियाँ", unit: "cr" },
  total_equity: { en: "Net worth (equity)", hi: "नेट वर्थ", unit: "cr" },
  pat_current: { en: "Profit after tax, this year", hi: "टैक्स बाद मुनाफ़ा, इस साल", unit: "cr" },
  pat_previous: { en: "Profit after tax, last year", hi: "टैक्स बाद मुनाफ़ा, पिछले साल", unit: "cr" },
  cfo_current: { en: "Cash from operations, this year", hi: "कारोबार से नकद, इस साल", unit: "cr" },
  cfo_previous: { en: "Cash from operations, last year", hi: "कारोबार से नकद, पिछले साल", unit: "cr" },
  receivables_current: { en: "Money owed by customers, this year", hi: "ग्राहकों पर बकाया, इस साल", unit: "cr" },
  receivables_previous: { en: "Money owed by customers, last year", hi: "ग्राहकों पर बकाया, पिछले साल", unit: "cr" },
};

const fmt = (v: number, unit?: string) =>
  unit === "%" ? `${v.toFixed(1)}%` : new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(v);

/** One plain sentence showing the maths and the threshold, built from the derived values. */
function maths(id: string, d: Record<string, number>, flagged: boolean, lang: "en" | "hi"): string | null {
  const f = (x?: number) => (x == null ? "?" : `${x.toFixed(1)}%`);
  const verdict = lang === "hi" ? (flagged ? "→ चेतावनी" : "→ ठीक") : flagged ? "→ warning" : "→ within the limit";
  switch (id) {
    case "promoter_pledge":
      return lang === "hi" ? `गिरवी ${f(d.pledged_pct_of_promoter_holding)}; सीमा 10% ${verdict}` : `Pledged ${f(d.pledged_pct_of_promoter_holding)}; limit 10% ${verdict}`;
    case "related_party":
      if (d.rpt_growth == null)
        return lang === "hi" ? `आय का ${f(d.rpt_pct_revenue)}; सीमा 10% (पिछले साल के आंकड़े नहीं मिले) ${verdict}` : `${f(d.rpt_pct_revenue)} of revenue; limit 10% (last year's figures not found) ${verdict}`;
      return lang === "hi"
        ? `आय का ${f(d.rpt_pct_revenue)} (सीमा 10%); बढ़त ${f(d.rpt_growth)} बनाम आय ${f(d.revenue_growth)} (अंतर सीमा 20 अंक) ${verdict}`
        : `${f(d.rpt_pct_revenue)} of revenue (limit 10%); grew ${f(d.rpt_growth)} vs revenue ${f(d.revenue_growth)} (gap limit 20 points) ${verdict}`;
    case "contingent_liabilities":
      return lang === "hi" ? `नेट वर्थ का ${f(d.contingent_pct_equity)}; सीमा 25% ${verdict}` : `${f(d.contingent_pct_equity)} of net worth; limit 25% ${verdict}`;
    case "cash_vs_profit":
      return lang === "hi" ? `2 साल में नकद, मुनाफ़े का ${f(d.cfo_to_pat)}; सीमा 50% ${verdict}` : `2-year cash is ${f(d.cfo_to_pat)} of 2-year profit; limit 50% ${verdict}`;
    case "receivables":
      return lang === "hi"
        ? `बकाया ${f(d.receivables_growth)} बढ़ा, आय ${f(d.revenue_growth)}; अंतर सीमा 20 अंक ${verdict}`
        : `Receivables grew ${f(d.receivables_growth)}, revenue ${f(d.revenue_growth)}: gap ${((d.receivables_growth ?? 0) - (d.revenue_growth ?? 0)).toFixed(1)} points; limit 20 ${verdict}`;
  }
  return null;
}

function Numbers({ c, lang }: { c: CheckResult; lang: "en" | "hi" }) {
  const { t } = useLang();
  const rows = Object.entries(c.values).filter(([k]) => FIELD[k]);
  if (!rows.length) return null;
  const line = maths(c.id, c.derived, c.status === "flagged", lang);
  return (
    <div style={{ marginTop: 10 }}>
      <p className="mono hint" style={{ margin: 0 }}>{t.numbers_title.toUpperCase()}</p>
      <table className="numbers">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}><td>{FIELD[k][lang]}</td><td className="num">{fmt(v, FIELD[k].unit)}{FIELD[k].unit === "cr" ? " cr" : ""}</td></tr>
          ))}
        </tbody>
      </table>
      {line && <p className="mono" style={{ margin: "6px 0 0", fontSize: 13 }}>{line}</p>}
      {c.breakdown && c.breakdown.length > 0 && (
        <>
          <p className="mono hint" style={{ margin: "10px 0 0" }}>
            {lang === "hi" ? "संबंधित पक्षों से सौदे, प्रकार के अनुसार (कोड ने जोड़ा)" : `RELATED-PARTY DEALS BY TYPE, ADDED UP BY CODE${c.basis ? ` (${c.basis.toUpperCase()})` : ""}`}
          </p>
          <table className="numbers">
            <tbody>
              {c.breakdown.slice(0, 5).map((b) => (
                <tr key={b.type}><td>{b.type}</td><td className="num">{fmt(b.current, "cr")} cr</td></tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      <p className="hint" style={{ margin: "4px 0 0", fontSize: 13 }}>{t.numbers_note}</p>
    </div>
  );
}

function pageLabel(e: Evidence, t: { pdf_page: string; printed_page: string }) {
  return e.printed_page && e.printed_page !== e.page ? `${t.pdf_page} ${e.page} · ${t.printed_page} ${e.printed_page}` : `p. ${e.page}`;
}

// ---------------------------------------------------------------- one check
function CheckBlock({ c, lang, onOpen, nPages }: { c: CheckResult; lang: "en" | "hi"; onOpen: (ev: Evidence) => void; nPages?: number }) {
  const { t } = useLang();
  const label = { flagged: t.st_flagged, passed: t.st_passed, not_found: t.st_not_found, unverified: t.st_unverified, not_applicable: t.st_not_applicable, disputed: t.st_disputed }[c.status];
  const cls = c.status === "flagged" ? "status-flagged" : c.status === "passed" ? "status-passed" : "status-unknown";
  const na = c.status === "not_applicable";
  return (
    <article className="card" style={{ padding: "16px 18px", borderColor: c.status === "flagged" ? "#e3b8b3" : undefined, opacity: na ? 0.85 : 1 }}>
      <div className="row between gap-8">
        <span className="row gap-8"><span className={`status ${cls}`}><StatusIcon status={c.status} /> {label}</span>{c.status === "flagged" && <LevelBadge level={c.level} />}</span>
        {!na && <span className="hint">{c.severity === "high" ? "High weight" : "Medium weight"}</span>}
      </div>
      <h3 className="h3" style={{ marginTop: 8, fontSize: "1.1rem" }}>{c.title[lang]}</h3>
      {c.summary[lang] && <p style={{ margin: "6px 0 0" }}>{c.summary[lang]}</p>}
      {c.review && c.review.agree && (
        <p className="verify-badge" style={{ margin: "8px 0 0" }}><Check size={14} color="var(--green)" /> <span>{t.review_ok(c.review.by, c.review.same_model)}{c.review.reason ? ` ${c.review.reason}` : ""}</span></p>
      )}
      {c.review && !c.review.agree && (
        <p className="verify-badge bad" style={{ margin: "8px 0 0" }}><Warn color="var(--red)" /> <span>{t.review_no(c.review.by)} {c.review.reason}</span></p>
      )}
      {!na && c.status !== "not_found" && <AITrace c={c} lang={lang} nPages={nPages} open={c.status === "flagged" || c.status === "disputed"} />}
      {!na && <p className="muted" style={{ margin: "6px 0 0", fontSize: 15 }}>{c.what[lang]}</p>}
      {!na && <Numbers c={c} lang={lang} />}
      {c.evidence.filter((e) => e.quote).map((e, i) => (
        <div key={i}>
          <blockquote className="quote">“{e.quote}”</blockquote>
          <div className="row gap-12" style={{ marginTop: 6, fontSize: 14 }}>
            <button className="btn btn-sm" onClick={() => onOpen(e)}>{pageLabel(e, t)} · {t.open_page}</button>
            {e.verified ? (
              <span className="row gap-4 green"><Check size={14} color="var(--green)" /> {t.quote_verified} {e.page}</span>
            ) : (
              <span className="hint">{t.unverified}</span>
            )}
          </div>
        </div>
      ))}
      {(c.status === "flagged" || c.status === "unverified" || c.status === "disputed") && c.caveat && (
        <div className="stack gap-4" style={{ marginTop: 10, fontSize: 14 }}>
          <p style={{ margin: 0 }}><strong>{t.caveat_t}:</strong> <span className="muted">{c.caveat[lang]}</span></p>
          {c.clears && <p style={{ margin: 0 }}><strong>{t.clears_t}:</strong> <span className="muted">{c.clears[lang]}</span></p>}
        </div>
      )}
      {!na && (
        <details className="working" style={{ marginTop: 8 }}>
          <summary>{t.rule}</summary>
          <p style={{ margin: "4px 0 0", fontSize: 14 }}>{c.rule}</p>
          <p className="hint" style={{ margin: "6px 0 0" }}>{t.method}: {c.method === "heuristic" ? "pattern matching (no AI)" : c.method === "table" ? "table read and added up by code (no AI)" : c.method.replace("llm:", "AI model via ")} · confidence {c.confidence}</p>
        </details>
      )}
    </article>
  );
}


// ---------------------------------------------------------------- AI trace
const MODEL: Record<string, string> = { groq: "Groq · gpt-oss-120b", gemini: "Google · Gemini Flash-Lite", mistral: "Mistral", azure: "Azure OpenAI", ollama: "local Ollama", openai: "OpenAI-compatible" };
function Step({ n, who, title, children }: { n: number; who: "AI" | "CODE"; title: string; children?: React.ReactNode }) {
  const ai = who === "AI";
  return (
    <li style={{ display: "grid", gridTemplateColumns: "22px 52px 1fr", gap: 8, alignItems: "start", padding: "7px 0", borderTop: n > 1 ? "1px solid var(--border)" : undefined }}>
      <span className="mono hint" style={{ fontSize: 12, paddingTop: 2 }}>{String(n).padStart(2, "0")}</span>
      <span className="mono" style={{ fontSize: 11, textAlign: "center", padding: "2px 0", borderRadius: 10, background: ai ? "#e6eefa" : "#e8f3ea", color: ai ? "#1f4f99" : "#2f6b3b" }}>{who}</span>
      <span style={{ fontSize: 14 }}><strong style={{ fontWeight: 600 }}>{title}</strong>{children ? <span className="muted"> {children}</span> : null}</span>
    </li>
  );
}
function AITrace({ c, lang, nPages, open }: { c: CheckResult; lang: "en" | "hi"; nPages?: number; open: boolean }) {
  const hi = lang === "hi";
  const base = c.method.split("+")[0];
  const viaAI = base.startsWith("llm:");
  const provider = viaAI ? base.slice(4) : "";
  const pages = (c.seen_pages ?? []).slice(0, 8);
  const nFig = Object.keys(c.values || {}).length;
  const nQ = c.evidence.filter((e) => e.quote).length;
  const line = maths(c.id, c.derived, c.status === "flagged", lang);
  let n = 0;
  return (
    <details open={open} style={{ marginTop: 10, border: "1px solid #c9d6ee", borderLeft: "4px solid #1f4f99", borderRadius: 0, background: "#f7f9fd", padding: "8px 12px" }}>
      <summary style={{ cursor: "pointer", fontWeight: 600, fontSize: 14, color: "#1f4f99" }}>
        {hi ? "AI इस नतीजे तक कैसे पहुँचा" : "How the AI reached this"}
        <span className="hint" style={{ fontWeight: 400, marginLeft: 8 }}>{hi ? "हर कदम, AI या कोड" : "every step, and whether AI or code did it"}</span>
      </summary>
      <ol style={{ listStyle: "none", margin: "6px 0 0", padding: 0 }}>
        <Step n={++n} who="CODE" title={hi ? "खोजा:" : "Searched"}>
          {hi ? `${nPages ?? "?"} पेज, सबसे काम के ${pages.length} पेज चुने` : `${nPages ? `${nPages} pages` : "the report"} and picked the most relevant passages${pages.length ? `, from pages ${pages.join(", ")}` : ""} (BM25 retrieval, tables rebuilt row by row).`}
        </Step>
        {viaAI && (
          <Step n={++n} who="AI" title={hi ? `${MODEL[provider] ?? provider} ने पढ़ा` : `${MODEL[provider] ?? provider} read only those passages`}>
            {hi ? `${nFig} आंकड़े और ${nQ} सटीक उद्धरण JSON में लौटाए।` : `and returned ${nFig ? `${nFig} figure${nFig > 1 ? "s" : ""}` : "a verdict"} with ${nQ} exact quote${nQ === 1 ? "" : "s"} and page numbers, as JSON. It did not decide the warning.`}
          </Step>
        )}
        {base === "table" && (
          <Step n={++n} who="CODE" title={hi ? "कोड ने तालिका जोड़ी" : "Code read the table and added it up"}>
            {hi ? "रिपोर्ट में कुल नहीं था, इसलिए हर पंक्ति जोड़ी गई।" : `because the report gives no total: ${c.breakdown?.length ?? 0} transaction types summed row by row, directors' pay excluded.`}
          </Step>
        )}
        {base === "heuristic" && (
          <Step n={++n} who="CODE" title={hi ? "नियम-आधारित रीडर" : "Rule-based reader"}>{hi ? "AI उपलब्ध नहीं था; केवल सिद्ध आंकड़े लिए गए।" : "read the figures (the AI was unavailable); it only uses what it can prove."}</Step>
        )}
        {c.method.includes("+pattern") && (
          <Step n={++n} who="CODE" title={hi ? "कमी पूरी की" : "Filled a gap"}>{hi ? "जो आंकड़ा AI से छूटा, वह नियम-आधारित रीडर ने सिद्ध उद्धरण के साथ जोड़ा।" : "a figure the AI missed was added by the rule-based reader, with its own verified quote."}</Step>
        )}
        <Step n={++n} who="CODE" title={hi ? "नियम लागू किया:" : "Applied the published rule:"}>{line ?? (hi ? c.rule : c.rule)}</Step>
        <Step n={++n} who="CODE" title={hi ? "उद्धरण जाँचे:" : "Checked every quote on its page:"}>
          {c.evidence.filter((e) => e.quote).map((e) => `p. ${e.page} ${e.verified ? "✓" : "✗"} ${Math.round(e.match)}% text match`).join(" · ") || (hi ? "कोई उद्धरण नहीं" : "no quote")}
          {hi ? "" : ", and every number in each quote appears exactly on that page."}
        </Step>
        {c.review ? (
          <Step n={++n} who="AI" title={c.review.agree ? (hi ? `दूसरे मॉडल (${MODEL[c.review.by] ?? c.review.by}) ने सहमति दी:` : `A second model (${MODEL[c.review.by] ?? c.review.by}) re-read the full pages and agreed:`) : (hi ? `दूसरा मॉडल असहमत:` : `A second model (${MODEL[c.review.by] ?? c.review.by}) disagreed, so this is not scored:`)}>
            {c.review.reason}{c.review.same_model ? (hi ? " (उसी मॉडल से, क्योंकि दूसरा उपलब्ध नहीं था)" : " (same model family; the other was unavailable)") : ""}
          </Step>
        ) : c.status === "flagged" ? (
          <Step n={++n} who="AI" title={hi ? "दूसरी राय: बाकी" : "Second opinion: pending"}>{hi ? "" : "this warning has not been re-checked yet."}</Step>
        ) : null}
        {typeof c.ms === "number" && <Step n={++n} who="CODE" title={hi ? "समय:" : "Time:"}>{(c.ms / 1000).toFixed(1)} s {hi ? "इस जाँच में" : "for this check, end to end"}</Step>}
      </ol>
    </details>
  );
}

// ---------------------------------------------------------------- page view
/** Find where the quote sits on the page. Exact first; otherwise the longest run of the quote's
 *  words that appears in order (page text often breaks lines and spacing differently). */
function locate(text: string, quote: string): { start: number; end: number; exact: boolean } | null {
  const esc = (w: string) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const words = quote.replace(/[“”"…]/g, " ").replace(/\.\.\./g, " ").trim().split(/\s+/).filter(Boolean);
  if (!words.length) return null;
  const exact = new RegExp(words.map(esc).join("[\\s\\W]+"), "i").exec(text);
  if (exact) return { start: exact.index, end: exact.index + exact[0].length, exact: true };
  // shrink a sliding window until some run of consecutive quote words matches
  for (let len = Math.min(words.length - 1, 30); len >= 4; len--) {
    for (let i = 0; i + len <= words.length; i++) {
      const m = new RegExp(words.slice(i, i + len).map(esc).join("[\\s\\W]+"), "i").exec(text);
      if (m) return { start: m.index, end: m.index + m[0].length, exact: false };
    }
  }
  // last resort: the first number from the quote that appears on the page
  for (const n of quote.match(/\d[\d,]*(?:\.\d+)?/g) ?? []) {
    const i = text.indexOf(n);
    if (i >= 0 && n.length >= 3) return { start: i, end: i + n.length, exact: false };
  }
  return null;
}

function PageView({ isin, ev, onBack }: { isin: string; ev: Evidence; onBack: () => void }) {
  const { t } = useLang();
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const markRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    getPage(isin, ev.page).then((r) => setText(r.text)).catch((e) => setErr(e.message));
  }, [isin, ev.page]);

  const hit = useMemo(() => (text ? locate(text, ev.quote) : null), [text, ev.quote]);
  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [hit]);

  return (
    <div className="stack gap-12">
      <div className="row between gap-8">
        <button className="link-btn" onClick={onBack}>← {t.flagged} / {t.passed}</button>
        <a className="row gap-4" href={reportPdfUrl(isin, ev.page)} target="_blank" rel="noreferrer">{t.open_pdf} <External /></a>
      </div>
      {ev.verified ? (
        <p className="verify-badge" style={{ margin: 0 }}><Check size={16} color="var(--green)" /> <span>{t.verified_badge(ev.printed_page ?? ev.page, Math.round(ev.match))}</span></p>
      ) : (
        <p className="verify-badge bad" style={{ margin: 0 }}><Warn color="var(--red)" /> <span>{t.not_verified_badge}</span></p>
      )}
      <p className="mono hint" style={{ margin: 0 }}>{pageLabel(ev, t).toUpperCase()}</p>
      {err && <p className="error">{err}</p>}
      {!text && !err && <div className="skeleton" style={{ height: 300 }} />}
      {text && hit && !hit.exact && <p className="hint" style={{ margin: 0 }}>{t.highlight_missing}</p>}
      {text && (
        <div className="page-text" tabIndex={0} aria-label={`Page ${ev.page} text`}>
          {hit ? (
            <>
              {text.slice(0, hit.start)}
              <mark ref={markRef}>{text.slice(hit.start, hit.end)}</mark>
              {text.slice(hit.end)}
            </>
          ) : text}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- timeline
function Cell({ status, level }: { status: string; level: Timeline["checks"][number]["cells"][number]["level"] }) {
  if (status === "flagged") return <span className="row gap-4" style={{ justifyContent: "center" }}><Warn color="var(--red)" /><LevelBadge level={level} /></span>;
  if (status === "passed") return <Check size={14} color="var(--green)" />;
  return <span className="hint">{status === "not_applicable" ? "n/a" : "–"}</span>;
}

function TimelineView({ isin, lang }: { isin: string; lang: "en" | "hi" }) {
  const { t } = useLang();
  const [tl, setTl] = useState<Timeline | null | undefined>(undefined);
  useEffect(() => {
    getTimeline(isin).then(setTl).catch(() => setTl(null));
  }, [isin]);
  if (!tl) return null;
  if (tl.years.length < 2) return <p className="hint" style={{ margin: 0 }}>{t.tl_title}: {t.tl_one}</p>;
  const arrow = { worse: `▲ ${t.tl_worse}`, better: `▼ ${t.tl_better}`, same: t.tl_same, unknown: "–" } as const;
  return (
    <div className="card" style={{ padding: "14px 16px" }}>
      <p className="mono hint" style={{ margin: 0 }}>{t.tl_title.toUpperCase()}</p>
      <p style={{ margin: "4px 0 8px", fontSize: 15 }}>{t.tl_sub(tl.summary.worse, tl.summary.better)}</p>
      <div className="scroll-x">
        <table className="numbers">
          <thead>
            <tr><td /> {tl.years.map((y) => <td key={y} className="mono hint" style={{ textAlign: "center" }}>{y}</td>)}<td /></tr>
          </thead>
          <tbody>
            {tl.checks.map((r) => (
              <tr key={r.id}>
                <td>{r.title[lang]}</td>
                {r.cells.map((c) => <td key={c.fy} style={{ textAlign: "center" }}><Cell status={c.status} level={c.level} /></td>)}
                <td className="mono" style={{ fontSize: 12, color: r.trend === "worse" ? "var(--red)" : r.trend === "better" ? "var(--green)" : undefined, whiteSpace: "nowrap" }}>{arrow[r.trend]}</td>
              </tr>
            ))}
            <tr>
              <td style={{ fontWeight: 600 }}>{t.tl_score}</td>
              {tl.scores.map((s) => <td key={s.fy} className="mono" style={{ textAlign: "center", fontWeight: 600 }}>{s.score}</td>)}
              <td />
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
