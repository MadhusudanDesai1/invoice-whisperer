"""Synthetic invoice generator: images + ground-truth JSON labels."""
import json
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

VENDORS = [
    "ACME Supplies Ltd", "Northwind Traders", "Blue Harbor Logistics",
    "Greenleaf Organics", "Pioneer Office Systems", "Sunrise Bakery Co",
    "Vertex Engineering", "Lakeside Hardware", "Orion Digital Services",
    "Maple & Pine Furniture", "Summit Print Works", "Coastal Freight Inc",
]
ITEMS = [
    "Printer paper (ream)", "USB-C cable", "Desk lamp", "Ink cartridge",
    "Consulting hour", "Shipping fee", "Stapler", "Notebook pack",
    "Monitor stand", "Cleaning service", "Wireless mouse", "Packing tape",
]
CURRENCIES = {"USD": "$", "EUR": "EUR ", "GBP": "GBP ", "INR": "Rs "}
LAYOUTS = ["classic", "compact", "boxed"]


def _font(size: int) -> ImageFont.FreeTypeFont:
    """Pillow's built-in scalable font (no system fonts needed on Windows)."""
    return ImageFont.load_default(size=size)


def make_label(rng: random.Random, idx: int) -> dict:
    """Create the ground-truth values for one invoice."""
    currency = rng.choice(list(CURRENCIES))
    items = []
    for _ in range(rng.randint(2, 5)):
        qty = rng.randint(1, 5)
        price = Decimal(rng.randint(150, 9000)) / 100
        items.append({
            "description": rng.choice(ITEMS),
            "quantity": qty,
            "unit_price": str(price),
            "amount": str(price * qty),
        })
    total = sum(Decimal(i["amount"]) for i in items)
    d = date(2023, 1, 1) + timedelta(days=rng.randint(0, 700))
    return {
        "id": f"inv_{idx:03d}",
        "vendor": rng.choice(VENDORS),
        "date": d.isoformat(),
        "currency": currency,
        "total": str(total),
        "line_items": items,
    }


def render(label: dict, layout: str) -> Image.Image:
    """Draw a clean invoice image for the given label and layout."""
    sym = CURRENCIES[label["currency"]]
    h = 420 + 50 * len(label["line_items"])
    img = Image.new("RGB", (900, h), "white")
    d = ImageDraw.Draw(img)
    big, mid, small = _font(40), _font(26), _font(22)

    if layout == "boxed":
        d.rectangle([20, 20, 880, h - 20], outline="black", width=3)
    x0 = 50
    d.text((x0, 50), label["vendor"], fill="black", font=big)
    d.text((x0, 110), "INVOICE", fill="gray", font=mid)
    date_text = label["date"] if layout != "compact" else \
        date.fromisoformat(label["date"]).strftime("%d/%m/%Y")
    d.text((560, 115), f"Date: {date_text}", fill="black", font=mid)

    y = 200
    d.line([x0, y, 850, y], fill="black", width=2)
    d.text((x0, y + 10), "Description", fill="black", font=small)
    d.text((480, y + 10), "Qty", fill="black", font=small)
    d.text((570, y + 10), "Price", fill="black", font=small)
    d.text((720, y + 10), "Amount", fill="black", font=small)
    y += 55
    for it in label["line_items"]:
        d.text((x0, y), it["description"], fill="black", font=small)
        d.text((480, y), str(it["quantity"]), fill="black", font=small)
        d.text((570, y), f"{sym}{it['unit_price']}", fill="black", font=small)
        d.text((720, y), f"{sym}{it['amount']}", fill="black", font=small)
        y += 50
    d.line([x0, y, 850, y], fill="black", width=2)
    d.text((540, y + 25), f"TOTAL: {sym}{label['total']}",
           fill="black", font=mid)
    return img


def add_noise(img: Image.Image, rng: random.Random, level: str) -> Image.Image:
    """Apply scan-like damage. level: clean | mild | ugly."""
    if level == "clean":
        return img
    angle = rng.uniform(-4, 4) if level == "mild" else rng.uniform(-12, 12)
    img = img.rotate(angle, expand=True, fillcolor="white", resample=Image.BICUBIC)
    blur = 0.8 if level == "mild" else rng.uniform(1.6, 2.4)
    img = img.filter(ImageFilter.GaussianBlur(blur))
    # Shadow: darken a diagonal band with a translucent overlay
    shadow = Image.new("L", img.size, 255)
    sd = ImageDraw.Draw(shadow)
    dark = 215 if level == "mild" else 140
    w, h = img.size
    sd.polygon([(0, 0), (w * 0.55, 0), (0, h * 0.7)], fill=dark)
    shadow = shadow.filter(ImageFilter.GaussianBlur(40))
    img = Image.composite(img, Image.new("RGB", img.size, "black"), shadow)
    return img


def generate(n: int, out_dir: Path, seed: int = 42) -> None:
    """Generate n invoices: ~50% clean, ~35% mild noise, ~15% ugly."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        label = make_label(rng, i)
        layout = LAYOUTS[i % len(LAYOUTS)]
        r = rng.random()
        level = "clean" if r < 0.5 else "mild" if r < 0.85 else "ugly"
        label["layout"], label["noise"] = layout, level
        img = add_noise(render(label, layout), rng, level)
        img.save(out_dir / f"{label['id']}.png")
        (out_dir / f"{label['id']}.json").write_text(
            json.dumps(label, indent=2), encoding="utf-8")
