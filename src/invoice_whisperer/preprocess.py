"""Stage 2 - Pre-process: flatten shadows, deskew, resize, encode for Groq."""
import base64
import io

import numpy as np
from PIL import Image, ImageFilter, ImageOps

# Groq allows 20 MB per request; we stay far below it (base64 adds ~33%).
MAX_LONG_SIDE = 1600
MAX_JPEG_BYTES = 4_000_000


def flatten_illumination(img: Image.Image, work: int = 400) -> Image.Image:
    """Remove shadows / uneven lighting by dividing out the paper brightness.

    1. Shrink a copy, then a max-filter wipes out thin dark text, leaving only
       the paper's brightness (shadows included).
    2. Blur it smooth and scale it back up.
    3. Divide the image by that background: shadowed paper becomes white again.
    """
    img = img.convert("RGB")
    small = img.copy()
    small.thumbnail((work, work), Image.LANCZOS)
    bg = small.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(8))
    bg = bg.resize(img.size, Image.BILINEAR)
    a = np.asarray(img, dtype=np.float32)
    b = np.maximum(np.asarray(bg, dtype=np.float32), 1.0)
    out = np.clip(a / b * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def estimate_skew(img: Image.Image, search: float = 15.0) -> float:
    """Return the rotation (degrees, PIL convention) that straightens the text.

    Projection-profile method: when text lines are horizontal, the row sums of
    the 'ink' pixels are spiky (high variance). We try angles and keep the best.
    Shadows are flattened first so they are not mistaken for ink.
    """
    thumb = img.convert("RGB")
    thumb.thumbnail((500, 500))
    gray = ImageOps.grayscale(flatten_illumination(thumb))
    arr = np.asarray(gray, dtype=np.float32)
    # After flattening, paper is ~255, so ink = clearly darker than the median.
    ink = Image.fromarray(((arr < 0.8 * np.median(arr)) * 255).astype(np.uint8))

    def score(angle: float) -> float:
        rows = np.asarray(ink.rotate(angle, fillcolor=0), dtype=np.float32).sum(axis=1)
        return float(np.var(rows))

    coarse = max(np.arange(-search, search + 1.0, 1.0), key=score)
    fine = max(np.arange(coarse - 1.0, coarse + 1.01, 0.25), key=score)
    return float(fine)


def preprocess_page(img: Image.Image, deskew: bool = True, enhance: bool = True) -> Image.Image:
    """Deskew, flatten shadows, and shrink so the long side is <= MAX_LONG_SIDE."""
    if deskew:
        angle = estimate_skew(img)
        if abs(angle) >= 0.5:  # ignore tiny corrections
            img = img.rotate(angle, expand=True, fillcolor="white", resample=Image.BICUBIC)
    if enhance:
        img = flatten_illumination(img)
    img = img.copy()
    img.thumbnail((MAX_LONG_SIDE, MAX_LONG_SIDE), Image.LANCZOS)
    return img


def encode_jpeg(img: Image.Image) -> bytes:
    """JPEG-encode, lowering quality (then size) until under MAX_JPEG_BYTES."""
    img = img.convert("RGB")
    while True:
        for quality in (85, 70, 55):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            if buf.tell() <= MAX_JPEG_BYTES:
                return buf.getvalue()
        img = img.resize((int(img.width * 0.8), int(img.height * 0.8)), Image.LANCZOS)


def to_data_url(img: Image.Image) -> str:
    """Return a base64 data URL ready for the chat-completions image_url field."""
    b64 = base64.b64encode(encode_jpeg(img)).decode()
    return f"data:image/jpeg;base64,{b64}"
