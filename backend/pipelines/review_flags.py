"""Second-model review of every warning sign in the finished scorecards.

    python -m pipelines.review_flags             # review flags that haven't been reviewed yet
    python -m pipelines.review_flags --redo      # review all again

Run after build_redflags. Uses a different AI provider from the one that found the warning when
one is available (set LLM_ORDER to control which). No PDFs needed: it reads the saved page text.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.data_store import DataStore  # noqa: E402
from app.llm import LLMClient  # noqa: E402
from app.redflag.review import review_card  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("review_flags")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--rate-wait", type=float, default=45.0)
    a = ap.parse_args()
    store = DataStore(settings.data_dir)
    llm = LLMClient(settings)
    llm.rate_wait_max = a.rate_wait
    if not llm.enabled:
        sys.exit("No AI key set in backend/.env; the review needs one.")
    agreed = disputed = 0
    for isin in sorted(store.covered_isins):
        path = settings.data_dir / "scorecards" / f"{isin}.json"
        card = json.loads(path.read_text("utf-8"))
        n = await review_card(llm, card, store.pages(isin), redo=a.redo)
        if n:
            path.write_text(json.dumps(card, ensure_ascii=False, indent=1), "utf-8")
        for c in card["checks"]:
            if c.get("review"):
                agreed += c["review"]["agree"]
                disputed += not c["review"]["agree"]
        log.info("%-28s reviewed %d  -> flagged=%d disputed=%d", card["name"][:28], n,
                 card["counts"].get("flagged", 0), card["counts"].get("disputed", 0))
    await llm.aclose()
    total = agreed + disputed
    log.info("Second reviewer agreed with %d of %d warning signs%s", agreed, total,
             f" ({100 * agreed / total:.0f}%)" if total else "")


if __name__ == "__main__":
    asyncio.run(main())
