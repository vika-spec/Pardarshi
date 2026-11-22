"use client";

import { useEffect, useState } from "react";
import { getMethodology } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { Benchmark, Methodology } from "@/lib/types";

export default function MethodologyPage() {
  const { t, lang } = useLang();
  const [m, setM] = useState<Methodology | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    getMethodology().then(setM).catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="wrap section" style={{ maxWidth: 900 }}>
      <p className="eyebrow">{t.nav_method}</p>
      <h1 className="display h1" style={{ marginTop: 14 }}>How every number is made.</h1>
      <p className="lede" style={{ marginTop: 16 }}>
        Pardarshi is built so you never have to trust it blindly. Every rule, formula and data source is listed here. The code is open source.
      </p>
      {err && <p className="error">{err}</p>}
      {!m && !err && <div className="skeleton" style={{ height: 300, marginTop: 30 }} />}
      {m && (
        <>
          <h2 className="display h2" style={{ marginTop: 48 }}>{t.acc_title}</h2>
          {m.accuracy ? (
            <>
              <div className="grid-3" style={{ gap: 14, marginTop: 16 }}>
                {([
                  ["Flag precision", m.accuracy.flag_precision, "Of the checks we flagged, how many a human reviewer also flagged"],
                  ["Flag recall", m.accuracy.flag_recall, "Of the problems a human found, how many we flagged"],
                  ["Evidence verified", m.accuracy.evidence_verified_rate, "Quotes found word for word on the cited page"],
                  ["Coverage", m.accuracy.coverage, "Checks that gave an answer instead of 'not found'"],
                  ["Flag F1", m.accuracy.flag_f1 ?? null, "Balance of precision and recall"],
                  ["Missed warnings", m.accuracy.false_negative_rate ?? null, "Of the problems a human found, how many we did not flag (incl. not found)"],
                  ["1 · Retrieval", m.accuracy.retrieval_hit_rate ?? null, "The page with the answer was among the passages the AI read"],
                  ["2 · Right page cited", m.accuracy.evidence_page_accuracy ?? null, "When we answered, we cited the page the human found"],
                ] as const).map(([k, v, d]) => (
                  <div key={k} className="card" style={{ padding: "16px 18px" }}>
                    <p className="mono hint" style={{ margin: 0 }}>{k.toUpperCase()}</p>
                    <p className="display" style={{ fontSize: 40, margin: "4px 0 0", lineHeight: 1 }}>{v == null ? "–" : `${Math.round(v * 100)}%`}</p>
                    <p className="hint" style={{ margin: "6px 0 0" }}>{d}</p>
                  </div>
                ))}
              </div>
              {m.accuracy.examples && m.accuracy.examples.length > 0 && (
                <div className="card" style={{ padding: "14px 18px", marginTop: 14 }}>
                  <p style={{ margin: 0, fontWeight: 600 }}>{t.acc_errors}: {m.accuracy.false_positives ?? 0} {t.acc_fp}, {m.accuracy.false_negatives ?? 0} {t.acc_fn}</p>
                  <table className="table" style={{ marginTop: 8 }}>
                    <thead><tr><th>Company</th><th>Check</th><th>Human</th><th>App</th><th /></tr></thead>
                    <tbody>
                      {m.accuracy.examples.map((e, i) => (
                        <tr key={i}><td>{e.company}</td><td className="mono">{e.check}</td><td>{e.human}</td><td>{e.app}</td>
                          <td className={e.kind === "missed" ? "" : "red"}>{e.kind}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="hint" style={{ marginTop: 10 }}>Measured stage by stage (retrieval → cited page → final verdict) on {m.accuracy.labelled_checks} hand-labelled checks{m.accuracy.evaluated_at ? `, ${m.accuracy.evaluated_at}` : ""}. Script: pipelines/evaluate_flags.py.</p>
            </>
          ) : (
            <p className="muted" style={{ marginTop: 10 }}>Not measured on this dataset yet. Run pipelines/evaluate_flags.py after hand-labelling a sample of checks.</p>
          )}

          {m.figures && m.figures.compared > 0 && (
            <>
              <h2 className="display h2" style={{ marginTop: 48 }}>Figures checked against an independent source</h2>
              <p className="muted">
                Every figure we extracted (revenue, profit, operating cash flow, equity) that has a public reference was compared with {m.figures.source}.
                A figure matches if, after converting its unit (crore, lakh, million, thousand or rupees), it is within 2%.
              </p>
              <p className="display" style={{ fontSize: 44, margin: "8px 0 0" }}>
                {m.figures.matched} <span style={{ fontSize: 22 }}>of {m.figures.compared} figures are real published figures</span>
              </p>
              <table className="numbers" style={{ marginTop: 12 }}>
                <tbody>
                  {m.figures.rows.map((r, i) => (
                    <tr key={i}>
                      <td>{r.company}</td><td>{r.figure.replace("_", " ")}</td>
                      <td className="num">{r.result.startsWith("match") ? "✓" : "✗"} {r.result === "match (other basis)" ? "(other basis)" : r.unit ? `(${r.unit})` : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="hint">Checked {m.figures.checked_at}. Mismatches are shown, not hidden. Script: pipelines/check_figures.py.</p>
            </>
          )}

          {m.ai_pipeline && (
            <>
              <h2 className="display h2" style={{ marginTop: 48 }}>How the AI works</h2>
              <p className="muted">The AI finds and reads. Code decides, proves and measures. Each step below is labelled with who does it.</p>
              <ol className="stack gap-8" style={{ listStyle: "none", padding: 0, margin: "16px 0 0" }}>
                {m.ai_pipeline.map((s, i) => (
                  <li key={s.step} className="card row gap-16" style={{ padding: "12px 16px", alignItems: "flex-start", flexWrap: "nowrap" }}>
                    <span className="mono hint" style={{ minWidth: 24 }}>{String(i + 1).padStart(2, "0")}</span>
                    <span className="mono" style={{ minWidth: 52, fontSize: 12, padding: "2px 8px", borderRadius: 10, textAlign: "center",
                      background: s.who === "AI" ? "#e8eefb" : "var(--green-tint)", color: s.who === "AI" ? "#2a4a8a" : "var(--green)" }}>{s.who.toUpperCase()}</span>
                    <span><strong>{s.step}.</strong> {s.text}</span>
                  </li>
                ))}
              </ol>
            </>
          )}

          <h2 className="display h2" style={{ marginTop: 48 }}>Tested: honesty, failure and speed</h2>
          {m.benchmark ? <BenchmarkView b={m.benchmark} /> : (
            <p className="muted" style={{ marginTop: 10 }}>Not run on this dataset yet. Run <span className="mono">python -m pipelines.benchmark --live</span>.</p>
          )}

          {m.limitations && m.limitations.length > 0 && (
            <>
              <h2 className="display h2" style={{ marginTop: 48 }}>What it can&apos;t do (yet)</h2>
              <ul style={{ paddingLeft: 22, fontSize: 17, lineHeight: 1.8 }}>{m.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
            </>
          )}

          <h2 className="display h2" style={{ marginTop: 48 }}>Principles</h2>
          <ol style={{ paddingLeft: 22, fontSize: 17, lineHeight: 1.8 }}>{m.principles.map((p) => <li key={p}>{p}</li>)}</ol>

          <h2 className="display h2" style={{ marginTop: 40 }}>Formulas</h2>
          <dl className="card" style={{ padding: "8px 22px", margin: "16px 0 0" }}>
            {Object.entries(m.formulas).map(([k, v]) => (
              <div key={k} style={{ padding: "12px 0", borderBottom: "1px solid var(--rule)" }}>
                <dt style={{ fontWeight: 600, textTransform: "capitalize" }}>{k.replace("_", " ")}</dt>
                <dd className="mono" style={{ margin: "4px 0 0", fontSize: 15, overflowWrap: "anywhere" }}>{v}</dd>
              </div>
            ))}
          </dl>

          <h2 className="display h2" style={{ marginTop: 40 }}>The seven warning-sign checks</h2>
          <p className="muted">Each check reads the company&apos;s annual report. Figures are extracted with their page numbers, the rule below is applied by code, and a flag is shown only if its quote is found on the cited page.</p>
          <div className="stack gap-12" style={{ marginTop: 16 }}>
            {m.checks.map((c, i) => (
              <article key={c.id} className="card" style={{ padding: "16px 20px" }}>
                <p className="mono red" style={{ margin: 0, fontSize: 13 }}>CHECK {String(i + 1).padStart(2, "0")} · {c.kind === "numeric" ? "calculated" : "read"} · {c.severity} weight</p>
                <h3 className="h3" style={{ marginTop: 6 }}>{c.title[lang]}</h3>
                <p style={{ margin: "6px 0 0" }}>{c.what[lang]}</p>
                <p className="muted" style={{ margin: "8px 0 0", fontSize: 15 }}><strong style={{ fontWeight: 600 }}>{t.rule}:</strong> {c.rule}</p>
              </article>
            ))}
          </div>

          <h2 className="display h2" style={{ marginTop: 40 }}>Data</h2>
          <ul style={{ fontSize: 16, lineHeight: 1.8, paddingLeft: 20 }}>
            <li>Fund holdings: {m.dataset.holdings_source}</li>
            <li>Expense ratios: {m.dataset.ter_source}</li>
            <li>Dataset built: {m.dataset.built_at}</li>
            <li>Annual reports: the companies&apos; own filings; page numbers refer to the PDF page.</li>
            <li>AI providers in use: {m.ai_providers.length ? m.ai_providers.join(", ") : "none (template answers only)"}</li>
          </ul>
          {m.dataset.notice && <p className="banner" style={{ padding: "10px 14px", borderRadius: 4 }}>{m.dataset.notice}</p>}

          <h2 className="display h2" style={{ marginTop: 40 }}>Known limits</h2>
          <ul style={{ fontSize: 16, lineHeight: 1.8, paddingLeft: 20 }}>
            <li>Holdings are monthly disclosures, so they can be up to a few weeks old.</li>
            <li>Cost projections assume one constant return and ignore future SIPs and taxes.</li>
            <li>Only companies whose annual reports we have processed get a scorecard; we say so for the rest.</li>
            <li>Pattern-matching extraction (used when no AI model is configured) can miss figures in unusual layouts; such checks show as &quot;not found&quot;, never as passed.</li>
          </ul>
        </>
      )}
    </div>
  );
}


function Stat({ k, v, d }: { k: string; v: string; d: string }) {
  return (
    <div className="card" style={{ padding: "16px 18px" }}>
      <p className="mono hint" style={{ margin: 0 }}>{k.toUpperCase()}</p>
      <p className="display" style={{ fontSize: 34, margin: "4px 0 0", lineHeight: 1.05 }}>{v}</p>
      <p className="hint" style={{ margin: "6px 0 0" }}>{d}</p>
    </div>
  );
}

function BenchmarkView({ b }: { b: Benchmark }) {
  const cg = b.citation_guard;
  const fbOk = b.fallbacks.filter((f) => f.ok).length + (b.chat_without_ai.streamed_answer && b.chat_without_ai.mode_fallback ? 1 : 0);
  const fbAll = b.fallbacks.length + 1;
  const speed = Object.entries(b.api_speed);
  return (
    <>
      <div className="grid-3" style={{ gap: 14, marginTop: 16 }}>
        <Stat k="Made-up quotes caught" v={cg.tampered_rejected_pct == null ? "–" : `${cg.tampered_rejected_pct}%`}
          d={`${cg.tampered_quotes} quotes tampered on purpose (a changed number, the wrong page, an invented sentence). Every one must be rejected.`} />
        <Stat k="Real quotes accepted" v={cg.genuine_accepted_pct == null ? "–" : `${cg.genuine_accepted_pct}%`}
          d={`${cg.genuine_quotes} quotes from the reports, re-checked word for word against their page.`} />
        <Stat k="Failure drills passed" v={`${fbOk} / ${fbAll}`}
          d="AI provider down, rate-limited, timing out or replying garbage: the app moves to the next one, and still answers when all are down." />
      </div>
      <details className="card" style={{ padding: "12px 18px", marginTop: 14 }}>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>Details: drills, speed{b.live_ai ? ", live AI" : ""}</summary>
        <table className="table" style={{ marginTop: 10, width: "100%" }}>
          <tbody>
            {b.fallbacks.map((f) => (
              <tr key={f.case}><td>{f.ok ? "✓" : "✗"} {f.case}</td><td className="mono" style={{ textAlign: "right" }}>{f.ms} ms</td></tr>
            ))}
            <tr><td>{b.chat_without_ai.streamed_answer ? "✓" : "✗"} Chat answers from saved findings with no AI at all</td><td /></tr>
            {speed.map(([k, v]) => (
              <tr key={k}><td>{k}</td><td className="mono" style={{ textAlign: "right" }}>p50 {v.p50_ms} ms · p95 {v.p95_ms} ms</td></tr>
            ))}
            {(b.live_ai || []).map((r) => (
              <tr key={r.provider}><td>Live AI: {r.provider} <span className="hint">({r.model})</span></td>
                <td className="mono" style={{ textAlign: "right" }}>first word {r.first_word_ms ?? "–"} ms · full {r.total_ms ?? "–"} ms</td></tr>
            ))}
          </tbody>
        </table>
        <p className="hint" style={{ marginTop: 8 }}>
          Speed is measured inside the server, without network time. {b.coverage.companies_checked} of {b.coverage.companies_held} held companies have warning-sign checks.
          Run on {b.generated_at.slice(0, 10)}. Script: pipelines/benchmark.py.
        </p>
      </details>
    </>
  );
}
