"""Stage 7 - Human review page. Run: streamlit run src/invoice_whisperer/review_app.py"""
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from invoice_whisperer.config import ROOT, load_settings
from invoice_whisperer.review import (apply_review, items_to_canonical, load_doc,
                                      normalize_input, pending_docs)
from invoice_whisperer.schema import FIELDS
from invoice_whisperer.store import connect

DB = Path(os.environ.get("REVIEW_DB", ROOT / "data" / "outputs" / "results.db"))
ITEM_COLS = ["description", "quantity", "unit_price", "amount"]

st.set_page_config(page_title="Invoice Whisperer - Review", layout="wide")


def main() -> None:
    conn = connect(DB)
    threshold = st.sidebar.slider(
        "Review fields below this confidence", 0.50, 1.00,
        float(load_settings().confidence_threshold), 0.005)
    ids = pending_docs(conn, threshold)
    st.sidebar.metric("Documents waiting", len(ids))

    st.title("Invoice Whisperer - human review")
    if "msg" in st.session_state:
        st.success(st.session_state.pop("msg"))
    if not ids:
        st.info("The review queue is empty at this threshold.")
        return

    doc_id = st.sidebar.selectbox("Document", ids)
    path, rows = load_doc(conn, doc_id)
    left, right = st.columns(2)

    with left:
        st.subheader(doc_id)
        if Path(path).exists():
            st.image(path)
        else:
            st.warning(f"Image not found: {path}")

    new_values: dict[str, str | None] = {}
    errors: list[str] = []
    with right:
        st.subheader("Extracted fields")
        for f in FIELDS:
            row = rows[f]
            flagged = row["confidence"] < threshold
            if flagged:
                st.markdown(f":orange-background[⚠️ **{f}** needs review"
                            f" · confidence {row['confidence']:.2f}]")
            else:
                st.markdown(f"✅ **{f}** · confidence {row['confidence']:.2f}")
            st.caption(f"self-rating {row['self_rating'] or 0:.2f} · "
                       f"validation {row['validation'] or 0:.2f} · "
                       f"agreement {row['agreement'] or 0:.2f}")
            key = f"{doc_id}:{f}"
            if f == "line_items":
                items = json.loads(row["final_value"] or "[]")
                df = pd.DataFrame(items, columns=ITEM_COLS).fillna("").astype(str)
                edited = st.data_editor(df, num_rows="dynamic", hide_index=True, key=key)
                new_values[f] = items_to_canonical(edited.to_dict("records"))
            else:
                raw = st.text_input(f, value=row["final_value"] or "", key=key,
                                    label_visibility="collapsed")
                new_values[f] = normalize_input(f, raw)
                if f == "total" and raw.strip() and new_values[f] is None:
                    errors.append("Total is not a valid number.")

        if st.button("Save review for this document", type="primary"):
            if errors:
                st.error(" ".join(errors))
            else:
                n_rev, n_cor = apply_review(conn, doc_id, new_values, threshold)
                st.session_state["msg"] = (
                    f"Saved {doc_id}: {n_rev} fields reviewed, {n_cor} corrected.")
                st.rerun()


main()
