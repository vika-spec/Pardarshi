"use client";

import { fill, useLang } from "@/lib/i18n";
import { roughCount, rupeesWords } from "@/lib/format";
import type { Report } from "@/lib/types";

export function LedgerCard({ report }: { report: Report | null }) {
  const { t, lang } = useLang();
  const rows: [string, string, boolean][] = report
    ? [
        [t.l_checked, String(report.risk.n_checked), false],
        [t.l_flags, `${report.risk.n_flags} · ${t.in_companies(report.risk.n_with_flags)}`, report.risk.n_flags > 0],
        [t.l_funds, String(report.overlap.n_funds), false],
        [t.l_behave, t.funds_word(roughCount(report.overlap.effective_funds)), true],
        [fill(t.l_cost, { n: report.cost.years }), rupeesWords(report.cost.projected_loss, lang), true],
      ]
    : [];

  return (
    <div className="ledger" style={{ padding: "26px 30px 38px" }} aria-busy={!report}>
      <div className="row between" style={{ minHeight: "var(--ledger-line)", alignItems: "baseline" }}>
        <span className="display" style={{ fontSize: 24 }}>{t.ledger_title}</span>
        <span className="mono muted" style={{ fontSize: 13 }}>{t.ledger_entry}</span>
      </div>
      {report ? (
        <dl style={{ margin: 0 }}>
          {rows.map(([k, v, hot]) => (
            <div className="ledger-row" key={k}>
              <dt style={{ fontSize: 16 }}>{k}</dt>
              <dd className={`mono ${hot ? "red" : ""}`} style={{ margin: 0, fontSize: 17 }}>{v}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <div className="stack gap-16" style={{ paddingTop: 12 }}>
          {[0, 1, 2, 3, 4].map((i) => <div key={i} className="skeleton" style={{ height: 22 }} />)}
          <span className="sr-only">{t.loading}</span>
        </div>
      )}
      <div className="stamp" style={{ position: "absolute", right: 20, bottom: -24, whiteSpace: "pre-line" }}>{t.stamp}</div>
    </div>
  );
}
