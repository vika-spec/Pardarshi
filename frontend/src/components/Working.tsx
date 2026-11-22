"use client";

import type { Working as W } from "@/lib/types";
import { useLang } from "@/lib/i18n";
import { Chevron } from "./icons";

/** "Show the working": formula, plain words, inputs and data source for a number. */
export function Working({ w, open = false }: { w: W; open?: boolean }) {
  const { t } = useLang();
  return (
    <details className="working" style={{ marginTop: 14 }} open={open} key={String(open)}>
      <summary><Chevron /> {t.show_working}</summary>
      <div className="navy" style={{ padding: "18px 22px", marginTop: 8 }}>
        <p className="mono" style={{ margin: 0, fontSize: 12, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--navy-muted)" }}>{t.formula}</p>
        <p className="mono" style={{ margin: "6px 0 0", fontSize: 16, lineHeight: 1.6, overflowWrap: "anywhere" }}>{w.formula}</p>
        <p style={{ margin: "12px 0 0", fontSize: 15, lineHeight: 1.6 }}><span className="muted">{t.in_words}: </span>{w.plain}</p>
        <p style={{ margin: "12px 0 0", paddingTop: 12, borderTop: "1px solid #3a4663", fontSize: 14, lineHeight: 1.6 }} className="muted">
          {t.inputs}: {w.inputs}
          <br />
          {t.source}: {w.source}
        </p>
      </div>
    </details>
  );
}
