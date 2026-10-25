"""Process two cached invoices, route them at two thresholds, save to SQLite."""
from invoice_whisperer.config import ROOT, load_settings
from invoice_whisperer.pipeline import process_document
from invoice_whisperer.router import route
from invoice_whisperer.store import connect, save_result


def main() -> None:
    s = load_settings()
    conn = connect(ROOT / "data" / "outputs" / "results.db")
    for name in ["inv_001", "inv_004"]:
        r = process_document(ROOT / f"data/synthetic/{name}.png", s)
        saved = save_result(conn, r, s.confidence_threshold)
        print(f"{name}: real API calls={r.api_calls} saved={saved}")
        for t in (s.confidence_threshold, 0.995):
            d = route(r.confidence, t)
            flagged = [f for f, v in d.items() if v == "review"]
            print(f"  threshold {t}: review -> {flagged or 'none'}")
    print("--- rows in results.db ---")
    q = ("SELECT doc_id, field, confidence, decision, substr(final_value, 1, 30) AS value "
         "FROM fields ORDER BY doc_id, field")
    for row in conn.execute(q):
        print(f"{row['doc_id']} {row['field']:11} conf={row['confidence']:.2f} "
              f"{row['decision']:6} {row['value']}")


if __name__ == "__main__":
    main()
