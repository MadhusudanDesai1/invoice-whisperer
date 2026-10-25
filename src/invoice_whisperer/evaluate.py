"""Stage 8 (evaluation half): compare stored values with ground-truth labels."""
import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .router import _num


def truth_value(label: dict, field: str) -> str:
    """Ground truth in the same canonical text form the router stores."""
    if field == "total":
        return f"{Decimal(label['total']):.2f}"
    if field == "line_items":
        return json.dumps(
            [{"description": i["description"],
              "quantity": _num(Decimal(str(i["quantity"]))),
              "unit_price": _num(Decimal(i["unit_price"])),
              "amount": _num(Decimal(i["amount"]))}
             for i in label["line_items"]], sort_keys=True)
    return label[field]


def load_frame(conn: sqlite3.Connection, label_dir: Path) -> pd.DataFrame:
    """One row per (document, field) with truth, correctness and metadata."""
    q = ("SELECT f.doc_id, f.field, f.model_value, f.final_value, f.confidence, "
         "f.decision, f.reviewed, f.corrected "
         "FROM fields f JOIN documents d USING (doc_id)")
    rows = [dict(r) for r in conn.execute(q)]
    labels: dict[str, dict] = {}
    for r in rows:
        doc = r["doc_id"]
        if doc not in labels:
            labels[doc] = json.loads((label_dir / f"{doc}.json").read_text(encoding="utf-8"))
        lab = labels[doc]
        r["truth"] = truth_value(lab, r["field"])
        r["noise"] = lab.get("noise", "?")
        r["trap"] = lab.get("trap", "none")
        r["correct"] = r["model_value"] is not None and r["model_value"] == r["truth"]
        r["final_correct"] = r["final_value"] is not None and r["final_value"] == r["truth"]
    df = pd.DataFrame(rows)
    df["correct"] = df["correct"].astype(bool)
    df["final_correct"] = df["final_correct"].astype(bool)
    return df


def metrics(df: pd.DataFrame, threshold: float) -> dict:
    """Headline metrics at one confidence threshold (recomputed from raw confidence)."""
    auto = df["confidence"] >= threshold
    total = df[df["field"] == "total"]
    reviewed = int(df["reviewed"].sum())
    nan = float("nan")
    return {
        "documents": int(df["doc_id"].nunique()),
        "fields": len(df),
        "field_accuracy": float(df["correct"].mean()),
        "exact_match_total": float(total["correct"].mean()) if len(total) else nan,
        "auto_accept_rate": float(auto.mean()),
        "auto_accuracy": float(df[auto]["correct"].mean()) if auto.any() else nan,
        "confident_errors": int((auto & ~df["correct"]).sum()),
        "correction_rate": float(df["corrected"].sum() / reviewed) if reviewed else nan,
    }


def review_metrics(df: pd.DataFrame, threshold: float) -> dict:
    """Metrics that include human review (final_value) at one threshold."""
    rev = df[df["reviewed"] == 1]
    # Final value: human-reviewed fields use final_value; the rest keep the model value.
    flagged = df["confidence"] < threshold
    final_ok = df["final_correct"] | (~(df["reviewed"] == 1) & df["correct"])
    total = df["field"] == "total"
    nan = float("nan")
    return {
        "reviewed_fields": len(rev),
        "corrected_fields": int(df["corrected"].sum()),
        "correction_rate": float(df["corrected"].sum() / len(rev)) if len(rev) else nan,
        "model_correct_when_reviewed": float(rev["correct"].mean()) if len(rev) else nan,
        "final_accuracy_all": float(final_ok.mean()),
        "final_exact_total": float(final_ok[total].mean()),
        "unreviewed_flagged": int((flagged & (df["reviewed"] == 0)).sum()),
    }
