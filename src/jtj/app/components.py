"""Shared UI building blocks: header/nav, footer, cards, badges, ⓘ panels, CI whiskers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlencode

import flet as ft

from . import theme
from .data import AppData

NARROW = 760  # px: below this the nav collapses to a menu and panes stack

NAV = [
    ("/", "Overview"),
    ("/explorer", "Case Explorer"),
    ("/scorecard", "Scorecard"),
    ("/rate", "Rate notes"),
    ("/protocol", "Protocol"),
    ("/about", "About"),
]


@dataclass
class Ctx:
    page: ft.Page
    data: AppData
    p: theme.Palette
    narrow: bool
    go: Callable[[str], None]
    rerender: Callable[[], None]
    query: dict
    state: dict  # per-session UI state (e.g. challenge-mode marks), survives re-renders
    after: list  # callables run after page.update() (e.g. scroll_to)

    def with_query(self, route: str, **changes) -> str:
        """Build a route with the current query updated; None removes a key."""
        q = {**self.query, **changes}
        q = {k: v for k, v in q.items() if v not in (None, "")}
        return route + ("?" + urlencode(q) if q else "")


# ---------------- text ----------------


def h1(s: str, ctx: Ctx) -> ft.Text:
    return ft.Text(s, size=34 if ctx.narrow else 52, weight=ft.FontWeight.W_700, font_family=theme.SERIF,
                   color=ctx.p.text)


def h2(s: str, ctx: Ctx, size: int | None = None) -> ft.Text:
    return ft.Text(s, size=size or (22 if ctx.narrow else 26), weight=ft.FontWeight.W_700,
                   font_family=theme.SERIF, color=ctx.p.text)


def h3(s: str, ctx: Ctx) -> ft.Text:
    return ft.Text(s, size=17, weight=ft.FontWeight.W_600, font_family=theme.SANS_SEMI, color=ctx.p.text)


def eyebrow(s: str, ctx: Ctx, color: str | None = None) -> ft.Text:
    return ft.Text(s.upper(), size=12, weight=ft.FontWeight.W_600, font_family=theme.SANS_SEMI,
                   color=color or ctx.p.accent,
                   style=ft.TextStyle(letter_spacing=1.4))


def body(s: str, ctx: Ctx, size: int = 15, muted: bool = False, **kw) -> ft.Text:
    kw.setdefault("color", ctx.p.text_muted if muted else ctx.p.text)
    if kw.get("weight") in (ft.FontWeight.W_600, ft.FontWeight.W_700, ft.FontWeight.BOLD):
        kw.setdefault("font_family", theme.SANS_SEMI)
    return ft.Text(s, size=size, **kw)


def mono(s: str, ctx: Ctx, size: int = 13, **kw) -> ft.Text:
    kw.setdefault("color", ctx.p.text)
    return ft.Text(s, size=size, font_family=theme.MONO, **kw)


# ---------------- containers ----------------


def card(content: ft.Control, ctx: Ctx, padding: int = 24, dashed: bool = False, bg: str | None = None,
         col=None, expand=None) -> ft.Container:
    return ft.Container(
        content=content, padding=padding, bgcolor=bg or ctx.p.surface, border_radius=14,
        border=ft.Border.all(1.5 if dashed else 1, ctx.p.flag[2] if dashed else ctx.p.border),
        col=col, expand=expand,
        shadow=None if theme.is_dark(ctx.page) or dashed else ft.BoxShadow(
            blur_radius=18, spread_radius=-6, offset=ft.Offset(0, 6), color=ft.Colors.with_opacity(0.10, ctx.p.brand)),
    )


def pill(label: str, fg: str, bg: str, border: str | None = None, size: int = 12) -> ft.Container:
    return ft.Container(
        ft.Text(label, size=size, weight=ft.FontWeight.W_600, color=fg),
        bgcolor=bg, border_radius=999, padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border=ft.Border.all(1, border) if border else None,
    )


def tier_badge(tier: str, ctx: Ctx, score: int | None = None) -> ft.Container:
    fg, bg, bd = ctx.p.tier[tier]
    return pill(f"{tier}{f' · {score}' if score else ''}", fg, bg, bd)


def flag_badge(ctx: Ctx, label: str = "Judge flag · not in answer key") -> ft.Container:
    fg, bg, bd = ctx.p.flag
    return pill(label, fg, bg, bd)


def status_pill(text: str, ctx: Ctx) -> ft.Container:
    fg, bg, bd = ctx.p.flag
    return pill(text, fg, bg, bd)


def info_panel(title: str, text: str, ctx: Ctx) -> ft.Control:
    """ⓘ toggle that reveals a plain-English explanation (BUILD_SPEC §3.3 Scorecard, §3.4)."""
    panel = ft.Container(
        body(text, ctx, size=14), visible=False, bgcolor=ctx.p.accent_soft, border_radius=10, padding=14,
    )

    def toggle(e):
        panel.visible = not panel.visible
        panel.update()

    btn = ft.TextButton(title, icon=ft.Icons.INFO_OUTLINE, on_click=toggle,
                        style=ft.ButtonStyle(color=ctx.p.accent, padding=ft.Padding.symmetric(horizontal=6)))
    return ft.Column([btn, panel], spacing=6)


def pending_block(title: str, text: str, ctx: Ctx) -> ft.Container:
    return ft.Container(
        ft.Column([
            ft.Row([ft.Icon(ft.Icons.HOURGLASS_EMPTY, color=ctx.p.flag[0], size=18),
                    ft.Text(title, size=15, weight=ft.FontWeight.W_600, color=ctx.p.flag[0])], spacing=8),
            body(text, ctx, size=14, muted=True),
        ], spacing=6),
        bgcolor=ctx.p.flag[1], border=ft.Border.all(1, ctx.p.flag[2]), border_radius=12, padding=16,
    )


def link(text: str, ctx: Ctx, on_click, size: int = 15) -> ft.Text:
    return ft.Text(spans=[ft.TextSpan(text, style=ft.TextStyle(
        color=ctx.p.accent, decoration=ft.TextDecoration.UNDERLINE, size=size), on_click=on_click)])


# ---------------- charts (plain containers; DECISIONS D-02) ----------------


def whisker(p: float | None, lo: float | None, hi: float | None, tone: str, ctx: Ctx, width: float,
            height: int = 22) -> ft.Control:
    """Dot (point estimate) with a line for the 95% CI on a 0–1 axis of `width` px."""
    track = ft.Container(left=0, top=height / 2 - 1, width=width, height=2, bgcolor=ctx.p.border)
    items: list[ft.Control] = [track]
    if p is not None and lo is not None and hi is not None:
        items.append(ft.Container(left=lo * width, top=height / 2 - 1.5, width=max(2, (hi - lo) * width),
                                  height=3, bgcolor=tone, border_radius=2))
        items.append(ft.Container(left=p * width - 8, top=height / 2 - 8, width=16, height=16,
                                  bgcolor=tone, border_radius=8, border=ft.Border.all(2, ctx.p.surface)))
    return ft.Stack(items, width=width, height=height)


def fmt_p(x: float | None, pct: bool = False) -> str:
    if x is None:
        return "–"
    return f"{x * 100:.0f}%" if pct else f"{x:.2f}"


# ---------------- page chrome ----------------


def header(ctx: Ctx, current: str) -> ft.Container:
    p = ctx.p
    logo = ft.Row([
        ft.Container(ft.Icon(ft.Icons.CHECK, color="#FFFFFF", size=18), border_radius=8, width=30, height=30,
                     alignment=ft.Alignment.CENTER,
                     gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                                colors=[p.accent if not theme.is_dark(ctx.page) else "#1E8C8F",
                                                        p.brand])),
        ft.Text("Judge the Judge", size=20, weight=ft.FontWeight.W_700, font_family=theme.SERIF, color=p.text),
    ], spacing=10)
    logo_btn = ft.Container(logo, on_click=lambda e: ctx.go("/"), tooltip="Overview")

    def toggle_theme(e):
        ctx.page.theme_mode = ft.ThemeMode.LIGHT if theme.is_dark(ctx.page) else ft.ThemeMode.DARK
        ctx.rerender()

    mode_btn = ft.IconButton(
        icon=ft.Icons.LIGHT_MODE_OUTLINED if theme.is_dark(ctx.page) else ft.Icons.DARK_MODE_OUTLINED,
        tooltip="Switch to light mode" if theme.is_dark(ctx.page) else "Switch to dark mode",
        icon_color=p.text, on_click=toggle_theme,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), side=ft.BorderSide(1, p.border)),
    )

    if ctx.narrow:
        menu = ft.PopupMenuButton(
            icon=ft.Icons.MENU, tooltip="Menu", icon_color=p.text,
            items=[ft.PopupMenuItem(content=label, checked=(route == current),
                                    on_click=lambda e, r=route: ctx.go(r)) for route, label in NAV],
        )
        row = ft.Row([logo_btn, ft.Row([mode_btn, menu], spacing=4)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    else:
        links = []
        for route, label in NAV:
            active = route == current
            links.append(ft.Container(
                ft.Text(label, size=15, weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_400,
                        color=p.text if active else p.text_muted),
                padding=ft.Padding.only(top=8, bottom=6),
                border=ft.Border.only(bottom=ft.BorderSide(2.5, p.accent if active else "#00000000")),
                on_click=lambda e, r=route: ctx.go(r),
            ))
        row = ft.Row([ft.Row([logo_btn, ft.Container(width=18), ft.Row(links, spacing=26)]), mode_btn],
                     alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    return ft.Container(row, bgcolor=p.surface, padding=ft.Padding.symmetric(horizontal=16 if ctx.narrow else 40,
                                                                               vertical=12),
                        border=ft.Border.only(bottom=ft.BorderSide(1, p.border)))


def footer(ctx: Ctx) -> ft.Container:
    text = "Synthetic data only. Independent study. Not a medical device."
    if not ctx.data.all_reviewed:
        text += " Clinical content drafted for clinician review."
    return ft.Container(body(text, ctx, size=13, muted=True), bgcolor=ctx.p.surface,
                        padding=ft.Padding.symmetric(horizontal=16 if ctx.narrow else 40, vertical=22),
                        border=ft.Border.only(top=ft.BorderSide(1, ctx.p.border)))


def limitations_strip(ctx: Ctx) -> ft.Container:
    p, d = ctx.p, ctx.data
    items = ["Synthetic data only", "Pilot sample: wide confidence intervals", "Clinician ratings pending"]
    if not d.all_reviewed:
        items.append("Answer key awaiting clinician review")
    if not d.complete:
        items.insert(0, "Judge results pending")
    parts: list[ft.Control] = [
        ft.Icon(ft.Icons.ERROR_OUTLINE, color=p.warn_text, size=18),
        ft.Text("Read with care", size=14, weight=ft.FontWeight.W_700, color=p.warn_text),
    ]
    for i, it in enumerate(items):
        if i:
            parts.append(ft.Text("·", color=p.warn_border, size=14))
        parts.append(ft.Text(it, size=14, color=p.warn_text))
    return ft.Container(ft.Row(parts, wrap=True, spacing=10, run_spacing=4), bgcolor=p.warn_bg,
                        border=ft.Border.all(1, p.warn_border), border_radius=12,
                        padding=ft.Padding.symmetric(horizontal=18, vertical=14))


def section_gap(h: int = 28) -> ft.Container:
    return ft.Container(height=h)
