"""Stage 5 - Confidence: combine self-rating, validation and two-pass agreement."""
import re
from dataclasses import dataclass
from decimal import Decimal

from .schema import FIELDS, Extraction

# Weights sum to 1.0. Agreement is weighted highest because LLM self-ratings
# tend to be overconfident.
W_SELF, W_VALID, W_AGREE = 0.25, 0.35, 0.40
CAP_ON_FAILED_VALIDATION = 0.5   # validation score <= 0.2 -> confidence capped
DEFAULT_SELF = 0.5               # used when the model gave no self-rating


@dataclass
class FieldConfidence:
    self_rating: float
    validation: float
    agreement: float
    final: float


def _norm_text(s: str | None) -> str:
    """Lowercase, drop punctuation/extra spaces so 'ACME Ltd.' == 'acme ltd'."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _dec_eq(a: Decimal | None, b: Decimal | None) -> bool:
    return a is not None and b is not None and a == b


def _items_agreement(a: Extraction, b: Extraction) -> float:
    """Fraction of line-item rows that match (by position) across the two passes."""
    n = max(len(a.line_items), len(b.line_items))
    if n == 0:
        return 1.0
    matches = 0
    for x, y in zip(a.line_items, b.line_items):
        if (_norm_text(x.description) == _norm_text(y.description)
                and _dec_eq(x.quantity, y.quantity)
                and _dec_eq(x.unit_price, y.unit_price)
                and _dec_eq(x.amount, y.amount)):
            matches += 1
    return matches / n


def agreement(a: Extraction, b: Extraction) -> dict[str, float]:
    """Per-field agreement between two extraction passes (1.0 = identical)."""
    return {
        "vendor": 1.0 if _norm_text(a.vendor) == _norm_text(b.vendor) and a.vendor else 0.0,
        "date": 1.0 if a.date is not None and a.date == b.date else 0.0,
        "currency": 1.0 if a.currency is not None and a.currency == b.currency else 0.0,
        "total": 1.0 if _dec_eq(a.total, b.total) else 0.0,
        "line_items": _items_agreement(a, b),
    }


def combine(ex: Extraction, validation: dict[str, float],
            agree: dict[str, float]) -> dict[str, FieldConfidence]:
    """Blend the three signals into one confidence per field."""
    out: dict[str, FieldConfidence] = {}
    for f in FIELDS:
        s = ex.confidence.get(f, DEFAULT_SELF)
        v = validation.get(f, 0.0)
        g = agree.get(f, 0.0)
        final = W_SELF * s + W_VALID * v + W_AGREE * g
        if v <= 0.2:  # failed arithmetic / missing: never auto-accept
            final = min(final, CAP_ON_FAILED_VALIDATION)
        out[f] = FieldConfidence(s, v, g, round(final, 4))
    return out
