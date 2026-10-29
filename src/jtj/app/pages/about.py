"""About page: first person, Paulina's voice; reviewed by Paulina on 2026-10-29 (BUILD_SPEC §3.3.6)."""
from __future__ import annotations

import flet as ft

from .. import components as C

GITHUB = "https://github.com/Boadiwaa"
PREPRINT = "https://doi.org/10.1101/2024.04.17.24305971"

ABOUT = [
    "I'm Paulina Mensah, a medical doctor and an engineer. I build software for clinical settings, and I care "
    "about what happens when it meets real patients.",
    "AI scribes are arriving fast, and their safety claims depend on automated judges that read notes no human "
    "has time to check. I've seen this pattern before: in earlier work with colleagues on large language models "
    "for emergency medical help, models rated their own first-aid answers 10–19% higher than clinicians did. "
    "So before trusting a judge's safety numbers, I wanted to measure the judge itself.",
    "This project is small on purpose: 24 synthetic consultations, 174 planted errors, three judge designs, "
    "honest confidence intervals, and a way for clinicians to check the answer key. It is independent, and it "
    "doesn't test any company's product.",
]

NEXT = [
    ("Post-market surveillance with judges",
     "Run judges continuously over production notes, with drift monitoring on flag rates and error-type mix, so a "
     "change in the scribe or the judge shows up as a signal rather than a surprise."),
    ("Periodic clinician re-calibration",
     "Have clinicians rate a fresh random sample of notes every quarter, and re-estimate judge sensitivity and "
     "agreement each time."),
    ("Retire judges that drift",
     "Set agreement thresholds in advance, and retire or retrain a judge whose agreement with clinicians drops "
     "below them."),
    ("Multilingual extension",
     "Seed the same errors into translated consultations to test whether judge sensitivity holds across languages, "
     "including languages under-served by today's models."),
]


def build(ctx: C.Ctx) -> ft.Control:
    links = ft.Row([
        ft.OutlinedButton("GitHub · Boadiwaa", icon=ft.Icons.CODE, url=GITHUB,
                          style=ft.ButtonStyle(color=ctx.p.text, side=ft.BorderSide(1, ctx.p.border))),
        ft.OutlinedButton("Preprint: LLMs for emergency medical help (medRxiv)", icon=ft.Icons.ARTICLE_OUTLINED,
                          url=PREPRINT, style=ft.ButtonStyle(color=ctx.p.text, side=ft.BorderSide(1, ctx.p.border))),
    ], wrap=True, spacing=10, run_spacing=10)
    nxt = ft.ResponsiveRow([
        C.card(ft.Column([C.h3(t, ctx), C.body(b, ctx, size=14, muted=True)], spacing=8), ctx, padding=20,
               col={"xs": 12, "md": 6}) for t, b in NEXT
    ], spacing=16, run_spacing=16)
    return ft.Column([
        C.eyebrow("About", ctx), C.h1("Why I built this", ctx) if not ctx.narrow else C.h2("Why I built this", ctx),
        C.card(ft.Column([C.body(p, ctx, size=16) for p in ABOUT] + [links], spacing=14), ctx, padding=28),
        C.h2("What I'd do next with production data", ctx), nxt,
    ], spacing=16)
