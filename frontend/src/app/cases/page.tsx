"use client";

import { useEffect, useState } from "react";
import { EvidenceDrawer } from "@/components/Evidence";
import { Warn } from "@/components/icons";
import { Term } from "@/components/Term";
import { getCases } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { Case } from "@/lib/types";

/** Backtest: what the checks found in a report filed BEFORE something went wrong. */
export default function CasesPage() {
  const { lang, t } = useLang();
  const hi = lang === "hi";
  const [cases, setCases] = useState<Case[] | null>(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    getCases().then(setCases).catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="wrap section" style={{ maxWidth: 940 }}>
      <p className="eyebrow">{t.nav_cases}</p>
      <h1 className="display h1" style={{ marginTop: 14 }}>
        {hi ? "क्या संकेत पहले से दिख रहे थे?" : "Were the signs there before the fall?"}
      </h1>
      <p className="lede" style={{ marginTop: 14 }}>
        {hi
          ? "ये उदाहरण के तौर पर केस स्टडी हैं, सांख्यिकीय बैकटेस्ट नहीं: हर मामले में हमने कंपनी की वह सालाना रिपोर्ट पढ़ी जो किसी बड़ी घटना से पहले छपी थी, और देखा कि हमारी 7 जाँचों में से कितनी ने संकेत दिया।"
          : "Illustrative case studies, not a statistical backtest: for each case we ran our seven checks on the annual report published before something went wrong, using only what was public at the time. Checks that did not fire are shown too."}{" "}
        <Term id="red-flag">{hi ? "चेतावनी संकेत" : "Warning signs"}</Term>{" "}
        {hi ? "गड़बड़ी का सबूत नहीं हैं।" : "are reasons to look closer, not proof."}
      </p>

      {err && <p className="error" style={{ marginTop: 20 }}>{err}</p>}
      {!cases && !err && <div className="skeleton" style={{ height: 220, marginTop: 28 }} />}
      {cases && cases.length === 0 && (
        <p className="muted" style={{ marginTop: 28 }}>
          {hi ? "अभी कोई मामला नहीं जोड़ा गया।" : "No cases added yet. Add a company's pre-event report and its event to report_sources.csv, then rebuild."}
        </p>
      )}

      <div className="stack gap-24" style={{ marginTop: 32 }}>
        {cases?.map((c) => (
          <article key={c.isin} className="ledger" style={{ padding: "22px 26px 26px" }}>
            <div className="row between gap-12" style={{ alignItems: "baseline" }}>
              <h2 className="display" style={{ fontSize: 30 }}>{c.name}</h2>
              <span className="mono muted" style={{ fontSize: 13 }}>{hi ? "रिपोर्ट" : "Report"} {c.fy}</span>
            </div>
            <div className="row gap-24" style={{ marginTop: 14, alignItems: "stretch" }}>
              <div style={{ flex: "1 1 240px" }}>
                <p className="mono red" style={{ margin: 0, fontSize: 12 }}>{hi ? "पहले: हमारी जाँच" : "BEFORE: WHAT OUR CHECKS FOUND"}</p>
                <p className="display red" style={{ fontSize: 46, margin: "4px 0 0", lineHeight: 1 }}>
                  {c.flags.length}<span style={{ fontSize: 22 }}> / {c.n_checks}</span>
                </p>
                <p className="muted" style={{ margin: "4px 0 0" }}>{hi ? "चेतावनी संकेत, हर एक पेज के साथ" : "warning signs, each with its page"}</p>
              </div>
              <div style={{ flex: "2 1 360px", borderLeft: "1px solid var(--border)", paddingLeft: 20 }}>
                <p className="mono" style={{ margin: 0, fontSize: 12, color: "var(--ink-2)" }}>{hi ? "बाद में" : "AFTER"} · {c.event.date}</p>
                <p style={{ margin: "6px 0 0", fontSize: 17 }}>{c.event.summary}</p>
                {c.event.source && (
                  <p className="hint" style={{ margin: "6px 0 0" }}>
                    <a href={c.event.source} target="_blank" rel="noopener noreferrer">{hi ? "स्रोत" : "Source"} ↗</a>
                  </p>
                )}
              </div>
            </div>
            {c.published && (
              <p className="mono" style={{ margin: "14px 0 0", fontSize: 13 }}>
                {hi ? "रिपोर्ट छपी" : "Report public"} {c.published} <span className="red">──{c.lead_months != null ? ` ${c.lead_months} ${hi ? "महीने पहले" : "months earlier"} ` : ""}──▶</span> {hi ? "घटना" : "Event"} {c.event.date}
              </p>
            )}
            <ul style={{ margin: "18px 0 0", paddingLeft: 0, listStyle: "none" }} className="stack gap-8">
              {c.flags.map((f) => (
                <li key={f.id} className="row gap-8" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
                  <span style={{ paddingTop: 4 }}><Warn color="var(--red)" /></span>
                  <span><strong style={{ fontWeight: 600 }}>{f.title[lang]}.</strong> <span className="muted">{f.summary[lang]}</span> {f.pages.length > 0 && <span className="mono hint">p. {f.pages.join(", ")}</span>}</span>
                </li>
              ))}
            </ul>
            {c.event.note && <p className="hint" style={{ margin: "10px 0 0" }}>ⓘ {c.event.note}</p>}
            {c.others && c.others.length > 0 && (
              <p className="hint" style={{ margin: "12px 0 0" }}>
                {hi ? "जो जाँचें नहीं लगीं" : "Checks that did not fire"}: {c.others.map((o) => `${o.title[lang]} (${o.status.replace("_", " ")})`).join(" · ")}
              </p>
            )}
            <button className="btn btn-sm" style={{ marginTop: 16 }} onClick={() => setOpen(c.isin)}>{t.open_evidence}</button>
          </article>
        ))}
      </div>

      <p className="hint" style={{ marginTop: 28 }}>
        {hi
          ? "यह पिछली घटनाओं पर जाँच है। चेतावनी संकेत वाली हर कंपनी गिरती नहीं, और हर गिरने वाली कंपनी में संकेत नहीं होते।"
          : "This is a look back at past events. Not every company with warning signs fails, and not every failure shows warning signs first."}
      </p>
      {open && <EvidenceDrawer isin={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
