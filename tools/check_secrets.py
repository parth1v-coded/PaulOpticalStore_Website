"""Run before publishing:  python tools/check_secrets.py
Scans every file that WOULD be published (i.e. not matched by .gitignore) for API keys, passwords and private files.
Exits non-zero if anything looks sensitive."""
import fnmatch
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ignore = [l.strip() for l in (ROOT / ".gitignore").read_text().splitlines() if l.strip() and not l.startswith("#")]
PATTERNS = {
    "Google/Gemini API key": re.compile(r"AQ\.[A-Za-z0-9_\-]{30,}|AIza[0-9A-Za-z_\-]{35}"),
    "OpenAI-style key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "hard-coded password": re.compile(r"(?i)(password|passwd|secret|api[_-]?key)\s*[:=]\s*['\"][^'\"\s]{6,}['\"]"),
}
PRIVATE_NAMES = {".env", "admin_password.txt", "paul_optical.db"}


def ignored(path):
    rel = path.relative_to(ROOT).as_posix()
    return any(fnmatch.fnmatch(rel, g.rstrip("/") + ("/*" if g.endswith("/") else "")) or fnmatch.fnmatch(path.name, g.rstrip("/")) or rel.startswith(g) for g in ignore)


problems = []
for f in ROOT.rglob("*"):
    if not f.is_file() or ".git" in f.parts or "vendor" in f.parts or f.suffix in (".jpg", ".png", ".woff2", ".wasm", ".task", ".db") or ignored(f):
        continue
    if f.name in PRIVATE_NAMES:
        problems.append(f"{f.relative_to(ROOT)}: private file would be published")
        continue
    text = f.read_text(encoding="utf-8", errors="ignore")
    for label, rx in PATTERNS.items():
        for m in rx.finditer(text):
            problems.append(f"{f.relative_to(ROOT)}: looks like a {label}: {m.group(0)[:18]}...")
print("\n".join(problems) or "OK - no secrets in publishable files.")
sys.exit(1 if problems else 0)
