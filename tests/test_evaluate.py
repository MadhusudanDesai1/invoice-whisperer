"""Truth canonicalisation must match what the router stores."""
from invoice_whisperer.evaluate import truth_value
from invoice_whisperer.router import canonical_value
from invoice_whisperer.schema import Extraction

LABEL = {
    "vendor": "ACME", "date": "2024-04-04", "currency": "USD", "total": "553.80",
    "line_items": [{"description": "A", "quantity": 2, "unit_price": "10.50", "amount": "21.00"}],
}


def test_truth_matches_canonical_model_value():
    ex = Extraction.model_validate({
        "vendor": "ACME", "date": "2024-04-04", "currency": "USD", "total": "553.8",
        "line_items": [{"description": "A", "quantity": "2.0", "unit_price": "10.5", "amount": "21"}],
    })
    for f in ("vendor", "date", "currency", "total", "line_items"):
        assert truth_value(LABEL, f) == canonical_value(ex, f)
