"""Batch run: python scripts/run_batch.py [--noise ugly|mild|clean|all] [--limit N]"""
import argparse
import json
from decimal import Decimal
from pathlib import Path

from invoice_whisperer.config import ROOT, load_settings
from invoice_whisperer.pipeline import process_document
from invoice_whisperer.router import route
from invoice_whisperer.store import connect, save_result

FOLDER = ROOT / "data" / "synthetic"


def pick_ids(noise: str, limit: int) -> list[str]:
    """Invoice ids (sorted) whose ground-truth noise level matches."""
    ids = []
    for f in sorted(FOLDER.glob("inv_*.json")):
        label = json.loads(f.read_text(encoding="utf-8"))
        if noise == "all" or label["noise"] == noise:
            ids.append(label["id"])
    return ids[:limit]


def quick_wrong(ex, truth: dict) -> list[str]:
    """Simple fields that differ from ground truth (full evaluation comes in Step 11)."""
    wrong = []
    for f in ("vendor", "date", "currency"):
        if getattr(ex, f) != truth[f]:
            wrong.append(f)
    if ex.total is None or ex.total != Decimal(truth["total"]):
        wrong.append("total")
    return wrong


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--noise", default="ugly", choices=["ugly", "mild", "clean", "brutal", "all"])
    ap.add_argument("--limit", type=int, default=8)
    args = ap.parse_args()

    s = load_settings()
    conn = connect(ROOT / "data" / "outputs" / "results.db")
    ids = pick_ids(args.noise, args.limit)
    print(f"Processing {len(ids)} invoices (noise={args.noise}) with model {s.model}")

    total_calls = 0
    for n, inv_id in enumerate(ids, 1):
        try:
            r = process_document(FOLDER / f"{inv_id}.png", s)
        except Exception as e:  # e.g. retries exhausted: skip, cache keeps finished work
            print(f"[{n}/{len(ids)}] {inv_id}: FAILED ({type(e).__name__}: {str(e)[:120]})")
            continue
        total_calls += r.api_calls
        save_result(conn, r, s.confidence_threshold)
        if r.extraction is None:
            print(f"[{n}/{len(ids)}] {inv_id}: extraction failed -> {r.error}")
            continue
        truth = json.loads((FOLDER / f"{inv_id}.json").read_text(encoding="utf-8"))
        flagged = [f for f, d in route(r.confidence, s.confidence_threshold).items()
                   if d == "review"]
        wrong = quick_wrong(r.extraction, truth)
        print(f"[{n}/{len(ids)}] {inv_id}: calls={r.api_calls} "
              f"review={flagged or '-'} wrong={wrong or '-'}")

    print(f"Done. Real API calls: {total_calls} (about {total_calls * 2.4:.0f}K tokens)")


if __name__ == "__main__":
    main()
