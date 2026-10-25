"""Stage 3 - Extract: call the Groq vision model with a token budget, retries and a cache."""
import hashlib
import json
import random
import re
import time
from dataclasses import dataclass, field

from groq import APIConnectionError, APIStatusError, Groq
from PIL import Image

from .config import Settings
from .preprocess import to_data_url
from .ratelimit import TokenBudget
from .schema import Extraction

BASE_PROMPT = """You are an invoice data-extraction engine. Read the invoice image and \
return ONLY one JSON object, with no markdown and no commentary.

Schema:
{
  "vendor": string or null,
  "date": "YYYY-MM-DD" or null,
  "currency": 3-letter ISO 4217 code (e.g. USD, EUR, GBP, INR) or null,
  "total": number (no currency symbol, no thousands separator) or null,
  "line_items": [{"description": string, "quantity": number, "unit_price": number, "amount": number}],
  "confidence": {"vendor": 0-1, "date": 0-1, "currency": 0-1, "total": 0-1, "line_items": 0-1}
}

Rules:
- Copy values exactly as printed. Never invent or calculate values. Use null if unreadable.
- Convert the date to YYYY-MM-DD. If day/month order is ambiguous, give your best guess and lower the date confidence.
- Map currency symbols or names (e.g. "$", "Rs") to ISO codes.
- confidence is your honest certainty per field: 1.0 = certain, 0.5 = unsure, below 0.3 = mostly guessing. Lower it for blurry, skewed or shadowed text.
"""

# Variant 1 is used for the second pass (different wording).
PROMPTS = [
    BASE_PROMPT,
    "Re-read every digit carefully. Start from the bottom of the invoice (the total) "
    "and work upwards.\n\n" + BASE_PROMPT,
]

_budget: TokenBudget | None = None  # shared across all calls in this process


def _get_budget(s: Settings) -> TokenBudget:
    """Create the process-wide token budget on first use."""
    global _budget
    if _budget is None:
        _budget = TokenBudget(s.tpm_limit, s.tpm_safety, s.sleep_between_calls)
    return _budget


class QuotaExhausted(RuntimeError):
    """Server asked for a long wait (daily token limit): stop and resume later."""


MAX_WAIT_SECONDS = 300  # longer than this = daily limit, not a per-minute limit


@dataclass
class ExtractionResult:
    extraction: Extraction | None
    raw_text: str
    error: str | None
    cached: bool
    usage: dict = field(default_factory=dict)


def parse_response(text: str) -> Extraction:
    """Defensively parse model text: strip <think>, find the JSON, validate."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in reply")
    return Extraction.model_validate(json.loads(text[start:end + 1]))


def _cache_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _retry_after(e: Exception) -> float | None:
    """Seconds the server asked us to wait (Retry-After header), if present."""
    headers = getattr(getattr(e, "response", None), "headers", None)
    try:
        return float(headers.get("retry-after")) if headers else None
    except (TypeError, ValueError):
        return None


def _call_api(client: Groq, s: Settings, messages: list, temperature: float) -> tuple[str, dict]:
    """One chat call: token-budget wait, then retries (honouring Retry-After) on 429/5xx."""
    budget = _get_budget(s)
    kwargs: dict = dict(
        model=s.model, messages=messages, temperature=temperature,
        max_tokens=1200, response_format={"type": "json_object"},
    )
    if s.reasoning_effort:
        kwargs["extra_body"] = {"reasoning_effort": s.reasoning_effort}

    for attempt in range(s.max_retries + 1):
        budget.acquire()
        try:
            resp = client.chat.completions.create(**kwargs)
            u = resp.usage
            usage = {"prompt": u.prompt_tokens, "completion": u.completion_tokens,
                     "total": u.total_tokens} if u else {}
            budget.record(usage.get("total", budget.estimate))
            return resp.choices[0].message.content or "", usage
        except (APIConnectionError, APIStatusError) as e:
            code = getattr(e, "status_code", None)
            retryable = code is None or code == 429 or code >= 500
            if not retryable or attempt == s.max_retries:
                raise
            if code == 429:
                budget.record(budget.estimate)  # assume the failed call counted
            ra = _retry_after(e)
            backoff = ra + 1 if ra else min(10 * 2 ** attempt, 120) + random.uniform(0, 3)
            if code == 429 and backoff > MAX_WAIT_SECONDS:
                raise QuotaExhausted(
                    f"Daily token limit reached (server asks for {backoff / 60:.0f} min). "
                    "Finished work is cached; re-run later to resume.") from e
            print(f"  [{code or 'connection'}] retry {attempt + 1}/{s.max_retries} in {backoff:.0f}s")
            time.sleep(backoff)
    raise RuntimeError("unreachable")


def extract_invoice(img: Image.Image, s: Settings, variant: int = 0,
                    temperature: float = 0.0, client: Groq | None = None) -> ExtractionResult:
    """Extract fields from one preprocessed page image (cached on disk)."""
    prompt = PROMPTS[variant]
    data_url = to_data_url(img)
    key = _cache_key(data_url, prompt, s.model, str(temperature), s.reasoning_effort)
    path = s.cache_dir / f"{key}.json"

    if path.exists():
        hit = json.loads(path.read_text(encoding="utf-8"))
        return ExtractionResult(parse_response(hit["text"]), hit["text"], None, True, hit["usage"])

    client = client or Groq(api_key=s.groq_api_key)
    messages = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]}]
    text, usage = _call_api(client, s, messages, temperature)
    try:
        extraction = parse_response(text)
    except ValueError as e:  # includes JSON and Pydantic validation errors
        return ExtractionResult(None, text, str(e), False, usage)

    # Only cache replies that parsed, so a bad reply is retried on the next run.
    s.cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"text": text, "usage": usage}), encoding="utf-8")
    return ExtractionResult(extraction, text, None, False, usage)
