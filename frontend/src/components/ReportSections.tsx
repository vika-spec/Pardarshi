"use client";

import { useState } from "react";
import { pct, roughCount, rupees, rupeesWords } from "@/lib/format";
import { fill, useLang } from "@/lib/i18n";
import type { Level, Report } from "@/lib/types";
import { Warn, Check as CheckIcon } from "./icons";
import { Term } from "./Term";
import { Working } from "./Working";

function SectionHead({ n, title, sub, plain, terms }: { n: string; title: string; sub: string; plain?: string; terms?: React.ReactNode }) {
  const { mode } = useLang();
  return (
    <div style={{ marginBottom: 22 }}>
      <p className="mono red" style={{ margin: 0, fontSize: 13 }}>COL. {n}</p>
      <h2 className="display h2" style={{ marginTop: 8 }}>{title}</h2>
      <p className="lede" style={{ marginTop: 10 }}>{sub}</p>
      {mode === "simple" && plain && <p className="callout" style={{ margin: "12px 0 0", maxWidth: 720 }}>{plain}</p>}
      {terms && <p className="hint" style={{ margin: "10px 0 0" }}>{terms}</p>}
    </div>
  );
}

/** A short "Words used here: …" line so beginners can tap each term. */
function Words({ ids }: { ids: string[] }) {
  const { lang } = useLang();
  return (
    <>
      {lang === "hi" ? "यहाँ इस्तेमाल शब्द: " : "Words used here: "}
      {ids.map((id, i) => (
        <span key={id}>{i ? " · " : ""}<Term id={id} /></span>
      ))}
    </>
  );
}

export function ModeToggle() {
  const { t, mode, setMode } = useLang();
  return (
    <div className="row gap-12 no-print">
      <span className="hint" id="mode-label">{t.mode_label}</span>
      <div className="seg" role="group" aria-labelledby="mode-label">
        <button aria-pressed={mode === "simple"} onClick={() => setMode("simple")}>{t.mode_simple}</button>
        <button aria-pressed={mode === "expert"} onClick={() => setMode("expert")}>{t.mode_expert}</button>
      </div>
      <span className="hint">{mode === "simple" ? t.mode_hint_simple : t.mode_hint_expert}</span>
    </div>
  );
}

export function SummaryLedger({ r }: { r: Report }) {
  const { t, lang } = useLang();
  const rows: [string, string, boolean][] = [
    [t.r_flags, `${r.risk.n_flags} · ${t.in_companies(r.risk.n_with_flags)}`, r.risk.n_flags > 0],
    [t.r_total, rupees(r.total_value), false],
    [t.r_funds, String(r.overlap.n_funds), false],
    [t.r_behave, t.funds_word(roughCount(r.overlap.effective_funds)), r.overlap.effective_funds < r.overlap.n_funds * 0.6],
    [fill(t.r_cost_years, { n: r.cost.years }), r.cost.n_regular ? rupeesWords(r.cost.projected_loss, lang) : "₹0", r.cost.projected_loss > 0],
  ];
  return (
    <div className="ledger" style={{ padding: "22px 28px 30px" }}>
      <dl style={{ margin: 0 }}>
        {rows.map(([k, v, hot]) => (
          <div className="ledger-row" key={k}>
            <dt>{k}</dt>
            <dd className={`mono ${hot ? "red" : ""}`} style={{ margin: 0, fontSize: 17 }}>{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function OwnSection({ r }: { r: Report }) {
  const { t, mode } = useLang();
  const [toggled, setToggled] = useState<boolean | null>(null);
  const asTable = toggled ?? mode === "expert";
  const setAsTable = (v: boolean) => setToggled(v);
  const top = r.exposure.top_stocks.slice(0, 10);
  const max = Math.max(...top.map((s) => s.pct_of_portfolio), 1);
  return (
    <section className="section rule-top" aria-labelledby="own-h">
      <SectionHead n="02" title={t.sec_own} sub={t.sec_own_sub(r.exposure.top10_pct)} plain={t.plain_own} terms={<Words ids={["exposure", "sector", "concentration", "weight"]} />} />
      <span id="own-h" className="sr-only">{t.sec_own}</span>
      <div className="row gap-32" style={{ alignItems: "flex-start" }}>
        <div style={{ flex: "2 1 480px", minWidth: 0 }}>
          <div className="row between" style={{ marginBottom: 10 }}>
            <span className="mono hint">TOP 10</span>
            <button className="link-btn" onClick={() => setAsTable(!asTable)} aria-pressed={asTable}>{asTable ? t.view_bars : t.view_table}</button>
          </div>
          {asTable ? (
            <div className="scroll-x">
              <table className="table">
                <thead><tr><th>{t.company}</th><th>{t.sector}</th><th className="num">{t.share}</th><th className="num">{t.amount}</th><th>{t.via_funds}</th></tr></thead>
                <tbody>
                  {top.map((s) => (
                    <tr key={s.isin}>
                      <td>{s.name}</td><td>{s.sector}</td><td className="num">{pct(s.pct_of_portfolio)}</td><td className="num">{rupees(s.rupees)}</td>
                      <td style={{ fontSize: 14 }}>{s.via.map((v) => v.fund).join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <ol style={{ listStyle: "none", padding: 0, margin: 0 }} className="stack gap-12">
              {top.map((s) => (
                <li key={s.isin}>
                  <div className="row between gap-8" style={{ fontSize: 15 }}>
                    <span>{s.name} <span className="hint">· {s.sector} · via {s.held_by_n_funds} {s.held_by_n_funds === 1 ? "fund" : "funds"}</span></span>
                    <span className="mono">{pct(s.pct_of_portfolio)}</span>
                  </div>
                  <div className="bar" style={{ marginTop: 6 }} aria-hidden="true"><span style={{ width: `${(s.pct_of_portfolio / max) * 100}%` }} /></div>
                </li>
              ))}
            </ol>
          )}
        </div>
        <div style={{ flex: "1 1 260px", minWidth: 0 }}>
          <p className="mono hint" style={{ margin: "0 0 10px" }}>{t.sectors.toUpperCase()}</p>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {r.exposure.sectors.slice(0, 8).map((s) => (
              <li key={s.sector} className="row between" style={{ borderBottom: "1px solid var(--rule)", padding: "8px 0" }}>
                <span>{s.sector}</span><span className="mono">{pct(s.pct_of_portfolio)}</span>
              </li>
            ))}
            {r.exposure.other_pct > 0.5 && (
              <li className="row between muted" style={{ padding: "8px 0" }}><span>Cash, bonds, other</span><span className="mono">{pct(r.exposure.other_pct)}</span></li>
            )}
          </ul>
        </div>
      </div>
      <Working w={r.exposure.working} open={mode === "expert"} />
    </section>
  );
}

export function OverlapSection({ r }: { r: Report }) {
  const { t, mode } = useLang();
  const o = r.overlap;
  const short = (s: string) => s.replace(/^Demo\s+/, "").replace(/\s+Fund\b/, "");
  return (
    <section className="section rule-top">
      <SectionHead n="03" title={t.sec_overlap} sub={t.sec_overlap_sub(o.n_funds, t.funds_word(roughCount(o.effective_funds)))} plain={t.plain_overlap} terms={<Words ids={["overlap", "behaves-like", "diversification"]} />} />
      {o.n_funds > 1 && mode === "expert" && (
        <div className="scroll-x">
          <table className="table" style={{ minWidth: 120 + o.n_funds * 90 }}>
            <caption className="sr-only">Overlap between each pair of funds, in percent</caption>
            <thead>
              <tr><th scope="col"><span className="sr-only">{t.fund}</span></th>{o.labels.map((l, j) => <th key={j} scope="col" className="num" style={{ fontSize: 11, textTransform: "none", letterSpacing: 0 }}>{short(l)}</th>)}</tr>
            </thead>
            <tbody>
              {o.matrix.map((row, i) => (
                <tr key={i}>
                  <th scope="row" style={{ fontSize: 13, textTransform: "none", letterSpacing: 0, borderBottom: "1px solid var(--rule)", fontFamily: "var(--f-body)", color: "var(--ink)" }}>{short(o.labels[i])}</th>
                  {row.map((v, j) => (
                    <td key={j} className="num" style={{ background: i === j ? "#efe8d6" : `rgba(163, 38, 42, ${Math.min(0.85, v / 100)})`, color: i !== j && v > 55 ? "#fff" : "var(--ink)", fontSize: 14 }}>
                      {i === j ? "—" : `${v.toFixed(0)}%`}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {o.pairs.length > 0 && (
        <ul style={{ margin: "20px 0 0", paddingLeft: 20 }}>
          {o.pairs.slice(0, 3).map((p) => (
            <li key={p.a + p.b} style={{ marginBottom: 6 }}>
              <strong style={{ fontWeight: 600 }}>{p.a}</strong> + <strong style={{ fontWeight: 600 }}>{p.b}</strong>: <span className="mono red">{p.overlap_pct.toFixed(0)}%</span> <span className="hint">· {p.shared_stocks} {t.shared.toLowerCase()}</span>
            </li>
          ))}
        </ul>
      )}
      <Working w={o.working} open={mode === "expert"} />
    </section>
  );
}

export function CostSection({ r, age, onAge, busy }: { r: Report; age: string; onAge: (a: string) => void; busy: boolean }) {
  const { t, lang, mode } = useLang();
  const c = r.cost;
  const rows = mode === "expert" ? c.rows : c.rows.filter((row) => row.projected_loss);
  return (
    <section className="section rule-top">
      <SectionHead n="04" title={t.sec_cost} sub={c.n_regular ? t.sec_cost_sub(rupeesWords(c.projected_loss, lang), c.years) : t.sec_cost_none} plain={t.plain_cost} terms={<Words ids={["ter", "regular-plan", "direct-plan", "commission", "compounding"]} />} />
      <div className="row gap-16 no-print" style={{ marginBottom: 18, alignItems: "flex-end" }}>
        <div className="field" style={{ width: 160 }}>
          <label htmlFor="age-in">{t.age_label}</label>
          <input id="age-in" className="input" inputMode="numeric" maxLength={2} value={age} onChange={(e) => onAge(e.target.value.replace(/\D/g, ""))} />
        </div>
        <p className="hint" style={{ margin: 0 }} aria-live="polite">{busy ? t.loading : `${t.years_label}: ${c.years} · assumed return ${c.gross_return_pct}% before costs`}</p>
      </div>
      <div className="scroll-x">
        <table className="table">
          <thead><tr><th>{t.fund}</th><th>{t.plan}</th><th className="num">{t.value}</th>{mode === "expert" && <th className="num">TER R / D</th>}<th className="num">{t.extra_cost}</th><th className="num">{t.loss}</th></tr></thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                <td>{row.fund}</td>
                <td>{row.plan === "direct" ? <span className="badge badge-green">{t.plan_direct}</span> : <span className="badge badge-amber">{t.plan_regular}</span>}</td>
                <td className="num">{rupees(row.value)}</td>
                {mode === "expert" && <td className="num">{row.ter_regular_pct ?? "–"}% / {row.ter_direct_pct ?? "–"}%</td>}
                <td className="num">{row.annual_cost_now ? rupees(row.annual_cost_now) : "–"}</td>
                <td className={`num ${row.projected_loss ? "red" : ""}`}>{row.projected_loss ? rupees(row.projected_loss) : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Working w={c.working} open={mode === "expert"} />
    </section>
  );
}

export function RiskSection({ r, onOpen }: { r: Report; onOpen: (isin: string) => void }) {
  const { t, lang } = useLang();
  const k = r.risk;
  return (
    <section className="section rule-top">
      <SectionHead n="01" title={t.sec_risk} sub={t.sec_risk_sub(k.n_checked, k.n_with_flags)} plain={t.plain_risk} terms={<Words ids={["red-flag", "annual-report", "auditor", "pledge", "rpt", "cfo", "verified-quote"]} />} />
      {k.money_flagged != null && k.money_flagged > 0 && (
        <p className="callout" style={{ margin: "0 0 14px", fontSize: 17, display: "flex", gap: 10, alignItems: "flex-start" }}>
          <span style={{ paddingTop: 3, flex: "none" }}><Warn color="var(--red)" /></span>
          <span>{t.money_flagged(rupees(k.money_flagged), pct(k.pct_flagged ?? 0))}</span>
        </p>
      )}
      <ScoreCard r={r} />
      <TrustStrip trust={k.trust} />
      <TopFlagged r={r} onOpen={onOpen} />
      <div className="card">
        {k.companies.map((c, i) => (
          <div key={c.isin} className="row gap-16" style={{ padding: "16px 20px", borderTop: i ? "1px solid var(--rule)" : "none", alignItems: "flex-start" }}>
            <span className={`status ${c.flags.length ? "status-flagged" : "status-passed"}`} style={{ width: 120, paddingTop: 3 }}>
              {c.flags.length ? <Warn color="var(--red)" /> : <CheckIcon color="var(--green)" />} {c.flags.length ? `${c.flags.length} ${t.flagged}` : t.passed}
            </span>
            <div style={{ flex: "1 1 280px", minWidth: 0 }}>
              <p style={{ margin: 0, fontWeight: 600 }}>{c.name} <span className="hint" style={{ fontWeight: 400 }}>· {pct(c.pct_of_portfolio)} of your money{c.fy ? ` · ${c.fy}` : ""}{c.report_date ? ` · ${t.published} ${c.report_date}` : ""}</span>
                {c.old_report && <span className="badge badge-amber" title={t.old_report_hint} style={{ marginLeft: 8 }}>{t.old_report}</span>}
              </p>
              {c.via && c.via.length > 0 && (
                <p className="hint" style={{ margin: "4px 0 0" }}>{t.held_through}: {c.via.join(", ")}</p>
              )}
              {c.event && (
                <p className="badge badge-red" style={{ margin: "6px 0 0" }}>{t.later_event} ({c.event.date}): {c.event.summary}</p>
              )}
              {c.flags.length > 0 ? (
                <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                  {c.flags.map((f) => <li key={f.id}><LevelBadge level={f.level} /> <span style={{ fontWeight: 500 }}>{f.title[lang]}.</span> <span className="muted">{f.summary[lang]}</span></li>)}
                </ul>
              ) : (
                <p className="muted" style={{ margin: "4px 0 0" }}>{t.checks_of(0, c.counts.passed ?? 0)}</p>
              )}
            </div>
            <button className="btn btn-sm" onClick={() => onOpen(c.isin)} aria-label={`${t.open_evidence}: ${c.name}`}>{t.open_evidence}</button>
          </div>
        ))}
      </div>
      {k.by_fund && k.by_fund.length > 0 && (
        <div style={{ marginTop: 22 }}>
          <h3 className="h3" style={{ margin: 0 }}>{t.by_fund_title}</h3>
          <p className="hint" style={{ margin: "4px 0 10px" }}>{t.by_fund_sub}</p>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }} className="stack gap-8">
            {k.by_fund.map((f) => (
              <li key={f.fund}>
                <div className="row between gap-8" style={{ fontSize: 15 }}>
                  <span>{f.fund}</span>
                  <span className="mono">{rupees(f.rupees)}{f.pct_of_fund != null && <span className="hint"> · {pct(f.pct_of_fund)} {t.of_fund}</span>}</span>
                </div>
                <div className="bar bar-red" style={{ marginTop: 5 }} aria-hidden="true"><span style={{ width: `${Math.min(100, (f.pct_of_fund ?? 0) * 3)}%` }} /></div>
              </li>
            ))}
          </ul>
        </div>
      )}
      {k.coverage_pct != null && <p className="hint" style={{ marginTop: 14 }}>{t.coverage_note(pct(k.coverage_pct), k.n_checked, k.n_checked + k.n_not_covered)}</p>}
      {k.n_not_covered > 0 && <p className="hint" style={{ marginTop: 6 }}>{t.not_covered(k.n_not_covered)}</p>}
      <p style={{ marginTop: 10 }}><a href="/cases">{t.cases_link}</a></p>
      <p className="hint" style={{ marginTop: 6 }}>{t.not_proof}</p>
    </section>
  );
}

export function TrustStrip({ trust }: { trust?: Report["risk"]["trust"] }) {
  const { t } = useLang();
  const lines: string[] = [];
  if (trust?.fakes_tried && trust.fakes_rejected_pct != null) lines.push(t.trust_fakes(trust.fakes_tried, `${trust.fakes_rejected_pct}%`));
  if (trust?.review_total) lines.push(t.trust_review(trust.review_agreed ?? 0, trust.review_total));
  if (trust?.labelled && trust.precision != null && trust.recall != null)
    lines.push(t.trust_acc(`${Math.round(trust.precision * 100)}%`, `${Math.round(trust.recall * 100)}%`, trust.labelled));
  if (!lines.length) return null;
  return (
    <div className="row gap-12" style={{ margin: "0 0 14px", padding: "10px 14px", border: "1px solid var(--rule)", borderRadius: 10, background: "var(--paper)", alignItems: "flex-start", flexWrap: "nowrap" }}>
      <span style={{ paddingTop: 2, flex: "none" }}><CheckIcon color="var(--green)" /></span>
      <p style={{ margin: 0, fontSize: 15 }}>{lines.join(" ")} <a href="/methodology">{t.trust_how} →</a></p>
    </div>
  );
}

export function LevelBadge({ level }: { level?: Level | null }) {
  const { t } = useLang();
  if (!level) return null;
  const style: Record<Level, React.CSSProperties> = {
    high: { background: "#f6e1de", color: "var(--red)" },
    moderate: { background: "#f8ecd2", color: "#8a5a00" },
    low: { background: "#eceae4", color: "#4b5160" },
  };
  const label = { high: t.lvl_high, moderate: t.lvl_moderate, low: t.lvl_low }[level];
  return <span className="mono" title={t.lvl_hint} style={{ ...style[level], fontSize: 11, padding: "2px 7px", borderRadius: 10, letterSpacing: "0.03em", whiteSpace: "nowrap" }}>{label.toUpperCase()}</span>;
}

export function ScoreCard({ r }: { r: Report }) {
  const { t } = useLang();
  const sc = r.risk.score;
  if (!sc) return null;
  const color = sc.band === "few" ? "var(--green)" : sc.band === "some" ? "#8a5a00" : "var(--red)";
  return (
    <div className="card" style={{ padding: "18px 20px", marginBottom: 14 }}>
      <div className="row gap-24" style={{ alignItems: "center" }}>
        <div style={{ minWidth: 150 }}>
          <p className="mono hint" style={{ margin: 0 }}>{t.score_title.toUpperCase()}</p>
          <p className="display" style={{ fontSize: 56, lineHeight: 1, margin: "4px 0 0", color }}>{sc.value}</p>
          <p className="hint" style={{ margin: "4px 0 0" }}>{t.score_of(sc.n_companies)}</p>
        </div>
        <div style={{ flex: "1 1 320px", minWidth: 0 }}>
          <p style={{ margin: 0, fontWeight: 600, color }}>{t.score_band[sc.band]}</p>
          <p style={{ margin: "4px 0 0", fontSize: 15 }}>{t.score_what}</p>
          <p className="hint" style={{ margin: "6px 0 0" }}>{t.score_cov(pct(sc.coverage_pct), sc.data_pct)}</p>
          {sc.lowest.some((l) => l.score < 100) && (
            <p className="hint" style={{ margin: "6px 0 0" }}>
              {t.score_lowest}: {sc.lowest.filter((l) => l.score < 100).map((l) => `${l.name} (${l.score})`).join(", ")}
            </p>
          )}
        </div>
      </div>
      <details className="working" style={{ marginTop: 10 }}>
        <summary>{t.score_how}</summary>
        <ol style={{ margin: "6px 0 0", paddingLeft: 20, fontSize: 14, lineHeight: 1.6 }}>
          <li>{t.score_how_1}</li>
          <li>{t.score_how_2}</li>
          <li>{t.score_how_3}</li>
        </ol>
        <p className="mono hint" style={{ margin: "6px 0 0", fontSize: 12, overflowWrap: "anywhere" }}>{sc.formula}</p>
      </details>
    </div>
  );
}

export function TopFlagged({ r, onOpen }: { r: Report; onOpen: (isin: string) => void }) {
  const { t } = useLang();
  const top = r.risk.top_flagged ?? [];
  if (!top.length) return null;
  return (
    <div style={{ margin: "0 0 14px" }}>
      <p className="mono hint" style={{ margin: "0 0 8px" }}>{t.top5_title.toUpperCase()}</p>
      <div className="row gap-8">
        {top.map((c) => (
          <button key={c.isin} className="card" onClick={() => onOpen(c.isin)} style={{ padding: "10px 14px", textAlign: "left", cursor: "pointer", flex: "1 1 160px", minWidth: 0 }}>
            <span style={{ display: "block", fontWeight: 600, fontSize: 15 }}>{c.name}</span>
            <span className="mono" style={{ display: "block", fontSize: 14 }}>{rupees(c.rupees)} · {pct(c.pct_of_portfolio)}</span>
            <span className="row gap-4" style={{ marginTop: 4, fontSize: 13 }}><Warn color="var(--red)" /> {c.n_flags} · {t.worst_level} <LevelBadge level={c.worst} /></span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function LookInto({ r }: { r: Report }) {
  const { t } = useLang();
  const items: string[] = [];
  for (const c of r.risk.companies.filter((c) => c.flags.length).slice(0, 2)) {
    const pages = Array.from(new Set(c.flags.flatMap((f) => f.pages ?? []))).sort((a, b) => a - b);
    items.push(t.look_flag(c.name, pages.join(", ") || "—"));
  }
  const top = r.overlap.pairs[0];
  if (top && top.overlap_pct >= 50) items.push(t.look_overlap(top.a, top.b, top.overlap_pct));
  if (r.cost.n_regular > 0) items.push(t.look_cost);
  if (!items.length) return null;
  return (
    <section className="navy" style={{ padding: "24px 28px", marginTop: 8 }}>
      <p className="mono" style={{ margin: 0, fontSize: 12, letterSpacing: "0.06em", color: "var(--navy-muted)", textTransform: "uppercase" }}>{t.look_into}</p>
      <ul style={{ margin: "10px 0 0", paddingLeft: 20, fontSize: 17, lineHeight: 1.7 }}>
        {items.map((s) => <li key={s}>{s}</li>)}
      </ul>
      <p className="muted" style={{ margin: "12px 0 0", fontSize: 14 }}>{t.not_advice}</p>
    </section>
  );
}
