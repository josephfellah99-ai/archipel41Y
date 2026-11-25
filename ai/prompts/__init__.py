"""Gabarits de consignes (prompts) versionnés, chargés par nom."""
from pathlib import Path

_DIR = Path(__file__).parent


def load(name: str, **values) -> str:
    text = (_DIR / f"{name}.md").read_text(encoding="utf-8")
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text
