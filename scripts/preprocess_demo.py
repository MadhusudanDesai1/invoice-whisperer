"""Demo: ingest + preprocess a few invoices, print stats, save the results."""
from PIL import Image

from invoice_whisperer.config import ROOT
from invoice_whisperer.ingest import load_pages
from invoice_whisperer.preprocess import estimate_skew, preprocess_page, to_data_url

SRC = ROOT / "data" / "synthetic"
OUT = ROOT / "data" / "outputs" / "preprocessed"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ["inv_000", "inv_004", "inv_005", "inv_006"]:
        page = load_pages(SRC / f"{name}.png")[0]
        angle = estimate_skew(page)
        proc = preprocess_page(page)
        url = to_data_url(proc)
        proc.save(OUT / f"{name}_pre.png")
        print(f"{name}: in={page.size} skew_fix={angle:+.2f}deg "
              f"out={proc.size} data_url={len(url) / 1000:.0f} KB")

    # PDF ingest test: wrap one PNG into a PDF, then load it back.
    pdf = ROOT / "data" / "outputs" / "test.pdf"
    Image.open(SRC / "inv_001.png").convert("RGB").save(pdf)
    pages = load_pages(pdf)
    print(f"PDF: {len(pages)} page(s), first page size={pages[0].size}")


if __name__ == "__main__":
    main()
