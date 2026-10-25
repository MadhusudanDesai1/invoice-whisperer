"""Metrics including human review: python scripts/evaluate_review.py [--threshold 0.85]"""
import argparse

from invoice_whisperer.config import ROOT, load_settings
from invoice_whisperer.evaluate import load_frame, metrics, review_metrics
from invoice_whisperer.store import connect

ap = argparse.ArgumentParser()
ap.add_argument("--threshold", type=float, default=None)
args = ap.parse_args()
t = args.threshold if args.threshold is not None else load_settings().confidence_threshold

df = load_frame(connect(ROOT / "data/outputs/results.db"), ROOT / "data/synthetic")
m, r = metrics(df, t), review_metrics(df, t)
print(f"=== BEFORE human review (model only, threshold {t}) ===")
print(f"field accuracy        : {m['field_accuracy']:.1%}")
print(f"exact-match total     : {m['exact_match_total']:.1%}")
print(f"=== AFTER human review ===")
print(f"fields reviewed       : {r['reviewed_fields']}")
print(f"fields corrected      : {r['corrected_fields']}")
print(f"correction rate       : {r['correction_rate']:.1%}")
print(f"model right on reviewed: {r['model_correct_when_reviewed']:.1%}")
print(f"final field accuracy  : {r['final_accuracy_all']:.1%}")
print(f"final exact-match total: {r['final_exact_total']:.1%}")
print(f"flagged but unreviewed: {r['unreviewed_flagged']}")
