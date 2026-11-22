"""Parse fund houses' monthly portfolio disclosure spreadsheets into holdings.

SEBI requires every fund house to publish each scheme's full portfolio every
month, usually as an Excel workbook with one sheet per scheme (sometimes one
file per scheme, sometimes zipped). Layouts differ, but nearly all have a
header row with an ISIN column and a '% to NAV' column. This parser finds that
header on each sheet and keeps listed Indian equity shares (ISIN 'INE…' with
security type '01').

    python -m pipelines.parse_amc_portfolios data/raw/portfolios/
    python -m pipelines.parse_amc_portfolios hdfc.xlsx sbi.zip nippon.xls

Accepts files, folders and .zip archives containing any of:
  .xlsx .xlsm .xls .xlsb .ods   (one sheet per scheme, or several schemes stacked in one sheet)
  .csv                          (one scheme per file)
  .html / .xls that is really HTML (some fund houses serve this)
  .pdf                          (only if the PDF lists ISINs; Excel is always more reliable)
If there is no % column, weights are worked out from market value and the scheme's total.
Writes DATA_DIR/raw/holdings_raw.json and prints a per-file report.
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PCT_COL = re.compile(
    r"%\s*(to|of)\s*(the\s+)?(nav|net\s*assets?|aum)|percentage\s+(to|of)\s+(nav|net\s*assets?)|net\s*assets?\s*\(?%|^\s*%\s*$|weight(age)?\s*\(?%",
    re.I,
)
NAME_COL = re.compile(r"name\s+of\s+(the\s+)?(instrument|issuer|security|company)|instrument|issuer|security|company|scrip", re.I)
SECTOR_COL = re.compile(r"industry|sector", re.I)
EQUITY_ISIN = re.compile(r"^INE[A-Z0-9]{4}01[A-Z0-9]{2}[0-9]$")  # e.g. INE002A01018 (equity shares)
ASOF = re.compile(r"as\s+(on|at)\s*:?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\s\-/.]*[A-Za-z]+[\s\-/.,]*[0-9]{2,4}|[A-Za-z]+\s+[0-9]{1,2}(?:st|nd|rd|th)?,?\s+[0-9]{4}|[0-9]{1,2}[\-/.][0-9]{1,2}[\-/.][0-9]{2,4})", re.I)
EXCEL_EXT = {".xlsx", ".xlsm", ".xls", ".xlsb", ".ods"}
OTHER_EXT = {".csv", ".html", ".htm", ".pdf"}
ALL_EXT = EXCEL_EXT | OTHER_EXT
VALUE_COL = re.compile(r"market\s*value|market\s*/\s*fair\s*value|value\s*\(rs|amount\s*\(rs", re.I)
TOTAL_ROW = re.compile(r"grand\s*total|net\s*assets|total\s*net\s*assets|^\s*total\s*$", re.I)


def _cells(row) -> list[str]:
    return [re.sub(r"\s+", " ", str(c)).strip() for c in row.tolist()]


def _is_header(cells: list[str]) -> bool:
    has_isin = any("ISIN" in c.upper() for c in cells)
    return has_isin and (any(PCT_COL.search(c) for c in cells) or any(VALUE_COL.search(c) for c in cells))


def _find_headers(df: pd.DataFrame) -> list[int]:
    """Every table header in the sheet (some fund houses stack many schemes in one sheet)."""
    return [i for i in range(len(df)) if _is_header(_cells(df.iloc[i]))]


def _find_header(df: pd.DataFrame) -> int | None:
    hs = _find_headers(df)
    return hs[0] if hs else None


DESCRIPTION = re.compile(r"^\s*(an?|the)\s+open|open[- ]ended|scheme\s+(investing|tracking|replicating|following|predominantly)|exchange\s+traded\s+fund\s+tracking", re.I)


LABEL = re.compile(r"^\s*(scheme\s*name|name\s+of\s+the\s+scheme|portfolio\s+statement\s+as\s+on|portfolio\s+as\s+on|as\s+on)\s*[:\-]?\s*$", re.I)
DATE_CELL = re.compile(r"^\d{4}-\d{2}-\d{2}( 00:00:00)?$")
FORMER = re.compile(r"\s*\((an? open[- ]ended|formerly|erstwhile|previously)[^)]*\)?", re.I)


def _clean_name(s: str) -> str:
    return FORMER.sub("", s).strip()


def _index_names(book: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Some workbooks (SBI) list 'short code -> scheme name' on an Index sheet."""
    out: dict[str, str] = {}
    sheets = set(map(str, book))
    for name, df in book.items():
        if not re.search(r"index|contents|scheme", str(name), re.I) or df.shape[0] > 2000:
            continue
        for _, row in df.iterrows():
            cells = [c for c in _cells(row) if c and c.lower() != "nan"]
            code = next((c for c in cells if c in sheets and c != str(name)), None)
            label = next((c for c in cells if re.search(r"fund|etf|plan|scheme", c, re.I) and c != code), None)
            if code and label:
                out[code] = _clean_name(label)
    return out


def _context(df: pd.DataFrame, header: int, sheet: str, start: int = 0) -> tuple[str, str, str]:
    """(scheme name, fund house, as-of date) from the lines above the table.

    Fund houses put the name, a SEBI category description ("An open-ended equity
    scheme investing in…") and the date above the table, in varying order. The
    name is the first fund/scheme line that isn't a description.
    """
    names, amc, asof = [], "", ""
    for i in range(start, header):
        for s in _cells(df.iloc[i]):
            if not s or s.lower() == "nan" or s == sheet:
                continue
            if LABEL.match(s):  # "SCHEME NAME :" / "PORTFOLIO STATEMENT AS ON :" - the value is in the next cell
                continue
            if not asof and DATE_CELL.match(s):
                asof = s[:10]
                continue
            s = _clean_name(s)
            m = ASOF.search(s)
            if m and not asof:
                try:
                    asof = pd.to_datetime(re.sub(r"(st|nd|rd|th)\b", "", m.group(2)), dayfirst=True).date().isoformat()
                except (ValueError, OverflowError):
                    pass
            if re.search(r"mutual\s+fund\s*$", s, re.I) and len(s) < 80:
                amc = amc or s
            elif (re.search(r"fund|scheme|plan|etf", s, re.I) and len(s) > 8 and not DESCRIPTION.search(s)
                    and not re.search(r"portfolio\s+statement|monthly\s+portfolio", s, re.I)):
                names.append(s)
    scheme = names[0] if names else ""
    scheme = re.sub(r"^\s*(scheme\s*name|name\s+of\s+the\s+scheme)\s*[:\-]\s*", "", scheme, flags=re.I)
    scheme = re.sub(r"\s*\(an? open[- ]ended.*?\)\s*", " ", scheme, flags=re.I)
    scheme = re.sub(r"\s*portfolio\s+as\s+on.*$", "", scheme, flags=re.I).strip(" -:")
    if scheme.isupper():
        scheme = scheme.title().replace("Etf", "ETF").replace("Bse", "BSE").replace("Msci", "MSCI")
    return scheme or sheet, amc, asof


def _to_num(x) -> float | None:
    s = str(x).replace("%", "").replace(",", "").strip()
    if s in ("", "nan", "-", "--", "NIL", "Nil"):
        return None
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return None


def _table(df: pd.DataFrame, h: int, end: int) -> list[dict] | None:
    cols = _cells(df.iloc[h])
    isin_i = next(i for i, c in enumerate(cols) if "ISIN" in c.upper())
    pct_i = next((i for i, c in enumerate(cols) if PCT_COL.search(c)), None)
    val_i = next((i for i, c in enumerate(cols) if VALUE_COL.search(c)), None)
    name_i = next((i for i, c in enumerate(cols) if i != isin_i and NAME_COL.search(c)), None)
    sec_i = next((i for i, c in enumerate(cols) if i not in (isin_i, name_i) and SECTOR_COL.search(c)), None)
    use_i = pct_i if pct_i is not None else val_i

    holdings: dict[str, dict] = {}
    total_value = None
    for _, row in df.iloc[h + 1 : end].iterrows():
        isin = re.sub(r"\s+", "", str(row.iloc[isin_i])).upper()
        if not EQUITY_ISIN.match(isin):
            if pct_i is None and total_value is None and any(TOTAL_ROW.search(c) for c in _cells(row)[: max(isin_i, 3) + 1]):
                total_value = _to_num(row.iloc[val_i])
            continue
        v = _to_num(row.iloc[use_i])
        if v is None or v <= 0:
            continue
        name = str(row.iloc[name_i]).strip() if name_i is not None else isin
        sector = str(row.iloc[sec_i]).strip() if sec_i is not None else "Other"
        rec = holdings.setdefault(isin, {"isin": isin, "name": name, "sector": sector if sector.lower() != "nan" else "Other", "weight": 0.0})
        rec["weight"] += v
    if not holdings:
        return None

    if pct_i is None:  # market value only: divide by the scheme total if we found it
        if not total_value:
            return None
        for r in holdings.values():
            r["weight"] /= total_value
    else:
        # Units differ by fund house: 7.25 (percent) or 0.0725 (fraction). Decide per table.
        vals = [r["weight"] for r in holdings.values()]
        if max(vals) > 1.0 or sum(vals) > 1.5:
            for r in holdings.values():
                r["weight"] /= 100.0
    for r in holdings.values():
        r["weight"] = round(r["weight"], 6)
    return sorted(holdings.values(), key=lambda r: -r["weight"])


def parse_tables(df: pd.DataFrame, sheet: str) -> list[dict]:
    """All scheme tables in a sheet: usually one, sometimes many stacked vertically."""
    heads = _find_headers(df)
    out = []
    for k, h in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(df)
        holdings = _table(df, h, end)
        if not holdings:
            continue
        start = 0 if k == 0 else _last_data_row(df, heads[k - 1], h) + 1
        scheme, amc, asof = _context(df, h, sheet, start)
        out.append({"scheme_name": scheme, "amc_hint": amc, "asof": asof, "sheet": f"{sheet}#{k + 1}", "holdings": holdings})
    if len(out) == 1:  # only number tables when a sheet really holds several schemes
        out[0]["sheet"] = sheet
    # a stacked sheet's later tables often lack their own fund-house/date line: inherit from the first
    for o in out[1:]:
        o["amc_hint"] = o["amc_hint"] or out[0]["amc_hint"]
        o["asof"] = o["asof"] or out[0]["asof"]
    return out


def _last_data_row(df: pd.DataFrame, h: int, nxt: int) -> int:
    """Last row of the previous table that still holds a security, so the next table's title lines start after it."""
    last = h
    for i in range(h + 1, nxt):
        if any(re.match(r"^IN[A-Z0-9]{10}$", c) for c in _cells(df.iloc[i])):
            last = i
    return last


def parse_sheet(df: pd.DataFrame, sheet: str) -> dict | None:
    tables = parse_tables(df, sheet)
    return tables[0] if tables else None


def _name_from_file(label: str) -> str:
    """'Monthly HDFC Value Fund - 31 October 2026.xlsx' -> 'HDFC Value Fund'."""
    stem = Path(label.split("/")[-1]).stem
    stem = re.sub(r"[_]+", " ", stem)
    stem = re.sub(r"\b(monthly|fortnightly|portfolio|disclosure|statement|as\s+on|half\s*yearly)\b", " ", stem, flags=re.I)
    stem = re.sub(r"\b\d{1,2}(st|nd|rd|th)?[\s\-]*[A-Za-z]{3,9}[\s\-,]*\d{2,4}\b|\b\d{6,8}\b|\(\d+\)", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" -_")
    return stem if re.search(r"fund|etf|scheme|plan", stem, re.I) else ""


def _books(path: Path):
    """Yield (label, path-or-bytes, extension) for files, folders and zips (zips inside zips too)."""
    if path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.is_file() and p.suffix.lower() in ALL_EXT | {".zip"}:
                yield from _books(p)
    elif path.suffix.lower() == ".zip":
        yield from _zip_members(zipfile.ZipFile(path), path.name)
    elif path.suffix.lower() in ALL_EXT:
        yield path.name, path, path.suffix.lower()


def _zip_members(z: zipfile.ZipFile, label: str):
    with z:
        for name in z.namelist():
            base = Path(name).name
            if base.startswith(("~$", ".")) or name.startswith("__MACOSX"):
                continue
            ext = Path(name).suffix.lower()
            if ext == ".zip":
                yield from _zip_members(zipfile.ZipFile(io.BytesIO(z.read(name))), f"{label}/{name}")
            elif ext in ALL_EXT:
                yield f"{label}/{name}", io.BytesIO(z.read(name)), ext


def _raw(src) -> bytes:
    if isinstance(src, (str, Path)):
        return Path(src).read_bytes()
    src.seek(0)
    return src.read()


def _read_all_sheets(src, ext: str) -> dict[str, pd.DataFrame]:
    if ext == ".csv":
        data = _raw(src)
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                return {"csv": pd.read_csv(io.BytesIO(data), header=None, dtype=str, encoding=enc, sep=None, engine="python")}
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        raise ValueError("unreadable CSV")
    if ext in (".html", ".htm"):
        return _read_html(_raw(src))
    if ext == ".pdf":
        return _read_pdf(_raw(src))
    engine = {".xls": "xlrd", ".xlsb": "pyxlsb", ".ods": "odf"}.get(ext)
    try:
        return pd.read_excel(src, sheet_name=None, header=None, engine=engine)
    except Exception:
        data = _raw(src)
        head = data[:2048].lower()
        if b"<html" in head or b"<table" in head:  # an '.xls' that is really a web page
            return _read_html(data)
        if engine == "xlrd" and data[:4] == b"PK\x03\x04":  # an '.xls' that is really .xlsx
            return pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
        raise


def _read_html(data: bytes) -> dict[str, pd.DataFrame]:
    tables = pd.read_html(io.BytesIO(data), header=None)
    return {f"table{i + 1}": t for i, t in enumerate(tables)}


ISIN_ANY = re.compile(r"\bIN[EF][A-Z0-9]{9}\b")
PCT_TOKEN = re.compile(r"-?\d{1,3}(?:\.\d+)?\s*%|^-?\d{1,2}\.\d{2,4}$")


def _read_pdf(data: bytes) -> dict[str, pd.DataFrame]:
    """Best effort: rebuild rows from text lines that carry an ISIN, keep the last %-looking number.
    Each scheme title line ('X Fund' near 'Portfolio as on') starts a new block."""
    import pymupdf

    rows: list[list] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            lines = [l.strip() for l in page.get_text("text", sort=True).splitlines() if l.strip()]
            for i, line in enumerate(lines):
                if re.search(r"portfolio\s+(statement\s+)?as\s+(on|at)", line, re.I):
                    title = next((lines[j] for j in range(i - 1, max(-1, i - 4), -1)
                                  if re.search(r"fund|etf|scheme|plan", lines[j], re.I) and not ISIN_ANY.search(lines[j])), "")
                    rows.append([title, None, None])
                    rows.append([line, None, None])
                    rows.append(["Name of the Instrument", "ISIN", "% to NAV"])
                    continue
                m = ISIN_ANY.search(line)
                if not m:
                    continue
                # the % is normally on the same line; otherwise look at the next lines, up to the next security
                window = line[m.end():].split()
                for nxt in lines[i + 1 : i + 3]:
                    if ISIN_ANY.search(nxt) or any(PCT_TOKEN.search(t) for t in window):
                        break
                    window += nxt.split()
                pct = next((t for t in reversed(window) if PCT_TOKEN.search(t)), None)
                rows.append([line[: m.start()].strip(" -|") or m.group(0), m.group(0), pct])
    if not rows:
        return {}
    if not any(r[0] == "Name of the Instrument" for r in rows):
        rows.insert(0, ["Name of the Instrument", "ISIN", "% to NAV"])
    return {"pdf": pd.DataFrame(rows)}


def parse_paths(paths: list[Path], log=print) -> list[dict]:
    out: list[dict] = []
    report: list[tuple[str, int, str]] = []
    for p in paths:
        for label, src, ext in _books(p):
            try:
                book = _read_all_sheets(src, ext)
            except Exception as exc:  # noqa: BLE001
                report.append((label, 0, f"could not open ({type(exc).__name__}: {str(exc)[:80]})"))
                continue
            index = _index_names(book)
            file_name = _name_from_file(label)
            found = []
            has_table = any(_find_headers(df) for df in book.values())
            for sheet, df in book.items():
                for res in parse_tables(df, str(sheet)):
                    base_sheet = res["sheet"].split("#")[0]
                    if res["scheme_name"] in (base_sheet, "") and base_sheet in index:
                        res["scheme_name"] = index[base_sheet]
                    total = sum(h["weight"] for h in res["holdings"])
                    if not 0.05 <= total <= 1.02:
                        log(f"  skip {label}:{res['sheet']} (equity weights sum to {total:.2f}; check the % column units)")
                        continue
                    res["file"] = label
                    found.append(res)
            if len(found) == 1 and file_name and (found[0]["scheme_name"] == found[0]["sheet"] or not re.search(r"fund|etf|scheme|plan", found[0]["scheme_name"], re.I)):
                found[0]["scheme_name"] = file_name  # one scheme per file: the file name is the best label
            for res in found:
                total = sum(h["weight"] for h in res["holdings"])
                note = "  (hybrid/partial?)" if total < 0.6 else ""
                flag = "  (NO NAME FOUND)" if res["scheme_name"] == res["sheet"] else ""
                log(f"  {label}:{res['sheet']} -> {res['scheme_name'][:58]} | {len(res['holdings'])} stocks, {total:.0%} equity{note}{flag}")
            why = ""
            if not found:
                if has_table:
                    why = "no Indian stocks (debt, gold/silver, fund-of-funds or overseas fund) - fine to ignore"
                elif ext == ".pdf":
                    why = "PDF without ISINs - download the Excel version instead"
                else:
                    why = "no table with an ISIN column and a %/market-value column - share this file"
            report.append((label, len(found), why))
            out.extend(found)

    log("\nFile report:")
    for label, n, why in report:
        log(f"  {'OK ' if n else 'XX '} {n:4d} schemes  {label}" + (f"  <- {why}" if why else ""))
    bad = [r for r in report if not r[1]]
    unknown = [r for r in bad if "share this file" in r[2] or "could not open" in r[2]]
    log(f"\n{sum(1 for r in report if r[1])} file(s) OK, {len(bad) - len(unknown)} skipped as non-equity, {len(unknown)} need a look.")
    if unknown:
        log("Share the 'need a look' files so the parser can learn their layout.")
    return out


def main(args: list[str]) -> None:
    from app.config import settings

    if not args:
        args = [str(settings.data_dir / "raw" / "portfolios")]
    out = parse_paths([Path(a) for a in args])
    dest = settings.data_dir / "raw" / "holdings_raw.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False), "utf-8")
    print(f"{len(out)} scheme portfolios -> {dest}")


if __name__ == "__main__":
    main(sys.argv[1:])
