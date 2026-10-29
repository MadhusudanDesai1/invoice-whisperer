"""Run any bill through the pipeline: python scripts/demo.py path/to/bill.pdf"""
import sys
from pathlib import Path

from invoice_whisperer.config import ROOT, load_settings
from invoice_whisperer.ingest import load_pages
from invoice_whisperer.pipeline import process_document
from invoice_whisperer.router import canonical_value, route
from invoice_whisperer.store import connect, save_result


def main() -> None:
    src = Path(sys.argv[1])
    s = load_settings()
    pages = load_pages(src)
    print(f"{len(pages)} page(s) read; using page 1 only")
    png = ROOT / "data" / "demo" / f"{src.stem}.png"  # the review page needs an image
    pages[0].save(png)

    r = process_document(png, s)
    conn = connect(ROOT / "data" / "outputs" / "demo.db")  # separate from results.db
    save_result(conn, r, s.confidence_threshold)
    if r.extraction is None:
        print("Extraction failed:", r.error)
        return

    decisions = route(r.confidence, s.confidence_threshold)
    print(f"\nreal API calls: {r.api_calls} | threshold {s.confidence_threshold}\n")
    for f, c in r.confidence.items():
        val = (canonical_value(r.extraction, f) or "")[:60]
        tag = "AUTO  " if decisions[f] == "auto" else "REVIEW"
        print(f"{tag} {f:11} conf={c.final:.2f}  {val}")
    print("\nvalidation issues:", r.validation.issues or "none")


main()
