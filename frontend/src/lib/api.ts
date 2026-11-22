import type { Case, CitationCheck, FundHit, Methodology, Report, Scorecard, Timeline } from "./types";

/**
 * API base: if NEXT_PUBLIC_API_URL is set the browser calls the backend directly
 * (CORS is configured for *.vercel.app); otherwise calls go to /api on this
 * origin and next.config.ts rewrites them to BACKEND_URL.
 */
const BASE = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
export const apiUrl = (path: string) => `${BASE}${path}`;

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

/** Fired when we fall back to the bundled offline demo, so the UI can say so. */
export const OFFLINE_EVENT = "pardarshi:offline";
function announceOffline() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(OFFLINE_EVENT));
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 15000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(apiUrl(path), { ...init, signal: ctrl.signal });
    if (!r.ok) {
      let msg = `Request failed (${r.status})`;
      try {
        const body = await r.json();
        msg = body.detail || body.error || msg;
        if (Array.isArray(msg)) msg = "Some of the details you entered don't look right. Please check the amounts.";
      } catch {
        /* not JSON */
      }
      throw new ApiError(String(msg), r.status);
    }
    return (await r.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError("We couldn't reach the server.", 0);
  } finally {
    clearTimeout(timer);
  }
}

async function demo<T>(file: string): Promise<T> {
  const r = await fetch(`/demo/${file}`);
  if (!r.ok) throw new ApiError("Offline demo data is missing.", r.status);
  announceOffline();
  return (await r.json()) as T;
}

/** Server unreachable or failing: use the bundled demo so the product still works. */
const shouldFallback = (e: unknown) => e instanceof ApiError && (e.status === 0 || e.status >= 500);

export async function getSample(age?: number): Promise<Report> {
  try {
    return await request<Report>(`/api/sample${age ? `?age=${age}` : ""}`);
  } catch (e) {
    if (shouldFallback(e)) return demo<Report>("sample.json");
    throw e;
  }
}

export type ManualHolding = { scheme_id?: string; name?: string; plan?: "direct" | "regular"; value: number };

export function analyzeManual(holdings: ManualHolding[], age?: number): Promise<Report> {
  return request<Report>("/api/analyze/manual", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ holdings, age: age || undefined }),
  });
}

export function analyzeCas(file: File, password: string, age?: number): Promise<Report> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("password", password);
  if (age) fd.append("age", String(age));
  return request<Report>("/api/analyze/cas", { method: "POST", body: fd }, 60000);
}

export async function searchFunds(q: string): Promise<FundHit[]> {
  const r = await request<{ results: FundHit[] }>(`/api/funds/search?q=${encodeURIComponent(q)}`, undefined, 8000);
  return r.results;
}

export async function getScorecard(isin: string): Promise<Scorecard> {
  try {
    return await request<Scorecard>(`/api/companies/${encodeURIComponent(isin)}/scorecard`);
  } catch (e) {
    if (shouldFallback(e)) return demo<Scorecard>(`scorecards/${isin}.json`);
    throw e;
  }
}

export async function getTimeline(isin: string): Promise<Timeline | null> {
  try {
    return await request<Timeline>(`/api/companies/${encodeURIComponent(isin)}/timeline`);
  } catch (e) {
    if (shouldFallback(e)) return demo<Timeline>(`timeline/${isin}.json`).catch(() => null);
    return null;
  }
}

export async function getPage(isin: string, page: number): Promise<{ page: number; n_pages: number; text: string }> {
  try {
    return await request(`/api/companies/${encodeURIComponent(isin)}/pages/${page}`);
  } catch (e) {
    if (!shouldFallback(e)) throw e;
    const pages = await demo<Record<string, string>>(`pages/${isin}.json`);
    if (!(String(page) in pages)) throw new ApiError("Page not found.", 404);
    return { page, n_pages: Object.keys(pages).length, text: pages[String(page)] };
  }
}

export async function getMethodology(): Promise<Methodology> {
  try {
    return await request<Methodology>("/api/methodology");
  } catch (e) {
    if (shouldFallback(e)) return demo<Methodology>("methodology.json");
    throw e;
  }
}

export const reportPdfUrl = (isin: string, page?: number) => apiUrl(`/api/reports/${isin}.pdf${page ? `#page=${page}` : ""}`);

/** Stream a grounded answer. Calls back with tokens; resolves with sources + mode. */
export async function streamChat(
  body: { question: string; isins: string[]; portfolio?: unknown; lang: string },
  onToken: (t: string) => void,
  onMeta: (m: { mode: string; provider: string | null; sources: { isin: string; company: string; page: number }[] }) => void,
  signal?: AbortSignal,
  onCheck?: (c: CitationCheck) => void,
  onEvent?: (ev: string, data: Record<string, unknown>) => void,
): Promise<void> {
  const r = await fetch(apiUrl("/api/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok || !r.body) throw new ApiError(r.status === 429 ? "You're asking quickly! Please wait a few seconds." : "Chat is unavailable right now.", r.status);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const ev = /^event: (.+)$/m.exec(block)?.[1];
      const data = /^data: (.+)$/m.exec(block)?.[1];
      if (!ev || !data) continue;
      const parsed = JSON.parse(data);
      if (ev === "token") onToken(parsed.t);
      else if (ev === "meta") onMeta(parsed);
      else if (ev === "check" && onCheck) onCheck(parsed);
      else if (onEvent) onEvent(ev, parsed);
    }
  }
}

export async function getCases(): Promise<Case[]> {
  try {
    return (await request<{ cases: Case[] }>("/api/cases")).cases;
  } catch (e) {
    if (shouldFallback(e)) return (await demo<{ cases: Case[] }>("cases.json")).cases;
    throw e;
  }
}
