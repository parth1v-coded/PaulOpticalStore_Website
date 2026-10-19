"""Search openly-licensed photos and build a labelled contact sheet so candidates can be eyeballed.

Usage: python find_images.py <outdir> <commons|openverse> "<query>" [more queries...]
Writes <outdir>/cands.json (metadata) + <outdir>/sheet_<n>.jpg contact sheets.
Dev-time helper only - not needed to run the site.
"""
import io, json, re, sys, pathlib
import requests
from PIL import Image, ImageDraw

UA = {"User-Agent": "PaulOpticalBuild/1.0 (portfolio project; see the project's GitHub page)"}
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
source = sys.argv[2]
cands_file = out / "cands.json"
cands = json.loads(cands_file.read_text()) if cands_file.exists() else []
seen = {c["title"] for c in cands}


def strip(html):
    return re.sub(r"<[^>]+>", "", html or "").strip()


def commons(q):
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params={
        "action": "query", "format": "json", "generator": "search", "gsrsearch": q + " filetype:bitmap",
        "gsrnamespace": 6, "gsrlimit": 40, "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 360})
    for p in sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in ("image/jpeg", "image/png") or ii.get("width", 0) < 900:
            continue
        md = ii.get("extmetadata", {})
        yield dict(title=p["title"], url=ii["url"], thumb=ii["thumburl"], w=ii["width"], h=ii["height"],
                   page=ii["descriptionurl"], license=md.get("LicenseShortName", {}).get("value", "?"),
                   author=strip(md.get("Artist", {}).get("value", "?"))[:80])


def openverse(q):
    r = requests.get("https://api.openverse.org/v1/images/", headers=UA, timeout=30, params={
        "q": q, "license": "cc0,pdm,by,by-sa", "page_size": 30, "mature": "false"})
    if r.status_code != 200:
        print("openverse", r.status_code, q, r.text[:120])
        return
    for x in r.json().get("results", []):
        if (x.get("width") or 1024) < 800 or x.get("filetype") not in (None, "jpg", "jpeg", "png"):
            continue
        yield dict(title=x["id"], url=x["url"], thumb=x["thumbnail"], w=x.get("width") or 0, h=x.get("height") or 0,
                   page=x.get("foreign_landing_url", ""), license=f'{x["license"]} {x.get("license_version", "")}'.strip(),
                   author=(x.get("creator") or "?")[:80] + " / " + x.get("title", "")[:40])


for q in sys.argv[3:]:
    for c in (commons if source == "commons" else openverse)(q):
        if c["title"] in seen:
            continue
        c.update(id=len(cands), q=q)
        cands.append(c); seen.add(c["title"])
cands_file.write_text(json.dumps(cands, indent=1))

tiles = []
for c in cands:
    t = out / f"t{c['id']}.jpg"
    if not t.exists():
        try:
            Image.open(io.BytesIO(requests.get(c["thumb"], headers=UA, timeout=30).content)).convert("RGB").save(t)
        except Exception as e:
            print("thumb fail", c["id"], e)
    tiles.append(c["id"])
CW, CH, COLS, ROWS = 300, 240, 5, 4
per = COLS * ROWS
for s in range(0, len(tiles), per):
    sheet = Image.new("RGB", (COLS * CW, ROWS * CH), "white")
    d = ImageDraw.Draw(sheet)
    for k, cid in enumerate(tiles[s:s + per]):
        tp = out / f"t{cid}.jpg"
        if not tp.exists():
            continue
        im = Image.open(tp); im.thumbnail((CW - 6, CH - 22))
        x, y = (k % COLS) * CW, (k // COLS) * CH
        sheet.paste(im, (x + 3, y + 3))
        d.rectangle([x, y + CH - 20, x + 120, y + CH - 2], fill="black")
        d.text((x + 4, y + CH - 18), f"#{cid} {cands[cid]['w']}x{cands[cid]['h']}", fill="white")
    sheet.save(out / f"sheet_{s // per}.jpg", quality=80)
print(len(cands), "candidates;", (len(tiles) + per - 1) // per, "sheets")

