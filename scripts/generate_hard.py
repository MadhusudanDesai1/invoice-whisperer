"""Add harder invoices: python scripts/generate_hard.py [N]"""
import sys

from invoice_whisperer.config import ROOT
from invoice_whisperer.synth_hard import generate_hard

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    out = ROOT / "data" / "synthetic"
    generate_hard(n, out)
    print(f"Generated {n} hard invoices in {out}")
