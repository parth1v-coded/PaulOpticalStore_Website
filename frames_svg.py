"""Generates the transparent front-view SVG used by the virtual try-on, straight from a Frame row.

Geometry is in real millimetres: the viewBox is centred on the point *between the wearer's pupils*
and each lens centre sits at +/-(lens_width + bridge)/2 - roughly one pupil per lens. The viewBox is in real
millimetres, so the front end scales it from the wearer's pupil distance (average adult = 63 mm) and the
Small / Large frame variants really do come out different sizes on the same face.
"""
from html import escape

# (height as a fraction of lens width, how far the lens centre sits below the pupil, as a fraction of height)
SHAPES = {"Round": (1.0, 0.04), "Oval": (0.78, 0.04), "Rectangle": (0.64, 0.05), "Square": (0.86, 0.05),
          "Aviator": (0.95, 0.12), "Cat-Eye": (0.74, 0.10), "Geometric": (0.86, 0.04)}
# rim thickness in mm per material (acetate/TR90 are chunky, metal/titanium are wire-thin)
RIM = {"Acetate": 3.4, "TR90": 2.6, "Metal": 1.0, "Titanium": 0.8}
TINT = {"Clear": ("#cfe6f2", 0.16), "Gray": ("#2b2f36", 0.78), "Brown": ("#5a3a22", 0.72), "Blue": ("#1d3f7a", 0.70),
        "Blue-Light": ("#8fc0ff", 0.24)}  # clear-looking lens with a faint blue reflection (the blue-light filter option)


def _shade(hex_color, k):
    """Lighten (k>1) / darken (k<1) a #rrggbb colour."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * k))) for c in (r, g, b))


def _lens_path(shape, w, h):
    """Right-lens outline centred on (0,0); the left lens is this mirrored (outer corner = +x)."""
    a, b = w / 2, h / 2
    if shape == "Round" or shape == "Oval":
        return f"M{-a},0 A{a},{b} 0 1 0 {a},0 A{a},{b} 0 1 0 {-a},0Z"
    if shape in ("Rectangle", "Square"):
        r = b * (0.35 if shape == "Rectangle" else 0.45)
        return (f"M{-a + r},{-b} H{a - r} Q{a},{-b} {a},{-b + r} V{b - r} Q{a},{b} {a - r},{b} "
                f"H{-a + r} Q{-a},{b} {-a},{b - r} V{-b + r} Q{-a},{-b} {-a + r},{-b}Z")
    if shape == "Aviator":  # teardrop: broad, squarish top shoulders tapering to a rounded bottom
        return (f"M0,{-b} C{.75 * a},{-b} {a},{-.85 * b} {a},{-.4 * b} C{a},{.2 * b} {.55 * a},{b} {-.05 * a},{b} "
                f"C{-.65 * a},{b} {-a},{.45 * b} {-a},{-.05 * b} C{-a},{-.65 * b} {-.7 * a},{-b} 0,{-b}Z")
    if shape == "Cat-Eye":  # outer top corner swept up and out, bottom softly rounded
        return (f"M{-a},{.05 * b} C{-a},{-.5 * b} {-.5 * a},{-.62 * b} {.05 * a},{-.78 * b} "
                f"C{.5 * a},{-.9 * b} {.95 * a},{-1.02 * b} {1.05 * a},{-b} C{a},{-.4 * b} {.85 * a},{.55 * b} {.15 * a},{.95 * b} "
                f"C{-.45 * a},{1.1 * b} {-a},{.65 * b} {-a},{.05 * b}Z")
    # Geometric: hexagon
    return (f"M{-a},0 L{-.5 * a},{-b} H{.5 * a} L{a},0 L{.5 * a},{b} H{-.5 * a}Z")


ARM = 18  # visible length of the temple arms past the lens edge in the front view, mm


def frame_width_mm(lens_width, bridge):
    """Width of the front-view SVG in mm (what the try-on scales from the wearer's pupil distance)."""
    return round(2 * lens_width + bridge + 2 * ARM, 2)


def overlay_svg(f, color=None, lens_width=None, tint=None, annotate=False):
    """f is a Frame row. Returns (svg_text, width_mm): the SVG is drawn 1 unit = 1 mm, so the browser can scale it from the wearer's pupil distance.
    Optional overrides draw a variant of the same frame: `color` (#rrggbb), `lens_width` (mm), `tint` (a TINT key).
    annotate=True adds measurement lines (the 'dimensions' gallery slide)."""
    lw, br = float(lens_width or f.lens_width), float(f.bridge)
    hr, drop = SHAPES[f.shape]
    h = lw * hr
    dy = h * drop                               # lens centre below the pupil line
    pd = lw + br                                # pupil-to-pupil distance of the frame, mm
    arm = ARM
    half_w = pd / 2 + lw / 2 + arm
    half_h = h / 2 + dy + 6
    W, H = half_w * 2, half_h * 2
    t = RIM[f.material]
    base = color or f.color_hex
    tint, tint_op = TINT[tint or f.lens_tint]
    path = _lens_path(f.shape, lw, h)
    pos, neg = pd / 2, -pd / 2

    lens = lambda cx, flip: (  # noqa: E731
        f'<g transform="translate({cx},{dy}) scale({flip},1)">'
        f'<path d="{path}" fill="{tint}" fill-opacity="{tint_op}"/>'
        f'<path d="{path}" fill="url(#sheen)"/>'
        + (f'<path d="{path}" fill="none" stroke="url(#frame)" stroke-width="{t}" stroke-linejoin="round"/>'
           if f.rim_type == "Full" else
           f'<path d="{path}" fill="none" stroke="url(#frame)" stroke-width="{t}" stroke-linejoin="round" '
           f'clip-path="url(#top)"/><path d="{path}" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width=".35"/>'
           if f.rim_type == "Half" else
           f'<path d="{path}" fill="none" stroke="#fff" stroke-opacity=".7" stroke-width=".5"/>')
        + "</g>")

    top_y = dy - h / 2 + h * 0.2                # where bridge + temples attach
    bridge = (f'<path d="M{neg + lw / 2 - t / 2},{top_y} Q0,{top_y - h * 0.16} {pos - lw / 2 + t / 2},{top_y}" '
              f'fill="none" stroke="url(#frame)" stroke-width="{max(t, 1.4)}" stroke-linecap="round"/>')
    temples = "".join(
        f'<path d="M{s * (pd / 2 + lw / 2)},{top_y} L{s * (pd / 2 + lw / 2 + arm)},{top_y + 3}" fill="none" '
        f'stroke="{_shade(base, .75)}" stroke-width="{max(t * 0.8, 1.2)}" stroke-linecap="round"/>' for s in (-1, 1))
    pads = "" if f.material in ("Acetate", "TR90") else "".join(
        f'<ellipse cx="{s * br / 2.6}" cy="{top_y + h * 0.22}" rx=".9" ry="1.7" fill="#fff" fill-opacity=".55"/>' for s in (-1, 1))

    notes, pad_y = "", 0
    if annotate:  # measurement lines + labels, drawn in the same millimetre space
        pad_y = 17
        y_top, y_bot = -half_h - 5, half_h + 4
        line = 'stroke="#12294d" stroke-width=".45" fill="none"'
        txt = 'font-family="Montserrat,Segoe UI,sans-serif" font-size="4.6" font-weight="600" fill="#12294d" text-anchor="middle"'
        lx0, lx1 = neg - lw / 2, neg + lw / 2
        notes = (f'<path d="M{lx0},{y_top} H{lx1} M{lx0},{y_top - 2} V{y_top + 2} M{lx1},{y_top - 2} V{y_top + 2}" {line}/>'
                 f'<text x="{neg}" y="{y_top - 3}" {txt}>lens {lw:g} mm</text>'
                 f'<path d="M{-br / 2},{y_bot} H{br / 2} M{-br / 2},{y_bot - 2} V{y_bot + 2} M{br / 2},{y_bot - 2} V{y_bot + 2}" {line}/>'
                 f'<text x="0" y="{y_bot + 7}" {txt}>bridge {br:g} mm</text>'
                 f'<path d="M{pos + lw / 2 + 4},{dy - h / 2} V{dy + h / 2} M{pos + lw / 2 + 2},{dy - h / 2} H{pos + lw / 2 + 6} M{pos + lw / 2 + 2},{dy + h / 2} H{pos + lw / 2 + 6}" {line}/>'
                 f'<text x="{pos + lw / 2 + 6}" y="{dy}" {txt} transform="rotate(90 {pos + lw / 2 + 6} {dy})" dy="-1.5">height {h:.0f} mm</text>')
    vy, vh = -half_h - pad_y, H + 2 * pad_y
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-half_w - (6 if annotate else 0):.2f} {vy:.2f} {W + (12 if annotate else 0):.2f} {vh:.2f}" width="{(W + (12 if annotate else 0)) * 10:.0f}" height="{vh * 10:.0f}" role="img" aria-label="{escape(f.name)}">
<defs>
<linearGradient id="frame" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{_shade(base, 1.18)}"/><stop offset=".55" stop-color="{base}"/><stop offset="1" stop-color="{_shade(base, .7)}"/></linearGradient>
<linearGradient id="sheen" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".38"/><stop offset=".45" stop-color="#fff" stop-opacity="0"/><stop offset=".6" stop-color="#fff" stop-opacity=".12"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<clipPath id="top"><rect x="{-lw}" y="{-h}" width="{2 * lw}" height="{h * 0.95}"/></clipPath>
<filter id="shadow" x="-10%" y="-10%" width="120%" height="140%"><feDropShadow dx="0" dy="1.2" stdDeviation="1.1" flood-color="#000" flood-opacity=".28"/></filter>
</defs>
<g filter="url(#shadow)">{temples}{lens(neg, -1)}{lens(pos, 1)}{bridge}{pads}</g>{notes}
</svg>'''
    return svg, round(W, 2)


def side_svg(f, color=None, lens_width=None):
    """Side (profile) view: the front rim edge-on and the temple arm with its ear bend, 1 unit = 1 mm."""
    lw = float(lens_width or f.lens_width)
    h = lw * SHAPES[f.shape][0]
    t = RIM[f.material]
    base = color or f.color_hex
    depth = 4.5 if f.material in ("Acetate", "TR90") else 2.6          # how thick the rim is front-to-back
    tl = float(f.temple)
    x0, y0 = 10.0, 14 + h * 0.2                                         # hinge position
    end_x, end_y = x0 + depth + tl, y0 + 28
    W, H = end_x + 14, h + 30
    arm_w = max(t * 1.15, 1.8)
    arm = (f'M{x0 + depth},{y0} H{x0 + depth + tl - 42} C{x0 + depth + tl - 18},{y0} {end_x - 8},{y0 + 6} {end_x - 6},{y0 + 14} '
           f'L{end_x},{end_y}')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.1f} {H:.1f}" width="{W * 8:.0f}" height="{H * 8:.0f}" role="img" aria-label="{escape(f.name)} side view">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{_shade(base, 1.2)}"/><stop offset=".55" stop-color="{base}"/><stop offset="1" stop-color="{_shade(base, .68)}"/></linearGradient>
<filter id="s" x="-10%" y="-10%" width="120%" height="140%"><feDropShadow dx="0" dy="1.2" stdDeviation="1.1" flood-color="#000" flood-opacity=".25"/></filter></defs>
<g filter="url(#s)"><rect x="{x0 - 1.2}" y="14" width="{depth + 1.2}" height="{h:.1f}" rx="{depth / 2:.1f}" fill="url(#g)"/>
<path d="{arm}" fill="none" stroke="url(#g)" stroke-width="{arm_w:.1f}" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="{x0 + depth}" cy="{y0}" r="{arm_w * .55:.1f}" fill="{_shade(base, .6)}"/></g>
<path d="M{x0 + depth},{H - 6} H{x0 + depth + tl}" stroke="#12294d" stroke-width=".45"/>
<text x="{x0 + depth + tl / 2}" y="{H - 8.5}" font-family="Montserrat,Segoe UI,sans-serif" font-size="4.6" font-weight="600" fill="#12294d" text-anchor="middle">temple {tl:g} mm</text>
</svg>'''
    return svg

