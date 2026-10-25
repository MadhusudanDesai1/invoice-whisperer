"""Unit tests for review helpers (no API calls, no Streamlit)."""
from invoice_whisperer.confidence import FieldConfidence
from invoice_whisperer.pipeline import DocResult
from invoice_whisperer.review import (apply_review, items_to_canonical, normalize_input,
                                      pending_docs)
from invoice_whisperer.router import canonical_value
from invoice_whisperer.schema import FIELDS, Extraction
from invoice_whisperer.store import connect, save_result


def make() -> Extraction:
    return Extraction.model_validate({
        "vendor": "ACME", "date": "2024-04-04", "currency": "USD", "total": "553.8",
        "line_items": [{"description": "A", "quantity": "2.0", "unit_price": "10",
                        "amount": "20.00"}]})


def seeded(tmp_path):
    """DB with one document whose total is low-confidence (0.5), the rest 0.9."""
    conn = connect(tmp_path / "t.db")
    conf = {f: FieldConfidence(1, 1, 1, 0.9) for f in FIELDS}
    conf["total"] = FieldConfidence(1, 0.2, 1, 0.5)
    save_result(conn, DocResult("x/inv_900.png", make(), None, None, conf), 0.85)
    model = {r["field"]: r["model_value"]
             for r in conn.execute("SELECT field, model_value FROM fields")}
    return conn, model


def row(conn, field):
    return conn.execute("SELECT * FROM fields WHERE field=?", (field,)).fetchone()


def test_normalize_input():
    assert normalize_input("total", "$1,234.5") == "1234.50"
    assert normalize_input("currency", " usd ") == "USD"
    assert normalize_input("vendor", "   ") is None


def test_items_roundtrip_matches_router_canonical():
    rows = [{"description": "A", "quantity": "2.0", "unit_price": "10", "amount": "20.00"}]
    assert items_to_canonical(rows) == canonical_value(make(), "line_items")


def test_queue_then_correction(tmp_path):
    conn, model = seeded(tmp_path)
    assert pending_docs(conn, 0.85) == ["inv_900"]
    assert apply_review(conn, "inv_900", {**model, "total": "553.90"}, 0.85) == (1, 1)
    assert pending_docs(conn, 0.85) == []
    r = row(conn, "total")
    assert (r["model_value"], r["final_value"], r["reviewed"], r["corrected"]) == (
        "553.80", "553.90", 1, 1)


def test_confirm_without_change_is_not_a_correction(tmp_path):
    conn, model = seeded(tmp_path)
    assert apply_review(conn, "inv_900", dict(model), 0.85) == (1, 0)


def test_editing_an_auto_field_counts_as_review(tmp_path):
    conn, model = seeded(tmp_path)
    apply_review(conn, "inv_900", {**model, "vendor": "ACME Ltd"}, 0.85)
    r = row(conn, "vendor")
    assert (r["reviewed"], r["corrected"]) == (1, 1)
