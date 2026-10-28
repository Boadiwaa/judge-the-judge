"""Protocol page: a short pre-registered-style protocol with prompts in collapsible blocks (§3.3.5)."""
from __future__ import annotations

import flet as ft

from .. import components as C
from ... import protocol

JUDGE_NAMES = {"J0": "J0 Naive", "J1": "J1 Rubric", "J2": "J2 Claim-check"}


def _md(text: str, ctx: C.Ctx) -> ft.Markdown:
    return ft.Markdown(text, selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                       md_style_sheet=ft.MarkdownStyleSheet(
                           p_text_style=ft.TextStyle(size=15, color=ctx.p.text),
                           code_text_style=ft.TextStyle(size=13, font_family="monospace"),
                           table_body_text_style=ft.TextStyle(size=14, color=ctx.p.text),
                           table_head_text_style=ft.TextStyle(size=14, weight=ft.FontWeight.W_700, color=ctx.p.text),
                       ))


def build(ctx: C.Ctx) -> ft.Control:
    secs = protocol.sections(ctx.data.cases)
    items: list[ft.Control] = [
        ft.ResponsiveRow([ft.Column([C.eyebrow("Protocol", ctx), C.h1("How the study works", ctx) if not ctx.narrow
                           else C.h2("How the study works", ctx),
                           C.body(f"Version {protocol.VERSION} · {protocol.DATE}", ctx, size=14, muted=True)],
                          spacing=6, col={"xs": 12, "md": 8}),
                ft.OutlinedButton("Download protocol (Markdown)", icon=ft.Icons.DOWNLOAD, url="/protocol.md",
                                  style=ft.ButtonStyle(color=ctx.p.text, side=ft.BorderSide(1, ctx.p.border),
                                                       shape=ft.RoundedRectangleBorder(radius=10)),
                                  col={"xs": 12, "md": 4})],
                         vertical_alignment=ft.CrossAxisAlignment.END),
    ]
    for title, body in secs:
        block = [C.h2(title, ctx, size=20), _md(body, ctx)]
        if title == "Judges":
            for j, parts in protocol.judge_prompts().items():
                block.append(ft.ExpansionTile(
                    title=ft.Text(f"Full prompt · {JUDGE_NAMES[j]}", size=15, weight=ft.FontWeight.W_600,
                                  color=ctx.p.text),
                    controls=[ft.Container(ft.Column([ft.Column([C.eyebrow(label, ctx, ctx.p.text_muted),
                                                                 C.mono(text, ctx, 12, selectable=True)], spacing=6)
                                                      for label, text in parts], spacing=14),
                                           bgcolor=ctx.p.surface_alt, border_radius=10, padding=14)],
                    collapsed_shape=ft.RoundedRectangleBorder(radius=10), shape=ft.RoundedRectangleBorder(radius=10),
                    bgcolor=ctx.p.surface, collapsed_bgcolor=ctx.p.surface,
                ))
        items.append(C.card(ft.Column(block, spacing=10), ctx))
    return ft.Column(items, spacing=16)
