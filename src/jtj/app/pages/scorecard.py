"""Judge Scorecard (BUILD_SPEC §3.3.3). Every number links to the cases behind it; every metric has ⓘ.

With no results, it shows the answer-key composition (real counts) and labelled pending states,
never placeholder numbers.
"""
from __future__ import annotations

import math

import flet as ft

from .. import components as C
from .. import theme
from ..rating_status import rater_progress
from ...schema import ERROR_TYPES, TIERS

JUDGES = {"J0": "J0 Naive", "J1": "J1 Rubric", "J2": "J2 Claim-check"}

INFO = {
    "sensitivity": (
        "Of the errors we planted, how many did the judge find? A missed high-risk error is the failure that matters "
        "most. The dot is the estimate; the line is the 95% confidence interval (Wilson). With a few dozen errors, "
        "intervals are wide: read them as a range of plausible values, not a precise rate."),
    "heatmap": (
        "Each cell is the share of planted errors of that type that the judge found, with n (the number planted) "
        "beside the row. Darker means more caught. With small n, read rows as patterns, not precise rates. Tap a "
        "cell to open the cases where that judge missed that error type."),
    "tier": "Detection broken down by the answer key's risk tier. A good judge should be best at the highest tiers.",
    "subtle": (
        "Subtle errors leave the note reading as plausible and consistent, so a busy clinician could miss them on a "
        "quick read; only the transcript gives them away (for example \"3 days\" recorded as \"3 weeks\"). Obvious "
        "errors make the note look wrong on its own, such as an implausible dose. A judge that only catches obvious "
        "errors adds little to a quick human read."),
    "mcnemar": (
        "Both judges saw exactly the same planted errors, so we compare them pairwise: on how many errors did one "
        "judge succeed where the other failed? McNemar's exact test asks whether that imbalance could be chance. "
        "Holm's correction adjusts for making two comparisons. A small p-value (below 0.05) suggests a real "
        "difference; a large one means this pilot cannot tell them apart."),
    "agreement": (
        "When a judge does find an error, does it grade the severity like the answer key? Weighted kappa and Gwet's "
        "AC2 measure agreement beyond chance on the 1–5 scale, giving partial credit for near-misses. 1 is perfect, "
        "0 is chance level. Gwet's AC2 is more stable when most ratings fall in a few categories. Intervals come "
        "from resampling whole cases (2,000 times)."),
    "flags": (
        "Findings that match no planted error. They may be false alarms, or genuine problems in the base note. "
        "They are not counted as false positives until a clinician has reviewed them. On clean notes (no planted "
        "errors), more flags per note suggests more false alarms."),
    "clinician": (
        "The real test: do clinicians agree with the judge? Clinicians rate notes blind to the answer key and to "
        "the judges. Agreement on whether an error is present uses Gwet's AC1; agreement on risk tier uses AC2."),
}


def _cell_color(p: float | None, ctx: C.Ctx) -> tuple[str, str]:
    """Sequential teal scale for the heatmap; returns (bg, fg). Text pairs meet WCAG AA on every step."""
    if p is None:
        return ctx.p.surface_alt, ctx.p.text_muted
    light = ["#E1F0F0", "#BCDFDF", "#89C4C5", "#4E9EA3", "#1F7C84", "#0B5F67"]
    dark = ["#13232B", "#173539", "#1D4A4E", "#286569", "#3E8F92", "#7FD0D0"]
    scale = dark if theme.is_dark(ctx.page) else light
    i = min(5, int(p * 6))
    fg = ("#0A1219" if i >= 4 else "#E6EEF3") if theme.is_dark(ctx.page) else ("#FFFFFF" if i >= 4 else "#0E1B2B")
    return scale[i], fg


def _primary(ctx: C.Ctx) -> ft.Control:
    d = ctx.data
    n_high = d.summary["by_tier"]["High"] + d.summary["by_tier"]["Very high"]
    head = ft.Row([C.h3("Primary endpoint · sensitivity for High + Very high risk errors", ctx)],
                  alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True)
    rows: list[ft.Control] = []
    w = 220 if ctx.narrow else 560
    pj = (d.metrics or {}).get("per_judge", {}) if d.has_any_results else {}
    best = max(pj, key=lambda j: pj[j]["primary"]["p"] or 0) if pj else None
    for j, label in JUDGES.items():
        pr = (d.metrics or {}).get("per_judge", {}).get(j, {}).get("primary") if d.has_any_results else None
        tone = theme.judge_tone(ctx.page, j)
        if pr and pr["n"]:
            val = f"{C.fmt_p(pr['p'])} ({C.fmt_p(pr['lo'])}–{C.fmt_p(pr['hi'])}) · {pr['k']}/{pr['n']}"
            link = lambda e, j=j: ctx.go(f"/explorer?missed={j}&tier=High%2B")
        else:
            val, link = "not yet run", None
        rows.append(ft.ResponsiveRow([
            ft.Container(ft.Text(label, size=15, color=ctx.p.text,
                                 weight=ft.FontWeight.W_700 if j == best else ft.FontWeight.W_400),
                         col={"xs": 12, "md": 2}),
            ft.Container(C.whisker(pr["p"] if pr else None, pr["lo"] if pr else None, pr["hi"] if pr else None,
                                   tone, ctx, w), col={"xs": 12, "md": 7}),
            ft.Container(C.mono(val, ctx, 13), on_click=link, col={"xs": 12, "md": 3},
                         tooltip="Open the high-risk errors this judge missed" if link else None),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER))
    axis = ft.ResponsiveRow([ft.Container(col={"xs": 12, "md": 2}, visible=not ctx.narrow), ft.Container(ft.Row(
        [C.mono(x, ctx, 11, color=ctx.p.text_muted) for x in ("0", "0.25", "0.5", "0.75", "1.0")], width=w,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN), col={"xs": 12, "md": 7})])
    items = [head, C.info_panel("What does this mean?", INFO["sensitivity"], ctx)]
    if not d.has_any_results:
        items.append(C.pending_block("Results pending", f"The judges have not been run. When they are, each row will "
                                     f"show the share of the {n_high} High and Very high risk planted errors that "
                                     "judge found, with a 95% confidence interval.", ctx))
    elif not d.complete:
        items.append(C.pending_block("Partial run", "Only some notes have been judged; these figures cover the "
                                     "judged notes only and will change.", ctx))
    items += rows + [axis]
    return C.card(ft.Column(items, spacing=12), ctx)


def _heatmap(ctx: C.Ctx) -> ft.Control:
    d = ctx.data
    pj = (d.metrics or {}).get("per_judge", {}) if d.has_any_results else {}
    cell_w = 64 if ctx.narrow else 150
    header = ft.Row([ft.Container(C.body("Error type", ctx, size=13, muted=True, weight=ft.FontWeight.W_600),
                                  expand=True),
                     ft.Container(C.body("n", ctx, size=13, muted=True), width=28)] +
                    [ft.Container(C.body(j, ctx, size=13, muted=True, weight=ft.FontWeight.W_600), width=cell_w,
                                  alignment=ft.Alignment.CENTER) for j in JUDGES], spacing=4)
    rows = [header]
    for t, label in ERROR_TYPES.items():
        n = d.summary["by_type"][t]
        cells = []
        for j in JUDGES:
            cell = pj.get(j, {}).get("by_type", {}).get(t)
            p = cell["p"] if cell else None
            bg, fg = _cell_color(p, ctx)
            cells.append(ft.Container(
                C.mono(C.fmt_p(p) if cell else "–", ctx, 13, color=fg), width=cell_w, height=38, bgcolor=bg,
                border_radius=6, alignment=ft.Alignment.CENTER,
                on_click=(lambda e, j=j, t=t: ctx.go(f"/explorer?type={t}&missed={j}")) if cell else None,
                tooltip=f"{j}: {cell['k']}/{cell['n']} {label} errors found. Tap to see the misses." if cell else
                "Not yet run"))
        rows.append(ft.Row([ft.Container(C.body(label, ctx, size=14), expand=True),
                            ft.Container(C.mono(str(n), ctx, 13, color=ctx.p.text_muted), width=28)] + cells, spacing=4))
    note = "Small n per cell: read rows as patterns, not precise rates." if pj else \
        "Planted errors per type are shown (n). Detection rates appear after the judge run."
    return C.card(ft.Column([
        ft.Row([C.h3("Sensitivity by error type", ctx), C.body("Darker = more errors caught · n = planted errors",
                                                              ctx, size=13, muted=True)],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
        C.info_panel("How to read this", INFO["heatmap"], ctx), *rows, C.body(note, ctx, size=13, muted=True)],
        spacing=6), ctx, col={"xs": 12, "lg": 8})


def _by_tier(ctx: C.Ctx) -> ft.Control:
    d = ctx.data
    pj = (d.metrics or {}).get("per_judge", {}) if d.has_any_results else {}
    rows = [ft.Row([ft.Container(C.body("Tier", ctx, size=13, muted=True), width=88),
                    ft.Container(C.body("n", ctx, size=13, muted=True), width=30)] +
                   [ft.Container(C.body(j, ctx, size=13, muted=True), expand=True) for j in JUDGES])]
    for t in TIERS:
        cells = []
        for j in JUDGES:
            c = pj.get(j, {}).get("by_tier", {}).get(t)
            cells.append(ft.Container(C.mono(f"{C.fmt_p(c['p'])}" if c else "–", ctx, 13), expand=True,
                                      on_click=(lambda e, j=j, t=t: ctx.go(f"/explorer?tier={t}&missed={j}"))
                                      if c else None))
        rows.append(ft.Row([ft.Container(C.tier_badge(t, ctx), width=88),
                            ft.Container(C.mono(str(d.summary["by_tier"][t]), ctx, 13, color=ctx.p.text_muted), width=30),
                            *cells]))
    return C.card(ft.Column([C.h3("Sensitivity by risk tier", ctx), C.info_panel("What does this mean?", INFO["tier"],
                                                                                 ctx), *rows], spacing=8), ctx)


def _by_subtlety(ctx: C.Ctx) -> ft.Control:
    d = ctx.data
    pj = (d.metrics or {}).get("per_judge", {}) if d.has_any_results else {}
    n_subtle = d.summary["n_subtle"]
    counts = {"subtle": n_subtle, "obvious": d.summary["n_errors"] - n_subtle}
    rows = [ft.Row([ft.Container(C.body("Errors", ctx, size=13, muted=True), width=70),
                    ft.Container(C.body("n", ctx, size=13, muted=True), width=30)] +
                   [ft.Container(C.body(j, ctx, size=13, muted=True), expand=True) for j in JUDGES])]
    for k in ("subtle", "obvious"):
        cells = []
        for j in JUDGES:
            c = pj.get(j, {}).get("by_subtlety", {}).get(k)
            cells.append(ft.Container(C.mono(C.fmt_p(c["p"]) if c else "–", ctx, 13), expand=True,
                                      tooltip=f"{j}: {c['k']}/{c['n']} {k} errors found. Tap to see the misses."
                                      if c else "Not yet run",
                                      on_click=(lambda e, j=j, k=k: ctx.go(f"/explorer?subtle={k}&missed={j}"))
                                      if c else None))
        rows.append(ft.Row([ft.Container(C.body(k.capitalize(), ctx, size=14), width=70),
                            ft.Container(C.mono(str(counts[k]), ctx, 13, color=ctx.p.text_muted), width=30), *cells]))
    return C.card(ft.Column([C.h3("Subtle vs obvious errors", ctx),
                             C.info_panel("What does this mean?", INFO["subtle"], ctx), *rows], spacing=8), ctx)


def _comparisons(ctx: C.Ctx) -> ft.Control:
    d = ctx.data
    items: list[ft.Control] = [C.h3("Is the better judge really better?", ctx)]
    comps = [c for c in (d.metrics or {}).get("comparisons", []) if c["scope"] == "high"] if d.has_any_results else []
    if not comps:
        items.append(C.body("J2 vs J0 and J1 vs J0, on the same high-risk errors: pending the judge run.", ctx,
                            size=14, muted=True))
    for c in comps:
        p = c.get("p_holm", c["p"])
        verdict = "a difference unlikely to be chance" if p < 0.05 else "no clear difference in this pilot"
        items.append(ft.Column([
            ft.Row([C.body(f"{c['a']} vs {c['b']}, same {c['n']} high-risk errors", ctx, size=14),
                    C.mono(f"p(Holm) = {p:.3f}", ctx, 13)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
            C.body(f"{c['a']} alone caught {c['only_a']}; {c['b']} alone caught {c['only_b']}: {verdict}.", ctx,
                   size=13, muted=True)], spacing=2))
    items.append(C.info_panel("What does this mean?", INFO["mcnemar"], ctx))
    return C.card(ft.Column(items, spacing=10), ctx)


def _agreement(ctx: C.Ctx) -> ft.Control:
    d = ctx.data
    pj = (d.metrics or {}).get("per_judge", {}) if d.has_any_results else {}

    def stat(name, val):
        if not val or val.get("est") is None or (isinstance(val["est"], float) and math.isnan(val["est"])):
            v, ci = "–", "pending" if not pj else "too few detections"
        else:
            v = f"{val['est']:.2f}"
            ci = f"95% CI {val['lo']:.2f}–{val['hi']:.2f}" if val.get("lo") is not None and not math.isnan(val["lo"]) \
                else "CI not estimable"
        return ft.Container(ft.Column([C.body(name, ctx, size=12, muted=True), C.mono(v, ctx, 22),
                                       C.body(ci, ctx, size=12, muted=True)], spacing=2),
                            bgcolor=ctx.p.surface_alt, border_radius=10, padding=12, expand=True)

    items: list[ft.Control] = [C.h3("Does the judge grade severity like the answer key?", ctx)]
    for j in (["J2"] if not pj else [j for j in JUDGES if j in pj]):
        sev = pj.get(j, {}).get("severity_agreement", {})
        items.append(C.body(f"{JUDGES[j]}" + (f" · on {sev.get('n', 0)} detected errors" if pj else ""), ctx, size=13,
                            weight=ft.FontWeight.W_600))
        items.append(ft.Row([stat("Weighted κ (quadratic)", sev.get("kappa_w")),
                             stat("Gwet's AC2 (ordinal)", sev.get("gwet_ac2"))], spacing=10))
    items.append(C.info_panel("What does this mean?", INFO["agreement"], ctx))
    return C.card(ft.Column(items, spacing=10), ctx)


def _clinician_unlocked(ctx: C.Ctx, ag: dict) -> ft.Control:
    f2 = lambda x: "–" if x is None else f"{x:.2f}"
    cs = ag.get("clinician_sensitivity", {})
    rows: list[ft.Control] = [
        C.body(f"Clinicians found {cs.get('k')} of {cs.get('n')} planted errors they saw "
               f"({C.fmt_p(cs.get('p'), True)}, 95% CI {C.fmt_p(cs.get('lo'), True)}–{C.fmt_p(cs.get('hi'), True)}): "
               "a human baseline for the judges.", ctx, size=14),
        C.body(f"Clinicians agree with each other: presence AC1 {f2(ag.get('inter_clinician_presence_ac1'))}, "
               f"tier AC2 {f2(ag.get('inter_clinician_tier_ac2'))}.", ctx, size=14),
    ]
    for j, r in ag.get("per_judge", {}).items():
        t = r.get("tier_ac2") or {}
        share = r.get("flags_real_share")
        rows.append(C.body(
            f"{JUDGES.get(j, j)}: presence AC1 {f2(r.get('presence_ac1'))} (n={r.get('presence_n')}); tier AC2 "
            f"{f2(t.get('est'))} (n={r.get('tier_n')}); flags judged real "
            f"{'–' if share is None else f'{share * 100:.0f}%'} of {r.get('flags_adjudicated')} adjudicated.",
            ctx, size=13, muted=True))
    rows.append(C.info_panel("What does this mean?", INFO["clinician"], ctx))
    return C.card(ft.Column([ft.Row([ft.Icon(ft.Icons.LOCK_OPEN, color=ctx.p.ok, size=20),
                                     C.h3("Clinician agreement", ctx)]), *rows], spacing=10), ctx)


def _clinician(ctx: C.Ctx) -> ft.Control:
    ag = ctx.data.agreement
    if ag and ag.get("unlocked"):
        return _clinician_unlocked(ctx, ag)
    prog = rater_progress()
    need_raters, need_notes = 2, 20
    rows = [C.body(f"Unlocks when {need_raters} clinicians have each rated {need_notes} notes blind.", ctx, size=14,
                   muted=True)]
    if not prog:
        rows.append(C.body("No ratings yet.", ctx, size=14, muted=True))
    for i, (who, n) in enumerate(prog[:4], 1):
        rows.append(ft.Column([ft.Row([C.body(f"Rater {i}", ctx, size=14), C.mono(f"{min(n, need_notes)} / {need_notes}",
                                                                                      ctx, 13)],
                                      alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                               ft.ProgressBar(value=min(1, n / need_notes), color=ctx.p.accent,
                                              bgcolor=ctx.p.surface_alt)], spacing=4))
    rows.append(C.link("Are you a clinician? Rate notes", ctx, lambda e: ctx.go("/rate"), 14))
    rows.append(C.info_panel("What will this show?", INFO["clinician"], ctx))
    return C.card(ft.Column([ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE, color=ctx.p.text, size=20),
                                     C.h3("Clinician agreement", ctx)]), *rows], spacing=10), ctx, dashed=True)


def _flags(ctx: C.Ctx) -> ft.Control:
    d = ctx.data
    pj = (d.metrics or {}).get("per_judge", {}) if d.has_any_results else {}
    rows = []
    for j in JUDGES:
        cf = pj.get(j, {}).get("clean_flags_per_note")
        val = "–" if not cf or cf.get("mean") is None else f"{cf['mean']:.2f} per clean note (n = {cf['n_notes']})"
        rows.append(ft.Row([C.body(JUDGES[j], ctx, size=14), C.mono(val, ctx, 13)],
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
    return C.card(ft.Column([C.h3("Flags on clean notes", ctx), *rows,
                             C.info_panel("What does this mean?", INFO["flags"], ctx)], spacing=8), ctx)


def _dangerous(ctx: C.Ctx) -> ft.Control:
    d = ctx.data
    misses = (d.metrics or {}).get("most_dangerous_misses", []) if d.has_any_results else []
    items: list[ft.Control] = [C.h3("Most dangerous misses", ctx),
                               C.body("Very high risk errors that at least one judge missed.", ctx, size=14, muted=True)]
    if not d.has_any_results:
        items.append(C.pending_block("Pending", f"There are {d.summary['by_tier']['Very high']} Very high risk planted "
                                     "errors. Any that a judge misses will be listed here, each linking to its case.",
                                     ctx))
    elif not misses:
        items.append(C.body("No judge missed a Very high risk error.", ctx, size=14))
    for e in misses:
        items.append(ft.Container(ft.ResponsiveRow([
            ft.Container(C.tier_badge(e["tier"], ctx, e["score"]), col={"xs": 12, "md": 2}),
            ft.Container(C.body(e["description"], ctx, size=15), col={"xs": 12, "md": 6}),
            ft.Container(C.body(f"Missed by {', '.join(e['missed_by'])}", ctx, size=13, muted=True),
                         col={"xs": 6, "md": 2}),
            ft.Container(C.link(f"Case {e['case_id'][-2:]} →", ctx, lambda ev, eid=e["error_id"]: ctx.go(
                f"/explorer?mode=explain&error={eid}&judge={e['missed_by'][0]}"), 14), col={"xs": 6, "md": 2}),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=ft.Padding.symmetric(vertical=8),
            border=ft.Border.only(bottom=ft.BorderSide(1, ctx.p.border))))
    return C.card(ft.Column(items, spacing=8), ctx)


def build(ctx: C.Ctx) -> ft.Control:
    d = ctx.data
    status = "Results pending" if not d.has_any_results else ("Partial run" if not d.complete else
                                                               f"Judge model: {d.metrics.get('judge_model') or 'n/a'}")
    head = ft.ResponsiveRow([ft.Column([C.h1("Judge Scorecard", ctx) if not ctx.narrow else C.h2("Judge Scorecard", ctx),
                              C.body("How often each judge found the errors I planted. Tap any number to see the "
                                     "cases behind it.", ctx, muted=True)], spacing=6, col={"xs": 12, "md": 9}),
                   ft.Container(C.status_pill(status, ctx), col={"xs": 12, "md": 3},
                                alignment=ft.Alignment.CENTER_LEFT if ctx.narrow else ft.Alignment.CENTER_RIGHT)],
                  vertical_alignment=ft.CrossAxisAlignment.END)
    side = ft.Column([_comparisons(ctx), _agreement(ctx), _clinician(ctx)], spacing=18, col={"xs": 12, "lg": 4})
    return ft.Column([
        head, _primary(ctx),
        ft.ResponsiveRow([_heatmap(ctx), side], spacing=18, run_spacing=18,
                         vertical_alignment=ft.CrossAxisAlignment.START),
        ft.ResponsiveRow([ft.Container(_by_tier(ctx), col={"xs": 12, "md": 6, "lg": 4}),
                          ft.Container(_by_subtlety(ctx), col={"xs": 12, "md": 6, "lg": 4}),
                          ft.Container(_flags(ctx), col={"xs": 12, "md": 12, "lg": 4})], spacing=18, run_spacing=18),
        _dangerous(ctx),
    ], spacing=18)
