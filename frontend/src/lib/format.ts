import type { Lang } from "./types";

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** ₹12,34,567 */
export const rupees = (n: number) => `₹${inr.format(Math.round(n))}`;

/** ₹6.9 lakh / ₹1.2 crore: how people in India say large amounts. */
export function rupeesWords(n: number, lang: Lang = "en"): string {
  const abs = Math.abs(n);
  const lakh = lang === "hi" ? "लाख" : "lakh";
  const crore = lang === "hi" ? "करोड़" : "crore";
  if (abs >= 1e7) return `₹${(n / 1e7).toFixed(abs >= 1e8 ? 0 : 2)} ${crore}`;
  if (abs >= 1e5) return `₹${(n / 1e5).toFixed(abs >= 1e6 ? 1 : 2)} ${lakh}`;
  return rupees(n);
}

export const pct = (n: number, digits = 1) => `${n.toFixed(digits)}%`;

/** 1.4 stays "1.4" (rounding to 1 would hide the overlap); whole numbers stay whole. */
export const roughCount = (n: number) => {
  const v = Math.max(1, Math.round(n * 10) / 10);
  return Number.isInteger(v) ? v : Number(v.toFixed(1));
};
