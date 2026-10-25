"""Pydantic schema for extracted invoice data (lenient in, strict out)."""
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field, field_validator

# The fields we score, route and evaluate (one confidence value each).
FIELDS = ["vendor", "date", "currency", "total", "line_items"]


def to_decimal(v: Any) -> Decimal | None:
    """Coerce '$1,234.50', 'Rs 12.30', 42.5 ... to Decimal; None if unparseable.

    Assumes '.' is the decimal separator and ',' a thousands separator.
    """
    if v is None or v == "":
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    if isinstance(v, str):
        cleaned = re.sub(r"[^0-9.\-]", "", v.replace(",", ""))
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    return None


class LineItem(BaseModel):
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None

    @field_validator("quantity", "unit_price", "amount", mode="before")
    @classmethod
    def _num(cls, v: Any) -> Decimal | None:
        return to_decimal(v)


class Extraction(BaseModel):
    vendor: str | None = None
    date: str | None = None          # kept as text; validated in Step 7
    currency: str | None = None
    total: Decimal | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)  # model self-rating

    @field_validator("total", mode="before")
    @classmethod
    def _total(cls, v: Any) -> Decimal | None:
        return to_decimal(v)

    @field_validator("currency", mode="before")
    @classmethod
    def _currency(cls, v: Any) -> str | None:
        return v.strip().upper() if isinstance(v, str) and v.strip() else None

    @field_validator("line_items", mode="before")
    @classmethod
    def _items(cls, v: Any) -> Any:
        return [] if v is None else v

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v: Any) -> dict[str, float]:
        """Keep only numeric self-ratings, clamped to [0, 1]."""
        out: dict[str, float] = {}
        if isinstance(v, dict):
            for k, x in v.items():
                try:
                    out[str(k)] = min(1.0, max(0.0, float(x)))
                except (TypeError, ValueError):
                    pass
        return out
