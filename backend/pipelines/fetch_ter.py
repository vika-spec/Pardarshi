"""Get AMFI's expense ratio (TER) table into DATA_DIR/raw/ter.xlsx.

Easiest route: open https://www.amfiindia.com/ter-of-mf-schemes, pick the
latest month, 'All' fund houses, download, and save the file as
data/raw/ter.xlsx. build_dataset.py reads it directly.

This script tries the open-source `amfipy` client first (pip install amfipy):

    python -m pipelines.fetch_ter --month 10-2026 --year 2026-2027
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    from app.config import settings

    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True, help="MM-YYYY, e.g. 10-2026")
    ap.add_argument("--year", required=True, help="financial year, e.g. 2026-2027")
    args = ap.parse_args()
    dest = settings.data_dir / "raw" / "ter.xlsx"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        from amfipy.ter import TERClient  # third-party, optional
    except ImportError:
        sys.exit("amfipy is not installed. Either `pip install amfipy` or download the TER sheet from "
                 "https://www.amfiindia.com/ter-of-mf-schemes and save it as data/raw/ter.xlsx")
    try:
        data = TERClient().download_excel(month=args.month, year=args.year)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"amfipy could not download the TER sheet ({exc}). Download it manually from AMFI instead.")
    dest.write_bytes(data)
    print(f"Saved {len(data) // 1024} KB -> {dest}")


if __name__ == "__main__":
    main()
