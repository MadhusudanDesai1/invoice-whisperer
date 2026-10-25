"""Send one tiny generated image to the model; test JSON mode support."""
import base64
import io
import json

from groq import BadRequestError, Groq
from PIL import Image, ImageDraw, ImageFont

from invoice_whisperer.config import load_settings


def make_test_image() -> str:
    """Draw a tiny fake invoice and return it as a base64 data URL."""
    img = Image.new("RGB", (500, 200), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=26)
    draw.text((20, 30), "ACME Supplies Ltd", fill="black", font=font)
    draw.text((20, 80), "Invoice date: 2024-03-15", fill="black", font=font)
    draw.text((20, 130), "TOTAL: 42.50 USD", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def main() -> None:
    s = load_settings()
    client = Groq(api_key=s.groq_api_key)
    prompt = (
        "Read this invoice image. Return ONLY a JSON object with keys "
        "vendor, date, total, currency."
    )
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": make_test_image()}},
        ],
    }]

    # Try JSON mode first; fall back to plain prompting if unsupported.
    try:
        resp = client.chat.completions.create(
            model=s.model, messages=messages, max_tokens=500,
            response_format={"type": "json_object"},
        )
        print("JSON mode: SUPPORTED")
    except BadRequestError as e:
        print("JSON mode: NOT supported ->", str(e)[:200])
        resp = client.chat.completions.create(
            model=s.model, messages=messages, max_tokens=500,
        )

    text = resp.choices[0].message.content or ""
    print("Raw reply:", text)
    try:
        print("Parsed:", json.loads(text))
    except json.JSONDecodeError:
        print("Reply was not clean JSON (we will parse defensively later).")


if __name__ == "__main__":
    main()
