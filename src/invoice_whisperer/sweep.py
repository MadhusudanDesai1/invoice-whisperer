"""Threshold sweep: accuracy / review rate at every confidence threshold."""
import numpy as np
import pandas as pd


def sweep(df: pd.DataFrame, thresholds=None) -> pd.DataFrame:
    """One row per threshold, computed from the raw stored confidences."""
    if thresholds is None:
        thresholds = np.round(np.arange(0.5, 1.0001, 0.005), 4)
    rows = []
    for t in thresholds:
        auto = df["confidence"] >= t
        n_auto = int(auto.sum())
        rows.append({
            "threshold": float(t),
            "auto_accept_rate": n_auto / len(df),
            "review_rate": 1 - n_auto / len(df),
            "auto_accuracy": float(df[auto]["correct"].mean()) if n_auto else float("nan"),
            "confident_errors": int((auto & ~df["correct"]).sum()),
        })
    return pd.DataFrame(rows)


def best_operating_point(sw: pd.DataFrame, min_accuracy: float):
    """Highest auto-accept rate whose auto-accepted accuracy meets the target.

    Ties go to the lowest threshold. Returns None if no threshold reaches the target.
    """
    ok = sw[sw["auto_accuracy"] >= min_accuracy]
    if ok.empty:
        return None
    return ok.sort_values(["auto_accept_rate", "threshold"],
                          ascending=[False, True]).iloc[0]
