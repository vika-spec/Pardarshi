export type Lang = "en" | "hi";
export type L10n = { en: string; hi: string };

export interface Working {
  formula: string;
  plain: string;
  inputs: string;
  source: string;
}

export interface FundRow {
  scheme_id: string;
  name: string;
  amc: string;
  category: string;
  plan: "direct" | "regular";
  value: number;
  pct_of_portfolio: number;
  matched_by: string;
}

export interface StockRow {
  isin: string;
  name: string;
  sector: string;
  rupees: number;
  pct_of_portfolio: number;
  held_by_n_funds: number;
  via: { fund: string; rupees: number }[];
  has_scorecard: boolean;
}

export interface RiskCompany {
  isin: string;
  name: string;
  fy: string;
  pct_of_portfolio: number;
  rupees: number;
  counts: Record<string, number>;
  via?: string[];
  event?: { date: string; summary: string; source?: string } | null;
  flags: { id: string; title: L10n; severity: string; level?: Level; summary: L10n; pages: number[] }[];
  report_date?: string;
  old_report?: boolean;
  score?: { value: number; checks_with_data: number; checks_applicable: number };
}

export type Level = "high" | "moderate" | "low";

export interface Timeline {
  isin: string;
  name: string;
  years: string[];
  checks: { id: string; title: L10n; cells: { fy: string; status: string; level: Level | null }[]; trend: "worse" | "better" | "same" | "unknown" }[];
  summary: { worse: number; better: number; years: number };
  scores: { fy: string; score: number }[];
}

export interface Case {
  isin: string;
  name: string;
  fy: string;
  event: { date: string; summary: string; source?: string; note?: string };
  published?: string;
  lead_months?: number | null;
  others?: { id: string; title: L10n; status: string }[];
  counts: Record<string, number>;
  n_checks: number;
  flags: { id: string; title: L10n; summary: L10n; pages: number[] }[];
}

export interface Accuracy {
  false_positives?: number;
  false_negatives?: number;
  examples?: { company: string; check: string; human: string; app: string; kind: string }[];
  labelled_checks: number;
  coverage: number | null;
  agreement_when_answered: number | null;
  flag_precision: number | null;
  flag_recall: number | null;
  evidence_verified_rate: number | null;
  flag_f1?: number | null;
  false_negative_rate?: number | null;
  retrieval_hit_rate?: number | null;
  evidence_page_accuracy?: number | null;
  stages_labelled?: number;
  evaluated_at?: string;
}

export interface Benchmark {
  generated_at: string;
  citation_guard: { genuine_quotes: number; genuine_accepted_pct: number | null; tampered_quotes: number; tampered_rejected_pct: number | null;
    by_kind: Record<string, { tried: number; rejected: number }> };
  fallbacks: { case: string; expected: string; got: string; ok: boolean; ms: number }[];
  chat_without_ai: { status: number; streamed_answer: boolean; mode_fallback: boolean };
  api_speed: Record<string, { p50_ms: number; p95_ms: number; n: number }>;
  coverage: { companies_checked: number; companies_held: number; checks_by_status: Record<string, number>; evidence_verified_pct: number | null };
  live_ai: { provider: string; model: string; runs: number; errors: number; first_word_ms: number | null; total_ms: number | null }[] | null;
}

export interface Report {
  label?: string;
  total_value: number;
  funds: FundRow[];
  exposure: {
    top_stocks: StockRow[];
    sectors: { sector: string; rupees: number; pct_of_portfolio: number }[];
    top10_pct: number;
    effective_stocks: number;
    in_stocks_pct: number;
    other_pct: number;
    working: Working;
  };
  overlap: {
    n_funds: number;
    effective_funds: number;
    pairs: { a: string; b: string; overlap_pct: number; shared_stocks: number }[];
    matrix: number[][];
    labels: string[];
    working: Working;
  };
  cost: {
    years: number;
    gross_return_pct: number;
    n_regular: number;
    projected_loss: number;
    annual_cost_now: number;
    rows: {
      fund: string;
      plan: string;
      value: number;
      ter_regular_pct: number | null;
      ter_direct_pct: number | null;
      extra_cost_pct?: number;
      projected_loss?: number;
      annual_cost_now?: number;
    }[];
    working: Working;
  };
  risk: {
    companies: RiskCompany[];
    n_checked: number;
    n_with_flags: number;
    n_flags: number;
    n_not_covered: number;
    n_checks_each: number;
    money_flagged?: number;
    pct_flagged?: number;
    coverage_pct?: number;
    by_fund?: { fund: string; rupees: number; pct_of_fund: number | null }[];
    top_flagged?: { isin: string; name: string; rupees: number; pct_of_portfolio: number; n_flags: number; worst: Level }[];
    score?: { value: number; band: "few" | "some" | "many"; coverage_pct: number; n_companies: number; data_pct: number;
      lowest: { name: string; score: number; rupees: number }[]; formula: string; points: Record<Level, number> } | null;
    trust?: { review_agreed?: number; review_total?: number; fakes_tried?: number | null; fakes_rejected_pct?: number | null; precision?: number | null; recall?: number | null; labelled?: number | null } | null;
  };
  unmatched: { name: string; value: number }[];
  direct_stocks: { isin: string; name: string; value: number; has_scorecard: boolean }[];
  dataset: { dataset?: string; notice?: string; holdings_source?: string; ter_source?: string; built_at?: string };
  statement?: { type: string; as_of: string };
  generated_at: string;
}

export interface Evidence {
  quote: string;
  page: number;
  printed_page?: number | null;
  verified: boolean;
  match: number;
}

export interface CheckResult {
  id: string;
  title: L10n;
  what: L10n;
  rule: string;
  severity: string;
  status: "flagged" | "passed" | "not_found" | "unverified" | "not_applicable" | "disputed";
  summary: L10n;
  values: Record<string, number>;
  derived: Record<string, number>;
  evidence: Evidence[];
  method: string;
  confidence: string;
  caveat?: L10n;
  clears?: L10n;
  level?: Level | null;
  review?: { agree: boolean; reason: string; by: string; same_model: boolean } | null;
  breakdown?: { type: string; current: number; previous: number }[];
  seen_pages?: number[];
  ms?: number;
  basis?: string | null;
}

export interface Scorecard {
  isin: string;
  name: string;
  fy: string;
  report_url: string;
  n_pages: number;
  checks: CheckResult[];
  counts: Record<string, number>;
  generated_at: string;
  source_url?: string;
  sector?: string;
  report_date?: string;
  old_report?: boolean;
}

export interface Methodology {
  checks: { id: string; kind: string; severity: string; title: L10n; what: L10n; rule: string }[];
  formulas: Record<string, string>;
  principles: string[];
  dataset: Report["dataset"];
  ai_providers: string[];
  accuracy?: Accuracy | null;
  benchmark?: Benchmark | null;
  limitations?: string[];
  ai_pipeline?: { step: string; who: string; text: string }[];
  figures?: { compared: number; matched: number; match_rate: number | null; standalone_skipped: number; source: string; checked_at: string;
    rows: { company: string; figure: string; ours: number; reference: number; unit?: string | null; result: string }[] } | null;
}

export interface FundHit {
  scheme_id: string;
  name: string;
  amc: string;
  category: string;
  plans: string[];
}

export interface CitationCheck {
  citations: { company: string; page: number; page_ok: boolean; figures: number; figures_missing: string[] }[];
  ok: number;
  total: number;
}
