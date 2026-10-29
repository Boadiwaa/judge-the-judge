"""Generate the web shell's icons, link-preview image, index.html and manifest.json (DECISIONS D-35).

Flet serves files in the app's assets directory ahead of its own web client files, so these replace
Flet's default title ("Flet"), description, favicon and loading logo. Run once after changing the
brand or the public URL; the outputs are committed. Needs Pillow (a dev dependency, not used at run time).

    .venv/bin/python scripts/make_web_assets.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jtj.app.theme import DARK, LIGHT  # noqa: E402

ASSETS = Path(__file__).resolve().parents[1] / "src" / "jtj" / "app" / "assets"
FONTS = ASSETS / "fonts"
URL = "https://judge-the-judge.fly.dev"
TITLE = "Judge the Judge"
DESCRIPTION = ("How well do LLM judges catch errors in AI-written clinical notes? An independent pilot study: "
               "174 planted errors in 72 notes from synthetic UK consultations, three judge designs, honest "
               "confidence intervals.")
SS = 4  # supersampling factor for smooth edges


def _hex(c: str) -> tuple[int, int, int]:
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _gradient(size: int, a: str, b: str) -> Image.Image:
    """Diagonal top-left to bottom-right gradient, like the header logo."""
    ca, cb = _hex(a), _hex(b)
    g = Image.new("RGB", (size, size))
    px = g.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            px[x, y] = tuple(round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))
    return g


def logo(size: int, rounded: bool = True, check_scale: float = 0.6) -> Image.Image:
    """The header logo: a white check on a teal-to-navy rounded square."""
    big = size * SS
    img = _gradient(big, LIGHT.accent, LIGHT.brand).convert("RGBA")
    if rounded:
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=round(big * 8 / 30), fill=255)
        img.putalpha(mask)
    d = ImageDraw.Draw(img)
    s, c = big * check_scale, big / 2
    pts = [(c - 0.42 * s, c + 0.02 * s), (c - 0.12 * s, c + 0.32 * s), (c + 0.44 * s, c - 0.28 * s)]
    w = round(big * 0.11)
    d.line(pts, fill="white", width=w, joint="curve")
    for x, y in (pts[0], pts[-1]):
        d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill="white")
    return img.resize((size, size), Image.LANCZOS)


def preview_image() -> Image.Image:
    """1200 x 630 link-preview card (Open Graph / Twitter)."""
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), DARK.bg)
    glow = _gradient(W, "#0F3236", DARK.bg).resize((W, H))
    img = Image.blend(img, glow, 0.85)
    d = ImageDraw.Draw(img)
    serif = lambda n: ImageFont.truetype(str(FONTS / "SourceSerif4-SemiBold.ttf"), n)  # noqa: E731
    sans = lambda n: ImageFont.truetype(str(FONTS / "Inter-Regular.ttf"), n)  # noqa: E731
    semi = lambda n: ImageFont.truetype(str(FONTS / "Inter-SemiBold.ttf"), n)  # noqa: E731
    img.paste(lg := logo(84), (80, 72), lg)
    d.text((184, 86), TITLE, font=serif(46), fill=DARK.text)
    d.text((80, 214), "Who checks the checker?", font=serif(82), fill=DARK.text)
    d.text((80, 330), "How well do LLM judges catch errors in", font=sans(36), fill=DARK.text_muted)
    d.text((80, 378), "AI-written clinical notes?", font=sans(36), fill=DARK.text_muted)
    x = 80
    for i, chip in enumerate(("174 planted errors", "72 notes", "3 judge designs")):
        f = semi(28)
        w = d.textlength(chip, font=f)
        d.rounded_rectangle((x, 466, x + w + 40, 520), radius=27, fill=DARK.accent_soft, outline=DARK.border)
        d.text((x + 20, 476), chip, font=f, fill=DARK.accent)
        x += w + 56
    d.text((80, 562), "Independent pilot study · synthetic UK consultations", font=sans(24), fill=DARK.text_muted)
    host = URL.removeprefix("https://")
    d.text((W - 80 - d.textlength(host, font=semi(24)), 562), host, font=semi(24), fill=DARK.accent)
    return img


def index_html() -> str:
    """Flet's web index.html with this app's title, description, preview tags, icons and loading screen."""
    import flet_web

    src = (Path(flet_web.__file__).parent / "web" / "index.html").read_text()
    meta = f"""<meta name="description" content="{DESCRIPTION}">
  <meta name="theme-color" content="{LIGHT.accent}">

  <!-- Link previews (Open Graph, Twitter) -->
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{TITLE}">
  <meta property="og:title" content="{TITLE}: who checks the checker?">
  <meta property="og:description" content="{DESCRIPTION}">
  <meta property="og:url" content="{URL}/">
  <meta property="og:image" content="{URL}/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="{TITLE}: who checks the checker? 174 planted errors, 72 notes, 3 judge designs.">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{TITLE}: who checks the checker?">
  <meta name="twitter:description" content="{DESCRIPTION}">
  <meta name="twitter:image" content="{URL}/og-image.png">"""
    reps = [
        ('<meta name="description" content="Flet application.">', meta),
        ('<meta name="apple-mobile-web-app-title" content="Flet">',
         f'<meta name="apple-mobile-web-app-title" content="{TITLE}">'),
        ("<title>Flet</title>", f"<title>{TITLE}</title>"),
        ("background: #ffffff;", f"background: {LIGHT.bg};"),
        ("background: #222222;", f"background: {DARK.bg};"),
        ("width: 200px;", "width: 96px;"),
    ]
    for a, b in reps:
        if src.count(a) != 1:
            raise SystemExit(f"Flet's index.html changed; can't find: {a!r}")
        src = src.replace(a, b)
    return src


def manifest() -> str:
    icons = [{"src": f"icons/icon-{n}.png", "sizes": f"{n}x{n}", "type": "image/png"} for n in (192, 512)]
    icons += [{"src": f"icons/icon-maskable-{n}.png", "sizes": f"{n}x{n}", "type": "image/png",
               "purpose": "maskable"} for n in (192, 512)]
    return json.dumps({"name": TITLE, "short_name": TITLE, "start_url": ".", "display": "standalone",
                       "background_color": LIGHT.bg, "theme_color": LIGHT.accent, "description": DESCRIPTION,
                       "orientation": "portrait-primary", "prefer_related_applications": False,
                       "icons": icons}, indent=2) + "\n"


def main() -> None:
    (ASSETS / "icons").mkdir(parents=True, exist_ok=True)
    logo(64).save(ASSETS / "favicon.png")
    logo(192, rounded=False, check_scale=0.62).convert("RGB").save(ASSETS / "icons" / "apple-touch-icon-192.png")
    for n in (192, 512):
        logo(n).save(ASSETS / "icons" / f"icon-{n}.png")
        logo(n, rounded=False, check_scale=0.45).convert("RGB").save(ASSETS / "icons" / f"icon-maskable-{n}.png")
    logo(192).save(ASSETS / "icons" / "loading-animation.png")
    preview_image().save(ASSETS / "og-image.png", optimize=True)
    (ASSETS / "index.html").write_text(index_html())
    (ASSETS / "manifest.json").write_text(manifest())
    print("wrote", ", ".join(sorted(str(p.relative_to(ASSETS)) for p in ASSETS.rglob("*")
                                    if p.suffix in (".png", ".html", ".json"))))


if __name__ == "__main__":
    main()
