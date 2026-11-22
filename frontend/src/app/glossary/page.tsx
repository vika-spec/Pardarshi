"use client";

import { useMemo, useState } from "react";
import { CATEGORIES, TERM_BY_ID, TERMS, type Category } from "@/lib/glossary";
import { useLang } from "@/lib/i18n";

export default function GlossaryPage() {
  const { lang } = useLang();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<Category | "all">("all");

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return TERMS.filter(
      (t) =>
        (cat === "all" || t.category === cat) &&
        (!needle || [t.term, t.hi, t.short.en, t.short.hi, t.more ?? ""].some((s) => s.toLowerCase().includes(needle))),
    );
  }, [q, cat]);

  const hi = lang === "hi";
  return (
    <div className="wrap section" style={{ maxWidth: 920 }}>
      <p className="eyebrow">{hi ? "शब्दकोश" : "Glossary"}</p>
      <h1 className="display h1" style={{ marginTop: 14 }}>{hi ? "हर शब्द, आसान भाषा में।" : "Every term, in plain words."}</h1>
      <p className="lede" style={{ marginTop: 14 }}>
        {hi
          ? "रिपोर्ट में रेखांकित किसी भी शब्द पर टैप करें, या यहाँ खोजें। हर शब्द की एक-लाइन परिभाषा शुरुआती लोगों के लिए है, और 'और जानें' विशेषज्ञों के लिए।"
          : "Tap any underlined word in your report, or search here. Each term has a one-line meaning for beginners and a 'more' section for experts."}
      </p>

      <div className="row gap-12" style={{ marginTop: 26 }}>
        <label htmlFor="g-search" className="sr-only">{hi ? "शब्द खोजें" : "Search terms"}</label>
        <input id="g-search" className="input" style={{ maxWidth: 360 }} placeholder={hi ? "खोजें: NAV, डायरेक्ट प्लान…" : "Search: NAV, direct plan, pledge…"} value={q} onChange={(e) => setQ(e.target.value)} />
        <span className="hint" aria-live="polite">{shown.length} {hi ? "शब्द" : "terms"}</span>
      </div>
      <div className="row gap-8" style={{ marginTop: 14 }} role="group" aria-label={hi ? "श्रेणी" : "Category"}>
        <button className="pill" aria-pressed={cat === "all"} onClick={() => setCat("all")}>{hi ? "सभी" : "All"}</button>
        {CATEGORIES.map((c) => (
          <button key={c.id} className="pill" aria-pressed={cat === c.id} onClick={() => setCat(c.id)}>{hi ? c.hi : c.en}</button>
        ))}
      </div>

      {CATEGORIES.filter((c) => shown.some((t) => t.category === c.id)).map((c) => (
        <section key={c.id} style={{ marginTop: 36 }} aria-labelledby={`cat-${c.id}`}>
          <h2 id={`cat-${c.id}`} className="display h2" style={{ fontSize: "1.8rem" }}>{hi ? c.hi : c.en}</h2>
          <dl style={{ margin: "12px 0 0", borderTop: "2px solid var(--ink)" }}>
            {shown.filter((t) => t.category === c.id).map((t) => (
              <div key={t.id} id={t.id} style={{ padding: "16px 0", borderBottom: "1px solid var(--rule)", scrollMarginTop: 20 }}>
                <dt style={{ fontWeight: 600, fontSize: "1.1rem" }}>
                  {t.term} <span lang="hi" className="muted" style={{ fontWeight: 400 }}>· {t.hi}</span>
                </dt>
                <dd style={{ margin: "6px 0 0" }}>
                  <p style={{ margin: 0 }}>{t.short[lang]}</p>
                  {t.example && <p className="callout" style={{ margin: "10px 0 0", fontSize: 15 }}><strong style={{ fontWeight: 600 }}>{hi ? "उदाहरण" : "Example"}:</strong> {t.example}</p>}
                  {t.more && (
                    <details className="working" style={{ marginTop: 6 }}>
                      <summary>{hi ? "और जानें" : "More detail"}</summary>
                      <p style={{ margin: "4px 0 0", color: "var(--ink-2)" }}>{t.more}</p>
                    </details>
                  )}
                  {t.related && (
                    <p className="hint" style={{ margin: "6px 0 0" }}>
                      {hi ? "संबंधित" : "See also"}:{" "}
                      {t.related.map((r, i) => (
                        <span key={r}>{i ? ", " : ""}<a href={`#${r}`}>{TERM_BY_ID[r]?.term ?? r}</a></span>
                      ))}
                    </p>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
      {shown.length === 0 && <p className="muted" style={{ marginTop: 30 }}>{hi ? "कोई शब्द नहीं मिला।" : "No terms match that search."}</p>}
    </div>
  );
}
