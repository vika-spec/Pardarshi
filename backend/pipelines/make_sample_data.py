"""Generate the FICTIONAL demo dataset so the app works with zero setup.

Every fund and company here is invented. ISINs start with 'ZZDEMO' (not a
real country code) so they can never be confused with real securities.
Three companies get a small synthetic annual report PDF; the real red-flag
pipeline then runs on those PDFs exactly as it would on real reports.

    python -m pipelines.make_sample_data && python -m pipelines.build_redflags --no-llm
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings  # noqa: E402

DATA = settings.data_dir

COMPANIES = [
    ("Northwind Bank Ltd", "Banking"),
    ("Lotus Bank Ltd", "Banking"),
    ("Indus Software Ltd", "IT services"),
    ("Saffron Energy Ltd", "Energy"),
    ("Sample Co. Ltd", "Consumer goods"),
    ("Kaveri Cement Ltd", "Cement"),
    ("Monsoon Foods Ltd", "Food products"),
    ("Deccan Pharma Ltd", "Pharma"),
    ("Ganga Motors Ltd", "Automobiles"),
    ("Narmada Telecom Ltd", "Telecom"),
    ("Vindhya Steel Ltd", "Metals"),
    ("Coral Insurance Ltd", "Insurance"),
    ("Teak Retail Ltd", "Retail"),
    ("Konkan Paints Ltd", "Consumer goods"),
    ("Brahmaputra Power Ltd", "Power"),
    ("Aravali Chemicals Ltd", "Chemicals"),
    ("Malabar Finance Ltd", "NBFC"),
    ("Satpura Logistics Ltd", "Logistics"),
]
ISIN = {name: f"ZZDEMO{n:06d}" for n, (name, _) in enumerate(COMPANIES, start=1)}
SECTOR = dict(COMPANIES)

LARGE = ["Northwind Bank Ltd", "Lotus Bank Ltd", "Indus Software Ltd", "Saffron Energy Ltd", "Sample Co. Ltd", "Narmada Telecom Ltd", "Coral Insurance Ltd", "Ganga Motors Ltd", "Konkan Paints Ltd", "Deccan Pharma Ltd"]
MID = ["Kaveri Cement Ltd", "Monsoon Foods Ltd", "Vindhya Steel Ltd", "Teak Retail Ltd", "Brahmaputra Power Ltd", "Malabar Finance Ltd"]
SMALL = ["Aravali Chemicals Ltd", "Satpura Logistics Ltd", "Monsoon Foods Ltd", "Teak Retail Ltd", "Malabar Finance Ltd"]

FUNDS = [
    # id, name, amc, category, universe, tilt seed, TER regular, TER direct
    ("DEMO-LCA", "Demo Large Cap Fund A", "Demo AMC One", "Large Cap", LARGE + MID[:2], 1, 1.72, 0.68),
    ("DEMO-FCB", "Demo Flexi Cap Fund B", "Demo AMC One", "Flexi Cap", LARGE + MID[:4], 2, 1.68, 0.71),
    ("DEMO-BCC", "Demo Bluechip Fund C", "Demo AMC Two", "Large Cap", LARGE, 3, 1.81, 0.92),
    ("DEMO-MCD", "Demo Mid Cap Fund D", "Demo AMC Two", "Mid Cap", MID + LARGE[6:9], 4, 1.89, 0.74),
    ("DEMO-SCE", "Demo Small Cap Fund E", "Demo AMC Three", "Small Cap", SMALL + MID[:2], 5, 1.95, 0.81),
    ("DEMO-IXF", "Demo Nifty 50 Index Fund F", "Demo AMC Three", "Index", LARGE, 0, 0.42, 0.18),
    ("DEMO-TSG", "Demo Tax Saver Fund G", "Demo AMC One", "ELSS", LARGE[:8] + MID[:3], 7, 1.77, 0.79),
    ("DEMO-FOH", "Demo Focused Fund H", "Demo AMC Four", "Focused", LARGE[:6] + MID[1:3], 8, 1.85, 0.66),
]


def holdings(universe: list[str], seed: int) -> list[dict]:
    rng = random.Random(seed)
    base = {name: (len(universe) - i) ** 1.3 for i, name in enumerate(universe)}  # big names get big weights
    if seed:
        for k in base:
            base[k] *= rng.uniform(0.55, 1.45)
    equity_share = 0.96 if seed else 0.995
    total = sum(base.values())
    return [
        {"isin": ISIN[n], "name": n, "sector": SECTOR[n], "weight": round(w / total * equity_share, 5)}
        for n, w in sorted(base.items(), key=lambda kv: -kv[1])
    ]


def build_json() -> None:
    funds = []
    for i, (sid, name, amc, cat, uni, seed, ter_r, ter_d) in enumerate(FUNDS):
        funds.append(
            {
                "scheme_id": sid,
                "name": name,
                "amc": amc,
                "category": cat,
                "holdings_asof": "2026-10-31",
                "plans": {
                    "direct": {"isins": [f"ZZDEMOD{i:05d}"], "amfi": f"9{i:05d}1", "ter": ter_d},
                    "regular": {"isins": [f"ZZDEMOR{i:05d}"], "amfi": f"9{i:05d}2", "ter": ter_r},
                },
                "holdings": holdings(uni, seed),
            }
        )
    companies = {
        ISIN[n]: {"name": n, "sector": s, "fy": "FY2025-26" if n in REPORTS else "", "report_url": f"/api/reports/{ISIN[n]}.pdf" if n in REPORTS else ""}
        for n, s in COMPANIES
    }
    companies[ISIN["Monsoon Foods Ltd"]]["event"] = {
        "date": "2026-09-15",
        "summary": "Fictional: lenders sold pledged promoter shares and the stock fell 70% in a month.",
    }
    meta = {
        "dataset": "demo",
        "notice": "Fictional demo data. All funds and companies are invented.",
        "holdings_source": "Demo dataset (fictional)",
        "ter_source": "Demo dataset (fictional)",
        "built_at": "2026-11-15",
    }
    sample = {
        "label": "Sample portfolio (fictional)",
        "holdings": [
            {"scheme_id": "DEMO-LCA", "plan": "regular", "value": 180000},
            {"scheme_id": "DEMO-FCB", "plan": "regular", "value": 150000},
            {"scheme_id": "DEMO-SCE", "plan": "regular", "value": 120000},
            {"scheme_id": "DEMO-IXF", "plan": "direct", "value": 90000},
            {"scheme_id": "DEMO-TSG", "plan": "regular", "value": 60000},
            {"scheme_id": "DEMO-MCD", "plan": "direct", "value": 75000},
        ],
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "funds.json").write_text(json.dumps(funds, indent=1), "utf-8")
    (DATA / "companies.json").write_text(json.dumps(companies, indent=1), "utf-8")
    (DATA / "meta.json").write_text(json.dumps(meta, indent=1), "utf-8")
    (DATA / "sample_portfolio.json").write_text(json.dumps(sample, indent=1), "utf-8")


# ---------------------------------------------------------------- PDF reports
def _report_pages(name: str, f: dict) -> list[tuple[str, list[str]]]:
    def row(label: str, a: str, b: str = "") -> str:
        return f"{label:<58}{a:>12}{b:>12}"

    auditor_para = (
        [
            "Basis for Qualified Opinion",
            "We were unable to obtain sufficient appropriate audit evidence regarding",
            "advances of Rs. 214.0 crore given to an entity under common control.",
            "In our opinion, except for the possible effects of the matter described in the",
            "Basis for Qualified Opinion paragraph, the financial statements give a true and fair view.",
        ]
        if f.get("qualified")
        else [
            "Opinion",
            "In our opinion and to the best of our information and according to the explanations",
            "given to us, the financial statements give a true and fair view in conformity with Ind AS.",
            "We have expressed an unmodified opinion on these standalone financial statements.",
        ]
    )
    auditor_line = (
        "M/s Field & Co., the statutory auditors, have resigned with effect from 12 February 2026, citing pre-occupation."
        if f.get("auditor_resigned")
        else "M/s Example & Associates were appointed as the statutory auditors of the Company at the 38th AGM."
    )
    return [
        (f"{name}", ["Annual Report FY2025-26", "", "FICTIONAL DEMO DOCUMENT - not a real company.", "Generated for the Pardarshi demo dataset."]),
        ("Directors' Report", [
            "The Board presents the annual report together with audited financial statements.",
            "Statutory auditors",
            auditor_line,
            "Dividend: The Board recommends a final dividend for the year.",
        ]),
        ("Management Discussion and Analysis", [
            "Demand remained steady through the year. The company expanded distribution",
            "to new districts and continued to invest in brand building and capacity.",
            "Working capital requirements increased with the expansion of the dealer network.",
        ]),
        ("Independent Auditor's Report", ["To the Members of " + name, "Report on the Audit of the Standalone Financial Statements", *auditor_para]),
        ("Balance Sheet as at 31 March 2026 (Rs. crore)", [
            row("Particulars", "31-Mar-26", "31-Mar-25"),
            row("Trade receivables", f["rec"][0], f["rec"][1]),
            row("Cash and cash equivalents", f["cash"][0], f["cash"][1]),
            row("Total equity", f["eq"][0], f["eq"][1]),
        ]),
        ("Statement of Profit and Loss (Rs. crore)", [
            row("Particulars", "FY26", "FY25"),
            row("Revenue from operations", f["rev"][0], f["rev"][1]),
            row("Total expenses", f["exp"][0], f["exp"][1]),
            row("Profit for the year", f["pat"][0], f["pat"][1]),
        ]),
        ("Statement of Cash Flows (Rs. crore)", [
            row("Particulars", "FY26", "FY25"),
            row("Net cash generated from operating activities", f["cfo"][0], f["cfo"][1]),
            row("Net cash used in investing activities", f["cfi"][0], f["cfi"][1]),
        ]),
        ("Note 38: Related party disclosures (Rs. crore)", [
            "Entities under common control of the promoter group: purchases of goods and loans given.",
            row("Purchases from entities under common control", f["rptp"][0], f["rptp"][1]),
            row("Loans given to entities under common control", f["rptl"][0], f["rptl"][1]),
            row("Total transactions with related parties", f["rpt"][0], f["rpt"][1]),
        ]),
        ("Note 34: Contingent liabilities and commitments (Rs. crore)", [
            row("Claims against the Company not acknowledged as debts", f["cl1"][0], f["cl1"][1]),
            row("Contingent liabilities not provided for", f["cl"][0], f["cl"][1]),
        ]),
        ("Shareholding pattern", [
            f"Promoter and promoter group holding: {f['promoter']}% of equity share capital.",
            f"Shares pledged or encumbered by the promoter group: {f['pledge']}% of promoter holding.",
        ]),
    ]


REPORTS = {
    "Sample Co. Ltd": dict(rev=("2,480.0", "2,130.0"), exp=("1,930.0", "1,700.0"), pat=("412.6", "318.2"), cfo=("96.4", "141.8"), cfi=("(210.0)", "(180.0)"),
                           rec=("642.0", "540.0"), cash=("88.0", "120.0"), eq=("2,950.0", "2,610.0"), rptp=("402.0", "190.0"), rptl=("84.0", "24.0"),
                           rpt=("486.0", "214.0"), cl1=("120.5", "110.0"), cl=("180.5", "160.0"), promoter="54.2", pledge="4.2"),
    "Kaveri Cement Ltd": dict(rev=("5,120.0", "4,700.0"), exp=("4,300.0", "3,980.0"), pat=("610.0", "560.0"), cfo=("720.0", "650.0"), cfi=("(480.0)", "(400.0)"),
                              rec=("410.0", "392.0"), cash=("310.0", "260.0"), eq=("4,800.0", "4,350.0"), rptp=("95.0", "88.0"), rptl=("25.0", "22.0"),
                              rpt=("120.0", "110.0"), cl1=("200.0", "190.0"), cl=("300.0", "285.0"), promoter="61.0", pledge="0.0"),
    "Monsoon Foods Ltd": dict(rev=("1,150.0", "1,020.0"), exp=("1,010.0", "905.0"), pat=("118.0", "96.0"), cfo=("(42.0)", "35.0"), cfi=("(160.0)", "(90.0)"),
                              rec=("520.0", "330.0"), cash=("12.0", "40.0"), eq=("640.0", "560.0"), rptp=("150.0", "70.0"), rptl=("214.0", "40.0"),
                              rpt=("364.0", "110.0"), cl1=("140.0", "60.0"), cl=("260.0", "120.0"), promoter="48.5", pledge="38.0",
                              qualified=True, auditor_resigned=True),
}


def build_pdfs() -> None:
    import pymupdf

    (DATA / "reports").mkdir(parents=True, exist_ok=True)
    for name, figures in REPORTS.items():
        doc = pymupdf.open()
        for title, lines in _report_pages(name, figures):
            page = doc.new_page(width=595, height=842)
            page.insert_text((56, 72), title, fontsize=15, fontname="helv")
            y = 110
            for line in lines:
                page.insert_text((56, y), line, fontsize=9.5, fontname="cour" if "  " in line else "helv")
                y += 18
            page.insert_text((56, 810), "Fictional demo document generated for Pardarshi.", fontsize=7, fontname="helv")
        doc.save(DATA / "reports" / f"{ISIN[name]}.pdf")
        doc.close()


if __name__ == "__main__":
    build_json()
    build_pdfs()
    print(f"Demo dataset written to {DATA}")
