"""Offline: build red-flag scorecards + page text for every company with a report.

    python -m pipelines.build_redflags                 # every company with a PDF that has no scorecard yet
    python -m pipelines.build_redflags --force         # rebuild everything
    python -m pipelines.build_redflags --isin INE...   # just these
    python -m pipelines.build_redflags --dense         # local embeddings + reranker (uses your GPU)
    python -m pipelines.build_redflags --pause 4       # seconds between AI calls (free-tier rate limits)
    python -m pipelines.build_redflags --history       # older years (reports/history/<ISIN>/<FY>.pdf) for the timeline

Reads  DATA_DIR/companies.json and DATA_DIR/reports/<ISIN>.pdf
Writes DATA_DIR/scorecards/<ISIN>.json and DATA_DIR/chunks/<ISIN>.jsonl

Resumable: finished companies are skipped unless --force, and one bad PDF
never stops the run. Set an LLM key (GEMINI_API_KEY, GROQ_API_KEY,
AZURE_OPENAI_* or OLLAMA_URL) for real reports; without one, the pattern
extractor is used and most checks on real 300-page reports will be 'not found'.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.llm import LLMClient  # noqa: E402
from app.redflag.engine import build_scorecard  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("build_redflags")


def _load_dense():
    try:
        from sentence_transformers import CrossEncoder, SentenceTransformer
    except ImportError:
        log.warning("sentence-transformers not installed; using BM25 only (pip install -r requirements-pipeline.txt)")
        return None, None
    dense = SentenceTransformer("BAAI/bge-base-en-v1.5")
    rerank = CrossEncoder("BAAI/bge-reranker-base")
    return dense, rerank


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--isin", action="append", help="only these ISINs")
    ap.add_argument("--dense", action="store_true", help="use local embeddings + reranker")
    ap.add_argument("--no-llm", action="store_true", help="force pattern extraction (no AI)")
    ap.add_argument("--force", action="store_true", help="rebuild scorecards that already exist")
    ap.add_argument("--pause", type=float, default=0.0, help="seconds to wait between AI calls")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many companies")
    ap.add_argument("--history", action="store_true", help="build older-year scorecards for the timeline")
    ap.add_argument("--redo-weak", action="store_true",
                    help="rebuild only scorecards where the AI was skipped (rate limits) or 3+ checks found no data")
    ap.add_argument("--rate-wait", type=float, default=45.0,
                    help="seconds to wait for a rate-limited (429) provider before using the backup method (default 45)")
    args = ap.parse_args()

    data = settings.data_dir
    companies: dict = json.loads((data / "companies.json").read_text("utf-8"))
    (data / "scorecards").mkdir(exist_ok=True)
    (data / "chunks").mkdir(exist_ok=True)
    llm = None if args.no_llm else LLMClient(settings)
    if llm is not None:
        llm.rate_wait_max = args.rate_wait
    if llm is not None and not llm.enabled:
        log.warning("No LLM key set: using pattern extraction. Fine for the demo reports; weak on real ones.")
    dense, rerank = _load_dense() if args.dense else (None, None)
    if args.history:
        await _history(args, data, companies, llm, dense, rerank)
        return

    targets = [i for i in companies if (not args.isin or i in args.isin) and (data / "reports" / f"{i}.pdf").exists()]
    if args.redo_weak:
        targets = [i for i in targets if _weak(data / "scorecards" / f"{i}.json")]
    elif not args.force:
        targets = [i for i in targets if not (data / "scorecards" / f"{i}.json").exists()]
    if args.limit:
        targets = targets[: args.limit]
    log.info("%d companies to process", len(targets))

    done, failed = 0, []
    for n, isin in enumerate(targets, start=1):
        comp = {"isin": isin, **companies[isin]}
        t0 = time.perf_counter()
        try:
            card, pages = await build_scorecard(comp, data / "reports" / f"{isin}.pdf", llm, dense_model=dense, reranker=rerank, pause_s=args.pause)
        except Exception as exc:  # noqa: BLE001 - one bad PDF must not stop the run
            log.error("[%d/%d] %s failed: %s: %s", n, len(targets), comp["name"], type(exc).__name__, str(exc)[:160])
            failed.append(comp["name"])
            continue
        # write page text first, scorecard last, so a scorecard never exists without its pages
        tmp = data / "chunks" / f"{isin}.jsonl.tmp"
        with tmp.open("w", encoding="utf-8") as fh:
            for p, text in sorted(pages.items()):
                fh.write(json.dumps({"page": p, "text": text}, ensure_ascii=False) + "\n")
        tmp.replace(data / "chunks" / f"{isin}.jsonl")
        _archive_if_new_year(data, isin, card)
        (data / "scorecards" / f"{isin}.json").write_text(json.dumps(card, ensure_ascii=False, indent=1), "utf-8")
        c = card["counts"]
        methods = {chk["method"] for chk in card["checks"]}
        log.info("[%d/%d] %-26s %3dp %5.1fs flagged=%d passed=%d not_found=%d unverified=%d n/a=%d via %s",
                 n, len(targets), comp["name"][:26], card["n_pages"], time.perf_counter() - t0,
                 c["flagged"], c["passed"], c["not_found"], c["unverified"], c.get("not_applicable", 0), ",".join(sorted(methods)))
        done += 1
    if llm:
        await llm.aclose()
    log.info("Built %d scorecards in %s", done, data / "scorecards")
    if failed:
        log.warning("%d failed (rerun to retry): %s", len(failed), ", ".join(failed))


def _weak(path: Path) -> bool:
    """A scorecard worth redoing: some checks fell back to pattern matching, or 3+ found no data."""
    if not path.exists():
        return True
    try:
        card = json.loads(path.read_text("utf-8"))
    except ValueError:
        return True
    applicable = [c for c in card["checks"] if c["status"] != "not_applicable"]
    heuristic = sum(1 for c in applicable if c.get("method") == "heuristic")
    missing = sum(1 for c in applicable if c["status"] in ("not_found", "unverified"))
    return heuristic > 0 or missing >= 3


def _archive_if_new_year(data: Path, isin: str, card: dict) -> None:
    """Keep last year's scorecard for the timeline when a newer year replaces it."""
    cur = data / "scorecards" / f"{isin}.json"
    if not cur.exists():
        return
    try:
        old = json.loads(cur.read_text("utf-8"))
    except ValueError:
        return
    if old.get("fy") and old.get("fy") != card.get("fy"):
        hdir = data / "scorecards" / "history" / isin
        hdir.mkdir(parents=True, exist_ok=True)
        (hdir / f"{old['fy']}.json").write_text(json.dumps(old, ensure_ascii=False, indent=1), "utf-8")


async def _history(args, data: Path, companies: dict, llm, dense, rerank) -> None:
    root = data / "reports" / "history"
    jobs = sorted(root.glob("*/*.pdf")) if root.exists() else []
    jobs = [j for j in jobs if j.parent.name in companies and (not args.isin or j.parent.name in args.isin)]
    if not args.force:
        jobs = [j for j in jobs if not (data / "scorecards" / "history" / j.parent.name / f"{j.stem}.json").exists()]
    log.info("%d older reports to process", len(jobs))
    for n, pdf in enumerate(jobs, start=1):
        isin, fy = pdf.parent.name, pdf.stem
        comp = {"isin": isin, **companies[isin], "fy": fy}
        t0 = time.perf_counter()
        try:
            card, _ = await build_scorecard(comp, pdf, llm, dense_model=dense, reranker=rerank, pause_s=args.pause)
        except Exception as exc:  # noqa: BLE001
            log.error("[%d/%d] %s %s failed: %s", n, len(jobs), comp["name"], fy, str(exc)[:160])
            continue
        card["fy"] = fy
        out = data / "scorecards" / "history" / isin
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{fy}.json").write_text(json.dumps(card, ensure_ascii=False, indent=1), "utf-8")
        c = card["counts"]
        log.info("[%d/%d] %-26s %s %5.1fs flagged=%d passed=%d not_found=%d", n, len(jobs), comp["name"][:26], fy,
                 time.perf_counter() - t0, c["flagged"], c["passed"], c["not_found"])
    if llm:
        await llm.aclose()


if __name__ == "__main__":
    asyncio.run(main())
