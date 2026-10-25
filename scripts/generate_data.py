"""Generate the synthetic invoice set: python scripts/generate_data.py [N]"""
import sys
from pathlib import Path

from invoice_whisperer.config import ROOT
from invoice_whisperer.synth import generate

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    out = ROOT / "data" / "synthetic"
    generate(n, out)
    print(f"Generated {n} invoices in {out}")
