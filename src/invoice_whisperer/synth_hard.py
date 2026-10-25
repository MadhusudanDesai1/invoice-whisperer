"""Harder synthetic invoices: brutal scan damage and ambiguous dates.

Ids continue after the base set (inv_040+), so the base set is untouched.
"""
import io
import json
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

from .synth import add_noise, make_label, render


def brutal_noise(img: Image.Image, rng: random.Random) -> Image.Image:
    """Ugly noise + low resolution + low contrast + sensor grain + JPEG damage."""
    img = add_noise(img, rng, "ugly")
    w, h = img.size
    f = rng.uniform(0.55, 0.7)  # shrink then enlarge: pixelated, low-res text
    img = img.resize((int(w * f), int(h * f)), Image.BILINEAR).resize((w, h), Image.BILINEAR)
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.5, 0.7))
    grain = np.random.default_rng(rng.randrange(2**32)).normal(0, 18, (h, w, 1))
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) + grain
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=rng.randint(12, 25))  # heavy compression
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def ambiguous_date(rng: random.Random) -> date:
    """A date whose DD/MM and MM/DD readings differ (day <= 12, day != month)."""
    while True:
        d = date(2023, 1, 1) + timedelta(days=rng.randint(0, 700))
        if d.day <= 12 and d.day != d.month:
            return d


def generate_hard(n: int, out_dir: Path, start: int = 40, seed: int = 7) -> None:
    """Even-numbered invoices get the ambiguous-date trap (compact layout, DD/MM/YYYY)."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        label = make_label(rng, start + i)
        trap = "ambiguous_date" if i % 2 == 0 else "none"
        layout = "compact" if trap != "none" else ["classic", "boxed"][(i // 2) % 2]
        if trap != "none":
            label["date"] = ambiguous_date(rng).isoformat()
        label.update(layout=layout, noise="brutal", trap=trap)
        img = brutal_noise(render(label, layout), rng)
        img.save(out_dir / f"{label['id']}.png")
        (out_dir / f"{label['id']}.json").write_text(
            json.dumps(label, indent=2), encoding="utf-8")
