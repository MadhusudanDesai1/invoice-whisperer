"""Stage 4 - Validate: rule checks that turn an Extraction into per-field scores.

Scores: 1.0 = passes, 0.0 = fails, in between = suspicious / can't fully check.
"""
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from .schema import Extraction

KNOWN_CURRENCIES = {
    "USD", "EUR", "GBP", "INR", "JPY", "CAD", "AUD", "CHF", "CNY", "SGD",
    "AED", "MXN", "BRL", "ZAR", "SEK", "NOK", "DKK", "NZD", "HKD",
}
TOLERANCE = Decimal("0.01")   # allowed rounding difference in money maths
MIN_DATE = date(2000, 1, 1)   # earlier than this is implausible for an invoice


@dataclass
class ValidationResult:
    scores: dict[str, float] = field(default_factory=dict)  # one per field
    issues: list[str] = field(default_factory=list)         # readable problems


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCE


def _check_date(value: str | None, today: date, issues: list[str]) -> float:
    """Strict YYYY-MM-DD, a real calendar date, and in a plausible range."""
    if not value:
        issues.append("date missing")
        return 0.0
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        issues.append(f"date not YYYY-MM-DD: {value!r}")
        return 0.0
    try:
        d = date.fromisoformat(value)
    except ValueError:
        issues.append(f"date is not a real calendar date: {value!r}")
        return 0.0
    if not (MIN_DATE <= d <= today + timedelta(days=365)):
        issues.append(f"date outside plausible range: {value}")
        return 0.3
    return 1.0


def _check_currency(value: str | None, issues: list[str]) -> float:
    if not value:
        issues.append("currency missing")
        return 0.0
    if value in KNOWN_CURRENCIES:
        return 1.0
    if re.fullmatch(r"[A-Z]{3}", value):
        issues.append(f"currency code not in known list: {value}")
        return 0.5
    issues.append(f"currency is not a 3-letter code: {value!r}")
    return 0.0


def validate(ex: Extraction, today: date | None = None) -> ValidationResult:
    """Apply all rules. Money maths assumes no tax/discount lines (true for our data)."""
    today = today or date.today()
    r = ValidationResult()

    # vendor: present and not trivially short
    if ex.vendor and len(ex.vendor.strip()) >= 2:
        r.scores["vendor"] = 1.0
    else:
        r.scores["vendor"] = 0.0
        r.issues.append("vendor missing")

    r.scores["date"] = _check_date(ex.date, today, r.issues)
    r.scores["currency"] = _check_currency(ex.currency, r.issues)

    # line items: row maths (qty x unit_price = amount) ...
    items = ex.line_items
    rows_checked = rows_ok = 0
    for i, it in enumerate(items, 1):
        if it.quantity is not None and it.unit_price is not None and it.amount is not None:
            rows_checked += 1
            if _close(it.quantity * it.unit_price, it.amount):
                rows_ok += 1
            else:
                r.issues.append(f"line {i}: {it.quantity} x {it.unit_price} != {it.amount}")

    # ... and the sum of amounts versus the stated total
    amounts = [it.amount for it in items if it.amount is not None]
    sum_ok: bool | None = None  # None = could not check
    if ex.total is not None and items and len(amounts) == len(items):
        sum_ok = _close(sum(amounts), ex.total)
        if not sum_ok:
            r.issues.append(f"line items sum {sum(amounts)} != total {ex.total}")

    if not items:
        r.scores["line_items"] = 0.0
        r.issues.append("no line items")
    else:
        li = rows_ok / rows_checked if rows_checked else 0.5
        r.scores["line_items"] = min(li, 0.2) if sum_ok is False else li

    # total: positive, and cross-checked against the line items
    if ex.total is None or ex.total <= 0:
        r.scores["total"] = 0.0
        r.issues.append("total missing or not positive")
    elif sum_ok is True:
        r.scores["total"] = 1.0
    elif sum_ok is False:
        r.scores["total"] = 0.2   # either the total or an amount is wrong
    else:
        r.scores["total"] = 0.7   # plausible but not cross-checkable

    return r
