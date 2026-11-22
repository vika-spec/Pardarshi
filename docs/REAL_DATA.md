# Switching to real data: step-by-step checklist

Run this on your own laptop: it needs internet access to AMFI, fund house and company websites. Plan for **about half a day**; most of it is downloading files.

Scope that's realistic for the hackathon: **6–8 large fund houses**, their equity schemes, and annual reports for the **30–50 most-held companies** plus **2–3 well-documented collapse cases** for the "would have caught it early" demo moment.

Every command runs from `backend/`.

---

## 0. One-time setup (10 min)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-pipeline.txt
cp .env.example .env
```

In `.env`, add an AI key. Real annual reports need it (pattern matching alone mostly returns "not found" on real 300-page PDFs):

- `GEMINI_API_KEY=` a free key from Google AI Studio, and `GEMINI_MODEL=` a current Flash model from its model list; **or**
- `GROQ_API_KEY=` + `GROQ_MODEL=`; **or**
- `OLLAMA_URL=http://localhost:11434` to run a local model on your RTX 5050 (slower, but no limits and fully private).

Load it for the pipeline commands: `set -a; source .env; set +a` (PowerShell: set the variables in the session).

- [ ] Setup done, key set

## 1. Scheme list from AMFI (2 min)

```bash
python -m pipelines.fetch_amfi
```
Downloads AMFI's NAVAll file → `data/raw/amfi_schemes.csv` (every scheme with AMFI code, ISINs, direct/regular plan).
If the download is blocked, open `https://www.amfiindia.com/spages/NAVAll.txt` in a browser, save it, and run `python -m pipelines.fetch_amfi --file NAVAll.txt`.

- [ ] `amfi_schemes.csv` has thousands of rows

## 2. Expense ratios (TER) (5 min)

Open **AMFI → TER of MF Schemes** (`https://www.amfiindia.com/ter-of-mf-schemes`), choose the latest month and all fund houses, download, and save as **`data/raw/ter.xlsx`**.
(Or try `pip install amfipy && python -m pipelines.fetch_ter --month 10-2026 --year 2026-2027`.)

The builder recognises three layouts: an ISIN column + a total-TER column; a scheme-name column + Regular/Direct TER columns; or a plain `amfi,ter` CSV. Use the **total** TER (not the base expense ratio) so regular vs direct is like for like.

- [ ] `data/raw/ter.xlsx` saved

## 3. Monthly portfolios (30–60 min)

For each fund house you pick (e.g. SBI, HDFC, ICICI Prudential, Nippon India, Kotak, Axis, Parag Parikh, UTI), download the **latest month's portfolio disclosure** (Excel, sometimes zipped). Find it on the fund house's website under *Downloads / Disclosures / Monthly Portfolio*, or via **AMFI → Portfolio Disclosure**, which links to every fund house. Put everything in **`data/raw/portfolios/`** without unzipping or renaming anything.

```bash
python -m pipelines.parse_amc_portfolios
```

Each recognised scheme prints one line: `file:sheet -> Scheme name | N stocks, 97% equity`.

- [ ] Equity schemes show 60–100% equity. Debt sheets are skipped automatically; hybrids get a note.
- [ ] Read the **File report** at the end. Each file shows `OK` with a scheme count or `XX` with a reason. Supported: .xlsx/.xls/.xlsb/.xlsm/.ods (one sheet per scheme or several stacked in one sheet), .csv, HTML files saved as .xls, zips (even zips inside zips), and PDFs that list ISINs. If there is no % column, weights come from market value ÷ the scheme's Grand Total. Lines marked `(NO NAME FOUND)` fall back to the sheet code; add them to `data/raw/scheme_map.csv`. For an `XX` file with no obvious reason, share it so the parser can learn its layout.

## 4. Build the dataset (2 min)

```bash
python -m pipelines.build_dataset --sample
```

This writes `funds.json`, `companies.json`, a new **sample portfolio made of real funds**, and **`data/raw/reports_needed.csv`**, the companies your funds hold most, in order.

- [ ] "Unmatched" list is short. For each one, add a line to `data/raw/scheme_map.csv`:
  `Exact scheme name as printed,AMFI code` (the AMFI code is in `amfi_schemes.csv`), then rerun.
- [ ] "Missing TER" is zero or small.

## 5. Annual reports (1–2 hours)

Open `data/raw/reports_needed.csv`. For the top 30–50 rows, download the **latest annual report PDF** from the company's *Investor Relations* page or its BSE/NSE corporate filings. Also download the **pre-collapse** reports of 2–3 companies whose problems are well documented, for the demo's backtest moment.

Put all PDFs in one folder with whatever names they came with, then:

```bash
python -m pipelines.rename_reports ~/Downloads/annual_reports --fy FY2025-26 --dry-run   # check the matches
python -m pipelines.rename_reports ~/Downloads/annual_reports --fy FY2025-26
```

Files it can't match are listed; rename those to `<ISIN>.pdf` yourself (ISINs are in `reports_needed.csv`).

Real PDFs are large and are **not** committed to git or shipped in the Docker image. So the "Open original PDF" link works after deploy, record each report's official URL in `data/raw/report_sources.csv`:

```
isin,url,fy,event_date,event
INE...,https://company.com/.../annual-report-2025-26.pdf,FY2025-26,,
INE...,https://.../annual-report-2019-20.pdf,FY2019-20,2021-03-01,Stock fell 90% after auditor resignation and default
```

The `event_date,event` columns are only for the **Before the fall** backtest: for a company that later collapsed, use its annual report from *before* the event and describe what happened in one factual sentence (cite a news source in your README).

then rerun `python -m pipelines.build_dataset` (it keeps everything else).

- [ ] PDFs in `data/reports/<ISIN>.pdf`
- [ ] `report_sources.csv` filled

**Which reports first?** Run `python -m pipelines.report_list` after `build_dataset`. It ranks companies by rupees in the
sample portfolio (what judges see first), then by how widely they're held, and marks which are done. For real
"Before the fall" cases, follow `docs/BACKTEST_CASES.md`.

## 6. Red-flag checks (30–90 min, unattended)

```bash
python -m pipelines.build_redflags --dense --pause 4
```

- `--dense` adds local embeddings + a reranker on your GPU for better retrieval (first run downloads ~1 GB of models).
- `--pause 4` spaces out AI calls for free-tier rate limits (7 calls per company). Lower it if you have higher limits.
- It's resumable: stop it any time and rerun; finished companies are skipped. Use `--force` to rebuild after changing a key or model.
- Each company prints `flagged / passed / not_found / unverified` and the method used (`llm:gemini` or `heuristic`).

- [ ] Most checks say `via llm:…`. If you see mostly `heuristic`, the key isn't loaded.
- [ ] `not_found` is a minority of checks.

## 7. Spot-check and measure accuracy (45 min, worth it for judging)

Pick 5–8 companies. For each, open the scorecard in the app (step 9), click **Open page** on each flag, and check it against the report yourself. Write what *you* concluded in `data/eval/labels.csv`:

```
isin,check_id,expected
INE...,cash_vs_profit,flagged
INE...,auditor_opinion,passed
```

```bash
python -m pipelines.evaluate_flags
```

It prints flag precision/recall, coverage and the evidence-verified rate. **Put these numbers in your README and demo video**: almost no other team will have measured accuracy.

- [ ] At least ~40 labelled checks
- [ ] Numbers copied into the README

## 8. Validate (1 min)

```bash
python -m pipelines.validate_dataset
```

Must end with `OK`. It catches swapped TER columns, broken weights, scorecards without page text, flags without verified evidence, and a sample portfolio pointing at missing funds.

- [ ] `OK`

## 9. Try it locally, refresh the offline demo, deploy

```bash
uvicorn app.main:app --port 8000          # backend
# in frontend/: npm run dev                 → http://localhost:3000, click "Try a sample portfolio"
python -m pipelines.export_demo ../frontend/public/demo   # offline copy of the new sample
```

Old demo files (`ZZDEMO…`) left in `data/` are ignored automatically. You can delete them for a tidy repo:
`rm data/scorecards/ZZDEMO* data/chunks/ZZDEMO* data/reports/ZZDEMO*`

Then commit `data/` (without the big PDFs: `.gitignore` already excludes them) and redeploy the backend with the same `az containerapp up …` command from `docs/DEPLOY.md`. Vercel redeploys the frontend on push.

- [ ] Sample report shows real funds
- [ ] **See evidence** opens real report pages
- [ ] "Open original PDF" goes to the official report
- [ ] Deployed

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| A fund house's workbook gives no schemes | Header wording not recognised: share the header row, or extend `PCT_COL` |
| Weights look 100× too small or large | The validator flags it; check whether that file stores 7.25 or 0.0725 |
| Scheme matched to the wrong fund house | Add the right AMFI code in `scheme_map.csv` |
| Regular TER below direct TER | Columns swapped in your TER file; the validator reports it |
| Many `not_found` checks | AI key not loaded, rate-limited (raise `--pause`), or a scanned PDF with no text layer (skip that report) |
| Rate-limit errors | Raise `--pause`, add a second provider key (the chain falls through), or use Ollama locally |


## Measure it

```
python -m pipelines.evaluate_flags          # precision / recall against your hand labels (data/eval/labels.csv)
python -m pipelines.benchmark --live        # citation guard, failure drills, speed, live AI timing
```
Both write into `data/eval/`, and the Methodology page shows the results.


## Multi-year timeline (optional, strong for the demo)

Download the **previous year's** annual report (e.g. FY2024-25) for a few companies, put them in a separate folder, then:

```
python -m pipelines.rename_reports data/raw/reports_old --fy FY2024-25 --history
python -m pipelines.build_redflags --history --pause 6
```

The evidence panel then shows an **Across years** table: each check per year, whether it got worse or better, and the company score per year. When you later rebuild a company with a newer report, its old scorecard is kept automatically for the timeline.
