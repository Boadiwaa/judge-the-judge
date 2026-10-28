"""Overview (landing page): the point in 30 seconds (BUILD_SPEC §3.3.1)."""
from __future__ import annotations

import flet as ft

from .. import components as C
from .. import theme
from ...schema import ERROR_TYPES

JUDGE_LABEL = {"J0": "J0 Naive", "J1": "J1 Rubric", "J2": "J2 Claim-check"}


def _headline(ctx: C.Ctx) -> ft.Control:
    d, p = ctx.data, ctx.p
    head_row = ft.Row([C.eyebrow("Headline result", ctx, p.text_muted)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    if not d.complete:
        head_row.controls.append(C.status_pill("Results pending", ctx))
        s = d.summary
        text = ft.Column([
            ft.Text("Results pending", size=26, weight=ft.FontWeight.W_700, color=p.text),
            C.body(f"The three judges have not yet been run on all {s['n_notes']} notes, so no results are "
                   "shown here. Numbers will appear only once the full, pre-registered run is complete.",
                   ctx, muted=True),
        ], spacing=8)
        whiskers = [_whisker_row(j, None, ctx) for j in ("J0", "J1", "J2")]
        caption = (f"When complete: dot = sensitivity for High + Very high risk errors; line = 95% CI. "
                   f"n = {s['by_tier']['High'] + s['by_tier']['Very high']} high-risk errors.")
    else:
        pj = d.metrics["per_judge"]
        j2, j0 = pj["J2"]["primary"], pj["J0"]["primary"]
        text = ft.Text(spans=[
            ft.TextSpan("The structured judge caught "),
            ft.TextSpan(f"{j2['k']} of {j2['n']}", ft.TextStyle(color=p.accent, weight=ft.FontWeight.W_700)),
            ft.TextSpan(f" high-risk errors ({C.fmt_p(j2['p'], True)}, 95% CI {C.fmt_p(j2['lo'], True)}–"
                        f"{C.fmt_p(j2['hi'], True)}). The naive judge caught {j0['k']} of {j0['n']}."),
        ], size=24 if not ctx.narrow else 20, weight=ft.FontWeight.W_600, color=p.text)
        whiskers = [_whisker_row(j, pj[j]["primary"], ctx) for j in ("J0", "J1", "J2")]
        caption = "Dot = sensitivity for High + Very high risk errors. Line = 95% CI."
        if d.metrics.get("judge_model"):
            caption += f" Judge model: {d.metrics['judge_model']}."
    return C.card(ft.Column([head_row, text, C.section_gap(6), *whiskers, _axis(ctx),
                             C.body(caption, ctx, size=13, muted=True)], spacing=12), ctx, padding=28)


def _bar_width(ctx: C.Ctx) -> float:
    return 110 if ctx.narrow else 230


def _label_width(ctx: C.Ctx) -> int:
    return 96 if ctx.narrow else 118


def _whisker_row(j: str, prop: dict | None, ctx: C.Ctx) -> ft.Control:
    tone = theme.judge_tone(ctx.page, j)
    val = f"{C.fmt_p(prop['p'], True)}" if prop and prop["p"] is not None else "–"
    return ft.Row([
        ft.Container(ft.Text(JUDGE_LABEL[j], size=13 if ctx.narrow else 14, color=ctx.p.text,
                             weight=ft.FontWeight.W_700 if j == "J2" else ft.FontWeight.W_400),
                     width=_label_width(ctx)),
        C.whisker(prop["p"] if prop else None, prop["lo"] if prop else None, prop["hi"] if prop else None,
                  tone, ctx, _bar_width(ctx)),
        ft.Container(C.mono(val, ctx), width=40, alignment=ft.Alignment.CENTER_RIGHT),
    ], spacing=10)


def _axis(ctx: C.Ctx) -> ft.Control:
    w = _bar_width(ctx)
    return ft.Row([ft.Container(width=_label_width(ctx)), ft.Row([
        C.mono("0%", ctx, 11, color=ctx.p.text_muted), C.mono("50%", ctx, 11, color=ctx.p.text_muted),
        C.mono("100%", ctx, 11, color=ctx.p.text_muted)], width=w, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)],
        spacing=10)


def _found_card(ctx: C.Ctx) -> ft.Control:
    d = ctx.data
    if not d.complete:
        title, text = "Waiting for the judge run", (
            "This card will name the error type the judges miss most often, with the numbers behind it. "
            "Until the full run is complete it stays empty rather than showing placeholder values.")
    else:
        pj = d.metrics["per_judge"]
        worst = min(ERROR_TYPES, key=lambda t: sum((pj[j]["by_type"].get(t) or {}).get("p") or 0 for j in pj))
        rates = ", ".join(f"{j} {C.fmt_p(pj[j]['by_type'][worst]['p'], True)}" for j in pj if worst in pj[j]["by_type"])
        title = f"{ERROR_TYPES[worst]} slips past most often"
        text = f"Across the judges, this error type had the lowest detection ({rates})."
    return _story("03 · What I found", title, text, ctx, link=("See the scorecard", "/scorecard"))


def _story(kicker: str, title: str, text: str, ctx: C.Ctx, link=None) -> ft.Control:
    items = [ft.Text(kicker, size=14, weight=ft.FontWeight.W_600, color=ctx.p.accent),
             C.h2(title, ctx, size=22), C.body(text, ctx, muted=True)]
    if link:
        items.append(C.link(link[0], ctx, lambda e: ctx.go(link[1])))
    return C.card(ft.Column(items, spacing=10), ctx, padding=28, col={"xs": 12, "md": 4})


def _step(n: int, title: str, text: str, ctx: C.Ctx) -> ft.Control:
    return ft.Container(ft.Row([
        ft.Container(ft.Text(str(n), color=ctx.p.on_accent, weight=ft.FontWeight.W_700), width=34, height=34,
                     bgcolor=ctx.p.accent, border_radius=17, alignment=ft.Alignment.CENTER),
        ft.Column([ft.Text(title, size=16, weight=ft.FontWeight.W_600, color=ctx.p.text),
                   C.body(text, ctx, size=14, muted=True)], spacing=4, expand=True),
    ], vertical_alignment=ft.CrossAxisAlignment.START, spacing=14),
        bgcolor=ctx.p.surface_alt, border_radius=14, padding=20, col={"xs": 12, "sm": 6, "lg": 3})


def build(ctx: C.Ctx) -> ft.Control:
    s = ctx.data.summary
    hero = ft.Column([
        C.eyebrow("Independent pilot study · synthetic UK consultations", ctx),
        C.h1("Who checks the checker?", ctx),
        C.body(f"Safety claims for AI scribes rest on automated judges that find errors in clinical notes. "
               f"I planted {s['n_errors']} known errors in {s['n_notes']} AI-style notes and measured how many "
               "each of three LLM judge designs caught, and how badly the misses would matter.",
               ctx, size=17 if ctx.narrow else 19, muted=True),
        C.section_gap(6),
        ft.Row([
            ft.FilledButton("Try spotting the errors yourself", icon=ft.Icons.ARROW_FORWARD,
                            on_click=lambda e: ctx.go("/explorer?mode=challenge"),
                            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=22, vertical=18),
                                                 shape=ft.RoundedRectangleBorder(radius=10))),
            ft.OutlinedButton("Read the protocol", on_click=lambda e: ctx.go("/protocol"),
                              style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=22, vertical=18),
                                                   shape=ft.RoundedRectangleBorder(radius=10),
                                                   color=ctx.p.text, side=ft.BorderSide(1, ctx.p.border))),
        ], wrap=True, spacing=12, run_spacing=12),
    ], spacing=16, col={"xs": 12, "lg": 7})

    top = ft.ResponsiveRow([hero, ft.Container(_headline(ctx), col={"xs": 12, "lg": 5})], spacing=32,
                           run_spacing=24, vertical_alignment=ft.CrossAxisAlignment.START)
    stories = ft.ResponsiveRow([
        _story("01 · The problem", "Nobody can read every AI-written note",
               "At scale, safety numbers come from LLM judges. If a judge misses a swapped side or a dropped "
               "allergy, every number built on it is wrong.", ctx),
        _story("02 · What I did", "Planted known errors, then tested three judges",
               f"{s['n_cases']} synthetic UK consultations, {s['n_notes']} notes, {len(ERROR_TYPES)} error types graded by "
               "severity × likelihood. Because I planted them, there is an exact answer key.", ctx),
        _found_card(ctx),
    ], spacing=20, run_spacing=20)
    steps = ft.ResponsiveRow([
        _step(1, "Write consultations", "Transcript + clean reference note, UK practice.", ctx),
        _step(2, "Plant errors", "Omissions, negation flips, wrong side, dose slips.", ctx),
        _step(3, "Run three judges", "Naive, rubric and claim-by-claim checking.", ctx),
        _step(4, "Score against the key", "Then clinicians rate blind to validate.", ctx),
    ], spacing=16, run_spacing=16)
    why = ft.Text(spans=[
        ft.TextSpan("Why planted errors? ", style=ft.TextStyle(weight=ft.FontWeight.W_600, color=ctx.p.text)),
        ft.TextSpan("They give an exact miss rate for known error types; they don't replace real-note validation. ",
                    style=ft.TextStyle(color=ctx.p.text_muted)),
        ft.TextSpan("Read why", style=ft.TextStyle(color=ctx.p.accent, decoration=ft.TextDecoration.UNDERLINE),
                    on_click=lambda e: ctx.go("/protocol?section=external-validity")),
    ], size=14)
    return ft.Column([top, C.section_gap(12), ft.Column([C.limitations_strip(ctx), why], spacing=10),
                      C.section_gap(12), stories,
                      C.section_gap(16), C.h2("How the study works", ctx), steps], spacing=16)
