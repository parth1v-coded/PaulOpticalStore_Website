"""Paul Optical - Flask back end.   Run:  python app.py   then open http://127.0.0.1:5000

On first run it creates paul_optical.db (SQLite) and seeds it with sample products. No configuration needed.
"""
import base64
import hashlib
import hmac
import mimetypes
import os
import re
import secrets
import time
from html import escape
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_from_directory
from sqlalchemy import func, inspect, or_
from sqlalchemy.orm import with_polymorphic

import chatbot
from frames_svg import TINT, frame_width_mm, overlay_svg, side_svg
from models import (CATEGORIES, Accessory, Base, ColourOption, Frame, Lens, Message, Product, Review, Session, Spray, engine)
from seed import seed, seed_extras

# Windows can map .js to text/plain via the registry, which breaks ES modules - pin the types we serve.
for ext, mime in ((".js", "text/javascript"), (".mjs", "text/javascript"), (".wasm", "application/wasm")):
    mimetypes.add_type(mime, ext)

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.json.sort_keys = False
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # no request body here is ever larger; stops memory-exhaustion uploads


def init_db():
    Base.metadata.create_all(engine)  # creates any missing tables (also on databases made before the detail page existed)
    if "original_price" not in {c["name"] for c in inspect(engine).get_columns("products")}:
        with engine.begin() as c:     # create_all never alters an existing table, so add the one new column by hand
            c.exec_driver_sql("ALTER TABLE products ADD COLUMN original_price NUMERIC(10, 2)")
    with Session() as db:
        if not db.query(func.count(Product.id)).scalar():
            seed(db)
        seed_extras(db)


def spec_columns(model):
    """The category-specific columns of a model, i.e. its own table minus the id key."""
    return [c.name for c in model.__table__.columns if c.name != "id"]


def to_dict(p):
    d = dict(id=p.id, sku=p.sku, name=p.name, brand=p.brand, category=p.category, price=p.price,
             original_price=p.original_price,
             discount_pct=round((1 - p.price / p.original_price) * 100) if p.original_price and p.original_price > p.price else 0,
             description=p.description, image="/static/" + p.image, image_credit=p.image_credit,
             stock=p.stock, featured=p.featured,
             specs={k: getattr(p, k) for k in spec_columns(type(p))})
    if p.category == "frames":
        _, width_mm = overlay_svg(p)
        d["tryon"] = {"overlay": f"/api/frames/{p.id}/overlay.svg", "width_mm": width_mm}
    return d


def category_or_400():
    cat = request.args.get("category")
    if cat is not None and cat not in CATEGORIES:
        abort(400, f"unknown category '{cat}'")
    return cat


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/categories")
def categories():
    with Session() as db:
        counts = dict(db.query(Product.category, func.count()).group_by(Product.category).all())
    return jsonify([dict(key=k, label=v["label"], blurb=v["blurb"], count=counts.get(k, 0)) for k, v in CATEGORIES.items()])


@app.get("/api/facets")
def facets():
    """Filter options for one category, taken from the data so they can never go stale.
    ponytail: counts are per-category totals, not re-computed against the other active filters."""
    cat = category_or_400()
    if not cat:
        abort(400, "category is required")
    model = CATEGORIES[cat]["model"]
    out = []
    with Session() as db:
        for key, label in CATEGORIES[cat]["facets"].items():
            col = getattr(model, key)
            rows = db.query(col, func.count()).group_by(col).all()
            rows.sort(key=lambda r: r[0])
            out.append(dict(key=key, label=label, options=[dict(value=v, count=n) for v, n in rows]))
        lo, hi = db.query(func.min(model.price), func.max(model.price)).one()
    return jsonify(dict(facets=out, price=dict(min=lo, max=hi)))


@app.get("/api/products")
def products():
    """Filter params: category, q, min_price, max_price, sort, in_stock, plus any facet of the category
    (repeat a param to OR its values, e.g. ?category=frames&shape=Round&shape=Aviator&material=Metal)."""
    cat = category_or_400()
    poly = with_polymorphic(Product, [Frame, Lens, Accessory, Spray])
    model = CATEGORIES[cat]["model"] if cat else poly
    with Session() as db:
        qry = db.query(model)
        if cat:
            for key in CATEGORIES[cat]["facets"]:
                raw = request.args.getlist(key)
                if raw:
                    col = getattr(model, key)
                    cast = col.type.python_type
                    try:
                        vals = [cast(v) for v in raw]
                    except ValueError:
                        abort(400, f"bad value for '{key}'")
                    qry = qry.filter(col.in_(vals))
        if request.args.get("q"):
            like = f"%{request.args['q'].strip()}%"
            qry = qry.filter(or_(model.name.ilike(like), model.brand.ilike(like), model.description.ilike(like)))
        try:
            if request.args.get("min_price"):
                qry = qry.filter(model.price >= float(request.args["min_price"]))
            if request.args.get("max_price"):
                qry = qry.filter(model.price <= float(request.args["max_price"]))
        except ValueError:
            abort(400, "price must be a number")
        if request.args.get("in_stock") == "1":
            qry = qry.filter(model.stock > 0)
        order = {"price_asc": [model.price], "price_desc": [model.price.desc()], "name": [model.name]}.get(
            request.args.get("sort"), [model.featured.desc(), model.id])
        return jsonify([to_dict(p) for p in qry.order_by(*order).all()])


@app.get("/api/frames/<int:frame_id>/overlay.svg")
def overlay(frame_id):
    """Drawing of a frame. Optional query: color=rrggbb, lw=<lens width mm>, tint=<Clear|Gray|Brown|Blue|Blue-Light>,
    view=front (default, also the try-on overlay) | side | dims (front view with measurements)."""
    a = request.args
    color, lw, tint, view = a.get("color"), a.get("lw", type=int), a.get("tint"), a.get("view", "front")
    if (color and not re.fullmatch(r"[0-9a-fA-F]{6}", color)) or (a.get("lw") and not lw or lw and not 40 <= lw <= 66) \
            or (tint and tint not in TINT) or view not in ("front", "side", "dims"):
        abort(400, "bad variant parameters")
    color = f"#{color}" if color else None
    with Session() as db:
        frame = db.get(Frame, frame_id)
        if frame is None:
            abort(404)
        svg = side_svg(frame, color, lw) if view == "side" else overlay_svg(frame, color, lw, tint, annotate=view == "dims")[0]
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


# Lens choices offered on frames (the drawing, and the price, change with the choice)
LENS_OPTIONS = [dict(key="standard", name="Standard (as shown)", price_delta=0, tint=None),
                dict(key="blue-light", name="Blue-light filter", price_delta=1299, tint="Blue-Light"),
                dict(key="gray", name="Gray sun tint", price_delta=999, tint="Gray")]


def features(p):
    """Short, scannable bullets for the detail page, built only from the product's real attributes."""
    s = {k: getattr(p, k) for k in spec_columns(type(p))}
    if p.category == "frames":
        out = [f"{s['material']} frame, {s['rim_type'].lower()}-rim design" if s["rim_type"] != "Rimless" else f"{s['material']} frame, rimless design",
               {"Titanium": "Lightweight titanium", "Metal": "Slim metal build with adjustable nose pads", "Acetate": "Comfortable acetate that holds its shape",
                "TR90": "Flexible, featherlight TR90"}[s["material"]],
               f"{s['shape']} shape, {'unisex' if s['gender'] == 'Unisex' else 'for ' + s['gender'].lower()}",
               f"Fit {s['lens_width']}-{s['bridge']}-{s['temple']} mm ({s['size'].lower()})",
               "Clear lenses, prescription-ready: single vision, bifocal or progressive" if s["lens_tint"] == "Clear"
               else f"{s['lens_tint']} tinted lenses with UV400 protection"]
        return out
    if p.category == "lenses":
        thick = "standard thickness" if s["lens_index"] <= 1.5 else "thinner and lighter than standard" if s["lens_index"] >= 1.6 else "impact-resistant and light"
        return [f"{s['lens_type']} lenses", f"Index {s['lens_index']:.2f}: {thick}", f"{s['material']} material", f"{s['coating']} coating",
                "UV protection: yes" if s["uv_protection"] else "UV protection: no", "Cut and fitted to your prescription"]
    if p.category == "accessories":
        return [f"{s['accessory_type']}", f"{s['material']}, {s['color'].lower()}", f"Fits: {s['compatibility'].lower()}"]
    return [f"{s['volume_ml']} ml", f"{s['formula']} formula", f"Scent: {s['scent'].lower()}", f"Safe for: {s['safe_for'].lower()}",
            "Includes a cleaning cloth / wipes" if s["includes_cloth"] else "Cloth not included"]


def frame_options(f, db):
    cols = [dict(name=f.color, hex=f.color_hex)] + [dict(name=c.name, hex=c.hex) for c in
                                                    db.query(ColourOption).filter_by(product_id=f.id).order_by(ColourOption.id)]
    widths = [dict(lens_width=w, width_mm=frame_width_mm(w, f.bridge), label=f"{w} mm") for w in (f.lens_width - 2, f.lens_width, f.lens_width + 2)]
    return dict(colours=cols, widths=widths, default_width=f.lens_width, lenses=LENS_OPTIONS, default_tint=f.lens_tint,
                overlay=f"/api/frames/{f.id}/overlay.svg")


def rating_summary(db, pid):
    rows = dict(db.query(Review.rating, func.count()).filter_by(product_id=pid).group_by(Review.rating).all())
    n = sum(rows.values())
    return dict(count=n, average=round(sum(k * v for k, v in rows.items()) / n, 1) if n else 0, histogram={str(k): rows.get(k, 0) for k in (5, 4, 3, 2, 1)})


@app.get("/api/products/<int:pid>")
def product_detail(pid):
    with Session() as db:
        p = db.get(Product, pid)
        if p is None:
            abort(404)
        d = to_dict(p)
        d["features"] = features(p)
        d["rating"] = rating_summary(db, pid)
        if p.category == "frames":
            d["options"] = frame_options(p, db)
    return jsonify(d)


@app.get("/product/<int:pid>")
def product_page(pid):
    """Shareable link: the same single page, which opens the product's detail screen on load."""
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/products/<int:pid>/reviews")
def list_reviews(pid):
    """?sort=recent|highest|lowest  &stars=1-5 (filter)  &offset=0  &limit=5"""
    sort, stars = request.args.get("sort", "recent"), request.args.get("stars", type=int)
    offset, limit = max(request.args.get("offset", 0, type=int), 0), min(max(request.args.get("limit", 5, type=int), 1), 20)
    order = {"recent": [Review.created.desc()], "highest": [Review.rating.desc(), Review.created.desc()],
             "lowest": [Review.rating, Review.created.desc()]}.get(sort)
    if order is None or (stars is not None and stars not in range(1, 6)):
        abort(400, "bad sort or stars")
    with Session() as db:
        if db.get(Product, pid) is None:
            abort(404)
        q = db.query(Review).filter_by(product_id=pid)
        if stars:
            q = q.filter(Review.rating == stars)
        total = q.count()
        items = [dict(id=r.id, author=r.author, rating=r.rating, text=r.text, date=r.created.strftime("%Y-%m-%d"), sample=r.is_sample)
                 for r in q.order_by(*order, Review.id.desc()).offset(offset).limit(limit)]
        return jsonify(summary=rating_summary(db, pid), total=total, items=items)


@app.post("/api/products/<int:pid>/reviews")
def add_review(pid):
    if rate_limited("review", 5):
        return jsonify(error="Too many reviews - please wait a minute and try again."), 429
    d = request.get_json(silent=True) or {}
    author, text, rating = str(d.get("author", "")).strip(), str(d.get("text", "")).strip(), d.get("rating")
    if not author or len(author) > 60:
        abort(400, "Please enter your name (up to 60 characters).")
    if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5:
        abort(400, "Please choose a star rating from 1 to 5.")
    if not 5 <= len(text) <= 600:
        abort(400, "Please write a review of 5 to 600 characters.")
    with Session() as db:
        if db.get(Product, pid) is None:
            abort(404)
        db.add(Review(product_id=pid, author=author, rating=rating, text=text))
        db.commit()
    return jsonify(ok=True), 201


_hits = {}


def rate_limited(bucket, limit, per=60, record=True):
    """True if this client already made `limit` calls to `bucket` in the last `per` seconds.
    ponytail: in-memory and per-process, keyed on request.remote_addr (behind a proxy that is the proxy's IP - configure
    ProxyFix; with several worker processes use a shared store such as Redis)."""
    now = time.time()
    if len(_hits) > 5000:  # drop entries nobody has touched for a while, so memory can't grow without bound
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > 600]:
            del _hits[k]
    key = (bucket, request.remote_addr)
    recent = [t for t in _hits.get(key, []) if now - t < per]
    limited = len(recent) >= limit
    if record and not limited:
        recent.append(now)
    _hits[key] = recent
    return limited


@app.post("/api/chat")
def chat():
    """Pricing chatbot. Body: {"messages": [{"role": "user"|"assistant", "content": "..."}]} -> {"reply": "..."}"""
    if rate_limited("chat", 20):  # protects the Gemini quota
        return jsonify(error="You're asking very quickly - please wait a minute and try again."), 429
    msgs = (request.get_json(silent=True) or {}).get("messages")
    if not isinstance(msgs, list) or len(request.get_data()) > 20_000:
        return jsonify(error="Invalid request."), 400
    try:
        return jsonify(reply=chatbot.answer(msgs))
    except chatbot.ChatError as e:
        return jsonify(error=str(e)), e.status


PHONE = re.compile(r"^[0-9+()\-\s.]{6,30}$")


@app.post("/api/messages")
def save_message():
    """Customer contact form: stores name + phone + message in the `messages` table."""
    if rate_limited("message", 10):
        return jsonify(error="Too many messages - please wait a minute and try again."), 429
    d = request.get_json(silent=True) or {}
    if d.get("website"):  # honeypot field: invisible to people, bots fill it in
        return jsonify(ok=True), 201
    name, phone, text = (str(d.get(k, "")).strip() for k in ("name", "phone", "message"))
    if not name or len(name) > 100:
        abort(400, "Please enter your name.")
    if not PHONE.match(phone):
        abort(400, "Please enter a valid phone number.")
    if not text or len(text) > 2000:   # 2000 so a large cart's order request fits; the contact textarea itself stops at 1000
        abort(400, "Please type a message (up to 2000 characters; for orders, remove a few items).")
    with Session() as db:
        db.add(Message(name=name, phone=phone, message=text))
        db.commit()
    return jsonify(ok=True), 201


ADMIN_FILE = Path(__file__).with_name("admin_password.txt")


def admin_password():
    """ADMIN_PASSWORD env var if set, otherwise a random one generated on first run and kept in admin_password.txt."""
    env = os.environ.get("ADMIN_PASSWORD", "")
    if env and not env.upper().startswith("YOUR"):   # a leftover ".env.example" placeholder must never become the real password
        return env
    if not ADMIN_FILE.exists():
        ADMIN_FILE.write_text(secrets.token_urlsafe(9))
    return ADMIN_FILE.read_text().strip()


@app.get("/admin")
def admin():
    """Where the owner reads customer messages. Browser asks for a login: any username, password as printed at startup."""
    if rate_limited("admin-fail", 8, per=300, record=False):  # locked out BEFORE comparing, so guesses can't be probed while locked
        return Response("Too many failed logins. Try again in a few minutes.", 429, {"Retry-After": "300"})
    auth = request.authorization
    if not auth or not hmac.compare_digest((auth.password or "").encode(), admin_password().encode()):
        if auth:  # a bare visit (no credentials yet) isn't a failed guess
            rate_limited("admin-fail", 8, per=300)
        return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="Paul Optical admin"'})
    with Session() as db:
        msgs = db.query(Message).order_by(Message.id.desc()).all()
    rows = "".join(
        f"<tr><td>{m.created:%Y-%m-%d %H:%M} UTC</td><td>{escape(m.name)}</td>"
        f"<td><a href='tel:{escape(m.phone)}'>{escape(m.phone)}</a></td><td class=m>{escape(m.message)}</td></tr>" for m in msgs
    ) or "<tr><td colspan=4>No messages yet.</td></tr>"
    page = f"""<!doctype html><meta charset=utf-8><title>Customer messages</title><meta name=viewport content="width=device-width">
<style>body{{font:15px system-ui;margin:2rem;background:#f6f2ea;color:#14233b}}table{{border-collapse:collapse;width:100%;background:#fff}}
td,th{{border:1px solid #d8d2c4;padding:.55rem .75rem;text-align:left;vertical-align:top}}th{{background:#12294d;color:#fff}}td.m{{white-space:pre-wrap;max-width:36rem}}</style>
<h1>Customer messages ({len(msgs)})</h1><table><tr><th>Received<th>Name<th>Phone<th>Message</tr>{rows}</table>"""
    return Response(page, mimetype="text/html", headers={"Cache-Control": "no-store"})


def _csp():
    """Content-Security-Policy: only our own files may run. The one inline script (the import map) is allowed by its hash,
    computed from index.html at startup so editing it can't silently break the policy. 'wasm-unsafe-eval' lets the
    face-detection WebAssembly compile (it does NOT allow JavaScript eval)."""
    html = (Path(app.static_folder) / "index.html").read_text(encoding="utf-8")
    m = re.search(r'<script type="importmap">(.*?)</script>', html, re.S)
    h = base64.b64encode(hashlib.sha256(m.group(1).encode()).digest()).decode()
    return ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval' 'sha256-%s'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'" % h)


CSP = _csp()


@app.after_request
def security_headers(resp):
    h = resp.headers
    h.setdefault("Content-Security-Policy", CSP)
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")                   # no clickjacking via iframes
    h.setdefault("Referrer-Policy", "same-origin")
    h.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=(), payment=()")
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp


@app.errorhandler(400)
def bad_request(e):
    return jsonify(error=e.description), 400


@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(413)
def api_errors(e):
    """The API always answers in JSON (the front end reads `error`); other URLs keep the normal error page."""
    if request.path.startswith("/api/"):
        msg = {404: "Not found.", 405: "That method isn't allowed here.", 413: "That request is too large."}[e.code]
        return jsonify(error=msg), e.code
    return e


init_db()

if __name__ == "__main__":
    print("Paul Optical running at http://127.0.0.1:5000")
    print("Customer messages: http://127.0.0.1:5000/admin   (username: anything, password: see admin_password.txt or $ADMIN_PASSWORD)")
    if len(admin_password()) < 12:
        print("WARNING: the admin password is shorter than 12 characters - choose a longer one.")
    app.run(host="127.0.0.1", port=5000)

