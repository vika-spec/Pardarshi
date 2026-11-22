import { useMemo, useSyncExternalStore } from "react";
import type { Report } from "./types";

/**
 * The report lives only in this browser tab (sessionStorage): it disappears
 * when the tab closes and is never sent anywhere else. It holds no name, PAN
 * or folio number: the server strips those before building the report.
 */
const KEY = "pardarshi:report";
const EVT = "pardarshi:report-changed";
let memory: string | null = null; // fallback when storage is blocked

function read(): string | null {
  try {
    return sessionStorage.getItem(KEY) ?? memory;
  } catch {
    return memory;
  }
}

export function saveReport(r: Report) {
  const s = JSON.stringify(r);
  memory = s;
  try {
    sessionStorage.setItem(KEY, s);
  } catch {
    /* blocked: memory copy is used */
  }
  window.dispatchEvent(new Event(EVT));
}

function subscribe(cb: () => void) {
  window.addEventListener(EVT, cb);
  return () => window.removeEventListener(EVT, cb);
}

/** Current report for this tab, or null. Server render always sees null. */
export function useStoredReport(): Report | null {
  const raw = useSyncExternalStore(subscribe, read, () => null);
  return useMemo(() => {
    if (!raw) return null;
    try {
      return JSON.parse(raw) as Report;
    } catch {
      return null;
    }
  }, [raw]);
}
