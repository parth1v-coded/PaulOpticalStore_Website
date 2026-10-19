# Paul Optical Store: online store with a virtual try-on

A complete website for an optical (eyewear) shop: customers browse frames, lenses, accessories and lens-care sprays, **try glasses on their own face through the camera**, add items to a cart, and send the shop their order or a question. The shop owner reads everything in a private inbox page.

![Home page](docs/1-hero.png)

> **Portfolio project:** this is a demo store. Brands, prices, stock and reviews are sample data, and no payments are taken.

---

## What it does (in plain English)

- **Shop by category.** Four collections (frames, lenses, accessories, cleaning sprays), each with filters that make sense for that category: shape and material for frames, lens index and coating for lenses, and so on.
- **Try glasses on virtually.** Open any frame, tap *Try On*, and the glasses appear on your face through your camera, following your head as you move. Switch frames and colours live and save a snapshot. Prefer not to use the camera? Upload a photo instead. Nothing is recorded or uploaded.
- **Full product pages.** Photo gallery you can swipe, price and discounts, colour / lens-width / lens-type choices, key features, and customer reviews you can sort, filter and add to.
- **Cart and order requests.** Customers add items and send an order request. It lands in the owner's private inbox and the shop calls to confirm.
- **Contact form.** Messages go to the same private inbox (password-protected `/admin` page).
- **Price assistant.** A chat helper that answers questions about prices, and *only* from the shop's own price list. It politely declines everything else.
- **Works on phones.** Designed phone-first, with smooth 3D and scroll animations that respect people's reduced-motion settings.

| Shop with filters | Product page | Live try-on |
|---|---|---|
| ![Shop](docs/3-shop-filters.png) | ![Product page](docs/8-product-detail-mobile.png) | ![Try-on](docs/10-live-tryon-permission.png) |

## Tech stack

| Part | Technology |
|---|---|
| Back end | Python, **Flask** |
| Database | **SQLite** through **SQLAlchemy** (created automatically, nothing to install or configure) |
| Front end | Plain HTML, CSS and JavaScript (no build step), **GSAP** for animation, **three.js** for the 3D hero |
| Face tracking | **MediaPipe** Face Landmarker, running in the visitor's browser |
| AI price assistant | Google **Gemini** API (optional) |
| Quality | 31 automated tests, plus browser checks; security headers, rate limiting, dependency audit |

## Quick start

You need **Python 3.10 or newer** ([python.org](https://www.python.org/downloads/)). No other software is required.

```bash
# 1. get the code
git clone https://github.com/YOUR-USERNAME/Optical-Store-Website.git
cd Optical-Store-Website

# 2. (recommended) create a private Python environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3. install the three dependencies
pip install -r requirements.txt

# 4. run it
python app.py
```

Open **http://127.0.0.1:5000** in your browser. The first start creates the database and fills it with sample products automatically.

**Optional settings.** Copy `.env.example` to a new file called `.env` and fill in:

- `GEMINI_API_KEY`: only needed for the price-assistant chat. Free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Everything else works without it.
- `ADMIN_PASSWORD`: password for the owner's inbox at `/admin` (any username). If you skip it, a strong random password is generated and saved in `admin_password.txt`.

The `.env` file is ignored by Git so your keys are never uploaded.

**Run the tests:** `python -m unittest discover -s tests -v`

## Project layout

```
app.py            the web server and API
models.py         database tables
seed.py           the sample products, reviews and discounts
frames_svg.py     draws each pair of glasses (used by the try-on and the gallery)
chatbot.py        the price assistant
pricing.md        the price list the assistant is allowed to use
static/           the website: index.html, css/, js/, images, bundled libraries
tests/            automated tests
tools/            helper scripts used to source the photos
docs/             screenshots and developer notes (docs/TECHNICAL.md)
```

More detail on how the try-on, cart, security and deployment work is in [docs/TECHNICAL.md](docs/TECHNICAL.md). All photos are from Wikimedia Commons under open licences; credits are in [CREDITS.md](CREDITS.md).

## Licence

The code is **All Rights Reserved** (see [LICENSE](LICENSE)): you're welcome to view it and learn from it, but please don't copy, modify or reuse it without my written permission. The photos, the Paul Optical logo and the bundled libraries have their own terms, explained in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [CREDITS.md](CREDITS.md).

## About this project

This is my **first official project**, and I built it as a beginner, working with AI coding assistance to go further than I could alone. I'm sharing it as a portfolio piece to show what I can deliver for optical stores and similar small shops: a clear online catalogue, a standout try-on feature, and a simple way to receive customer enquiries.

I want to be upfront about what it is and isn't. It's a **demo store**: the products and reviews are sample content, there's no payment system, and the virtual try-on is a flat 2D overlay (it works best with a front-facing photo or camera view). What it does show is a working, tested, secure foundation that could be adapted to a real shop's products, branding and checkout.

**Interested in a website like this for your store?** Get in touch through my GitHub profile.
