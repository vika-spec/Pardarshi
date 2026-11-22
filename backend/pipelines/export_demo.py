"""Export an offline copy of the demo for the frontend (public/demo/).

If the API is unreachable, the site falls back to these files and says so,
so judges and the demo video never see a blank screen.

    python -m pipelines.export_demo ../frontend/public/demo
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def main(out: Path) -> None:
    import logging

    logging.disable(logging.INFO)  # one line of output instead of a log line per page
    (out / "scorecards").mkdir(parents=True, exist_ok=True)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    (out / "timeline").mkdir(parents=True, exist_ok=True)
    with TestClient(app) as c:
        sample = c.get("/api/sample").json()
        (out / "sample.json").write_text(json.dumps(sample, ensure_ascii=False), "utf-8")
        (out / "methodology.json").write_text(json.dumps(c.get("/api/methodology").json(), ensure_ascii=False), "utf-8")
        cases = c.get("/api/cases").json()
        (out / "cases.json").write_text(json.dumps(cases, ensure_ascii=False), "utf-8")
        isins = list(dict.fromkeys([comp["isin"] for comp in sample["risk"]["companies"]] + [k["isin"] for k in cases.get("cases", [])]))
        for isin in isins:
            tl = c.get(f"/api/companies/{isin}/timeline")
            if tl.status_code == 200:
                (out / "timeline" / f"{isin}.json").write_text(json.dumps(tl.json(), ensure_ascii=False), "utf-8")
            card = c.get(f"/api/companies/{isin}/scorecard").json()
            (out / "scorecards" / f"{isin}.json").write_text(json.dumps(card, ensure_ascii=False), "utf-8")
            pages = {}
            # only the pages the evidence cites (and their neighbours): keeps the bundle small for a static host
            wanted = sorted({q for k in card["checks"] for e in k.get("evidence", []) for q in (e["page"] - 1, e["page"], e["page"] + 1)})
            for p in wanted:
                r = c.get(f"/api/companies/{isin}/pages/{p}")
                if r.status_code == 200:
                    pages[str(p)] = r.json()["text"]
            (out / "pages" / f"{isin}.json").write_text(json.dumps(pages, ensure_ascii=False), "utf-8")
    print(f"Offline demo written to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "../frontend/public/demo"))
