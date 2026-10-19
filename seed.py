"""Seed data: 9 frames, 6 lenses, 7 accessories, 5 cleaning sprays.

Attributes were written to match what each product photo actually shows. Every product has its own
photo (never reused anywhere on the site). Author/licence strings come from static/img/credits.json.
"""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func

from models import Accessory, ColourOption, Frame, Lens, Product, Review, Spray

CREDITS = json.loads((Path(__file__).parent / "static" / "img" / "credits.json").read_text(encoding="utf-8"))


USD_TO_INR = 85  # change this and reseed to re-price the whole catalogue


def to_inr(usd):
    """US$ -> rupees at USD_TO_INR, rounded to a retail price point (nearest 50, minus 1: US$129 -> Rs 10,949)."""
    return round(usd * USD_TO_INR / 50) * 50 - 1


def _img(rel):
    path = f"img/{rel}.jpg"
    c = CREDITS[path]
    return dict(image=path, image_credit=f'"{c["title"]}" by {c["author"]} ({c["license"]}) - {c["source"]}')


def seed(db):
    f = lambda sku, name, brand, price, desc, img, stock, feat, **kw: Frame(  # noqa: E731
        sku=sku, name=name, brand=brand, price=price, description=desc, stock=stock, featured=feat, **_img(img), **kw)
    frames = [
        f("FR-1001", "Halo Wire Round", "Paul Optical", 129, "Ultra-fine gold wire in a perfect circle. Weighs almost nothing, looks like it was drawn with a single line.",
          "frames/gold-round-wire", 14, True, shape="Round", material="Metal", size="Small", color="Gold", color_hex="#d4af6a",
          rim_type="Full", gender="Unisex", lens_tint="Clear", lens_width=49, bridge=21, temple=145),
        f("FR-1002", "Noir Panto", "Verra", 149, "Oversized round acetate in deep gloss black with a keyhole bridge. A bold, bookish statement.",
          "frames/black-round-acetate", 9, True, shape="Round", material="Acetate", size="Large", color="Black", color_hex="#1c1c1f",
          rim_type="Full", gender="Unisex", lens_tint="Clear", lens_width=54, bridge=21, temple=145),
        f("FR-1003", "Lilac Orbit Sun", "Verra", 169, "Soft lilac acetate sunglasses with deep indigo gradient lenses and full UV400 protection.",
          "frames/lavender-round-sun", 7, True, shape="Round", material="Acetate", size="Small", color="Lilac", color_hex="#a99be0",
          rim_type="Full", gender="Women", lens_tint="Blue", lens_width=46, bridge=22, temple=140),
        f("FR-1004", "Slate Half-Frame", "Nordlyn", 139, "Lightweight half-rim with a black metal brow bar and invisible nylon line - sharp without shouting.",
          "frames/semi-rimless-black", 11, False, shape="Oval", material="Metal", size="Large", color="Black", color_hex="#22262b",
          rim_type="Half", gender="Men", lens_tint="Clear", lens_width=55, bridge=17, temple=145),
        f("FR-1005", "Featherlite Rimless", "Nordlyn", 199, "Titanium rimless mount weighing under 4 grams. The lenses float; the frame disappears.",
          "frames/rimless-titanium", 6, False, shape="Rectangle", material="Titanium", size="Medium", color="Gunmetal", color_hex="#8a919a",
          rim_type="Rimless", gender="Unisex", lens_tint="Clear", lens_width=53, bridge=17, temple=140),
        f("FR-1006", "Skyline Aviator", "Paul Optical", 159, "The pilot's classic, refined: slim gold double-bridge metal with warm amber-brown gradient lenses.",
          "frames/gold-aviator", 12, True, shape="Aviator", material="Metal", size="Large", color="Gold", color_hex="#c9a24b",
          rim_type="Full", gender="Men", lens_tint="Brown", lens_width=58, bridge=14, temple=140),
        f("FR-1007", "Rose Tortoise Cat-Eye", "Calder", 179, "Hand-polished acetate in a rose-and-plum tortoise pattern with a gently lifted outer corner.",
          "frames/pink-tortoise-cat-eye", 8, True, shape="Cat-Eye", material="Acetate", size="Medium", color="Pink Tortoise", color_hex="#a63a6b",
          rim_type="Full", gender="Women", lens_tint="Clear", lens_width=51, bridge=19, temple=140),
        f("FR-1008", "Classic Rectangle 52", "Paul Optical", 99, "The everyday workhorse: a clean black acetate rectangle with spring hinges. Our best-selling shape.",
          "frames/black-rectangle-acetate", 20, False, shape="Rectangle", material="Acetate", size="Medium", color="Black", color_hex="#141416",
          rim_type="Full", gender="Men", lens_tint="Clear", lens_width=52, bridge=20, temple=145),
        f("FR-1009", "Ledger Slim", "Calder", 119, "A narrow black metal rectangle with adjustable silicone nose pads. Small face? This is yours.",
          "frames/black-rectangle-metal", 10, False, shape="Rectangle", material="Metal", size="Small", color="Black", color_hex="#26282c",
          rim_type="Full", gender="Unisex", lens_tint="Clear", lens_width=48, bridge=18, temple=140),
    ]
    l = lambda sku, name, brand, price, desc, img, stock, feat, **kw: Lens(  # noqa: E731
        sku=sku, name=name, brand=brand, price=price, description=desc, stock=stock, featured=feat, **_img(img), **kw)
    lenses = [
        l("LN-2001", "Classic CR-39 Single Vision", "Paul Optical", 59, "The trusted baseline: optical-grade CR-39 with hard-coat scratch protection and crisp clarity.",
          "lenses/single-vision-pack-a", 80, False, lens_type="Single Vision", lens_index=1.50, material="CR-39", coating="Scratch-Resistant", uv_protection=True),
        l("LN-2002", "Thin & Light 1.60 Single Vision", "Paul Optical", 99, "A 1.60 index lens roughly 20% thinner than standard, finished with multi-layer anti-reflective coating.",
          "lenses/single-vision-pack-b", 60, True, lens_type="Single Vision", lens_index=1.60, material="High-Index", coating="Anti-Reflective", uv_protection=True),
        l("LN-2003", "Freeform Progressive 1.67", "Optis", 249, "Digitally surfaced no-line progressives: wide distance and reading zones with soft, natural transitions.",
          "lenses/progressive-close-up", 30, True, lens_type="Progressive", lens_index=1.67, material="High-Index", coating="Anti-Reflective", uv_protection=True),
        l("LN-2004", "Sport Interchangeable Lens Set", "Optis", 129, "Impact-resistant polycarbonate in smoke, amber and clear - swap in seconds for sun, shade or overcast.",
          "lenses/interchangeable-set", 25, False, lens_type="Single Vision", lens_index=1.59, material="Polycarbonate", coating="Polarized", uv_protection=True),
        l("LN-2005", "Colour-Tint Fashion Lenses", "Optis", 79, "Solid-tint CR-39 lenses in blue, green and more. Made to order for your frame and prescription.",
          "lenses/tinted-lens-set", 40, False, lens_type="Single Vision", lens_index=1.50, material="CR-39", coating="Tinted", uv_protection=True),
        l("LN-2006", "Rimless Bifocal 1.60", "Paul Optical", 149, "Flat-top bifocal with a clear distance zone and a reading segment below - cut and drill-mounted for rimless frames.",
          "lenses/rimless-clear-lens", 18, True, lens_type="Bifocal", lens_index=1.60, material="High-Index", coating="Blue-Light Filter", uv_protection=True),
    ]
    a = lambda sku, name, brand, price, desc, img, stock, feat, **kw: Accessory(  # noqa: E731
        sku=sku, name=name, brand=brand, price=price, description=desc, stock=stock, featured=feat, **_img(img), **kw)
    accessories = [
        a("AC-3001", "Union Jack Hard Case", "Calder", 24, "Rigid shell case with a soft lining - protects against drops and pocket pressure.",
          "accessories/union-jack-case", 35, True, accessory_type="Case", material="Faux Leather", color="Multicolour", compatibility="All Eyewear"),
        a("AC-3002", "Sapphire Croc Case", "Calder", 39, "Embossed faux-croc finish in deep sapphire with a metal-edged shell.",
          "accessories/blue-croc-case", 22, False, accessory_type="Case", material="Faux Leather", color="Blue", compatibility="All Eyewear"),
        a("AC-3003", "Emerald Marble Case", "Calder", 34, "A marbled resin shell in emerald green - a small jewel for your frames.",
          "accessories/green-marble-case", 16, False, accessory_type="Case", material="Resin", color="Green", compatibility="Eyeglasses"),
        a("AC-3004", "Chestnut Retainer Cord", "Paul Optical", 12, "Soft adjustable cord with secure silicone grips. Keeps glasses on your neck, not on the floor.",
          "accessories/retainer-cord", 60, False, accessory_type="Cord", material="Nylon", color="Brown", compatibility="All Eyewear"),
        a("AC-3005", "Silver Link Eyeglass Chain", "Paul Optical", 29, "Fine hand-finished metal links with decorative ring terminals - an heirloom-style way to wear your glasses.",
          "accessories/silver-chain", 12, True, accessory_type="Chain", material="Metal", color="Silver", compatibility="Eyeglasses"),
        a("AC-3006", "Rose Microfibre Cleaning Cloth", "Paul Optical", 8, "Ultra-fine microfibre that lifts oil and fingerprints without a single scratch. Machine washable.",
          "accessories/microfiber-cloth", 150, False, accessory_type="Cloth", material="Microfibre", color="Pink", compatibility="All Eyewear"),
        a("AC-3007", "Mint Travel Lens Case", "Optis", 9, "Leak-resistant twin-well case with colour-coded caps for left and right lenses.",
          "accessories/lens-case", 70, False, accessory_type="Lens Case", material="Plastic", color="Mint", compatibility="Contact Lenses"),
    ]
    s = lambda sku, name, brand, price, desc, img, stock, feat, **kw: Spray(  # noqa: E731
        sku=sku, name=name, brand=brand, price=price, description=desc, stock=stock, featured=feat, **_img(img), **kw)
    sprays = [
        s("SP-4001", "Lens Cleaning Liquid + 30 Papers", "Optis", 12, "Gentle alcohol-free liquid plus 30 lint-free lens papers - a complete travel cleaning set.",
          "sprays/lens-cleaning-liquid", 90, True, volume_ml=30, formula="Alcohol-Free", scent="Unscented", safe_for="All Lenses", includes_cloth=True),
        s("SP-4002", "Crystal Mist Lens Spray", "Paul Optical", 10, "A fine, even mist that leaves coated lenses streak-free and static-free.",
          "sprays/clear-mist-bottle", 110, False, volume_ml=60, formula="Streak-Free", scent="Unscented", safe_for="Coated Lenses", includes_cloth=False),
        s("SP-4003", "Rose Fresh Lens & Frame Cleaner", "Paul Optical", 14, "Cleans lenses and frames with a light rose scent; anti-static finish repels dust.",
          "sprays/pink-trigger-bottle", 55, False, volume_ml=250, formula="Anti-Static", scent="Rose", safe_for="All Lenses", includes_cloth=True),
        s("SP-4004", "Ocean Anti-Fog Spray", "Optis", 11, "One spritz keeps lenses clear in masks, steam and cold - lasts up to 8 hours.",
          "sprays/blue-trigger-bottle", 48, False, volume_ml=120, formula="Anti-Fog", scent="Sea Breeze", safe_for="All Lenses", includes_cloth=False),
        s("SP-4005", "Citrus Shop-Size Cleaner", "Optis", 18, "The big refill bottle we use in our own store. Alcohol-free and safe on every coating.",
          "sprays/yellow-trigger-bottle", 40, False, volume_ml=500, formula="Alcohol-Free", scent="Citrus", safe_for="Sunglasses", includes_cloth=False),
    ]
    for p in frames + lenses + accessories + sprays:
        p.price = to_inr(p.price)  # the lists above were written in US$; the store sells in Indian rupees
    db.add_all(frames + lenses + accessories + sprays)
    db.commit()


# ---------------------------------------------------------------------------------------------------------------
# Detail-page extras: colourways, discounts and sample reviews. Idempotent: runs once (colour table empty = first run).
DISCOUNT_PCT = {"FR-1003": 20, "FR-1006": 15, "FR-1008": 10, "FR-1009": 12, "LN-2002": 25, "AC-3002": 30, "SP-4003": 15}
COLOURS = {
    "FR-1001": [("Rose Gold", "#d9a38f"), ("Silver", "#c5cbd3")], "FR-1002": [("Tortoise", "#7a4b2a"), ("Navy", "#1f2f5a")],
    "FR-1003": [("Sky Blue", "#8fb7e8"), ("Blush", "#e8a9bd")], "FR-1004": [("Gunmetal", "#5b636d"), ("Brown", "#6b4a35")],
    "FR-1005": [("Gold", "#c9a24b"), ("Black", "#22262b")], "FR-1006": [("Silver", "#c5cbd3"), ("Gunmetal", "#5b636d")],
    "FR-1007": [("Havana", "#8a5a2b"), ("Teal", "#1f6f78")], "FR-1008": [("Tortoise", "#7a4b2a"), ("Navy", "#1f2f5a")],
    "FR-1009": [("Silver", "#c5cbd3"), ("Bronze", "#8a6a3b")],
}
NO_REVIEWS = {"FR-1005", "LN-2005", "AC-3007", "AC-3004", "SP-4005"}  # left empty on purpose so the empty state is real
AUTHORS = ["Ananya R.", "Rohit K.", "Meera S.", "Vikram P.", "Sana A.", "Arjun M.", "Kavya N.", "Imran H.", "Divya T.", "Nikhil B.",
           "Priya D.", "Karan J.", "Neha G.", "Aditya V.", "Shreya L.", "Manish C."]
REVIEW_TEXT = {  # (rating, text) pools per category; {n} is replaced by the product name
    "frames": [(5, "Lovely fit and the finish looks far more expensive than the price. Very happy with the {n}."),
               (5, "Light enough to wear all day. The try-on on the site was pretty close to how it looks on me."),
               (4, "Good quality and comfortable. Took a couple of days to get used to the nose pads."),
               (4, "Looks great, true to the photos. Packaging was neat."),
               (3, "Nice frame but a little wide for my face. Pick the narrower lens width if you're between sizes."),
               (5, "Third pair I've bought from here. The {n} is my favourite so far."),
               (2, "Beautiful but the temples felt tight behind my ears at first. Adjusted by the store, fine now."),
               (5, "Exactly what I wanted. The lens width options helped me get the fit right."),
               (4, "Sturdy hinges and a clean finish. Delivery was quick."),
               (5, "Got compliments the very first day I wore the {n}."),
               (4, "Great value. The colour looks a touch different in daylight, but I like it even more."),
               (3, "Decent frame overall. I wish it came with a better case."),
               (5, "Light and well balanced, and it doesn't slip when I look down.")],
    "lenses": [(5, "Noticeably clearer vision and the coating cuts glare well when driving at night."),
               (4, "Good quality lenses. Thinner than my old pair, as promised."),
               (5, "Adapted within a day. The {n} is excellent value."),
               (3, "Fine lenses but they took a week to arrive after fitting."),
               (4, "No distortion at the edges. Would buy again."),
               (5, "Crisp vision from edge to edge, and the coating shrugs off fingerprints."),
               (4, "Comfortable from day one and a real step up from my old lenses."),
               (3, "Good lenses, but I'd have liked more guidance choosing the index.")],
    "accessories": [(5, "Sturdy and looks good. Exactly as pictured."),
                    (4, "Does the job well, good finish for the price."),
                    (5, "Bought as a gift and they loved it."),
                    (3, "Okay quality, smaller than I expected."),
                    (4, "Nice colour and well made."),
                    (5, "Feels premium for the price and arrived well packed."),
                    (4, "Practical and good looking. Does exactly what it should."),
                    (3, "Fine, though the colour is a little duller than the photo.")],
    "sprays": [(5, "Streak-free and no smell. A little goes a long way."),
               (4, "Works well on my coated lenses and doesn't leave residue."),
               (5, "Lenses look brand new. Will reorder the {n}."),
               (3, "Cleans fine but the nozzle clogged once."),
               (4, "Good value, cleans phone screens too."),
               (5, "No streaks on my glasses or my laptop screen. Very happy."),
               (4, "Gentle on my anti-glare coating and it dries fast."),
               (3, "Works, but I'd like a bigger bottle for the price.")],
}


def seed_extras(db):
    if db.query(func.count(ColourOption.id)).scalar():
        return
    prods = {p.sku: p for p in db.query(Product).all()}
    for sku, opts in COLOURS.items():
        for name, hx in opts:
            db.add(ColourOption(product_id=prods[sku].id, name=name, hex=hx))
    for sku, pct in DISCOUNT_PCT.items():
        p = prods[sku]
        if p.original_price is None:
            p.original_price, p.price = p.price, round(p.price * (1 - pct / 100) / 50) * 50 - 1
    db.commit()
    seed_reviews(db)


def seed_reviews(db):
    """Sample reviews (tagged as samples in the UI). Skipped if any already exist. A product's sample reviews never repeat a line."""
    if db.query(func.count(Review.id)).scalar():
        return
    now = datetime.now(timezone.utc)
    for p in db.query(Product).all():
        if p.sku in NO_REVIEWS:
            continue
        rng = random.Random(p.sku)                   # deterministic: same sample reviews on every fresh database
        pool = REVIEW_TEXT[p.category]
        n = rng.randint(6, min(12, len(pool))) if p.category == "frames" else rng.randint(2, min(7, len(pool)))
        for rating, text in rng.sample(pool, n):
            db.add(Review(product_id=p.id, author=rng.choice(AUTHORS), rating=rating, text=text.format(n=p.name),
                          created=now - timedelta(days=rng.randint(2, 420), hours=rng.randint(0, 23)), is_sample=True))
    db.commit()
