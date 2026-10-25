"""Unit tests for routing and storage (no API calls)."""
from invoice_whisperer.confidence import FieldConfidence
from invoice_whisperer.pipeline import DocResult
from invoice_whisperer.router import canonical_value, route, route_field
from invoice_whisperer.schema import FIELDS, Extraction
from invoice_whisperer.store import connect, save_result


def make(**over) -> Extraction:
    base = {"vendor": "ACME", "date": "2024-04-04", "currency": "USD", "total": "553.8",
            "line_items": [{"description": "A", "quantity": "2.0", "unit_price": "10",
                            "amount": "20.00"}]}
    base.update(over)
    return Extraction.model_validate(base)


def conf(final: float = 0.9) -> dict[str, FieldConfidence]:
    return {f: FieldConfidence(1.0, 1.0, 1.0, final) for f in FIELDS}


def test_threshold_boundary():
    assert route_field(0.85, 0.85) == "auto"
    assert route_field(0.8499, 0.85) == "review"


def test_route_mixed():
    c = conf(0.9)
    c["total"] = FieldConfidence(1, 0.2, 1, 0.5)
    d = route(c, 0.85)
    assert d["total"] == "review" and d["vendor"] == "auto"


def test_canonical_total_has_two_decimals():
    assert canonical_value(make(), "total") == "553.80"


def test_canonical_line_items_ignores_number_formatting():
    a = make(line_items=[{"description": "A", "quantity": "2.0", "unit_price": "10.00", "amount": "20"}])
    b = make(line_items=[{"description": "A", "quantity": "2", "unit_price": "10", "amount": "20.0"}])
    assert canonical_value(a, "line_items") == canonical_value(b, "line_items")


def test_store_roundtrip(tmp_path):
    conn = connect(tmp_path / "t.db")
    r = DocResult("x/inv_900.png", make(), None, None, conf(0.9))
    assert save_result(conn, r, 0.95) is True
    rows = conn.execute("SELECT field, decision, final_value FROM fields").fetchall()
    assert len(rows) == len(FIELDS)
    assert all(row["decision"] == "review" for row in rows)  # 0.9 < 0.95
    assert {row["field"]: row["final_value"] for row in rows}["total"] == "553.80"


def test_failed_document_goes_to_review(tmp_path):
    conn = connect(tmp_path / "t.db")
    save_result(conn, DocResult("x/inv_901.png", None, None, None, error="boom"), 0.85)
    assert conn.execute("SELECT status FROM documents").fetchone()[0] == "failed"
    assert {r[0] for r in conn.execute("SELECT decision FROM fields")} == {"review"}


def test_rerun_never_overwrites_human_review(tmp_path):
    conn = connect(tmp_path / "t.db")
    r = DocResult("x/inv_902.png", make(), None, None, conf(0.9))
    save_result(conn, r, 0.85)
    conn.execute("UPDATE fields SET reviewed=1 WHERE field='vendor'")
    conn.commit()
    assert save_result(conn, r, 0.85) is False
