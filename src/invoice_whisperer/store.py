"""Stage 8 (storage half) - SQLite: documents, per-field values, decisions, corrections."""
import sqlite3
from pathlib import Path

from .pipeline import DocResult
from .router import canonical_value, route_field
from .schema import FIELDS

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  doc_id       TEXT PRIMARY KEY,
  path         TEXT NOT NULL,
  status       TEXT NOT NULL,            -- 'ok' | 'failed'
  error        TEXT,
  api_calls    INTEGER DEFAULT 0,
  processed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS fields (
  doc_id       TEXT NOT NULL,
  field        TEXT NOT NULL,
  model_value  TEXT,                     -- what the model extracted (never edited)
  self_rating  REAL,
  validation   REAL,
  agreement    REAL,
  confidence   REAL,                     -- final blended confidence
  decision     TEXT NOT NULL,            -- 'auto' | 'review'
  final_value  TEXT,                     -- model value until a human edits it
  reviewed     INTEGER DEFAULT 0,        -- 1 once a human has looked at it
  corrected    INTEGER DEFAULT 0,        -- 1 if the human changed the value
  PRIMARY KEY (doc_id, field)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """Open (and create if needed) the results database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_result(conn: sqlite3.Connection, result: DocResult, threshold: float) -> bool:
    """Store one document. Returns False (and writes nothing) if a human already
    reviewed it, so re-running the batch can never wipe corrections."""
    doc_id = Path(result.path).stem
    done = conn.execute(
        "SELECT COUNT(*) FROM fields WHERE doc_id=? AND reviewed=1", (doc_id,)
    ).fetchone()[0]
    if done:
        return False

    ex = result.extraction
    with conn:  # one transaction
        conn.execute("DELETE FROM fields WHERE doc_id=?", (doc_id,))
        conn.execute(
            "INSERT OR REPLACE INTO documents (doc_id, path, status, error, api_calls) "
            "VALUES (?,?,?,?,?)",
            (doc_id, result.path, "ok" if ex else "failed", result.error, result.api_calls))
        for f in FIELDS:
            if ex is None:  # failed document: everything goes to a human
                row = (doc_id, f, None, None, None, None, 0.0, "review", None)
            else:
                c = result.confidence[f]
                val = canonical_value(ex, f)
                row = (doc_id, f, val, c.self_rating, c.validation, c.agreement,
                       c.final, route_field(c.final, threshold), val)
            conn.execute(
                "INSERT INTO fields (doc_id, field, model_value, self_rating, validation, "
                "agreement, confidence, decision, final_value) VALUES (?,?,?,?,?,?,?,?,?)",
                row)
    return True
