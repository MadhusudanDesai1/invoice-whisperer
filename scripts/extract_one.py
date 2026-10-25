"""Extract one synthetic invoice and compare to truth: python scripts/extract_one.py inv_001 [variant]"""
import json
import sys

from invoice_whisperer.config import ROOT, load_settings
from invoice_whisperer.extract import extract_invoice
from invoice_whisperer.ingest import load_pages
from invoice_whisperer.preprocess import preprocess_page


def main() -> None:
    inv_id = sys.argv[1] if len(sys.argv) > 1 else "inv_001"
    variant = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    s = load_settings()
    folder = ROOT / "data" / "synthetic"
    page = preprocess_page(load_pages(folder / f"{inv_id}.png")[0])
    truth = json.loads((folder / f"{inv_id}.json").read_text(encoding="utf-8"))

    res = extract_invoice(page, s, variant=variant)
    print("cached:", res.cached, "| tokens:", res.usage)
    if res.error:
        print("ERROR:", res.error)
        print("RAW REPLY:", res.raw_text[:800])
        return
    ex = res.extraction
    print(ex.model_dump_json(indent=2))
    print("--- vs ground truth ---")
    for k in ("vendor", "date", "currency", "total"):
        print(f"{k:9} truth={truth[k]:<24} got={getattr(ex, k)}")
    print(f"line_items truth={len(truth['line_items'])} got={len(ex.line_items)}")


if __name__ == "__main__":
    main()
