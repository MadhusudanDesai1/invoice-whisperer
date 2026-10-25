"""Threshold sweep + plot: python scripts/sweep.py [--target 0.98]"""
import argparse

import matplotlib
matplotlib.use("Agg")  # write PNG files; no GUI window needed
import matplotlib.pyplot as plt

from invoice_whisperer.config import ROOT, load_settings
from invoice_whisperer.evaluate import load_frame
from invoice_whisperer.store import connect
from invoice_whisperer.sweep import best_operating_point, sweep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, default=0.98,
                    help="minimum accuracy required on auto-accepted fields")
    args = ap.parse_args()

    conn = connect(ROOT / "data" / "outputs" / "results.db")
    df = load_frame(conn, ROOT / "data" / "synthetic")
    sw = sweep(df)
    out = ROOT / "data" / "outputs"
    sw.to_csv(out / "threshold_sweep.csv", index=False)

    show = [0.5, 0.7, 0.8, 0.85, 0.9, 0.95, 0.97, 0.99, 1.0]
    rows = sw[sw["threshold"].apply(lambda x: any(abs(x - v) < 1e-9 for v in show))]
    print(f"{len(df)} fields from {df['doc_id'].nunique()} documents\n")
    print(rows.round(3).to_string(index=False))

    best = best_operating_point(sw, args.target)
    configured = load_settings().confidence_threshold
    if best is None:
        print(f"\nNo threshold reaches {args.target:.0%} accuracy on auto-accepted fields.")
    else:
        print(f"\nBest operating point for >= {args.target:.0%} accuracy: "
              f"threshold {best['threshold']:.3f} -> {best['auto_accept_rate']:.1%} of fields "
              f"skip review at {best['auto_accuracy']:.1%} accuracy "
              f"({int(best['confident_errors'])} confident errors)")
        print("Caution: chosen and measured on the same data, so this is optimistic.")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(sw["threshold"], sw["auto_accuracy"] * 100, color="tab:green",
            label="Accuracy on auto-accepted fields (%)")
    ax.plot(sw["threshold"], sw["review_rate"] * 100, color="tab:orange",
            label="Review rate: fields sent to a human (%)")
    ax.axvline(configured, color="gray", linestyle="--", label=f"configured threshold ({configured})")
    if best is not None:
        ax.axvline(best["threshold"], color="tab:red", linestyle=":",
                   label=f"best for >= {args.target:.0%} accuracy ({best['threshold']:.3f})")
    ax.set_xlabel("Confidence threshold")
    ax.set_ylabel("Percent")
    ax.set_ylim(0, 102)
    ax.set_title(f"Accuracy and review rate vs threshold (n = {len(df)} fields)")
    ax.grid(alpha=0.3)
    ax.legend(loc="center left", fontsize=8)
    fig.tight_layout()
    fig.savefig(ROOT / "docs" / "threshold_sweep.png", dpi=150)
    print("\nSaved docs/threshold_sweep.png and data/outputs/threshold_sweep.csv")


if __name__ == "__main__":
    main()
