"""Stage 6 - Route: auto-accept or send to review, plus canonical value strings."""
import json
from decimal import Decimal

from .confidence import FieldConfidence
from .schema import Extraction


def route_field(confidence: float, threshold: float) -> str:
    """'auto' if confidence >= threshold, else 'review'."""
    return "auto" if confidence >= threshold else "review"


def route(conf: dict[str, FieldConfidence], threshold: float) -> dict[str, str]:
    """Routing decision for every field of one document."""
    return {f: route_field(c.final, threshold) for f, c in conf.items()}


def _num(d: Decimal | None) -> str | None:
    """Canonical number text: 2.0 -> '2', 100 -> '100' (no exponent, no trailing zeros)."""
    return None if d is None else format(d.normalize(), "f")


def canonical_value(ex: Extraction, field: str) -> str | None:
    """Stable text form of a field, so storage and comparisons never see '553.8' vs '553.80'."""
    if field == "total":
        return None if ex.total is None else f"{ex.total:.2f}"
    if field == "line_items":
        return json.dumps(
            [{"description": i.description, "quantity": _num(i.quantity),
              "unit_price": _num(i.unit_price), "amount": _num(i.amount)}
             for i in ex.line_items], sort_keys=True)
    return getattr(ex, field)
