"""Unit tests for validation rules (no API calls)."""
from invoice_whisperer.schema import FIELDS, Extraction
from invoice_whisperer.validate import validate


def make(**over) -> Extraction:
    base = {
        "vendor": "ACME Ltd", "date": "2024-04-04", "currency": "USD",
        "total": "100.00",
        "line_items": [
            {"description": "A", "quantity": 2, "unit_price": "30.00", "amount": "60.00"},
            {"description": "B", "quantity": 1, "unit_price": "40.00", "amount": "40.00"},
        ],
    }
    base.update(over)
    return Extraction.model_validate(base)


def test_clean_invoice_all_pass():
    v = validate(make())
    assert all(v.scores[f] == 1.0 for f in FIELDS)
    assert v.issues == []


def test_invalid_calendar_date():
    assert validate(make(date="2024-13-45")).scores["date"] == 0.0


def test_non_iso_date():
    assert validate(make(date="04/04/2024")).scores["date"] == 0.0


def test_total_mismatch_flags_total_and_items():
    v = validate(make(total="120.00"))
    assert v.scores["total"] == 0.2 and v.scores["line_items"] == 0.2
    assert v.issues


def test_row_arithmetic_error():
    items = [
        {"description": "A", "quantity": 2, "unit_price": "30.00", "amount": "61.00"},
        {"description": "B", "quantity": 1, "unit_price": "40.00", "amount": "40.00"},
    ]
    v = validate(make(total="101.00", line_items=items))
    assert v.scores["line_items"] == 0.5 and v.scores["total"] == 1.0


def test_unknown_currency_code():
    assert validate(make(currency="XYZ")).scores["currency"] == 0.5


def test_missing_vendor_and_no_items():
    v = validate(make(vendor=None, line_items=[]))
    assert v.scores["vendor"] == 0.0
    assert v.scores["line_items"] == 0.0
    assert v.scores["total"] == 0.7
