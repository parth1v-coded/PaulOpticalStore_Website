"""Regenerate pricing.md - the chatbot's ONLY knowledge - from the product database.

Run after changing products:   python tools/make_pricing.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import app  # noqa: E402,F401  (makes sure the DB exists and is seeded)
from models import Accessory, Frame, Lens, Session, Spray  # noqa: E402

yn = lambda b: "yes" if b else "no"  # noqa: E731
LINE = {
    Frame: lambda p: f"{p.shape}, {p.material}, {p.size}, {p.color}, {'rimless' if p.rim_type == 'Rimless' else p.rim_type.lower() + ' rim'}, {'unisex' if p.gender == 'Unisex' else 'for ' + p.gender.lower()}, {p.lens_tint.lower()} lenses, fit {p.lens_width}-{p.bridge}-{p.temple} mm",
    Lens: lambda p: f"{p.lens_type}, index {p.lens_index:.2f}, {p.material}, {p.coating}, UV protection: {yn(p.uv_protection)}",
    Accessory: lambda p: f"{p.accessory_type}, {p.material}, {p.color}, fits: {p.compatibility}",
    Spray: lambda p: f"{p.volume_ml} ml, {p.formula}, scent: {p.scent}, safe for: {p.safe_for}, includes cloth/wipes: {yn(p.includes_cloth)}",
}
out = ["# Paul Optical - Price list (all prices in Indian rupees (INR), per item)", "",
       "This list covers every product Paul Optical sells: frames, lenses, optical accessories and cleaning sprays. "
       "Prices are per single item. Lenses are priced per product as listed.", ""]
with Session() as db:
    for model, title in ((Frame, "Frames"), (Lens, "Lenses"), (Accessory, "Optical accessories"), (Spray, "Cleaning sprays")):
        out += [f"## {title}"]
        for p in db.query(model).order_by(model.price, model.id):
            stock = f"{p.stock} in stock" if p.stock else "out of stock"
            out.append(f"- {p.name} (SKU {p.sku}, brand {p.brand}): ₹{p.price:,.0f}. {f'Discounted from ₹{p.original_price:,.0f} ({round((1 - p.price / p.original_price) * 100)}% off). ' if p.original_price else ''}{LINE[model](p)}. {stock}.")
        out.append("")
(ROOT / "pricing.md").write_text("\n".join(out), encoding="utf-8")
print("pricing.md written")
