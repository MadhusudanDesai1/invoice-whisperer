"""Run the full per-document pipeline: ingest -> preprocess -> 2 passes -> validate -> score."""
from dataclasses import dataclass, field
from pathlib import Path

from .confidence import FieldConfidence, agreement, combine
from .config import Settings
from .extract import extract_invoice
from .ingest import load_pages
from .preprocess import preprocess_page
from .schema import Extraction
from .validate import ValidationResult, validate

PASS2_TEMPERATURE = 0.3  # second pass: different prompt AND slightly higher temperature


@dataclass
class DocResult:
    path: str
    extraction: Extraction | None            # pass 1 (the values we keep)
    second: Extraction | None                # pass 2 (used for agreement only)
    validation: ValidationResult | None
    confidence: dict[str, FieldConfidence] = field(default_factory=dict)
    error: str | None = None
    api_calls: int = 0                       # real (non-cached) calls made


def process_document(path: Path, s: Settings) -> DocResult:
    """Process the first page of one image/PDF. Never raises on model errors."""
    page = preprocess_page(load_pages(path)[0])
    r1 = extract_invoice(page, s, variant=0, temperature=0.0)
    r2 = extract_invoice(page, s, variant=1, temperature=PASS2_TEMPERATURE)
    calls = int(not r1.cached) + int(not r2.cached)

    if r1.extraction is None:
        return DocResult(str(path), None, None, None, error=f"pass 1 failed: {r1.error}",
                         api_calls=calls)

    val = validate(r1.extraction)
    if r2.extraction is None:
        # No second opinion: agreement is 0 for every field, so little gets auto-accepted.
        agree = {f: 0.0 for f in val.scores}
    else:
        agree = agreement(r1.extraction, r2.extraction)
    conf = combine(r1.extraction, val.scores, agree)
    return DocResult(str(path), r1.extraction, r2.extraction, val, conf, api_calls=calls)
