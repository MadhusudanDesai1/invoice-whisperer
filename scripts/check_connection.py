"""Check that the API key works, the model exists, and a text call succeeds."""
from groq import Groq

from invoice_whisperer.config import load_settings


def main() -> None:
    s = load_settings()
    client = Groq(api_key=s.groq_api_key)

    # 1) Key check + model existence check
    ids = [m.id for m in client.models.list().data]
    print(f"Key OK. {len(ids)} models available.")
    if s.model not in ids:
        print(f"WARNING: '{s.model}' not in model list. Check the ID in .env.")
        return
    print(f"Model found: {s.model}")

    # 2) Tiny text call
    resp = client.chat.completions.create(
        model=s.model,
        messages=[{"role": "user", "content": "Reply with the single word: pong"}],
        max_tokens=10,
    )
    print("Reply:", resp.choices[0].message.content.strip())


if __name__ == "__main__":
    main()
