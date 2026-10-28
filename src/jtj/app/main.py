"""Flet web app entry point: routing, layout chrome, theme, resize handling.

Run locally:  python -m jtj.app.main   (serves http://localhost:8080)
"""
from __future__ import annotations

import logging
import os
import traceback
from urllib.parse import parse_qsl

import flet as ft
from starlette.requests import Request

from . import components as C
from . import theme
from .data import load
from .pages import about, explorer, overview, protocol, rate, scorecard

log = logging.getLogger("jtj.app")

PAGES = {
    "/": overview.build,
    "/explorer": explorer.build,
    "/scorecard": scorecard.build,
    "/rate": rate.build,
    "/protocol": protocol.build,
    "/about": about.build,
}
MAX_W = 1240


def build_page_body(ctx: C.Ctx, route: str) -> ft.Control:
    """Build one page's body; any exception becomes a friendly error card (no stack traces to users)."""
    try:
        return PAGES.get(route, _not_found)(ctx)
    except Exception:  # noqa: BLE001
        log.error("page %s failed:\n%s", route, traceback.format_exc())
        return C.card(ft.Column([
            C.h2("Something went wrong on this page", ctx),
            C.body("The error has been logged. Try another page, or reload.", ctx, muted=True),
        ]), ctx)


def _not_found(ctx: C.Ctx) -> ft.Control:
    return C.card(ft.Column([C.h2("Page not found", ctx),
                             C.link("Go to the overview", ctx, lambda e: ctx.go("/"))]), ctx)


def main(page: ft.Page) -> None:
    page.title = "Judge the Judge"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.padding = 0
    page.spacing = 0
    page.scroll = ft.ScrollMode.AUTO
    theme.apply(page)
    data = load()
    last = {"w": None}
    state: dict = {}

    def go(route: str) -> None:
        page.run_task(page.push_route, route)

    def render() -> None:
        route, _, qs = (page.route or "/").partition("?")
        w = page.width or 1200
        last["w"] = w
        ctx = C.Ctx(page=page, data=data, p=theme.palette(page), narrow=w < C.NARROW, go=go,
                    rerender=render, query=dict(parse_qsl(qs)), state=state, after=[])
        page.bgcolor = ctx.p.bg
        side = 16 if ctx.narrow else 40
        inner = min(MAX_W, w - 2 * side)
        content = ft.Row([ft.Container(build_page_body(ctx, route), width=inner)],
                         alignment=ft.MainAxisAlignment.CENTER)
        nav_route = route if route in PAGES else ""
        page.controls = [ft.Column([
            C.header(ctx, nav_route),
            ft.Container(content, padding=ft.Padding.symmetric(horizontal=side, vertical=24 if ctx.narrow else 40)),
            C.footer(ctx),
        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)]
        page.update()
        for fn in ctx.after:
            try:
                fn()
            except Exception:  # noqa: BLE001
                log.warning("post-render hook failed:\n%s", traceback.format_exc())

    def on_resize(e) -> None:
        w = page.width or 1200
        if last["w"] is None or abs(w - last["w"]) > 24 or (w < C.NARROW) != (last["w"] < C.NARROW):
            render()

    page.on_route_change = lambda e: render()
    page.on_resize = on_resize
    page.on_platform_brightness_change = lambda e: render()
    render()


def write_protocol(assets_dir: str) -> None:
    """Regenerate the downloadable protocol so it always matches the running code and data."""
    from .. import protocol

    try:
        os.makedirs(assets_dir, exist_ok=True)
        with open(os.path.join(assets_dir, "protocol.md"), "w") as f:
            f.write(protocol.markdown(load().cases))
    except OSError:
        log.warning("could not write protocol.md:\n%s", traceback.format_exc())


ASSETS = os.path.join(os.path.dirname(__file__), "assets")
STATIC_SUFFIXES = (".wasm", ".js", ".mjs", ".otf", ".ttf", ".png", ".json", ".symbols")


def asgi_app():
    """Flet's web server as an ASGI app, with gzip and caching added.

    The Flet web client is about 11 MB uncompressed (an 8.5 MB WebAssembly bundle plus fonts) and Flet
    serves it without compression, which makes the first visit on a phone slow (DECISIONS D-19).
    """
    import base64
    import hmac

    from starlette.middleware.gzip import GZipMiddleware
    from starlette.responses import PlainTextResponse, Response

    write_protocol(ASSETS)
    app = ft.run(main, export_asgi_app=True, assets_dir=ASSETS)

    @app.middleware("http")
    async def cache_static(request, call_next):
        response = await call_next(request)
        if request.url.path.endswith(STATIC_SUFFIXES) and response.status_code == 200:
            response.headers.setdefault("Cache-Control", "public, max-age=86400")
        return response

    @app.get("/export/ratings.zip")
    async def export_ratings(request: Request):
        """Owner-only CSV export. HTTP Basic auth (any username, password = OWNER_CODE), so the secret
        never appears in a URL. Disabled when OWNER_CODE is unset."""
        expected = os.environ.get("OWNER_CODE", "")
        if not expected:
            return PlainTextResponse("Export is disabled (OWNER_CODE not set).", status_code=404)
        auth = request.headers.get("authorization", "")
        ok = False
        if auth.startswith("Basic "):
            try:
                _, _, pw = base64.b64decode(auth[6:]).decode().partition(":")
                ok = hmac.compare_digest(pw, expected)
            except (ValueError, UnicodeDecodeError):
                ok = False
        if not ok:
            return PlainTextResponse("Authentication required.", status_code=401,
                                     headers={"WWW-Authenticate": 'Basic realm="ratings export"'})
        from .rating_status import export_zip

        return Response(export_zip(), media_type="application/zip",
                        headers={"Content-Disposition": "attachment; filename=jtj_ratings.zip",
                                 "Cache-Control": "no-store"})

    # Flet mounts a catch-all static handler first; move our route ahead of it so it is reachable,
    # and drop FastAPI's auto-generated API docs, which this app doesn't need to expose
    app.router.routes.insert(0, app.router.routes.pop())
    app.router.routes[:] = [r for r in app.router.routes
                            if getattr(r, "path", None) not in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc")]
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)
    return app


def run() -> None:
    import uvicorn

    uvicorn.run(asgi_app(), host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8080")),
                proxy_headers=True, forwarded_allow_ips="*", log_level="warning")


if __name__ == "__main__":
    run()
