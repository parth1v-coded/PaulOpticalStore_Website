"""Regenerate CREDITS.md from static/img/credits.json (run after fetch_images.py)."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
credits = json.loads((root / "static" / "img" / "credits.json").read_text(encoding="utf-8"))
lines = ["# Image credits", "",
         "Every photograph on the site comes from Wikimedia Commons and is used under its open licence "
         "(CC0 / public domain / CC BY / CC BY-SA). The Paul Optical logo is the client's own artwork.", "",
         "| File | Photo | Author | Licence |", "|---|---|---|---|"]
for path, c in credits.items():
    title = c["title"].replace("|", "/")
    lines.append(f"| `{path}` | [{title}]({c['source']}) | {c['author'].replace('|', '/')} | {c['license']} |")
(root / "CREDITS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(len(credits), "credits written")
