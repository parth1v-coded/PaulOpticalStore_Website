"""Optional browser checks for the interactions unit tests can't see (needs the server running and Playwright):

    pip install playwright
    python app.py                       # in one terminal
    python tests/browser_checks.py      # in another   (add a URL as an argument to test somewhere else)

Each check is a bug that was found and fixed once; this keeps it fixed. Uses your installed Edge/Chrome, else Playwright's Chromium.
"""
import sys

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000").rstrip("/")
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"   ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def launch(p):
    for channel in ("msedge", "chrome", None):
        try:
            return p.chromium.launch(channel=channel, headless=True, args=ARGS) if channel else p.chromium.launch(headless=True, args=ARGS)
        except Exception:
            continue
    raise SystemExit("No Chromium-based browser found. Run: playwright install chromium")


with sync_playwright() as p:
    b = launch(p)
    pg = b.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/product/2", wait_until="networkidle"); pg.wait_for_timeout(1200)

    # one Escape closes only the top layer (cart), not the product screen under it
    pg.locator(".pdp-actions .btn-navy").click(); pg.locator(".pdp-toast button").click(); pg.wait_for_timeout(300)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    check("Escape closes only the cart", pg.evaluate("document.querySelector('#cart').hidden && !document.querySelector('#pdp').hidden"))

    # the rating button must not touch the URL or the history entry
    pg.locator(".pdp-rating").click(); pg.wait_for_timeout(400)
    check("rating tap leaves the URL alone (no #fragment)", pg.evaluate("location.hash === '' && location.pathname === '/product/2'"), pg.evaluate("location.href"))

    # keyboard focus stays inside the open screen
    pg.locator(".pdp-back").focus()
    for _ in range(60):
        pg.keyboard.press("Tab")
    check("Tab never leaves the product screen", pg.evaluate("!!document.activeElement.closest('#pdp, #cart, #live')"))

    # cart never exceeds stock
    pg.goto(BASE + "/product/3", wait_until="networkidle"); pg.wait_for_timeout(800); pg.evaluate("localStorage.clear()")
    stock = int(pg.evaluate("document.querySelector('.pdp-stock').textContent.match(/\\d+/)?.[0] || 10"))
    for _ in range(4):
        while not pg.locator("#qtyPlus").is_disabled():
            pg.locator("#qtyPlus").click()
        pg.locator(".pdp-actions .btn-navy").click(); pg.wait_for_timeout(120)
    qty = pg.evaluate("JSON.parse(localStorage.getItem('po_cart_v1')).reduce((n, i) => n + i.qty, 0)")
    check("cart quantity capped at stock", qty == min(10, stock), f"{qty} in cart, stock {stock}")
    pg.evaluate("localStorage.clear()")

    # review posting updates the headline rating (cleaned up afterwards by reloading only; this adds one review)
    # (skipped here so the check never writes to your data; the API tests cover posting)

    # hero 3D canvas is as wide as intended and not squashed
    pg.goto(BASE + "/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    ratio = pg.evaluate("document.querySelector('#heroCanvas').getBoundingClientRect().width / document.querySelector('.hero-stage').getBoundingClientRect().width")
    check("hero canvas is 130% of its column", abs(ratio - 1.3) < 0.02, f"ratio {ratio:.2f}")

    # phone: filter sheet 'Show results' is tappable (not hidden under the chat button) and nothing overflows sideways
    m = b.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    m.goto(BASE + "/", wait_until="networkidle"); m.wait_for_timeout(1500)
    check("no sideways overflow on a phone", m.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"))
    m.evaluate("document.querySelector('#shop').scrollIntoView()"); m.wait_for_timeout(800)
    m.click("#filtersToggle"); m.wait_for_timeout(600)
    try:
        m.click(".filters-done", timeout=4000)
        check("filter sheet 'Show results' is tappable", m.evaluate("!document.querySelector('#filters').classList.contains('open')"))
    except Exception as e:
        check("filter sheet 'Show results' is tappable", False, str(e)[:80])

    check("no JavaScript errors", not errors, "; ".join(errors)[:200])
    b.close()

print("\nAll checks passed." if not failures else f"\n{len(failures)} check(s) FAILED: {failures}")
sys.exit(1 if failures else 0)
