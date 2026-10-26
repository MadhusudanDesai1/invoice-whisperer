"""Unit tests for confidence scoring (no API calls)."""
from invoice_whisperer.confidence import agreement, combine
from invoice_whisperer.schema import Extraction


def make(**over) -> Extraction:
    base = {
        "vendor": "ACME Ltd", "date": "2024-04-04", "currency": "USD", "total": "100.00",
        "line_items": [{"description": "A", "quantity": 1, "unit_price": "100.00",
                        "amount": "100.00"}],
        "confidence": {"vendor": 1, "date": 1, "currency": 1, "total": 1, "line_items": 1},
    }
    base.update(over)
    return Extraction.model_validate(base)


def test_identical_passes_agree_fully():
    a = make()
    assert all(v == 1.0 for v in agreement(a, make()).values())


def test_decimal_equality_ignores_formatting():
    assert agreement(make(total="100.0"), make(total="100.00"))["total"] == 1.0


def test_disagreement_detected():
    ag = agreement(make(total="100.00"), make(total="108.00"))
    assert ag["total"] == 0.0


def test_vendor_normalisation():
    assert agreement(make(vendor="ACME Ltd."), make(vendor="acme ltd"))["vendor"] == 1.0


def test_perfect_signals_give_one():
    c = combine(make(), {f: 1.0 for f in make().confidence}, {f: 1.0 for f in make().confidence})
    assert all(fc.final == 1.0 for fc in c.values())


def test_failed_validation_is_capped():
    ones = {f: 1.0 for f in make().confidence}
    c = combine(make(), {**ones, "total": 0.2}, ones)
    assert c["total"].final <= 0.5


def test_self_floor_caps_unsure_field():
    from invoice_whisperer.confidence import blend
    assert blend(0.7, 1.0, 1.0, self_floor=0.9) <= 0.5   # unsure model -> review
    assert blend(0.7, 1.0, 1.0, self_floor=0.0) > 0.9    # rule off: old behaviour
    assert blend(0.95, 1.0, 1.0, self_floor=0.9) > 0.9   # confident model unaffected
