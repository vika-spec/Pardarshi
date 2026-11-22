"use client";

import { useRef, useState } from "react";
import { streamChat } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { Report, CitationCheck } from "@/lib/types";
import { Drawer } from "./Drawer";
import { Send } from "./icons";

type Timing = { retrieval_ms?: number; first_token_ms?: number; writing_ms?: number; check_ms?: number; total_ms: number; provider?: string; passages?: number; words?: number; guard?: boolean; fallback?: boolean; cached?: boolean };
type Msg = { role: "user" | "bot"; text: string; mode?: string; sources?: { company: string; page: number; isin: string }[]; check?: CitationCheck;
  stage?: { stage: string; ms?: number; passages?: number; reports?: number; provider?: string }; timing?: Timing; guard?: string[] };

const MODEL: Record<string, string> = { groq: "Groq · gpt-oss-120b", gemini: "Gemini Flash-Lite", mistral: "Mistral", azure: "Azure OpenAI", ollama: "local model", openai: "AI model" };

/** What the copilot is doing right now, so the wait is never a blank spinner. */
function StageLine({ st, hi }: { st: NonNullable<Msg["stage"]>; hi: boolean }) {
  const text = {
    search: hi ? `${st.reports ?? ""} सालाना रिपोर्ट में खोज रहे हैं…` : `Searching ${st.reports ?? "the"} annual reports…`,
    read: hi ? `${st.passages} अंश मिले (${st.ms} ms) · AI पढ़ रहा है…` : `Found ${st.passages} passages in ${st.ms} ms · the AI is reading them…`,
    write: hi ? `${MODEL[st.provider ?? ""] ?? "AI"} लिख रहा है…` : `${MODEL[st.provider ?? ""] ?? "The AI"} is writing…`,
    check: hi ? "कोड हर स्रोत जाँच रहा है…" : "Code is checking every citation…",
  }[st.stage];
  return text ? <p className="hint" style={{ margin: "0 0 6px" }}><span className="pulse-dot" aria-hidden /> {text}</p> : null;
}

/** Where the time went: search (code), waiting for the model's first word, writing, checking (code). */
function TimeBar({ tm, hi }: { tm: Timing; hi: boolean }) {
  if (tm.guard) return <p className="hint" style={{ margin: "8px 0 0" }}>{hi ? `सुरक्षा नियम से तुरंत जवाब · ${tm.total_ms} ms · कोई AI कॉल नहीं` : `Answered by a guardrail in ${tm.total_ms} ms · no AI call`}</p>;
  if (tm.cached) return <p className="hint" style={{ margin: "8px 0 0" }}>{hi ? `पहले से जाँचा जवाब · ${tm.total_ms} ms · कोई नई AI कॉल नहीं` : `Already-checked answer reused in ${tm.total_ms} ms · no new AI call`}</p>;
  if (tm.fallback) return <p className="hint" style={{ margin: "8px 0 0" }}>{hi ? `खोज ${tm.retrieval_ms} ms` : `Search ${tm.retrieval_ms} ms · AI unavailable, showing passages`}</p>;
  const parts = [
    { k: hi ? "खोज (कोड)" : "Search (code)", v: tm.retrieval_ms ?? 0, c: "#2f6b3b" },
    { k: hi ? "AI सोच रहा" : "AI thinking", v: tm.first_token_ms ?? 0, c: "#9db3dc" },
    { k: hi ? "AI लिख रहा" : "AI writing", v: tm.writing_ms ?? 0, c: "#1f4f99" },
    { k: hi ? "जाँच (कोड)" : "Check (code)", v: tm.check_ms ?? 0, c: "#6aa577" },
  ];
  const total = Math.max(1, parts.reduce((a, p) => a + p.v, 0));
  return (
    <div style={{ marginTop: 10 }} aria-label={hi ? "समय कहाँ लगा" : "Where the time went"}>
      <div className="row between" style={{ fontSize: 12 }}>
        <span className="hint">{hi ? "समय कहाँ लगा" : "Where the time went"}</span>
        <span className="mono" style={{ fontSize: 12 }}>{(tm.total_ms / 1000).toFixed(1)} s{tm.provider ? ` · ${MODEL[tm.provider] ?? tm.provider}` : ""}{tm.words ? ` · ${tm.words} ${hi ? "शब्द" : "words"}` : ""}</span>
      </div>
      <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", margin: "4px 0", gap: 1 }}>
        {parts.map((p) => <div key={p.k} title={`${p.k}: ${p.v} ms`} style={{ flex: Math.max(p.v, total * 0.015), background: p.c }} />)}
      </div>
      <div className="row gap-12" style={{ fontSize: 11.5, flexWrap: "wrap" }}>
        {parts.map((p) => <span key={p.k} className="hint"><i style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: p.c, marginRight: 4 }} />{p.k} {p.v < 1000 ? `${p.v} ms` : `${(p.v / 1000).toFixed(1)} s`}</span>)}
      </div>
    </div>
  );
}

const GUARD_TEXT: Record<string, { en: string; hi: string }> = {
  removed_pan: { en: "PAN removed before anything was sent", hi: "भेजने से पहले PAN हटाया" },
  removed_phone: { en: "phone number removed", hi: "फ़ोन नंबर हटाया" },
  removed_email: { en: "email removed", hi: "ईमेल हटाया" },
  removed_folio: { en: "folio number removed", hi: "फ़ोलियो नंबर हटाया" },
  advice: { en: "buy/sell advice is not given", hi: "खरीद-बिक्री की सलाह नहीं दी जाती" },
  injection: { en: "instruction-like text ignored", hi: "निर्देश जैसा पाठ अनदेखा किया" },
  ip_budget: { en: "your free AI questions for today are used up", hi: "आज के आपके मुफ़्त AI सवाल पूरे हुए" },
  site_budget: { en: "today's free AI allowance is used up", hi: "आज की मुफ़्त AI सीमा पूरी हुई" },
};

/** Only anonymous numbers go to the chat: fund names, values and computed results. */
function slimPortfolio(r: Report) {
  return {
    total_value: r.total_value,
    funds: r.funds.map((f) => ({ name: f.name, plan: f.plan, value: f.value })),
    effective_funds: r.overlap.effective_funds,
    top_overlaps: r.overlap.pairs.slice(0, 3),
    top_stocks: r.exposure.top_stocks.slice(0, 8).map((s) => ({ name: s.name, pct: s.pct_of_portfolio })),
    commission_loss: r.cost.projected_loss,
    years: r.cost.years,
    flagged_companies: r.risk.companies.filter((c) => c.flags.length).map((c) => ({ name: c.name, flags: c.flags.map((f) => f.title.en) })),
  };
}

export function ChatDrawer({ report, onClose, onOpenEvidence }: { report: Report; onClose: () => void; onOpenEvidence: (isin: string) => void }) {
  const { t, lang } = useLang();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const live = useRef<HTMLDivElement>(null);
  const isins = report.risk.companies.map((c) => c.isin);
  const suggestions = [
    ...report.risk.companies.filter((c) => c.flags.length).slice(0, 2).map((c) => (lang === "hi" ? `${c.name} पर संकेत क्यों है?` : `Why is ${c.name} flagged?`)),
    lang === "hi" ? "मेरे फंड इतने एक जैसे क्यों हैं?" : "Why do my funds overlap so much?",
    lang === "hi" ? "कमीशन मुझे कितना महंगा पड़ रहा है?" : "How much is commission costing me?",
  ];

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setQ("");
    setBusy(true);
    setMsgs((m) => [...m, { role: "user", text: question }, { role: "bot", text: "" }]);
    const update = (fn: (b: Msg) => Msg) => setMsgs((m) => [...m.slice(0, -1), fn(m[m.length - 1])]);
    try {
      await streamChat(
        { question, isins, portfolio: slimPortfolio(report), lang },
        (tok) => update((b) => ({ ...b, text: b.text + tok })),
        (meta) => update((b) => ({ ...b, mode: meta.mode, sources: meta.sources })),
        undefined,
        (check) => update((b) => ({ ...b, check })),
        (ev, data) => {
          if (ev === "stage") update((b) => ({ ...b, stage: data as Msg["stage"] }));
          else if (ev === "timing") update((b) => ({ ...b, timing: data as unknown as Timing, stage: undefined }));
          else if (ev === "guard") update((b) => ({ ...b, guard: (data as { fired: string[] }).fired }));
        },
      );
    } catch (e) {
      update((b) => ({ ...b, text: e instanceof Error ? e.message : "Chat is unavailable right now." }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Drawer title={t.ask_title} sub={t.not_advice} onClose={onClose}>
      <div className="card" style={{ padding: "10px 14px", marginBottom: 14, borderLeft: "4px solid #1f4f99", borderRadius: 0, background: "#f7f9fd" }}>
        <p style={{ margin: 0, fontWeight: 600, fontSize: 14 }}>{lang === "hi" ? "पारदर्शी कोपायलट · सुरक्षा नियमों के साथ" : "Pardarshi copilot · with guardrails"}</p>
        <p className="hint" style={{ margin: "4px 0 0", fontSize: 13 }}>
          {lang === "hi"
            ? "केवल आपके पोर्टफ़ोलियो के आंकड़ों और रिपोर्ट के अंशों से जवाब · हर स्रोत कोड से जाँचा जाता है · PAN/फ़ोन/ईमेल AI तक नहीं जाते · खरीद-बिक्री की सलाह या कीमत का अनुमान नहीं"
            : "Answers only from your portfolio's numbers and the report passages · every citation checked by code · PAN, phone and email never reach the AI · no buy/sell advice or price predictions"}
        </p>
      </div>
      <div className="stack gap-12" ref={live} aria-live="polite">
        {msgs.length === 0 && (
          <div className="row gap-8">
            {suggestions.map((s) => <button key={s} className="pill" onClick={() => ask(s)}>{s}</button>)}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role === "user" ? "chat-user" : "chat-bot"}`}>
            {m.guard && m.guard.length > 0 && (
              <p className="hint" style={{ margin: "0 0 6px", color: "#8a5a00" }}>🛡 {lang === "hi" ? "सुरक्षा नियम" : "Guardrail"}: {m.guard.map((g) => GUARD_TEXT[g]?.[lang] ?? g).join(" · ")}</p>
            )}
            {m.mode === "fallback" && <p className="hint" style={{ margin: "0 0 8px" }}>{t.ai_off}</p>}
            {m.stage && busy && i === msgs.length - 1 && <StageLine st={m.stage} hi={lang === "hi"} />}
            {m.text || (busy && i === msgs.length - 1 && !m.stage ? <span className="hint">…</span> : null)}
            {m.check && (
              <p className="hint" style={{ margin: "8px 0 0", color: m.check.total && m.check.ok === m.check.total ? "var(--green)" : undefined }}>
                {m.check.total === 0 ? t.cite_none : m.check.ok === m.check.total ? `✓ ${t.cite_ok(m.check.ok, m.check.total)}` : `⚠ ${t.cite_bad(m.check.total - m.check.ok)}`}
              </p>
            )}
            {m.timing && <TimeBar tm={m.timing} hi={lang === "hi"} />}
            {m.sources && m.sources.length > 0 && (
              <div style={{ marginTop: 10, fontSize: 14 }}>
                <span className="hint">{t.sources}: </span>
                {Array.from(new Map(m.sources.map((s) => [`${s.isin}-${s.page}`, s])).values()).slice(0, 4).map((s) => (
                  <button key={`${s.isin}-${s.page}`} className="link-btn" style={{ marginRight: 10 }} onClick={() => onOpenEvidence(s.isin)}>
                    {s.company}, p. {s.page}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <form
        className="row gap-8"
        style={{ marginTop: 18, flexWrap: "nowrap" }}
        onSubmit={(e) => {
          e.preventDefault();
          ask(q);
        }}
      >
        <label htmlFor="chat-q" className="sr-only">{t.ask_title}</label>
        <input id="chat-q" className="input" placeholder={t.ask_ph} value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} />
        <button className="btn btn-primary" type="submit" disabled={busy || q.trim().length < 2} aria-label={t.ask}><Send /></button>
      </form>
    </Drawer>
  );
}
