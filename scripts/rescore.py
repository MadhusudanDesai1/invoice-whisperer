"""Recompute stored confidences from the saved signals (no API calls).

Use after changing weights or SELF_FLOOR. Human-reviewed decisions are untouched.
"""
from invoice_whisperer.config import ROOT, load_settings
from invoice_whisperer.confidence import blend
from invoice_whisperer.router import route_field
from invoice_whisperer.store import connect

s = load_settings()
conn = connect(ROOT / "data" / "outputs" / "results.db")
rows = conn.execute("SELECT doc_id, field, self_rating, validation, agreement, confidence, "
                    "reviewed FROM fields WHERE self_rating IS NOT NULL").fetchall()
changed = 0
with conn:
    for r in rows:
        new = blend(r["self_rating"], r["validation"], r["agreement"], s.self_floor)
        if abs(new - r["confidence"]) > 1e-9:
            changed += 1
        conn.execute("UPDATE fields SET confidence=? WHERE doc_id=? AND field=?",
                     (new, r["doc_id"], r["field"]))
        if not r["reviewed"]:
            conn.execute("UPDATE fields SET decision=? WHERE doc_id=? AND field=?",
                         (route_field(new, s.confidence_threshold), r["doc_id"], r["field"]))
print(f"floor={s.self_floor} threshold={s.confidence_threshold}: "
      f"{changed} of {len(rows)} confidences changed")
