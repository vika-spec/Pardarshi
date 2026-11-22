"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { TERM_BY_ID } from "@/lib/glossary";
import { useLang } from "@/lib/i18n";

/**
 * A word with a plain-language explanation one tap away.
 * <Term id="ter">expense ratio</Term> → dotted underline; click/Enter opens a small card.
 */
export function Term({ id, children }: { id: string; children?: React.ReactNode }) {
  const { lang, t } = useLang();
  const term = TERM_BY_ID[id];
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLSpanElement>(null);
  const pid = useId();

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!term) return <>{children}</>;
  const label = children ?? (lang === "hi" ? term.hi : term.term);

  return (
    <span ref={wrap} className="term-wrap">
      <button type="button" className="term" aria-expanded={open} aria-controls={pid} onClick={() => setOpen(!open)}>
        {label}
        <span className="term-q" aria-hidden="true">?</span>
        <span className="sr-only"> ({t.what_is_this})</span>
      </button>
      {open && (
        <span id={pid} role="note" className="term-card">
          <span className="term-card-title">{lang === "hi" ? `${term.hi} · ${term.term}` : term.term}</span>
          <span className="term-card-body">{term.short[lang]}</span>
          {term.example && <span className="term-card-ex">{t.example}: {term.example}</span>}
          <Link href={`/glossary#${term.id}`} className="term-card-link" onClick={() => setOpen(false)}>{t.more_in_glossary} →</Link>
        </span>
      )}
    </span>
  );
}
