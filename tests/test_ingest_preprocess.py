"""Ingest + preprocess tests (no API calls)."""
from PIL import Image

from invoice_whisperer.ingest import load_pages
from invoice_whisperer.preprocess import MAX_LONG_SIDE, preprocess_page, to_data_url


def test_pdf_page_becomes_rgb_image(tmp_path):
    pdf = tmp_path / "doc.pdf"
    Image.new("RGB", (800, 600), "white").save(pdf)
    pages = load_pages(pdf)
    assert len(pages) == 1 and pages[0].mode == "RGB"


def test_large_image_is_shrunk_to_limit():
    big = Image.new("RGB", (4000, 3000), "white")
    out = preprocess_page(big, deskew=False)
    assert max(out.size) <= MAX_LONG_SIDE


def test_data_url_is_jpeg_base64():
    url = to_data_url(Image.new("RGB", (200, 100), "white"))
    assert url.startswith("data:image/jpeg;base64,")
