"""Evaluate stored results: python scripts/evaluate.py [--threshold 0.85]"""
import argparse

import pandas as pd

from invoice_whisperer.config import ROOT, load_settings
from invoice_whisperer.evaluate import load_frame, metrics
from invoice_whisperer.store import connect


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=None)
    args = ap.parse_args()
    t = args.threshold if args.threshold is not None else load_settings().confidence_threshold

    conn = connect(ROOT / "data" / "outputs" / "results.db")
    df = load_frame(conn, ROOT / "data" / "synthetic")
    m = metrics(df, t)

    print(f"=== HEADLINE (threshold {t}) ===")
    print(f"documents evaluated     : {m['documents']} ({m['fields']} fields)")
    print(f"field accuracy (all)    : {m['field_accuracy']:.1%}")
    print(f"exact-match total       : {m['exact_match_total']:.1%}")
    print(f"auto-accept rate        : {m['auto_accept_rate']:.1%}")
    print(f"accuracy on auto fields : {m['auto_accuracy']:.1%}")
    print(f"confident errors        : {m['confident_errors']} (wrong AND auto-accepted)")
    print(f"correction rate         : {m['correction_rate']:.1%} (n/a until Step 14)")

    df["auto"] = df["confidence"] >= t
    print("\n=== PER FIELD ===")
    print(df.groupby("field").agg(accuracy=("correct", "mean"), auto_rate=("auto", "mean"),
                                  n=("correct", "size")).round(3).to_string())

    print("\n=== PER NOISE LEVEL ===")
    print(df.groupby("noise").agg(documents=("doc_id", "nunique"), accuracy=("correct", "mean"),
                                  auto_rate=("auto", "mean")).round(3).to_string())

    bad = df[df["auto"] & ~df["correct"]]
    print("\n=== CONFIDENT ERRORS (wrong but auto-accepted) ===")
    if bad.empty:
        print("none")
    else:
        pd.set_option("display.max_colwidth", 40)
        print(bad[["doc_id", "field", "model_value", "truth", "confidence"]].to_string(index=False))

    wrong = df[~df["correct"] & ~df["auto"]]
    print(f"\nWrong fields correctly sent to review: {len(wrong)}")


if __name__ == "__main__":
    main()
