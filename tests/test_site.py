"""Checks that the shop is complete and that every image is real, loads, and is used exactly once.

Run from the project folder:   python -m unittest discover -s tests -v
"""
import hashlib
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app as shop  # noqa: E402  (creates + seeds the SQLite DB on first import)
from models import CATEGORIES  # noqa: E402

client = shop.app.test_client()
STATIC = ROOT / "static"


def all_products():
    return client.get("/api/products").json


def image_references():
    """Every image path the site uses: products (API) + <img src> in index.html + paths hard-coded in main.js."""
    refs = [p["image"] for p in all_products()]
    refs += re.findall(r'<img[^>]+src="(/static/img/[^"]+)"', (STATIC / "index.html").read_text(encoding="utf-8"))
    refs += re.findall(r"'(/static/img/[^']+)'", (STATIC / "js" / "main.js").read_text(encoding="utf-8"))
    return [r for r in refs if r.endswith((".jpg", ".png"))]  # (main.js also names credits.json - not an image)


class Catalogue(unittest.TestCase):
    def test_all_four_categories_seeded(self):
        counts = {c["key"]: c["count"] for c in client.get("/api/categories").json}
        self.assertEqual(set(counts), {"frames", "lenses", "accessories", "sprays"})
        self.assertTrue(all(n >= 5 for n in counts.values()), counts)

    def test_every_product_has_its_category_attributes(self):
        for p in all_products():
            expected = {c.name for c in CATEGORIES[p["category"]]["model"].__table__.columns if c.name != "id"}
            self.assertEqual(set(p["specs"]), expected, p["name"])
            self.assertTrue(all(v is not None and v != "" for v in p["specs"].values()), p["name"])

    def test_every_facet_filters(self):
        for cat, meta in CATEGORIES.items():
            data = client.get(f"/api/facets?category={cat}").json
            self.assertEqual([f["key"] for f in data["facets"]], list(meta["facets"]))
            for f in data["facets"]:
                for o in f["options"]:
                    got = client.get(f"/api/products?category={cat}&{f['key']}={o['value']}").json
                    self.assertEqual(len(got), o["count"], (cat, f["key"], o["value"]))

    def test_combined_filters_and_search(self):
        self.assertEqual([p["name"] for p in client.get("/api/products?category=frames&shape=Round&material=Metal").json], ["Halo Wire Round"])
        self.assertTrue(client.get("/api/products?q=aviator").json)
        self.assertEqual(client.get("/api/products?category=nope").status_code, 400)

    def test_every_frame_has_a_valid_tryon_overlay(self):
        frames = client.get("/api/products?category=frames").json
        self.assertTrue(frames)
        for f in frames:
            r = client.get(f["tryon"]["overlay"])
            self.assertEqual((r.status_code, r.mimetype), (200, "image/svg+xml"))
            ET.fromstring(r.data)  # well-formed XML
            self.assertGreater(f["tryon"]["width_mm"], f["specs"]["lens_width"] * 2)


class CustomerMessages(unittest.TestCase):
    def setUp(self):
        from models import Message, Session
        self.Message, self.Session = Message, Session

    def tearDown(self):  # leave the real database exactly as we found it
        with self.Session() as db:
            db.query(self.Message).filter(self.Message.name == "ZZ Test Customer").delete()
            db.commit()

    def test_message_is_saved_and_shown_to_the_owner_only(self):
        r = client.post("/api/messages", json={"name": "ZZ Test Customer", "phone": "+1 (555) 010-2468", "message": "Do you stock <b>round</b> frames?"})
        self.assertEqual(r.status_code, 201)
        with self.Session() as db:
            row = db.query(self.Message).filter_by(name="ZZ Test Customer").one()
            self.assertEqual((row.phone, row.message), ("+1 (555) 010-2468", "Do you stock <b>round</b> frames?"))
        self.assertEqual(client.get("/admin").status_code, 401)  # no login -> refused
        import base64
        token = base64.b64encode(f"x:{shop.admin_password()}".encode()).decode()
        page = client.get("/admin", headers={"Authorization": f"Basic {token}"})
        self.assertEqual(page.status_code, 200)
        self.assertIn("ZZ Test Customer", page.text)
        self.assertNotIn("<b>round</b>", page.text)  # HTML in a message is escaped, never rendered
        self.assertEqual(client.get("/admin", headers={"Authorization": "Basic " + base64.b64encode(b"x:wrong").decode()}).status_code, 401)

    def test_bad_input_is_rejected(self):
        for bad in ({"name": "", "phone": "5550102", "message": "hi"}, {"name": "A", "phone": "abc", "message": "hi"},
                    {"name": "A", "phone": "5550102", "message": "  "}):
            self.assertEqual(client.post("/api/messages", json=bad).status_code, 400, bad)


class Databases(unittest.TestCase):
    """Runs the app against throw-away database files (via PAUL_OPTICAL_DB), never your real one."""

    @staticmethod
    def boot(db_path):
        import os, subprocess
        subprocess.run([sys.executable, "-W", "ignore", "-c", "import app"], cwd=ROOT, check=True, capture_output=True,
                       env={**os.environ, "PAUL_OPTICAL_DB": str(db_path), "GEMINI_API_KEY": ""})

    @staticmethod
    def counts(db_path):
        import sqlite3
        c = sqlite3.connect(db_path)
        n = {t: c.execute(f"select count(*) from {t}").fetchone()[0] for t in ("products", "colour_options", "reviews", "messages")}
        n["discounted"] = c.execute("select count(*) from products where original_price is not null").fetchone()[0]
        c.close()
        return n

    def test_first_run_creates_and_seeds_everything(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "fresh.db"
            self.boot(path)
            n = self.counts(path)
            self.assertEqual((n["products"], n["colour_options"]), (27, 18))
            self.assertGreater(n["reviews"], 50)
            self.assertGreater(n["discounted"], 3)
            self.boot(path)                                    # starting again must not seed twice
            self.assertEqual(self.counts(path), n)

    def test_database_from_before_the_detail_page_is_upgraded_in_place(self):
        import sqlite3, tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "old.db"
            self.boot(path)
            c = sqlite3.connect(path)                          # rewind it to the old schema: undiscounted prices, no extras, plus a customer message
            c.execute("update products set price = original_price where original_price is not null")
            c.execute("alter table products drop column original_price")
            c.execute("drop table colour_options"); c.execute("drop table reviews")
            c.execute("insert into messages(name, phone, message, created) values ('Keep Me', '5550100', 'hello', '2026-01-01')")
            c.commit(); c.close()
            self.boot(path)
            n = self.counts(path)
            self.assertEqual((n["products"], n["colour_options"], n["messages"]), (27, 18, 1))   # nothing lost, extras added
            self.assertGreater(n["reviews"], 50)
            self.assertGreater(n["discounted"], 3)


class Regressions(unittest.TestCase):
    def test_api_errors_are_json_but_pages_keep_the_normal_error(self):
        r = client.get("/api/nope")
        self.assertEqual((r.status_code, r.mimetype, bool(r.json["error"])), (404, "application/json", True))
        self.assertEqual(client.delete("/api/products").json["error"], "That method isn't allowed here.")
        self.assertNotEqual(client.get("/nope").mimetype, "application/json")

    def test_an_order_with_many_items_is_not_truncated(self):
        from models import Message, Session
        big = "ORDER REQUEST\n" + "\n".join(f"- 1 x Rose Tortoise Cat-Eye (Pink Tortoise, 51 mm lens, Blue-light filter) @ ₹16,498 #{i}" for i in range(20))
        self.assertTrue(1000 < len(big) <= 2000)
        try:
            self.assertEqual(client.post("/api/messages", json={"name": "ZZ Order", "phone": "5550100", "message": big}, environ_overrides={"REMOTE_ADDR": "203.0.113.88"}).status_code, 201)
            with Session() as db:
                self.assertEqual(db.query(Message).filter_by(name="ZZ Order").one().message, big)
            self.assertEqual(client.post("/api/messages", json={"name": "ZZ Order", "phone": "5550100", "message": "x" * 2001}, environ_overrides={"REMOTE_ADDR": "203.0.113.88"}).status_code, 400)
        finally:
            with Session() as db:
                db.query(Message).filter(Message.name == "ZZ Order").delete(); db.commit()

    def test_front_end_guards_against_the_bugs_found_in_review(self):
        js = lambda n: (STATIC / "js" / n).read_text(encoding="utf-8")
        self.assertIn("stopImmediatePropagation", js("cart.js"))            # Esc closes only the top layer
        self.assertIn("inert", js("api.js"))                                # focus can't leave the open screen
        self.assertIn("defaultPrevented", js("fx.js"))                      # in-page link handler leaves history alone
        self.assertIn("file.value = ''", js("live.js")); self.assertIn("file.value = ''", js("tryon.js"))   # same photo twice
        self.assertIn("my !== session", js("live.js"))                      # closing during the permission prompt leaves no camera running
        self.assertIn("stock", js("cart.js"))                               # cart respects stock
        self.assertIn("max-width: none", (STATIC / "css" / "style.css").read_text(encoding="utf-8"))   # hero canvas isn't squashed
        css = (STATIC / "css" / "style.css").read_text(encoding="utf-8")
        z = lambda pat: int(re.search(pat, css).group(1))
        self.assertGreater(z(r"\.filters \{ position: fixed; z-index: (\d+)"), z(r"\.chat-open \{[^}]*z-index: (\d+)") if ".chat-open" in css else 0,
                           "the mobile filter sheet must sit above the floating chat button")


class ProductDetail(unittest.TestCase):
    def test_detail_screen_data(self):
        for p in all_products():
            d = client.get(f"/api/products/{p['id']}").json
            self.assertTrue(d["features"], p["name"])                       # section 4
            self.assertEqual(set(d["rating"]), {"count", "average", "histogram"})  # section 2
            if d["original_price"]:                                         # discounted: original must be higher, % consistent
                self.assertGreater(d["original_price"], d["price"])
                self.assertEqual(d["discount_pct"], round((1 - d["price"] / d["original_price"]) * 100))
            else:
                self.assertEqual(d["discount_pct"], 0)
            if p["category"] == "frames":                                   # section 3 variants + section 5 try-on data
                o = d["options"]
                self.assertGreaterEqual(len(o["colours"]), 3)
                self.assertEqual([w["lens_width"] for w in o["widths"]], [p["specs"]["lens_width"] + k for k in (-2, 0, 2)])
                self.assertTrue(any(l["price_delta"] for l in o["lenses"]))
            else:
                self.assertNotIn("options", d)
        self.assertTrue(any(p["discount_pct"] for p in all_products()), "at least one discounted product")
        self.assertEqual(client.get("/api/products/9999").status_code, 404)
        self.assertEqual(client.get("/product/3").status_code, 200)         # shareable page link

    def test_gallery_drawings_follow_the_chosen_variant(self):
        import xml.etree.ElementTree as ET
        front = client.get("/api/frames/3/overlay.svg?color=ff0000&lw=50&tint=Gray").data
        self.assertIn(b"#ff0000", front)
        a, b = (client.get(f"/api/frames/3/overlay.svg?lw={w}").data for w in (46, 50))
        self.assertNotEqual(ET.fromstring(a).get("viewBox"), ET.fromstring(b).get("viewBox"))   # wider lens -> wider drawing
        for view in ("side", "dims", "front"):
            ET.fromstring(client.get(f"/api/frames/3/overlay.svg?view={view}&color=1f6f78").data)
        self.assertIn(b"lens 46", client.get("/api/frames/3/overlay.svg?view=dims").data)
        for bad in ("color=zzz", "lw=5", "lw=500", "tint=Pink", "view=top"):
            self.assertEqual(client.get(f"/api/frames/3/overlay.svg?{bad}").status_code, 400, bad)

    def test_reviews_sort_filter_paginate_and_empty_state(self):
        first = client.get("/api/products/3/reviews?limit=5").json
        self.assertGreater(first["total"], 5)                                  # long enough to need "Load more"
        dates = [r["date"] for r in first["items"]]
        self.assertEqual(dates, sorted(dates, reverse=True))                   # most recent first
        high = client.get("/api/products/3/reviews?sort=highest&limit=20").json["items"]
        self.assertEqual([r["rating"] for r in high], sorted((r["rating"] for r in high), reverse=True))
        low = client.get("/api/products/3/reviews?sort=lowest&limit=20").json["items"]
        self.assertEqual([r["rating"] for r in low], sorted(r["rating"] for r in low))
        four = client.get("/api/products/3/reviews?stars=4&limit=20").json
        self.assertTrue(four["items"] and {r["rating"] for r in four["items"]} == {4})
        page1 = client.get("/api/products/3/reviews?limit=5&offset=0").json["items"]
        page2 = client.get("/api/products/3/reviews?limit=5&offset=5").json["items"]
        self.assertFalse({r["id"] for r in page1} & {r["id"] for r in page2})  # pages never overlap
        empty = client.get("/api/products/5/reviews").json                     # seeded with no reviews on purpose
        self.assertEqual((empty["total"], empty["items"], empty["summary"]["count"]), (0, [], 0))
        for bad in ("sort=newest", "stars=9"):
            self.assertEqual(client.get(f"/api/products/3/reviews?{bad}").status_code, 400, bad)
        self.assertEqual(client.get("/api/products/9999/reviews").status_code, 404)

    def test_posting_a_review(self):
        from models import Review, Session
        ip = {"REMOTE_ADDR": "203.0.113.77"}
        try:
            before = client.get("/api/products/12/reviews").json["summary"]["count"]
            ok = client.post("/api/products/12/reviews", json={"author": "ZZ Reviewer", "rating": 5, "text": "<b>Great</b> lenses, thank you!"}, environ_overrides=ip)
            self.assertEqual(ok.status_code, 201)
            got = client.get("/api/products/12/reviews").json
            self.assertEqual(got["summary"]["count"], before + 1)
            self.assertEqual(got["items"][0]["author"], "ZZ Reviewer")         # newest first
            self.assertFalse(got["items"][0]["sample"])                        # real reviews are not labelled "Sample"
            for bad in ({"author": "", "rating": 5, "text": "fine text"}, {"author": "A", "rating": 6, "text": "fine text"},
                        {"author": "A", "rating": "5", "text": "fine text"}, {"author": "A", "rating": 5, "text": "no"}):
                self.assertEqual(client.post("/api/products/12/reviews", json=bad, environ_overrides=ip).status_code, 400, bad)
        finally:
            with Session() as db:
                db.query(Review).filter(Review.author == "ZZ Reviewer").delete(); db.commit()

    def test_page_scripts_are_wired(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        for needle in ('id="pdp"', 'id="live"', 'id="cart"', 'id="cartBtn"', "pdp.css"):
            self.assertIn(needle, html)
        pdp = (STATIC / "js" / "pdp.js").read_text(encoding="utf-8")
        order = [pdp.index(f) for f in ("gallerySection()", "infoSection()", "buySection()", "featuresSection()", "tryonSection()", "reviewsSection()")]
        self.assertEqual(order[:], sorted(order[:]), "detail sections must stay in the specified order")


class Chatbot(unittest.TestCase):
    """No network: Google's API is mocked, so these run without a key."""

    def test_document_is_injected_into_system_prompt_and_question(self):
        import io, json
        from unittest import mock
        import chatbot
        sent = {}

        def fake_urlopen(req, timeout):
            sent["body"] = json.loads(req.data)
            return io.BytesIO(json.dumps({"candidates": [{"content": {"parts": [{"text": "It is $159."}]}}]}).encode())

        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "test"}), mock.patch.object(chatbot.urllib.request, "urlopen", fake_urlopen):
            r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Price of the Skyline Aviator?"}]})
        self.assertEqual(r.json, {"reply": "It is $159."})
        self.assertIn("Skyline Aviator", sent["body"]["systemInstruction"]["parts"][0]["text"])       # document in the system prompt
        self.assertIn("Skyline Aviator", sent["body"]["contents"][-1]["parts"][0]["text"])           # ...and around the question
        self.assertIn(chatbot.OUT_OF_SCOPE, sent["body"]["systemInstruction"]["parts"][0]["text"])   # refusal sentence is defined

    def test_pricing_doc_covers_every_product(self):
        import chatbot
        for p in all_products():
            self.assertIn(p["sku"], chatbot.PRICING_DOC, p["name"])
            self.assertIn(f"₹{p['price']:,.0f}.", chatbot.PRICING_DOC, p["name"])

    def test_rate_limit(self):
        ip = {"REMOTE_ADDR": "203.0.113.9"}  # a made-up client, so other tests are unaffected
        codes = [client.post("/api/chat", json={"messages": "x"}, environ_overrides=ip).status_code for _ in range(22)]
        self.assertEqual(codes[:20], [400] * 20)
        self.assertEqual(codes[20:], [429, 429])
        codes = [client.post("/api/messages", json={}, environ_overrides=ip).status_code for _ in range(12)]
        self.assertEqual(codes[10:], [429, 429])

    def test_clear_errors(self):
        from unittest import mock
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
            r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(r.status_code, 503)
        self.assertIn("GEMINI_API_KEY", r.json["error"])
        self.assertEqual(client.post("/api/chat", json={"messages": "nope"}).status_code, 400)
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "test"}):
            self.assertEqual(client.post("/api/chat", json={"messages": [{"role": "assistant", "content": "x"}]}).status_code, 400)


class Hardening(unittest.TestCase):
    def test_security_headers(self):
        h = client.get("/").headers
        csp = h["Content-Security-Policy"]
        for part in ("default-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "'sha256-"):
            self.assertIn(part, csp)
        self.assertNotIn("'unsafe-eval'", csp)
        self.assertNotIn("http", csp.replace("http-", ""))  # nothing loads from other origins
        self.assertEqual((h["X-Frame-Options"], h["X-Content-Type-Options"]), ("DENY", "nosniff"))
        self.assertIn("camera=(self)", h["Permissions-Policy"])  # only this site may use the camera (live try-on)
        self.assertNotIn("Strict-Transport-Security", h)  # only sent over HTTPS
        self.assertIn("max-age", client.get("/", headers={"X-Forwarded-Proto": "https"}).headers["Strict-Transport-Security"])

    def test_private_files_are_not_served(self):
        for path in ("/.env", "/admin_password.txt", "/paul_optical.db", "/app.py", "/chatbot.py", "/pricing.md", "/static/../app.py", "/static/%2e%2e/.env"):
            self.assertEqual(client.get(path).status_code, 404, path)

    def test_admin_locks_out_password_guessing(self):
        import base64
        ip = {"REMOTE_ADDR": "203.0.113.50"}
        bad = {"Authorization": "Basic " + base64.b64encode(b"x:guess").decode()}
        codes = [client.get("/admin", headers=bad, environ_overrides=ip).status_code for _ in range(10)]
        self.assertEqual(codes, [401] * 8 + [429, 429])
        good = {"Authorization": "Basic " + base64.b64encode(f"x:{shop.admin_password()}".encode()).decode()}
        self.assertEqual(client.get("/admin", headers=good, environ_overrides=ip).status_code, 429)  # even the right password waits
        self.assertEqual(client.get("/admin", headers=good).status_code, 200)                       # other clients are unaffected

    def test_oversized_body_is_refused(self):
        self.assertEqual(client.post("/api/messages", data="x" * 70_000, content_type="application/json").status_code, 413)

    def test_sql_injection_is_inert(self):
        for q in ("' OR 1=1--", "'; DROP TABLE products;--"):
            self.assertEqual(client.get("/api/products", query_string={"q": q}).json, [])
        self.assertEqual(len(all_products()), 27)


class Images(unittest.TestCase):
    def test_every_referenced_image_loads(self):
        for ref in set(image_references()):
            r = client.get(ref)
            self.assertEqual(r.status_code, 200, ref)
            self.assertTrue(r.mimetype.startswith("image/"), ref)
            self.assertTrue(r.data[:3] == b"\xff\xd8\xff" or r.data[:4] == b"\x89PNG", f"not a real JPEG/PNG: {ref}")
            self.assertGreater(len(r.data), 5_000, f"suspiciously small (blank/placeholder?): {ref}")
            r.close()

    def test_no_image_is_used_twice(self):
        refs = image_references()
        dupes = {r for r in refs if refs.count(r) > 1}
        self.assertFalse(dupes, f"image referenced more than once: {dupes}")

    def test_no_two_files_are_identical_and_none_are_orphans(self):
        files = [p for p in (STATIC / "img").rglob("*") if p.suffix in (".jpg", ".png")]
        by_hash = {}
        for f in files:
            by_hash.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), []).append(f.name)
        self.assertFalse([v for v in by_hash.values() if len(v) > 1], "byte-identical image files")
        used = {"/static/" + f.relative_to(STATIC).as_posix() for f in files}
        self.assertEqual(used - set(image_references()), set(), "image files that nothing uses")

    def test_every_image_is_credited(self):
        import json
        credits = json.loads((STATIC / "img" / "credits.json").read_text(encoding="utf-8"))
        for ref in set(image_references()):
            if "logo.png" not in ref:
                self.assertIn(ref.replace("/static/", ""), credits, ref)

    def test_front_end_assets_exist(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        for path in re.findall(r'(?:src|href)="(/static/[^"]+)"', html):
            with client.get(path) as r:
                self.assertEqual(r.status_code, 200, path)


if __name__ == "__main__":
    unittest.main()
