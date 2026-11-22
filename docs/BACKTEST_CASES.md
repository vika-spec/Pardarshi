# "Before the fall": real backtest cases

The point of this page is to show that the seven checks would have raised warning signs in an annual
report filed **before** a company's trouble became public. Pick 2–3 of the cases below. For each one:

1. Download the **annual report named below** (the one published before the event) from BSE:
   bseindia.com → search the company → Corp Information / Financials → Annual Reports.
   The page also shows the company's **ISIN**; copy it.
2. Save the PDF into `data/raw/reports_in/`.
3. Gensol is prepared: run `python -m pipelines.add_backtest gensol` (ISIN INE06H201014). For others, add a row to `data/raw/report_sources.csv` (columns: `isin,url,fy,event_date,event,name,source`).
   `name` lets you add a company that no fund holds today. `source` is a news link shown on the case card.
4. Run:
   ```
   python -m pipelines.build_dataset
   python -m pipelines.rename_reports data/raw/reports_in --fy <the FY below>
   python -m pipelines.build_redflags --pause 6
   ```
5. Open **Before the fall** in the app. Report what the checks found as it is, including checks that did
   **not** fire. Honest misses make the page more credible.

Also include 2 healthy large companies from your normal list as a comparison, so the page shows the
checks don't simply flag everything.

---

## 1. Gensol Engineering (2025: fund diversion)

- **What happened:** On 15 April 2025, SEBI issued an interim order barring Gensol Engineering and its
  promoters Anmol Singh Jaggi and Puneet Singh Jaggi from the securities market over alleged fund
  diversion and governance lapses. The order followed a complaint SEBI received in June 2024. Funds
  borrowed to buy electric vehicles were allegedly diverted for personal use and related entities.
- **Report to download:** FY2023-24 annual report (published in 2024, before the order).
- **Checks to watch:** related-party transactions, promoter pledge, receivables vs revenue, cash vs profit.
- **Sources:**
  [Business Today](https://www.businesstoday.in/markets/company-stock/story/sebi-bars-gensol-engineering-its-promoters-from-accessing-markets-in-fund-diversion-case-472151-2025-04-15),
  [Business Standard](https://www.business-standard.com/amp/markets/capital-market-news/gensol-engg-slumps-as-sebi-unplugs-promoters-over-alleged-fraud-125041700568_1.html)

```
<ISIN from BSE>,,FY2023-24,2025-04-15,SEBI interim order barred the company and its promoters over alleged diversion of borrowed funds and governance lapses.,Gensol Engineering Ltd,https://www.businesstoday.in/markets/company-stock/story/sebi-bars-gensol-engineering-its-promoters-from-accessing-markets-in-fund-diversion-case-472151-2025-04-15
```

## 2. Manpasand Beverages (2018–19: auditor exit, then GST fraud)

- **What happened:** In May 2018 the statutory auditor Deloitte Haskins & Sells resigned, saying it had
  not been given significant information it requested. In May 2019 the MD and CFO were arrested in an
  alleged ₹40 crore GST fake-invoice fraud, and in July 2019 the next auditor also resigned.
- **Report to download:** FY2016-17 annual report (published in 2017, before Deloitte resigned).
- **Checks to watch:** receivables vs revenue (one analysis says receivables were growing much faster than
  revenue in the years before), cash vs profit. Auditor change will **not** fire on this report, because the
  resignation came later; say so on the page.
- **Sources:**
  [BloombergQuint](https://www.bloombergquint.com/amp/law-and-policy/manpasand-beverages-top-officials-arrested-for-rs-40-crore-tax-fraud),
  [Business Today](https://www.businesstoday.in/amp/markets/company-stock/story/manpasand-beverages-stock-hits-5-lower-circuit-after-auditor-quits-amid-probe-in-gst-fraud-case-209769-2019-07-10)

```
<ISIN from BSE>,,FY2016-17,2018-05-26,Auditor Deloitte resigned saying it was not given significant information; in 2019 the MD and CFO were arrested in an alleged Rs 40 crore GST fraud.,Manpasand Beverages Ltd,https://www.bloombergquint.com/amp/law-and-policy/manpasand-beverages-top-officials-arrested-for-rs-40-crore-tax-fraud
```

## 3. Coffee Day Enterprises (2019–20: money owed by the founder's private firm)

- **What happened:** The founder died in July 2019. An investigation reported on 24 July 2020 found that
  his private company, Mysore Amalgamated Coffee Estates (MACEL), owed ₹3,535 crore to Coffee Day
  subsidiaries as of 31 July 2019. The audited accounts had shown only ₹842 crore due at 31 March 2019.
  SEBI later fined the company ₹26 crore over the diversion.
- **Report to download:** FY2017-18 annual report (published in 2018, before the event).
- **Checks to watch:** related-party transactions, promoter pledge, contingent liabilities.
- **Sources:**
  [Business Standard](https://www.business-standard.com/amp/article/companies/v-g-siddhartha-suicide-case-ccd-pe-investors-i-t-officials-get-clean-chit-120072402020_1.html),
  [Business Today](https://www.businesstoday.in/current/corporate/coffee-day-owner-suicide-siddharthas-personal-business-owes-group-over-3500-crore/story/410979.html)

```
<ISIN from BSE>,,FY2017-18,2020-07-24,An investigation found the founder's private firm owed Rs 3535 crore to group subsidiaries; audited accounts had shown Rs 842 crore.,Coffee Day Enterprises Ltd,https://www.business-standard.com/amp/article/companies/v-g-siddhartha-suicide-case-ccd-pe-investors-i-t-officials-get-clean-chit-120072402020_1.html
```

If your event text contains a comma, wrap the whole field in double quotes.

Keep the event text neutral and factual ("alleged", "an investigation found"). A warning sign is a reason
to look closer, not proof of wrongdoing.
