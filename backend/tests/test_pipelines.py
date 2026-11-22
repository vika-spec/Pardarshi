"""Real-data pipeline tests on realistic, messy fixtures (banner rows, % strings,
fraction units, debt rows, zipped workbooks, three TER layouts)."""
from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from pipelines.build_dataset import build, load_ter
from pipelines.fetch_amfi import parse as parse_amfi
from pipelines.parse_amc_portfolios import parse_paths
from pipelines.rename_reports import core, match
from pipelines.validate_dataset import validate

NAVALL = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Large Cap Fund)

Alpha Mutual Fund

100001;INF00A001AA1;-;Alpha Bluechip Fund - Direct Plan - Growth;95.10;31-Oct-2026
100002;INF00A001AB9;-;Alpha Bluechip Fund - Regular Plan - Growth;88.20;31-Oct-2026
100003;INF00A001AC7;INF00A001AD5;Alpha Bluechip Fund - Regular Plan - IDCW;21.00;31-Oct-2026

Beta Mutual Fund

200001;INF00B001AA0;-;Beta Bluechip Fund - Direct Plan - Growth;50.00;31-Oct-2026
200002;INF00B001AB8;-;Beta Bluechip Fund - Regular Plan - Growth;45.00;31-Oct-2026

Open Ended Schemes(Equity Scheme - Small Cap Fund)

Alpha Mutual Fund

100011;INF00A001SA1;-;Alpha Small Cap Fund - Direct Plan - Growth;40.00;31-Oct-2026
100012;INF00A001SB9;-;Alpha Small Cap Fund - Regular Plan - Growth;35.00;31-Oct-2026
"""


def _sheet(title: str, rows: list[list], pct_header: str = "% to NAV") -> pd.DataFrame:
    head = [["Alpha Mutual Fund"], ["Monthly Portfolio Statement as on 31st October 2026"], [title], [],
            ["Name of the Instrument", "ISIN", "Industry", "Quantity", "Market value (Rs. Lakh)", pct_header]]
    return pd.DataFrame(head + rows + [["Total", "", "", "", "", "100.00%"]])


@pytest.fixture()
def raw_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    (raw / "portfolios").mkdir(parents=True)
    rows = parse_amfi(NAVALL)
    with (raw / "amfi_schemes.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    bluechip = _sheet("Alpha Bluechip Fund (An open ended equity scheme predominantly investing in large cap stocks)", [
        ["Equity & Equity related"],
        ["Bank One Ltd", "INE040A01034", "Banks", 100, 1000, "9.52%"],
        ["Energy Co Ltd", "INE002A01018", "Petroleum Products", 100, 900, "8.10%"],
        ["Soft Ltd", "INE009A01021", "IT - Software", 100, 800, 7.2],
        ["Debt Instruments"],
        ["Some NCD", "INE040A08AB1", "CRISIL AAA", 1, 100, "1.00%"],
        ["TREPS", "", "", "", 50, "2.18%"],
    ])
    small = _sheet("Scheme Name: Alpha Small Cap Fund", [
        ["Tiny Chem Ltd", "INE111C01011", "Chemicals", 1, 1, 0.031],  # fractions, not percent
        ["Little Bank Ltd", "INE222D01012", "Banks", 1, 1, 0.027],
        ["Energy Co Ltd", "INE002A01018", "Petroleum Products", 1, 1, 0.02],
    ], pct_header="% to Net Assets")
    index = pd.DataFrame([["Index"], ["This workbook contains:"], ["Alpha Bluechip Fund"]])
    with pd.ExcelWriter(raw / "portfolios" / "alpha_oct.xlsx") as w:
        index.to_excel(w, sheet_name="Index", header=False, index=False)
        bluechip.to_excel(w, sheet_name="ABF", header=False, index=False)
        small.to_excel(w, sheet_name="ASCF", header=False, index=False)

    beta = _sheet("Beta Bluechip Fund", [["Bank One Ltd", "INE040A01034", "Banks", 1, 1, "6.00"], ["Soft Ltd", "INE009A01021", "IT", 1, 1, "5.00"]])
    beta.iloc[0, 0] = "Beta Mutual Fund"
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as w:
        beta.to_excel(w, sheet_name="BBF", header=False, index=False)
    with zipfile.ZipFile(raw / "portfolios" / "beta.zip", "w") as z:
        z.writestr("Beta Oct 2026/beta_bluechip.xlsx", buf.getvalue())
    return raw


def test_amfi_parse_groups_and_plans():
    rows = parse_amfi(NAVALL)
    assert len(rows) == 7
    r = next(r for r in rows if r["amfi"] == "100002")
    assert (r["amc"], r["category"], r["plan"], r["option"]) == ("Alpha Mutual Fund", "Equity Scheme - Large Cap Fund", "regular", "growth")
    assert next(r for r in rows if r["amfi"] == "100003")["option"] == "idcw"


def test_portfolio_parser_handles_messy_workbooks(raw_dir):
    out = parse_paths([raw_dir / "portfolios"], log=lambda *_: None)
    by = {o["scheme_name"]: o for o in out}
    assert set(by) == {"Alpha Bluechip Fund", "Alpha Small Cap Fund", "Beta Bluechip Fund"}
    blue = by["Alpha Bluechip Fund"]
    assert [h["isin"] for h in blue["holdings"]] == ["INE040A01034", "INE002A01018", "INE009A01021"]  # debt + TREPS dropped
    assert blue["holdings"][0]["weight"] == pytest.approx(0.0952)
    assert blue["asof"] == "2026-10-31" and blue["amc_hint"] == "Alpha Mutual Fund"
    small = by["Alpha Small Cap Fund"]
    assert small["holdings"][0]["weight"] == pytest.approx(0.031)  # fraction units kept
    assert by["Beta Bluechip Fund"]["file"].startswith("beta.zip/")


def test_ter_loader_three_layouts(tmp_path):
    a = pd.DataFrame([["AMFI TER report"], [], ["Scheme Name", "ISIN", "Plan", "Base TER (%)", "TER_total"],
                      ["Alpha Bluechip Fund - Direct", "INF00A001AA1", "Direct", "0.55", "0.62"],
                      ["Alpha Bluechip Fund - Regular", "INF00A001AB9", "Regular", "1.40", "1.71"]])
    with pd.ExcelWriter(tmp_path / "ter.xlsx") as w:
        a.to_excel(w, header=False, index=False)
    by_isin, _, _ = load_ter(tmp_path)
    assert by_isin == {"INF00A001AA1": 0.62, "INF00A001AB9": 1.71}

    b_dir = tmp_path / "b"
    b_dir.mkdir()
    pd.DataFrame([["Scheme Name", "Regular Plan - Total TER (%)", "Direct Plan - Total TER (%)"],
                  ["Beta Bluechip Fund", "1.90", "0.80"]]).to_csv(b_dir / "ter.csv", header=False, index=False)
    _, _, by_name = load_ter(b_dir)
    assert by_name[("beta bluechip", "regular")] == 1.90 and by_name[("beta bluechip", "direct")] == 0.80

    c_dir = tmp_path / "c"
    c_dir.mkdir()
    (c_dir / "ter.csv").write_text("amfi,ter\n100011,0.70\n100012,1.95\n")
    _, by_amfi, _ = load_ter(c_dir)
    assert by_amfi == {"100011": 0.70, "100012": 1.95}


def test_build_end_to_end_then_validate(raw_dir):
    data = raw_dir.parent
    (raw_dir / "holdings_raw.json").write_text(json.dumps(parse_paths([raw_dir / "portfolios"], log=lambda *_: None)))
    (raw_dir / "ter.csv").write_text("amfi,ter\n100001,0.62\n100002,1.71\n100011,0.70\n100012,1.95\n200001,0.80\n200002,1.90\n")
    msgs: list[str] = []
    stats = build(data, write_sample=True, log=msgs.append)
    assert stats == {"funds": 3, "companies": 5, "unmatched": 0, "missing_ter": 0}
    funds = {f["name"]: f for f in json.loads((data / "funds.json").read_text())}
    # same-named schemes at two fund houses must not be confused
    assert funds["Alpha Bluechip Fund"]["plans"]["regular"]["amfi"] == "100002"
    assert funds["Beta Bluechip Fund"]["plans"]["regular"]["amfi"] == "200002"
    assert funds["Alpha Bluechip Fund"]["plans"]["direct"]["ter"] == 0.62
    assert funds["Alpha Bluechip Fund"]["holdings_asof"] == "2026-10-31"
    needed = list(csv.DictReader((raw_dir / "reports_needed.csv").open()))
    assert needed[0]["isin"] == "INE040A01034"  # most-held company first
    errors, _, _ = validate(data)
    assert errors == []


def test_scheme_map_override(raw_dir):
    data = raw_dir.parent
    pf = parse_paths([raw_dir / "portfolios"], log=lambda *_: None)
    for p in pf:
        if p["scheme_name"] == "Alpha Small Cap Fund":
            p["scheme_name"] = "ASC Fund (renamed in sheet)"
            p["amc_hint"] = ""
    (raw_dir / "holdings_raw.json").write_text(json.dumps(pf))
    assert build(data, log=lambda *_: None)["unmatched"] == 1
    (raw_dir / "scheme_map.csv").write_text("ASC Fund (renamed in sheet),100012\n")
    assert build(data, log=lambda *_: None)["unmatched"] == 0


def test_report_renamer(tmp_path):
    import pymupdf

    choices = {core("Energy Co Ltd"): "INE002A01018", core("Bank One Limited"): "INE040A01034", core("Bank One Finance Ltd"): "INE999Z01011"}
    by_name = tmp_path / "energy-co-annual-report-2025-26.pdf"
    by_text = tmp_path / "AR_FY26_final.pdf"
    for path, text in ((by_name, "Annual Report"), (by_text, "Bank One Limited\nIntegrated Annual Report 2025-26")):
        doc = pymupdf.open()
        doc.new_page().insert_text((50, 72), text)
        doc.save(path)
    assert match(by_name, choices)[:2] == ("INE002A01018", "file name")
    assert match(by_text, choices)[:2] == ("INE040A01034", "first pages")


def test_rebuild_keeps_report_details_and_sources(raw_dir):
    data = raw_dir.parent
    (raw_dir / "holdings_raw.json").write_text(json.dumps(parse_paths([raw_dir / "portfolios"], log=lambda *_: None)))
    (raw_dir / "ter.csv").write_text("amfi,ter\n100001,0.62\n100002,1.71\n")
    build(data, log=lambda *_: None)
    comps = json.loads((data / "companies.json").read_text())
    comps["INE040A01034"]["fy"] = "FY2025-26"  # as rename_reports would set
    (data / "companies.json").write_text(json.dumps(comps))
    (raw_dir / "report_sources.csv").write_text("isin,url,fy\nINE002A01018,https://example.com/ar.pdf,FY2025-26\n")
    build(data, log=lambda *_: None)
    comps = json.loads((data / "companies.json").read_text())
    assert comps["INE040A01034"]["fy"] == "FY2025-26"
    assert comps["INE002A01018"]["source_url"] == "https://example.com/ar.pdf"
    assert comps["INE002A01018"]["report_url"] == "/api/reports/INE002A01018.pdf"


def test_evaluate_flags(tmp_path):
    from pipelines.evaluate_flags import evaluate

    (tmp_path / "scorecards").mkdir()
    card = {"checks": [
        {"id": "cash_vs_profit", "status": "flagged", "evidence": [{"verified": True}]},
        {"id": "receivables", "status": "passed", "evidence": [{"verified": True}]},
        {"id": "promoter_pledge", "status": "not_found", "evidence": []},
        {"id": "related_party", "status": "flagged", "evidence": [{"verified": False}]},
    ]}
    (tmp_path / "scorecards" / "X.json").write_text(json.dumps(card))
    labels = tmp_path / "labels.csv"
    labels.write_text("isin,check_id,expected\nX,cash_vs_profit,flagged\nX,receivables,flagged\nX,promoter_pledge,passed\nX,related_party,passed\n")
    r = evaluate(tmp_path, labels)
    assert r["labelled_checks"] == 4 and r["coverage"] == 0.75
    assert r["flag_precision"] == 0.5 and r["flag_recall"] == 0.5
    assert r["evidence_verified_rate"] == 0.667


def test_absl_style_sheet_name_description_and_month_first_date():
    # Real Aditya Birla layout: code + NAME in row 0, SEBI description in row 1, "October 31, 2026"
    df = pd.DataFrame([
        ["ABSLMCF", "ADITYA BIRLA SUN LIFE MULTI-CAP FUND"],
        ["An open-ended equity scheme investing across large cap, mid cap & small cap stocks"],
        ["Portfolio Statement as on October 31, 2026"],
        ["Name of the Instrument / Issuer", "ISIN", "Industry^ / Rating", "Quantity", "Market value\n(Rs. in Lakhs)", "% to AUM", "YTM %"],
        [],
        ["Equity & Equity Related"],
        ["ICICI Bank Ltd.", "INE090A01021", "Banks", 1573613, 21999.11, 0.0311],
        ["HDFC Bank Ltd.", "INE040A01034", "Banks", 1, 1, 0.0290],
    ])
    from pipelines.parse_amc_portfolios import parse_sheet

    r = parse_sheet(df, "ABSLMCF")
    assert r["scheme_name"] == "Aditya Birla Sun Life Multi-Cap Fund"
    assert r["asof"] == "2026-10-31"
    assert r["holdings"][0]["weight"] == pytest.approx(0.0311)


def test_match_without_growth_word(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    rows = [
        {"amfi": "1", "isin_1": "INF1", "isin_2": "", "name": "XYZ Flexi Cap Fund - Direct Plan", "nav": "1", "date": "", "amc": "XYZ Mutual Fund", "category": "Equity Scheme - Flexi Cap Fund", "plan": "direct", "option": "other"},
        {"amfi": "2", "isin_1": "INF2", "isin_2": "", "name": "XYZ Flexi Cap Fund - Regular Plan", "nav": "1", "date": "", "amc": "XYZ Mutual Fund", "category": "Equity Scheme - Flexi Cap Fund", "plan": "regular", "option": "other"},
        {"amfi": "3", "isin_1": "INF3", "isin_2": "INF4", "name": "XYZ Flexi Cap Fund - Regular Plan - IDCW", "nav": "1", "date": "", "amc": "XYZ Mutual Fund", "category": "Equity Scheme - Flexi Cap Fund", "plan": "regular", "option": "idcw"},
    ]
    with (raw / "amfi_schemes.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (raw / "holdings_raw.json").write_text(json.dumps([{"scheme_name": "XYZ Flexi Cap Fund", "amc_hint": "", "asof": "", "sheet": "S", "file": "f.xlsx",
                                                         "holdings": [{"isin": "INE040A01034", "name": "Bank", "sector": "Banks", "weight": 0.9}]}]))
    stats = build(tmp_path, log=lambda *_: None)
    assert stats["funds"] == 1 and stats["unmatched"] == 0
    plans = json.loads((tmp_path / "funds.json").read_text())[0]["plans"]
    assert plans["regular"]["amfi"] == "2" and plans["direct"]["amfi"] == "1"  # IDCW not chosen


def test_plan_spellings_and_sample_never_empty(tmp_path):
    from pipelines.build_dataset import _plan_of, write_sample_portfolio

    for name in ("X Fund - Direct Plan - Growth", "X Fund-DirectPlan-Growth", "X FUND DIR GR", "X Fund (D) Growth"):
        assert _plan_of({"name": name}) == "direct", name
    assert _plan_of({"name": "X Fund - Regular Plan - Growth"}) == "regular"
    # funds with only one plan each must still give a non-empty sample
    funds = [{"scheme_id": f"S{i}", "name": f"Fund {i}", "category": "Equity", "plans": {"regular": {}}, "holdings": [1]} for i in range(3)]
    write_sample_portfolio(tmp_path, funds)
    sample = json.loads((tmp_path / "sample_portfolio.json").read_text())
    assert len(sample["holdings"]) == 3 and all(h["plan"] == "regular" for h in sample["holdings"])


def test_sbi_layout_label_cells_and_index_sheet(tmp_path):
    """SBI: 'SCHEME NAME :' label cell, name in the next cell, date as its own cell, Index sheet."""
    from pipelines.parse_amc_portfolios import parse_paths

    def sheet(name_cell):
        rows = [[None] * 6 for _ in range(6)]
        rows[1][2], rows[1][3] = "SBI Mutual Fund", "017"
        rows[2][2], rows[2][3] = "SCHEME NAME :", name_cell
        rows[3][2], rows[3][3] = "PORTFOLIO STATEMENT AS ON :", pd.Timestamp("2026-10-31")
        rows[5][2:6] = ["Name of the Instrument / Issuer", "ISIN", "Quantity", "% to AUM"]
        rows.append([None, None, "Alpha Ltd", "INE000A01016", 10, 0.6])
        rows.append([None, None, "Beta Ltd", "INE000B01014", 10, 0.38])
        return pd.DataFrame(rows)

    index = pd.DataFrame([["Index", None, None], ["Scheme Code", "Scheme Short code", "Scheme Name"],
                          ["017", "SLMF", "SBI Large and Midcap Fund"],
                          ["024", "SEHF", "SBI Aggressive Hybrid Fund (Erstwhile known as SBI Equity Hybrid Fund)"]])
    f = tmp_path / "sbi.xlsx"
    with pd.ExcelWriter(f) as w:
        index.to_excel(w, sheet_name="Index", header=False, index=False)
        sheet("SBI Large and Midcap Fund").to_excel(w, sheet_name="SLMF", header=False, index=False)
        sheet(None).to_excel(w, sheet_name="SEHF", header=False, index=False)  # name only on the Index sheet
    out = {o["sheet"]: o for o in parse_paths([f], log=lambda *_: None)}
    assert out["SLMF"]["scheme_name"] == "SBI Large and Midcap Fund"
    assert out["SLMF"]["asof"] == "2026-10-31" and out["SLMF"]["amc_hint"] == "SBI Mutual Fund"
    assert out["SEHF"]["scheme_name"] == "SBI Aggressive Hybrid Fund"


def test_amfi_new_layout_with_plan_and_option_columns():
    from pipelines.build_dataset import _fix_amfi_rows, _prefer_growth
    from pipelines.fetch_amfi import parse

    text = ("Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date\n"
            "Open Ended Schemes(Equity Scheme - Flexi Cap Fund)\nX Mutual Fund\n"
            "1;INF1;-;X Flexi Cap Fund;Direct Plan;Growth;10.5;31-Oct-2026\n"
            "2;INF2;-;X Flexi Cap Fund;Regular Plan;Growth;10.1;31-Oct-2026\n")
    rows = parse(text)
    assert {r["plan"] for r in rows} == {"direct", "regular"} and rows[0]["nav"] == "10.5"
    # CSVs saved by the old parser: plan landed in 'nav', option in 'date'
    old = [{"amfi": "1", "isin_1": "INF1", "isin_2": "", "name": "X Flexi Cap Fund", "nav": "Direct Plan", "date": "Growth", "plan": "regular", "option": "other"},
           {"amfi": "2", "isin_1": "INF2", "isin_2": "", "name": "X Flexi Cap Fund", "nav": "Regular Plan", "date": "IDCW", "plan": "regular", "option": "other"},
           {"amfi": "3", "isin_1": "INF3", "isin_2": "", "name": "X Flexi Cap Fund", "nav": "Regular Plan", "date": "Growth", "plan": "regular", "option": "other"}]
    best = {r["plan"]: r["amfi"] for r in _prefer_growth(_fix_amfi_rows(old))}
    assert best == {"direct": "1", "regular": "3"}


def _rows(title, isins_pcts, pct_header="% to Net Assets"):
    rows = [[title, None, None, None], ["Portfolio as on 31-Oct-2026", None, None, None],
            ["Name of the Instrument", "ISIN", "Market Value (Rs. lakh)", pct_header]]
    rows += [[f"Co {i}", isin, 100.0 * p, p * 100] for i, (isin, p) in enumerate(isins_pcts)]
    rows += [["Net Current Assets", None, 1.0, 1.0], ["Grand Total", None, 10000.0, 100.0], [None] * 4]
    return rows


A, B, C = "INE000A01016", "INE000B01014", "INE000C01012"


def test_stacked_schemes_in_one_sheet(tmp_path):
    from pipelines.parse_amc_portfolios import parse_paths

    rows = [["XYZ Mutual Fund", None, None, None]] + _rows("XYZ Large Cap Fund", [(A, 0.6), (B, 0.38)]) \
        + _rows("XYZ Small Cap Fund", [(C, 0.9)])
    f = tmp_path / "all.xlsx"
    pd.DataFrame(rows).to_excel(f, header=False, index=False)
    out = parse_paths([f], log=lambda *_: None)
    assert [o["scheme_name"] for o in out] == ["XYZ Large Cap Fund", "XYZ Small Cap Fund"]
    assert out[1]["amc_hint"] == "XYZ Mutual Fund" and out[1]["asof"] == "2026-10-31"
    assert [h["isin"] for h in out[1]["holdings"]] == [C]


def test_csv_market_value_only_and_name_from_file(tmp_path):
    from pipelines.parse_amc_portfolios import parse_paths

    rows = [["Name of the Instrument", "ISIN", "Market Value (Rs. lakh)"], ["Alpha", A, "6,000"], ["Beta", B, "3,000"],
            ["Cash", "", "1,000"], ["Grand Total", "", "10,000"]]
    f = tmp_path / "Monthly XYZ Value Fund - 31 October 2026.csv"
    pd.DataFrame(rows).to_csv(f, header=False, index=False)
    out = parse_paths([f], log=lambda *_: None)
    assert out[0]["scheme_name"] == "XYZ Value Fund"
    assert {h["isin"]: h["weight"] for h in out[0]["holdings"]} == {A: 0.6, B: 0.3}


def test_html_disguised_as_xls_and_nested_zip(tmp_path):
    import zipfile

    from pipelines.parse_amc_portfolios import parse_paths

    html = pd.DataFrame(_rows("XYZ Flexi Cap Fund", [(A, 0.5), (B, 0.45)])).to_html(header=False, index=False)
    inner = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("XYZ Flexi Cap Fund.xls", html)
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as z:
        z.write(inner, "inner.zip")
        z.writestr("__MACOSX/._junk.xls", "x")
    out = parse_paths([outer], log=lambda *_: None)
    assert len(out) == 1 and out[0]["scheme_name"] == "XYZ Flexi Cap Fund"


def test_pdf_with_isins(tmp_path):
    import pymupdf

    from pipelines.parse_amc_portfolios import parse_paths

    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for line in ["XYZ Mutual Fund", "XYZ Midcap Fund", "Portfolio as on Oct 31,2026",
                 f"Alpha Ltd {A} Finance 1000 600.00 6.00%", f"Beta Ltd {B} Energy 500 300.00 3.00%"]:
        page.insert_text((72, y), line)
        y += 16
    f = tmp_path / "xyz.pdf"
    doc.save(f)
    out = parse_paths([f], log=lambda *_: None)
    assert out[0]["scheme_name"] == "XYZ Midcap Fund"
    assert {h["isin"]: h["weight"] for h in out[0]["holdings"]} == {A: 0.06, B: 0.03}


def test_unreadable_files_are_reported(tmp_path):
    from pipelines.parse_amc_portfolios import parse_paths

    (tmp_path / "notes.csv").write_text("hello,world\n")
    logs: list[str] = []
    assert parse_paths([tmp_path], log=logs.append) == []
    assert any("XX" in l and "notes.csv" in l for l in logs)


def test_debt_fund_is_reported_as_non_equity(tmp_path):
    from pipelines.parse_amc_portfolios import parse_paths

    rows = [["XYZ Liquid Fund"], ["Name of the Instrument", "ISIN", "% to NAV"], ["91 Day T-Bill", "IN002026X123", 50.0]]
    f = tmp_path / "XYZ Liquid Fund.xlsx"
    pd.DataFrame(rows).to_excel(f, header=False, index=False)
    logs: list[str] = []
    assert parse_paths([f], log=logs.append) == []
    assert any("fine to ignore" in l for l in logs) and any("0 need a look" in l for l in logs)


def test_benchmark_citation_guard_and_fallbacks():
    import asyncio
    import os

    from app.data_store import DataStore
    from pipelines.benchmark import citation_guard, fallbacks

    cg = citation_guard(DataStore(Path(os.environ["DATA_DIR"])))
    assert cg["genuine_quotes"] > 0 and cg["genuine_accepted_pct"] == 100.0
    assert cg["tampered_rejected_pct"] == 100.0
    assert all(f["ok"] for f in asyncio.run(fallbacks()))


def test_backtest_company_not_held_by_any_fund(raw_dir):
    data = raw_dir.parent
    (raw_dir / "holdings_raw.json").write_text(json.dumps(parse_paths([raw_dir / "portfolios"], log=lambda *_: None)))
    (raw_dir / "report_sources.csv").write_text(
        "isin,url,fy,event_date,event,name,source\n"
        "INE999Z01019,https://example.com/ar.pdf,FY2023-24,2025-04-15,Regulator found funds diverted,Fallen Co Ltd,https://news.example/x\n"
        "BADISIN,,,,,Ignored Co,\n")
    build(data, log=lambda *_: None)
    comps = json.loads((data / "companies.json").read_text())
    c = comps["INE999Z01019"]
    assert c["name"] == "Fallen Co Ltd" and c["backtest_only"] and c["fy"] == "FY2023-24"
    assert c["event"] == {"date": "2025-04-15", "summary": "Regulator found funds diverted", "source": "https://news.example/x"}
    assert "BADISIN" not in comps
    funds = json.loads((data / "funds.json").read_text())
    assert all(h["isin"] != "INE999Z01019" for f in funds for h in f["holdings"])


def test_report_list_ranks_sample_first():
    import os

    from pipelines.report_list import ranked

    rows = ranked(Path(os.environ["DATA_DIR"]), 5)
    assert rows[0]["in_sample_rupees"] >= rows[1]["in_sample_rupees"] > 0
    assert any(r["have_scorecard"] for r in ranked(Path(os.environ["DATA_DIR"]), 30))


def test_new_year_archives_old_scorecard(tmp_path):
    from pipelines.build_redflags import _archive_if_new_year

    (tmp_path / "scorecards").mkdir()
    (tmp_path / "scorecards" / "X.json").write_text(json.dumps({"fy": "FY2024-25", "checks": []}))
    _archive_if_new_year(tmp_path, "X", {"fy": "FY2025-26"})
    assert json.loads((tmp_path / "scorecards" / "history" / "X" / "FY2024-25.json").read_text())["fy"] == "FY2024-25"
    _archive_if_new_year(tmp_path, "X", {"fy": "FY2024-25"})  # same year: nothing new archived
    assert len(list((tmp_path / "scorecards" / "history" / "X").glob("*.json"))) == 1


def test_evaluate_reports_false_alarms_and_misses(tmp_path):
    from pipelines.evaluate_flags import evaluate

    (tmp_path / "scorecards").mkdir()
    (tmp_path / "companies.json").write_text(json.dumps({"A": {"name": "Alpha Ltd"}}))
    card = {"checks": [{"id": "receivables", "status": "flagged", "evidence": []},
                       {"id": "cash_vs_profit", "status": "passed", "evidence": []},
                       {"id": "contingent_liabilities", "status": "not_applicable", "evidence": []}]}
    (tmp_path / "scorecards" / "A.json").write_text(json.dumps(card))
    labels = tmp_path / "labels.csv"
    labels.write_text("isin,check_id,expected\nA,receivables,passed\nA,cash_vs_profit,flagged\nA,contingent_liabilities,flagged\n")
    r = evaluate(tmp_path, labels)
    assert r["labelled_checks"] == 2  # not applicable is skipped
    assert r["false_positives"] == 1 and r["false_negatives"] == 1
    kinds = {e["kind"] for e in r["examples"]}
    assert kinds == {"false alarm", "missed"} and r["examples"][0]["company"] == "Alpha Ltd"


def test_page_rows_keeps_label_with_figures(tmp_path):
    import pymupdf

    from app.redflag.engine import _heuristic_values, read_pdf_pages, read_pdf_rows, unpipe_cells

    pdf = tmp_path / "t.pdf"
    doc = pymupdf.open()
    pg = doc.new_page()
    # a table the way annual reports draw it: label and each year's figure as separate text objects
    for y, (label, a, b) in enumerate([("Trade receivables", "1,234.50", "1,100.20"), ("Revenue from operations", "9,876.00", "8,000.00")]):
        pg.insert_text((50, 100 + 20 * y), label)
        pg.insert_text((350, 100 + 20 * y), a)
        pg.insert_text((450, 100 + 20 * y), b)
    doc.save(pdf)
    rows = read_pdf_rows(pdf)[1]
    assert "Trade receivables | 1,234.50 | 1,100.20" in rows
    vals, ev = _heuristic_values({1: unpipe_cells(rows)}, [])
    assert vals["receivables_current"] == 1234.5 and vals["revenue_previous"] == 8000.0
    assert read_pdf_pages(pdf)[1]  # plain text still available for wording checks


def test_evaluate_reports_stage_metrics(tmp_path):
    import json

    from pipelines.evaluate_flags import evaluate

    (tmp_path / "scorecards").mkdir()
    (tmp_path / "scorecards" / "X.json").write_text(json.dumps({"checks": [
        {"id": "promoter_pledge", "status": "flagged", "seen_pages": [10, 40], "evidence": [{"page": 41, "verified": True}]},
        {"id": "related_party", "status": "not_found", "seen_pages": [5], "evidence": []},
        {"id": "auditor_opinion", "status": "passed", "seen_pages": [100], "evidence": [{"page": 100, "verified": True}]}]}))
    lab = tmp_path / "l.csv"
    lab.write_text("isin,check_id,expected,gold_page\nX,promoter_pledge,flagged,40\nX,related_party,flagged,77\n"
                   "X,auditor_opinion,passed,100\nX,receivables,,\n")
    r = evaluate(tmp_path, lab)
    assert r["labelled_checks"] == 3 and r["flag_precision"] == 1.0
    assert r["false_negative_rate"] == 0.5          # a not-found counts as a missed warning
    assert r["retrieval_hit_rate"] == 0.667 and r["evidence_page_accuracy"] == 1.0


def test_backtest_case_lead_time():
    from app.main import _months_between

    assert _months_between("2024-09-07", "2025-04-15") == 7
    assert _months_between("", "2025-04-15") is None


def test_reapply_rules_clears_a_retired_warning():
    from pipelines.reapply_rules import reapply

    card = {"name": "X", "checks": [{"id": "cash_vs_profit", "status": "flagged", "review": {"agree": True},
                                     "values": {"pat_current": 110, "pat_previous": 100, "cfo_current": 200, "cfo_previous": 230},
                                     "evidence": [{"verified": True}]}]}
    assert reapply(card) == ["X: cash_vs_profit flagged -> passed"]
    assert card["counts"]["passed"] == 1 and "review" not in card["checks"][0]


def test_related_party_table_is_added_up_by_code(tmp_path):
    import pymupdf

    from app.redflag.engine import read_pdf_rows, rpt_from_notes

    pdf = tmp_path / "r.pdf"
    doc = pymupdf.open()
    pg = doc.new_page()
    lines = [("Notes to the Consolidated Financial Statements", []), ("Related Party Disclosure (Rs in Crore)", []),
             ("Nature of Transaction", ["2024", "2023", "2024", "2023"]),
             ("1", ["Loans given :-"]), ("Promoter Co Pvt Ltd", ["-", "-", "100.00", "20.00"]),
             ("Other Co Pvt Ltd", ["5.00", "-", "50.00", "10.00"]),
             ("2", ["Salary :-"]), ("Mr Founder", ["-", "-", "9.00", "8.00"])]
    for i, (label, cells) in enumerate(lines):
        y = 80 + 18 * i
        pg.insert_text((40, y), label)
        for j, c in enumerate(cells):
            pg.insert_text((260 + 70 * j, y), c)
    doc.save(pdf)
    r = rpt_from_notes(read_pdf_rows(pdf))
    assert r["basis"] == "consolidated"
    assert r["rpt_current"] == 155.0 and r["rpt_previous"] == 30.0   # salary left out
    assert r["largest_type"].startswith("Loans given")


def test_figure_check_matches_across_units():
    from pipelines.check_figures import match

    assert match(76025.97, 76026) == "crore"
    assert match(746712933, 74671.29) == "thousand"
    assert match(80.48, 53) is None


def test_figure_check_detects_wrong_basis_and_mixing(tmp_path):
    import json

    from pipelines.check_figures import check

    ref = tmp_path / "ref.csv"
    ref.write_text("isin,company,basis,year,field,value_crore,source\n"
                   "X,Co,consolidated,current,pat,100,s\nX,Co,consolidated,current,cfo,90,s\n"
                   "X,Co,standalone,current,pat,60,s\nX,Co,standalone,current,cfo,70,s\n")
    (tmp_path / "scorecards").mkdir()
    (tmp_path / "scorecards" / "X.json").write_text(json.dumps({"checks": [
        {"id": "cash_vs_profit", "basis": "consolidated", "values": {"pat_current": 100, "cfo_current": 70}}]}))
    r = check(tmp_path, ref)
    assert r["matched_labelled_basis"] == 1 and r["wrong_basis_label"] == 1 and r["mismatched"] == 0
    assert r["mixed_basis_checks"] == [{"company": "Co", "check": "cash_vs_profit"}]
