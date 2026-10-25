"""Central configuration, loaded from environment variables / .env."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Project root = two levels above src/invoice_whisperer/
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    model: str                    # Groq vision model ID (swap in .env)
    confidence_threshold: float   # fields >= this are auto-accepted
    sleep_between_calls: float    # min seconds between API calls
    max_retries: int              # retries on 429 / transient errors
    reasoning_effort: str         # "" = don't send; else value from Groq docs
    cache_dir: Path = ROOT / ".cache"


def load_settings() -> Settings:
    """Read settings and fail early with a clear message if something is missing."""
    key = os.getenv("GROQ_API_KEY", "")
    model = os.getenv("GROQ_MODEL", "")
    if not key or key.startswith("your_"):
        raise RuntimeError("GROQ_API_KEY is not set in .env")
    if not model or model.startswith("your_"):
        raise RuntimeError("GROQ_MODEL is not set in .env")
    return Settings(
        groq_api_key=key,
        model=model,
        confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.85")),
        sleep_between_calls=float(os.getenv("SLEEP_BETWEEN_CALLS", "30")),
        max_retries=int(os.getenv("MAX_RETRIES", "5")),
        reasoning_effort=os.getenv("REASONING_EFFORT", "").strip(),
    )
