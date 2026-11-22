"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { analyzeCas, analyzeManual, ApiError, searchFunds, type ManualHolding } from "@/lib/api";
import { rupees } from "@/lib/format";
import { useLang } from "@/lib/i18n";
import { saveReport } from "@/lib/session";
import type { FundHit, Report } from "@/lib/types";
import { Lock, Upload } from "./icons";
import { Term } from "./Term";

type Tab = "upload" | "pick" | "paste";

export function StartPanel() {
  const { t } = useLang();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("upload");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [age, setAge] = useState("");
  const errRef = useRef<HTMLDivElement>(null);
  const ids = useId();

  useEffect(() => {
    if (error) errRef.current?.focus();
  }, [error]);

  async function run(fn: () => Promise<Report>) {
    setError("");
    setBusy(true);
    try {
      const report = await fn();
      saveReport(report);
      router.push("/report");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
      setBusy(false);
    }
  }
  const ageNum = age ? Math.min(90, Math.max(16, parseInt(age, 10) || 0)) || undefined : undefined;

  const tabs: [Tab, string][] = [
    ["upload", t.tab_upload],
    ["pick", t.tab_pick],
    ["paste", t.tab_paste],
  ];

  return (
    <div className="card" style={{ padding: "clamp(18px, 3vw, 30px)" }}>
      <div role="tablist" aria-label={t.start_title} className="row gap-8" style={{ marginBottom: 22 }}>
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" id={`${ids}-${k}`} aria-selected={tab === k} aria-controls={`${ids}-panel`} className="pill" onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`${ids}-panel`} aria-labelledby={`${ids}-${tab}`}>
        {tab === "upload" && <UploadForm busy={busy} onSubmit={(f, pw) => run(() => analyzeCas(f, pw, ageNum))} onError={setError} />}
        {tab === "pick" && <PickForm busy={busy} onSubmit={(h) => run(() => analyzeManual(h, ageNum))} onError={setError} />}
        {tab === "paste" && <PasteForm busy={busy} onSubmit={(h) => run(() => analyzeManual(h, ageNum))} onError={setError} />}
      </div>

      <div className="field" style={{ marginTop: 18, maxWidth: 220 }}>
        <label htmlFor={`${ids}-age`}>{t.age_label}</label>
        <input id={`${ids}-age`} className="input" inputMode="numeric" pattern="[0-9]*" maxLength={2} value={age} onChange={(e) => setAge(e.target.value.replace(/\D/g, ""))} aria-describedby={`${ids}-agehint`} />
        <span id={`${ids}-agehint`} className="hint">{t.age_hint}</span>
      </div>

      {error && (
        <div ref={errRef} tabIndex={-1} role="alert" className="error" style={{ marginTop: 16 }}>{error}</div>
      )}
      <p className="row gap-8 hint" style={{ marginTop: 16, marginBottom: 0 }}>
        <Lock color="var(--green)" /> {t.privacy_line}
      </p>
    </div>
  );
}

function UploadForm({ busy, onSubmit, onError }: { busy: boolean; onSubmit: (f: File, pw: string) => void; onError: (s: string) => void }) {
  const { t } = useLang();
  const [file, setFile] = useState<File | null>(null);
  const [pw, setPw] = useState("");
  const [show, setShow] = useState(false);
  const id = useId();
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!file) return onError(t.err_no_file);
        onSubmit(file, pw);
      }}
      className="stack gap-16"
    >
      <div className="field">
        <label htmlFor={`${id}-f`}>{t.upload_label} <Term id="cas" /></label>
        <label
          htmlFor={`${id}-f`}
          className="row gap-12"
          style={{ border: "2px dashed var(--border)", borderRadius: 4, padding: "18px 16px", cursor: "pointer", background: "#fff" }}
        >
          <Upload color="var(--red)" />
          <span>{file ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB` : t.upload_hint}</span>
        </label>
        <input id={`${id}-f`} type="file" accept="application/pdf,.pdf" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </div>
      <div className="field">
        <label htmlFor={`${id}-pw`}>{t.password_label}</label>
        <div className="row gap-8" style={{ flexWrap: "nowrap" }}>
          <input id={`${id}-pw`} className="input" type={show ? "text" : "password"} autoComplete="off" value={pw} onChange={(e) => setPw(e.target.value)} aria-describedby={`${id}-pwh`} />
          <button type="button" className="btn btn-sm" onClick={() => setShow(!show)} aria-pressed={show}>{show ? "Hide" : "Show"}</button>
        </div>
        <span id={`${id}-pwh`} className="hint">{t.password_hint}</span>
      </div>
      <details className="working">
        <summary>{t.get_cas}</summary>
        <ol style={{ margin: "6px 0 0", paddingLeft: 20, lineHeight: 1.7 }}>
          {t.get_cas_steps.map((s) => <li key={s}>{s}</li>)}
        </ol>
      </details>
      <div>
        <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? t.analysing : t.analyse}</button>
      </div>
    </form>
  );
}

type Picked = { fund: FundHit; value: number; plan: "direct" | "regular" };

function PickForm({ busy, onSubmit, onError }: { busy: boolean; onSubmit: (h: ManualHolding[]) => void; onError: (s: string) => void }) {
  const { t } = useLang();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<FundHit[]>([]);
  const [chosen, setChosen] = useState<FundHit | null>(null);
  const [amount, setAmount] = useState("");
  const [plan, setPlan] = useState<"direct" | "regular">("regular");
  const [list, setList] = useState<Picked[]>([]);
  const [searchErr, setSearchErr] = useState("");
  const id = useId();

  const searching = !chosen && q.trim().length >= 2;
  useEffect(() => {
    if (!searching) return;
    const h = setTimeout(() => {
      searchFunds(q)
        .then((r) => {
          setHits(r);
          setSearchErr("");
        })
        .catch(() => setSearchErr("Search is unavailable right now. Try the paste option."));
    }, 220);
    return () => clearTimeout(h);
  }, [q, searching]);
  const visible = searching ? hits : [];

  const add = () => {
    const v = parseFloat(amount.replace(/,/g, ""));
    if (!chosen || !(v > 0)) return onError(t.err_no_funds);
    setList([...list, { fund: chosen, value: v, plan }]);
    setChosen(null);
    setQ("");
    setAmount("");
  };

  return (
    <div className="stack gap-16">
      <div className="field" style={{ position: "relative" }}>
        <label htmlFor={`${id}-q`}>{t.search_label}</label>
        <input
          id={`${id}-q`}
          className="input"
          role="combobox"
          aria-expanded={visible.length > 0}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          placeholder={t.search_ph}
          value={chosen ? chosen.name : q}
          onChange={(e) => {
            setChosen(null);
            setQ(e.target.value);
          }}
        />
        {visible.length > 0 && (
          <ul id={`${id}-list`} role="listbox" className="card" style={{ listStyle: "none", margin: 0, padding: 4, position: "absolute", top: "100%", left: 0, right: 0, zIndex: 10, maxHeight: 280, overflowY: "auto" }}>
            {visible.map((h) => (
              <li key={h.scheme_id} role="option" aria-selected={false}>
                <button type="button" onClick={() => { setChosen(h); setHits([]); }} style={{ width: "100%", textAlign: "left", background: "none", border: "none", padding: "10px 12px", cursor: "pointer", minHeight: 44 }}>
                  <span style={{ display: "block", fontWeight: 500 }}>{h.name}</span>
                  <span className="hint">{h.amc} · {h.category}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {searchErr && <span className="hint red">{searchErr}</span>}
      </div>
      <div className="row gap-16" style={{ alignItems: "flex-end" }}>
        <div className="field" style={{ flex: "1 1 160px" }}>
          <label htmlFor={`${id}-a`}>{t.amount_label}</label>
          <input id={`${id}-a`} className="input" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} aria-describedby={`${id}-ah`} />
          <span id={`${id}-ah`} className="hint">{t.value_hint}</span>
        </div>
        <fieldset className="row gap-8" style={{ border: "none", padding: 0, margin: 0 }}>
          <legend className="hint" style={{ padding: 0, marginBottom: 4 }}>{t.plan_label} (<Term id="direct-plan">{t.plan_direct}</Term> / <Term id="regular-plan">{t.plan_regular}</Term>)</legend>
          {(["regular", "direct"] as const).map((p) => (
            <button key={p} type="button" className="pill" aria-pressed={plan === p} onClick={() => setPlan(p)}>
              {p === "direct" ? t.plan_direct : t.plan_regular}
            </button>
          ))}
        </fieldset>
        <button type="button" className="btn btn-sm" onClick={add}>{t.add}</button>
      </div>

      <div>
        <p style={{ margin: "0 0 6px", fontWeight: 500 }}>{t.your_funds}</p>
        {list.length === 0 ? (
          <p className="hint" style={{ margin: 0 }}>{t.none_yet}</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {list.map((p, i) => (
              <li key={i} className="row between gap-8" style={{ borderBottom: "1px solid var(--rule)", padding: "8px 0" }}>
                <span>{p.fund.name} <span className="hint">· {p.plan === "direct" ? t.plan_direct : t.plan_regular}</span></span>
                <span className="row gap-12"><span className="mono">{rupees(p.value)}</span>
                  <button className="link-btn" onClick={() => setList(list.filter((_, j) => j !== i))}>{t.remove}<span className="sr-only"> {p.fund.name}</span></button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <button className="btn btn-primary" disabled={busy} onClick={() => (list.length ? onSubmit(list.map((p) => ({ scheme_id: p.fund.scheme_id, plan: p.plan, value: p.value }))) : onError(t.err_no_funds))}>
          {busy ? t.analysing : t.analyse}
        </button>
      </div>
    </div>
  );
}

export function parsePasted(text: string): ManualHolding[] {
  const out: ManualHolding[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    const m = line.match(/^(.*?)(?:[\s,;:\t]|₹|Rs\.?)*([\d,]+(?:\.\d+)?)\s*$/);
    if (!m) continue;
    const name = m[1].replace(/[,;:\t₹]+$/g, "").trim();
    const value = parseFloat(m[2].replace(/,/g, ""));
    if (name.length >= 3 && value > 0) out.push({ name, value });
  }
  return out;
}

function PasteForm({ busy, onSubmit, onError }: { busy: boolean; onSubmit: (h: ManualHolding[]) => void; onError: (s: string) => void }) {
  const { t } = useLang();
  const [text, setText] = useState("");
  const id = useId();
  return (
    <form
      className="stack gap-16"
      onSubmit={(e) => {
        e.preventDefault();
        const h = parsePasted(text);
        if (!h.length) return onError(t.err_paste);
        onSubmit(h);
      }}
    >
      <div className="field">
        <label htmlFor={`${id}-t`}>{t.paste_label}</label>
        <textarea id={`${id}-t`} className="input" placeholder={t.paste_ph} value={text} onChange={(e) => setText(e.target.value)} aria-describedby={`${id}-h`} />
        <span id={`${id}-h`} className="hint">{t.paste_hint}</span>
      </div>
      <div>
        <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? t.analysing : t.analyse}</button>
      </div>
    </form>
  );
}
