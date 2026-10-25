"""Human-review helpers: queue query, input normalisation, saving corrections."""
import json
import sqlite3

from .router import _num
from .schema import to_decimal


def normalize_input(field: str, text: str | None) -> str | None:
    """Turn what a human typed into the canonical text form stored in the DB."""
    text = (text or "").strip()
    if not text:
        return None
    if field == "total":
        d = to_decimal(text)
        return None if d is None else f"{d:.2f}"
    if field == "currency":
        return text.upper()
    return text


def items_to_canonical(rows: list[dict]) -> str:
    """Edited line-item table -> the same canonical JSON the router stores."""
    out = []
    for r in rows:
        desc = str(r.get("description") or "").strip() or None
        q, p, a = (to_decimal(r.get(k)) for k in ("quantity", "unit_price", "amount"))
        if desc is None and q is None and p is None and a is None:
            continue  # skip fully blank rows
        out.append({"description": desc, "quantity": _num(q),
                    "unit_price": _num(p), "amount": _num(a)})
    return json.dumps(out, sort_keys=True)


def pending_docs(conn: sqlite3.Connection, threshold: float) -> list[str]:
    """Documents that still have a not-yet-reviewed field below the threshold."""
    q = ("SELECT DISTINCT doc_id FROM fields "
         "WHERE confidence < ? AND reviewed = 0 ORDER BY doc_id")
    return [r[0] for r in conn.execute(q, (threshold,))]


def load_doc(conn: sqlite3.Connection, doc_id: str) -> tuple[str, dict[str, dict]]:
    """Image path and all stored field rows (keyed by field name) for one document."""
    path = conn.execute("SELECT path FROM documents WHERE doc_id=?", (doc_id,)).fetchone()[0]
    rows = conn.execute("SELECT * FROM fields WHERE doc_id=?", (doc_id,)).fetchall()
    return path, {r["field"]: dict(r) for r in rows}


def apply_review(conn: sqlite3.Connection, doc_id: str, new_values: dict[str, str | None],
                 threshold: float) -> tuple[int, int]:
    """Save human decisions. Returns (fields reviewed, fields corrected).

    A field counts as reviewed if it was flagged (confidence < threshold) or the
    human edited it. It counts as corrected if the saved value differs from what
    the model extracted. model_value is never modified.
    """
    stored = {r["field"]: r for r in conn.execute(
        "SELECT field, model_value, confidence FROM fields WHERE doc_id=?", (doc_id,))}
    reviewed = corrected = 0
    with conn:
        for f, new in new_values.items():
            row = stored[f]
            if f == "line_items" and row["model_value"] is None and new == "[]":
                new = None  # failed doc, human added nothing: not a correction
            changed = new != row["model_value"]
            if not (row["confidence"] < threshold or changed):
                continue
            conn.execute(
                "UPDATE fields SET final_value=?, reviewed=1, corrected=? "
                "WHERE doc_id=? AND field=?", (new, int(changed), doc_id, f))
            reviewed += 1
            corrected += int(changed)
    return reviewed, corrected
