"""Download the chosen candidate photos into static/img/<category>/ and write static/img/credits.json.

Usage: python fetch_images.py <scratch dir holding the candidate folders>
Dev-time helper (documents where every image came from); the site itself only needs the downloaded files.
"""
import io, json, pathlib, sys, time, urllib.parse
import requests
from PIL import Image

UA = {"User-Agent": "PaulOpticalBuild/1.0 (portfolio project; see the project's GitHub page)"}
scratch = pathlib.Path(sys.argv[1])
IMG = pathlib.Path(__file__).resolve().parent.parent / "static" / "img"

# relative path under static/img  ->  (candidate folder, candidate id)
PICKS = {
    "frames/gold-round-wire": ("frames", 61), "frames/black-round-acetate": ("frames", 67),
    "frames/lavender-round-sun": ("frames", 71), "frames/semi-rimless-black": ("frames", 7),
    "frames/rimless-titanium": ("frames", 155), "frames/gold-aviator": ("frames", 42),
    "frames/pink-tortoise-cat-eye": ("frames", 116), "frames/black-rectangle-acetate": ("frames", 23),
    "frames/black-rectangle-metal": ("frames", 0),
    "lenses/single-vision-pack-a": ("lenses", 1), "lenses/single-vision-pack-b": ("lenses", 2),
    "lenses/progressive-close-up": ("lenses", 68), "lenses/interchangeable-set": ("lenses", 20),
    "lenses/tinted-lens-set": ("lenses", 107), "lenses/rimless-clear-lens": ("lenses", 0),
    "accessories/union-jack-case": ("acc", 41), "accessories/blue-croc-case": ("acc", 52),
    "accessories/green-marble-case": ("acc", 56), "accessories/retainer-cord": ("acc", 62),
    "accessories/silver-chain": ("acc", 63), "accessories/microfiber-cloth": ("spray", 4),
    "accessories/lens-case": ("acc", 11),
    "sprays/lens-cleaning-liquid": ("spray2", 38), "sprays/clear-mist-bottle": ("spray2", 33),
    "sprays/pink-trigger-bottle": ("spray2", 0), "sprays/blue-trigger-bottle": ("spray2", 8),
    "sprays/yellow-trigger-bottle": ("spray2", 3),
    "site/tile-frames": ("frames", 40), "site/tile-lenses": ("lenses", 106), "site/tile-accessories": ("acc", 16),
    "site/tile-sprays": ("spray2", 27), "site/lab-edging": ("lenses", 38), "site/showroom": ("lenses", 32),
    "site/eye-test": ("lenses", 101),
}

credits = {}
for rel, (folder, cid) in PICKS.items():
    c = json.loads((scratch / folder / "cands.json").read_text())[cid]
    dest = IMG / f"{rel}.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        name = urllib.parse.quote(c["title"].removeprefix("File:").replace(" ", "_"))
        url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{name}?width=1400"
        for attempt in range(6):
            r = requests.get(url, headers=UA, timeout=90)
            if r.status_code == 200:
                break
            time.sleep(5 * (attempt + 1))
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        im.thumbnail((1400, 1400))
        im.save(dest, quality=82, optimize=True)
        time.sleep(1.5)
    credits[f"img/{rel}.jpg"] = {"title": c["title"].removeprefix("File:"), "author": c["author"],
                                 "license": c["license"], "source": c["page"]}
    print(rel, "ok", c["license"])
(IMG / "credits.json").write_text(json.dumps(credits, indent=1), encoding="utf-8")
