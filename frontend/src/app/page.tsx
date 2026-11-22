"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LedgerCard } from "@/components/LedgerCard";
import { StartPanel } from "@/components/StartPanel";
import { Lock } from "@/components/icons";
import Link from "next/link";
import { getSample } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { saveReport } from "@/lib/session";
import type { Report } from "@/lib/types";

export default function Home() {
  const { t } = useLang();
  const router = useRouter();
  const [sample, setSample] = useState<Report | null>(null);

  useEffect(() => {
    getSample().then(setSample).catch(() => {});
  }, []);

  const openSample = () => {
    if (sample) saveReport({ ...sample, label: sample.label || "Sample portfolio" });
    router.push(sample ? "/report" : "/report?sample=1");
  };

  return (
    <>
      <section className="wrap section row gap-32" style={{ alignItems: "center", paddingTop: "clamp(40px, 7vw, 80px)" }}>
        <div style={{ flex: "1 1 460px", minWidth: 0 }}>
          <p className="eyebrow" style={{ marginBottom: 20 }}>{t.eyebrow}</p>
          <h1 className="display h1">
            {t.hero_a}
            <span className="italic red">{t.hero_em}</span>
            {t.hero_b}
          </h1>
          <p className="lede" style={{ marginTop: 22 }}>{t.hero_sub}</p>
          <div className="row gap-12" style={{ marginTop: 30 }}>
            <a className="btn btn-primary" href="#start">{t.cta_start}</a>
            <button className="btn" onClick={openSample}>{t.cta_sample}</button>
          </div>
          <p className="row gap-8 muted" style={{ marginTop: 18, fontSize: 14 }}>
            <Lock color="var(--green)" /> {t.privacy_line}
          </p>
        </div>
        <div style={{ flex: "1 1 400px", minWidth: 0 }}>
          <LedgerCard report={sample} />
        </div>
      </section>

      <section className="wrap" aria-labelledby="new-here" style={{ paddingBottom: 8 }}>
        <div className="card" style={{ padding: "22px 26px" }}>
          <h2 id="new-here" className="h3">{t.new_here}</h2>
          <ol className="grid-3" style={{ listStyle: "none", padding: 0, margin: "14px 0 0", gap: 18 }}>
            {[t.new_1, t.new_2, t.new_3].map((s, i) => (
              <li key={i} className="row gap-12" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
                <span className="step-num" style={{ fontSize: "2rem" }} aria-hidden="true">{i + 1}</span>
                <span style={{ color: "var(--ink-2)" }}>{s}</span>
              </li>
            ))}
          </ol>
          <p className="row gap-16" style={{ margin: "16px 0 0" }}>
            <Link href="/guide">{t.read_guide} →</Link>
            <Link href="/glossary">{t.open_glossary} →</Link>
          </p>
        </div>
      </section>

      <section id="how" className="wrap section rule-top">
        <h2 className="display h2" style={{ marginBottom: 30 }}>{t.how_title}</h2>
        <div className="grid-3" style={{ borderTop: "2px solid var(--ink)", borderBottom: "1px solid var(--ink)" }}>
          {[
            ["01", t.col1_t, t.col1_d],
            ["02", t.col2_t, t.col2_d],
            ["03", t.col3_t, t.col3_d],
          ].map(([n, title, d], i) => (
            <div key={n} style={{ padding: "22px 22px 26px", borderLeft: i ? "1px solid var(--border)" : "none" }}>
              <p className="mono red" style={{ margin: 0, fontSize: 13 }}>COL. {n}</p>
              <h3 className="h3" style={{ margin: "10px 0 8px" }}>{title}</h3>
              <p className="muted" style={{ margin: 0, color: "var(--ink-2)" }}>{d}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="start" className="wrap section rule-top row gap-32" style={{ alignItems: "flex-start" }}>
        <div style={{ flex: "1 1 320px", minWidth: 0 }}>
          <h2 className="display h2">{t.start_title}</h2>
          <p className="lede" style={{ marginTop: 14 }}>{t.working_sub}</p>
        </div>
        <div style={{ flex: "2 1 520px", minWidth: 0 }}>
          <StartPanel />
        </div>
      </section>
    </>
  );
}
