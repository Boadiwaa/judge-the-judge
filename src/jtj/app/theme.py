"""Colour tokens and Flet themes (BUILD_SPEC §3.4, mockups).

One accent (deep clinical teal) with a navy partner for the brand mark and hero, cool neutral greys, and
risk-tier colours that are always paired with a text label. Foreground/background pairs were chosen for WCAG AA (≥4.5:1) contrast; see tests/test_app.py.
"""
from __future__ import annotations

from dataclasses import dataclass

import os

import flet as ft


@dataclass(frozen=True)
class Palette:
    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    accent: str
    accent_soft: str
    brand: str  # navy partner to the accent: logo mark and hero gradient
    on_accent: str
    warn_bg: str
    warn_border: str
    warn_text: str
    ok: str
    miss: str
    # risk tiers: (text, background, border)
    tier: dict
    flag: tuple  # judge flag not in answer key


LIGHT = Palette(
    bg="#F5F7F8", surface="#FFFFFF", surface_alt="#EDF2F3", border="#D9E2E6",
    text="#0E1B2B", text_muted="#4A586B", accent="#0B6A72", accent_soft="#DCEFEF", brand="#12304A",
    on_accent="#FFFFFF",
    warn_bg="#FFF7E6", warn_border="#F0D9A6", warn_text="#6B4A00",
    ok="#1E6B45", miss="#1A1A1A",
    tier={
        "Low": ("#3F5266", "#E6EBF1", "#9AA9BA"),
        "Moderate": ("#7A4B00", "#FDF0D2", "#D9A441"),
        "High": ("#A33212", "#FBE2D6", "#E08A63"),
        "Very high": ("#8E1630", "#F8DCE3", "#D06A84"),
    },
    flag=("#5B4C6E", "#EEEAF3", "#A99BBE"),
)

DARK = Palette(
    bg="#0A1219", surface="#111C25", surface_alt="#182631", border="#263845",
    text="#E6EEF3", text_muted="#A2B1BE", accent="#52C4C4", accent_soft="#0F3236", brand="#1B4A6B",
    on_accent="#03191A",
    warn_bg="#2B2414", warn_border="#5A4A22", warn_text="#F1D69B",
    ok="#6FD3A0", miss="#E7EDF3",
    tier={
        "Low": ("#C3CFDC", "#26313D", "#5D6E80"),
        "Moderate": ("#F3CB7A", "#3A2E14", "#9C7A2E"),
        "High": ("#F6A889", "#40231A", "#B0603F"),
        "Very high": ("#F59AB0", "#41192A", "#B04A66"),
    },
    flag=("#CDBFE0", "#2C2638", "#7D6E95"),
)

JUDGE_TONE = {"J0": "#94A3B5", "J1": "#3E8E95", "J2": "#0B6A72"}  # light-mode dots; dark uses accent shades
JUDGE_TONE_DARK = {"J0": "#7D8B9B", "J1": "#5FA9AE", "J2": "#9BE3E5"}

# Bundled open-licence fonts (SIL OFL, from Google Fonts) in assets/fonts. Flutter web can't use system fonts,
# and Flet registers one file per family, so each weight we use is its own family. If a file is missing, text
# falls back to the default font (DECISIONS D-22).
SERIF = "SourceSerif"      # display headings (Source Serif 4, SemiBold)
SANS = "Inter"             # body text (Inter Regular)
SANS_SEMI = "InterSemiBold"  # labels and emphasis (Inter SemiBold)
MONO = "JetBrainsMono"     # numbers and code (JetBrains Mono Regular)
FONT_FILES = {
    SERIF: "fonts/SourceSerif4-SemiBold.ttf",
    SANS: "fonts/Inter-Regular.ttf",
    SANS_SEMI: "fonts/Inter-SemiBold.ttf",
    MONO: "fonts/JetBrainsMono-Regular.ttf",
}


def fonts(assets_dir: str) -> dict[str, str]:
    """Font families whose files are present, as Flet expects them (paths relative to the assets dir)."""
    return {name: "/" + path for name, path in FONT_FILES.items() if os.path.exists(os.path.join(assets_dir, path))}


def palette(page: ft.Page) -> Palette:
    return DARK if is_dark(page) else LIGHT


def is_dark(page: ft.Page) -> bool:
    if page.theme_mode == ft.ThemeMode.DARK:
        return True
    if page.theme_mode == ft.ThemeMode.LIGHT:
        return False
    return page.platform_brightness == ft.Brightness.DARK


def judge_tone(page: ft.Page, j: str) -> str:
    return (JUDGE_TONE_DARK if is_dark(page) else JUDGE_TONE)[j]


def _theme(p: Palette, dark: bool) -> ft.Theme:
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=p.accent, on_primary=p.on_accent, surface=p.surface, on_surface=p.text,
            on_surface_variant=p.text_muted, outline=p.border, outline_variant=p.border,
            primary_container=p.accent_soft, on_primary_container=p.text,
            secondary_container=p.accent_soft, on_secondary_container=p.text,
        ),
        scaffold_bgcolor=p.bg,
        font_family=SANS,
        divider_color=p.border,
        use_material3=True,
    )


def apply(page: ft.Page, assets_dir: str | None = None) -> None:
    if assets_dir:
        page.fonts = fonts(assets_dir)
    page.theme = _theme(LIGHT, False)
    page.dark_theme = _theme(DARK, True)
    page.bgcolor = palette(page).bg
