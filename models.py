"""SQLAlchemy models for Paul Optical.

One base `products` table holds what every product shares; each category has its own
table (joined-table inheritance) whose NOT NULL columns are the attributes that category
*must* have - a Frame can't be saved without a shape/material/size, a Lens without an
index/coating, etc. The database itself enforces "required fields tied to category".
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# SQLite file lives next to this script; created automatically on first run - nothing to configure.
DB_PATH = Path(os.environ.get("PAUL_OPTICAL_DB") or Path(__file__).with_name("paul_optical.db"))  # env override is for tests
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
Session = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Message(Base):
    """A customer's contact-form message (name + phone + text), saved the moment they press Send."""
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)
    created = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    sku = Column(String(24), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    brand = Column(String(60), nullable=False)
    category = Column(String(20), nullable=False, index=True)  # frames | lenses | accessories | sprays
    price = Column(Numeric(10, 2, asdecimal=False), nullable=False)
    original_price = Column(Numeric(10, 2, asdecimal=False), nullable=True)  # set only while discounted; `price` is always what's charged
    description = Column(Text, nullable=False)
    image = Column(String(200), nullable=False, unique=True)  # one photo per product, never shared
    image_credit = Column(String(300), nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    featured = Column(Boolean, nullable=False, default=False)
    __mapper_args__ = {"polymorphic_on": category}


class ColourOption(Base):
    """Extra colourways a frame is offered in (its own colour is on the Frame row)."""
    __tablename__ = "colour_options"
    id = Column(Integer, primary_key=True)
    product_id = Column(ForeignKey("products.id"), nullable=False, index=True)
    name = Column(String(30), nullable=False)
    hex = Column(String(7), nullable=False)


class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True)
    product_id = Column(ForeignKey("products.id"), nullable=False, index=True)
    author = Column(String(60), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    text = Column(Text, nullable=False)
    created = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_sample = Column(Boolean, nullable=False, default=False)  # seeded demo review (shown with a "Sample" tag)


class Frame(Product):
    __tablename__ = "frames"
    id = Column(ForeignKey("products.id"), primary_key=True)
    shape = Column(String(20), nullable=False)       # Round, Oval, Rectangle, Square, Aviator, Cat-Eye, Geometric
    material = Column(String(20), nullable=False)    # Acetate, Metal, Titanium, TR90
    size = Column(String(10), nullable=False)        # Small, Medium, Large
    color = Column(String(30), nullable=False)
    color_hex = Column(String(7), nullable=False)    # drives the try-on overlay
    rim_type = Column(String(12), nullable=False)    # Full, Half, Rimless
    gender = Column(String(10), nullable=False)      # Men, Women, Unisex
    lens_tint = Column(String(12), nullable=False)   # Clear, Gray, Brown, Blue  (sunglass frames carry a tint)
    lens_width = Column(Integer, nullable=False)     # mm; frame spec 52-18-140 = lens_width-bridge-temple
    bridge = Column(Integer, nullable=False)
    temple = Column(Integer, nullable=False)
    __mapper_args__ = {"polymorphic_identity": "frames"}


class Lens(Product):
    __tablename__ = "lenses"
    id = Column(ForeignKey("products.id"), primary_key=True)
    lens_type = Column(String(20), nullable=False)   # Single Vision, Bifocal, Progressive
    lens_index = Column(Float, nullable=False)       # 1.50 ... 1.74 (higher = thinner)
    material = Column(String(20), nullable=False)    # CR-39, Polycarbonate, Trivex, High-Index
    coating = Column(String(30), nullable=False)     # Anti-Reflective, Blue-Light Filter, Photochromic, Polarized, Scratch-Resistant
    uv_protection = Column(Boolean, nullable=False)
    __mapper_args__ = {"polymorphic_identity": "lenses"}


class Accessory(Product):
    __tablename__ = "accessories"
    id = Column(ForeignKey("products.id"), primary_key=True)
    accessory_type = Column(String(20), nullable=False)  # Case, Cleaning Cloth, Cord, Repair Kit, Stand
    material = Column(String(20), nullable=False)
    color = Column(String(30), nullable=False)
    compatibility = Column(String(20), nullable=False)   # Eyeglasses, Sunglasses, All Eyewear
    __mapper_args__ = {"polymorphic_identity": "accessories"}


class Spray(Product):
    __tablename__ = "sprays"
    id = Column(ForeignKey("products.id"), primary_key=True)
    volume_ml = Column(Integer, nullable=False)
    formula = Column(String(24), nullable=False)     # Alcohol-Free, Anti-Fog, Anti-Static, Streak-Free
    scent = Column(String(20), nullable=False)
    safe_for = Column(String(24), nullable=False)    # All Lenses, Coated Lenses, Sunglasses
    includes_cloth = Column(Boolean, nullable=False)
    __mapper_args__ = {"polymorphic_identity": "sprays"}


# Single source of truth for the shop: category label/blurb, the model class, which
# attribute columns are exposed as filters (and their labels). The API and UI are driven by this.
CATEGORIES = {
    "frames": dict(model=Frame, label="Frames", blurb="Eyeglasses & sunglass frames in every shape.",
                   facets={"shape": "Shape", "material": "Material", "size": "Size", "color": "Colour",
                           "rim_type": "Rim", "gender": "For", "lens_tint": "Lens tint"}),
    "lenses": dict(model=Lens, label="Lenses", blurb="Precision lenses for every prescription.",
                   facets={"lens_type": "Lens type", "lens_index": "Index", "material": "Material", "coating": "Coating"}),
    "accessories": dict(model=Accessory, label="Accessories", blurb="Cases, cords and care kits.",
                        facets={"accessory_type": "Type", "material": "Material", "color": "Colour",
                                "compatibility": "Fits"}),
    "sprays": dict(model=Spray, label="Cleaning Sprays", blurb="Streak-free lens care.",
                   facets={"formula": "Formula", "scent": "Scent", "safe_for": "Safe for", "volume_ml": "Volume (ml)"}),
}
