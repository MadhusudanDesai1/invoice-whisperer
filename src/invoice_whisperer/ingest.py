"""Stage 1 - Ingest: turn an image or PDF path into a list of RGB PIL images."""
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def load_pages(path: Path, dpi: int = 200, max_pages: int = 3) -> list[Image.Image]:
    """Load an image or PDF. PDFs yield one image per page (up to max_pages)."""
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        pages: list[Image.Image] = []
        with pymupdf.open(path) as doc:
            for i in range(min(len(doc), max_pages)):
                pix = doc.load_page(i).get_pixmap(dpi=dpi)
                pages.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        return pages

    if ext in IMAGE_EXTS:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)  # honour phone-camera rotation flags
        return [img.convert("RGB")]

    raise ValueError(f"Unsupported file type: {ext}")
