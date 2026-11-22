"use client";

import { useEffect, useRef } from "react";
import { useLang } from "@/lib/i18n";
import { Close } from "./icons";

/** Accessible side panel: focus moves in, Esc closes, focus is restored, Tab is trapped. */
export function Drawer({ title, sub, onClose, children }: { title: React.ReactNode; sub?: React.ReactNode; onClose: () => void; children: React.ReactNode }) {
  const { t } = useLang();
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && ref.current) {
        const f = ref.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input, textarea, select, summary, [tabindex]:not([tabindex="-1"])');
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      prev?.focus?.();
    };
  }, [onClose]);

  return (
    <>
      <div className="scrim" onClick={onClose} aria-hidden="true" />
      <div ref={ref} className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <div className="drawer-head">
          <div style={{ minWidth: 0 }}>
            <h2 id="drawer-title" className="display" style={{ fontSize: 28, lineHeight: 1.15 }}>{title}</h2>
            {sub && <div className="muted" style={{ fontSize: 14, marginTop: 4 }}>{sub}</div>}
          </div>
          <button ref={closeRef} className="icon-btn" onClick={onClose} aria-label={t.close}><Close /></button>
        </div>
        <div className="drawer-body">{children}</div>
      </div>
    </>
  );
}
