"""Case Explorer: transcript | note | findings, with challenge and explain modes (BUILD_SPEC §3.3.2).

All state lives in the URL query (case, variant, mode, judge, error, filters) so every view is
deep-linkable from the Scorecard. Challenge-mode marks live in ctx.state.
"""
from __future__ import annotations

import flet as ft

from .. import components as C
from ..data import PLAIN_TYPE, sentences
from ...schema import ERROR_TYPES, SECTION_LABELS, SECTIONS, SETTING_LABELS, TIERS

JUDGES = {"J0": "J0 Naive", "J1": "J1 Rubric", "J2": "J2 Claim-check"}
VARIANT_LABEL = {"clean": "Clean", "a": "Variant A", "b": "Variant B"}
PANE_H = 640


# ---------------------------------------------------------------- selection & filters


ERROR_FILTERS = ("type", "tier", "subtle", "missed")


def _matches_filters(ctx: C.Ctx, m) -> bool:
    q = ctx.query
    if q.get("type") and m.type != q["type"]:
        return False
    if q.get("tier") == "High+":
        if m.tier not in ("High", "Very high"):
            return False
    elif q.get("tier") and m.tier != q["tier"]:
        return False
    if q.get("subtle") in ("subtle", "obvious") and m.subtle != (q["subtle"] == "subtle"):
        return False
    if q.get("missed"):
        v = ctx.data.verdict(q["missed"], m.error_id)
        if not v or v["detected"]:
            return False
    return True


def _filtered_cases(ctx: C.Ctx):
    q, out = ctx.query, []
    error_filter = any(q.get(k) for k in ERROR_FILTERS)
    for c in ctx.data.cases:
        if q.get("setting") and c.setting != q["setting"]:
            continue
        if error_filter and not any(_matches_filters(ctx, m) for v in c.variants for m in v.mutations):
            continue
        out.append(c)
    return out


def _resolve(ctx: C.Ctx):
    """Pick case/variant/mode/judge from the query, defaulting sensibly and honouring filters."""
    q, d = ctx.query, ctx.data
    cases = _filtered_cases(ctx) or d.cases
    if q.get("error"):
        try:
            c, v, _ = d.mutation(q["error"])
            return c, v, cases
        except StopIteration:
            pass
    c = next((x for x in cases if x.case_id == q.get("case")), None)
    if c is None:
        c = next((x for x in cases if x.case_id == "case_07"), cases[0])  # the mockup's case
    kind = q.get("variant")
    error_filter = any(q.get(k) for k in ERROR_FILTERS)
    if kind is None and error_filter:
        kind = next((v.kind for v in c.variants if any(_matches_filters(ctx, m) for m in v.mutations)), "a")
    kind = kind or "a"
    v = next((x for x in c.variants if x.kind == kind), c.variants[1])
    return c, v, cases


# ---------------------------------------------------------------- controls


def _segmented(options: list[tuple[str, str]], selected: str, on_pick, ctx: C.Ctx) -> ft.Control:
    btns = []
    for val, label in options:
        active = val == selected
        btns.append(ft.Container(
            ft.Text(label, size=14, weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_400,
                    color=ctx.p.on_accent if active else ctx.p.text),
            bgcolor=ctx.p.accent if active else ctx.p.surface,
            padding=ft.Padding.symmetric(horizontal=14, vertical=9),
            on_click=lambda e, v=val: on_pick(v), border_radius=8,
        ))
    return ft.Container(ft.Row(btns, spacing=2, tight=True), border=ft.Border.all(1, ctx.p.border),
                        border_radius=10, padding=2)


def _labelled(label: str, control: ft.Control, ctx: C.Ctx) -> ft.Control:
    return ft.Column([C.body(label, ctx, size=13, muted=True), control], spacing=6, tight=True)


def _dropdown(value, options, on_select, ctx: C.Ctx, width=None) -> ft.Dropdown:
    return ft.Dropdown(
        value=value, options=[ft.DropdownOption(key=k, text=t) for k, t in options], on_select=on_select,
        width=width, dense=True, border_radius=10, text_size=14, enable_search=False,
    )


def _controls(ctx: C.Ctx, case, variant, cases, mode: str, judge: str) -> ft.Control:
    go = lambda **kw: ctx.go(ctx.with_query("/explorer", error=None, **kw))
    case_dd = _dropdown(case.case_id,
                        [(c.case_id, f"Case {c.case_id[-2:]} · {SETTING_LABELS[c.setting]} · {c.title}") for c in cases],
                        lambda e: go(case=e.control.value, variant=None), ctx, width=None if ctx.narrow else 380)
    row = [
        _labelled("Case", case_dd, ctx),
        _labelled("Note variant", _segmented([(k, VARIANT_LABEL[k]) for k in ("clean", "a", "b")], variant.kind,
                                             lambda v: go(case=case.case_id, variant=v), ctx), ctx),
        _labelled("Mode", _segmented([("challenge", "Challenge"), ("explain", "Explain")], mode,
                                     lambda v: go(case=case.case_id, variant=variant.kind, mode=v), ctx), ctx),
    ]
    if mode == "explain":
        row.append(_labelled("Judge shown in note", _segmented(list(JUDGES.items()), judge,
                             lambda v: ctx.go(ctx.with_query("/explorer", case=case.case_id, variant=variant.kind,
                                                             judge=v)), ctx), ctx))

    show_filters = ctx.state.get("filters_open") or any(ctx.query.get(k) for k in ("setting",) + ERROR_FILTERS)

    def toggle_filters(e):
        ctx.state["filters_open"] = not show_filters
        ctx.rerender()

    active = [ctx.query[k] for k in ("setting", "type", "tier", "subtle") if ctx.query.get(k)]
    if ctx.query.get("missed"):
        active.append(f"missed by {ctx.query['missed']}")
    filt_btn = ft.OutlinedButton(
        "Filters" + (f" · {', '.join(active)}" if active else ""), icon=ft.Icons.FILTER_LIST, on_click=toggle_filters,
        style=ft.ButtonStyle(color=ctx.p.text, side=ft.BorderSide(1, ctx.p.border),
                             shape=ft.RoundedRectangleBorder(radius=10)))
    controls_row = ft.Row(row, wrap=True, spacing=22, run_spacing=14, vertical_alignment=ft.CrossAxisAlignment.END)
    if ctx.narrow:
        top = ft.Column([controls_row, filt_btn], spacing=14)
    else:
        controls_row.expand = True
        top = ft.Row([controls_row, filt_btn], vertical_alignment=ft.CrossAxisAlignment.START)
    items: list[ft.Control] = [top]
    if show_filters:
        fq = lambda **kw: ctx.go(ctx.with_query("/explorer", case=None, variant=None, error=None, **kw))
        any_opt = [("", "Any")]
        missed_opts = any_opt + ([(j, f"Missed by {j}") for j in ctx.data.matches] if ctx.data.has_any_results else [])
        filters = [
            _labelled("Setting", _dropdown(ctx.query.get("setting", ""), any_opt + list(SETTING_LABELS.items()),
                                           lambda e: fq(setting=e.control.value), ctx, 200), ctx),
            _labelled("Error type", _dropdown(ctx.query.get("type", ""), any_opt + list(ERROR_TYPES.items()),
                                              lambda e: fq(type=e.control.value), ctx, 230), ctx),
            _labelled("Risk tier", _dropdown(ctx.query.get("tier", ""), any_opt + [(t, t) for t in TIERS] +
                                             [("High+", "High or Very high")],
                                             lambda e: fq(tier=e.control.value), ctx, 160), ctx),
            _labelled("Subtlety", _dropdown(ctx.query.get("subtle", ""), any_opt + [("subtle", "Subtle"),
                                                                                    ("obvious", "Obvious")],
                                            lambda e: fq(subtle=e.control.value), ctx, 140), ctx),
            _labelled("Judge", _dropdown(ctx.query.get("missed", ""), missed_opts,
                                         lambda e: fq(missed=e.control.value), ctx, 180), ctx),
            ft.TextButton("Clear filters", on_click=lambda e: ctx.go("/explorer"),
                          style=ft.ButtonStyle(color=ctx.p.accent)),
        ]
        if not ctx.data.has_any_results:
            filters.append(C.body("'Missed by judge' unlocks after the judge run.", ctx, size=13, muted=True))
        items.append(ft.Row(filters, wrap=True, spacing=16, run_spacing=12, vertical_alignment=ft.CrossAxisAlignment.END))
        items.append(C.body(f"{len(cases)} of {len(ctx.data.cases)} cases match.", ctx, size=13, muted=True))
    return C.card(ft.Column(items, spacing=16), ctx, padding=18)


def _key_row(ctx: C.Ctx) -> ft.Control:
    def sw(tier):
        fg, bg, bd = ctx.p.tier[tier]
        return ft.Row([ft.Container(width=14, height=14, bgcolor=bg, border=ft.Border.all(1.5, bd), border_radius=3),
                       C.body(tier, ctx, size=13)], spacing=6, tight=True)
    fg, bg, bd = ctx.p.flag
    return ft.Row([
        ft.Text("Key", size=13, weight=ft.FontWeight.W_700, color=ctx.p.text), *[sw(t) for t in TIERS],
        ft.Row([ft.Container(width=14, height=14, bgcolor=bg, border=ft.Border.all(1.5, bd), border_radius=3),
                C.body("Judge flag, not in answer key", ctx, size=13)], spacing=6, tight=True),
        C.body("✔ detected   ✖ missed (by the selected judge)", ctx, size=13),
    ], wrap=True, spacing=18, run_spacing=6)


# ---------------------------------------------------------------- transcript pane


def _transcript(ctx: C.Ctx, case, highlight: set[int]) -> ft.Control:
    rows = []
    for t in case.transcript:
        hl = t.turn in highlight
        fg, bg, bd = ctx.p.tier["High"]
        rows.append(ft.Container(
            ft.Row([
                ft.Container(C.mono(str(t.turn), ctx, 12, color=ctx.p.text_muted), width=26),
                ft.Text(spans=[ft.TextSpan(f"{t.speaker} — ", ft.TextStyle(weight=ft.FontWeight.W_700)),
                               ft.TextSpan(t.text)], size=14, color=ctx.p.text, expand=True, selectable=True),
            ], vertical_alignment=ft.CrossAxisAlignment.START, spacing=6),
            key=ft.ScrollKey(f"turn-{t.turn}"),
            bgcolor=bg if hl else None, border=ft.Border.all(1.5, bd) if hl else None, border_radius=10,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        ))
    col = ft.Column(rows, spacing=2, scroll=ft.ScrollMode.AUTO, height=None if ctx.narrow else PANE_H - 70)
    if highlight and not ctx.narrow:
        first = min(highlight)
        ctx.after.append(lambda: col.scroll_to(scroll_key=f"turn-{max(1, first - 1)}", duration=300))
    shown = f"turns {min(highlight)}–{max(highlight)} highlighted" if highlight else f"{len(case.transcript)} turns"
    return _pane("Transcript", shown, col, ctx)


def _pane(title: str, sub: str, content: ft.Control, ctx: C.Ctx, col_lg: int = 4) -> ft.Control:
    return ft.Container(ft.Column([
        ft.Row([ft.Text(title, size=17, weight=ft.FontWeight.W_700, color=ctx.p.text),
                C.body(sub, ctx, size=13, muted=True)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
        ft.Divider(height=1, color=ctx.p.border), content], spacing=12),
        bgcolor=ctx.p.surface, border=ft.Border.all(1, ctx.p.border), border_radius=14, padding=18,
        col={"xs": 12, "lg": col_lg})


# ---------------------------------------------------------------- note pane


def _section_label(s: str, ctx: C.Ctx) -> ft.Text:
    return C.eyebrow(SECTION_LABELS[s], ctx, ctx.p.text_muted)


def _note_explain(ctx: C.Ctx, variant, judge: str, selected: str | None) -> ft.Control:
    d = ctx.data
    blocks = []
    for s in SECTIONS:
        text = d.notes[variant.variant_id][s]
        spans, pos = [], 0
        for sp in d.spans(variant.variant_id, s):
            if sp.start < pos:
                continue
            if sp.start > pos:
                spans.append(ft.TextSpan(text[pos:sp.start]))
            m = sp.mutation
            fg, bg, bd = ctx.p.tier[m.tier]
            v = d.verdict(judge, m.error_id)
            mark = "" if v is None else (" ✔" if v["detected"] else " ✖")
            is_sel = m.error_id == selected
            style = ft.TextStyle(bgcolor=bg, color=fg if m.is_omission else ctx.p.text,
                                 weight=ft.FontWeight.W_700 if is_sel or m.is_omission else None,
                                 decoration=ft.TextDecoration.UNDERLINE, decoration_color=bd,
                                 decoration_thickness=3 if is_sel else 2)
            label = f" ⊘ Missing: {m.description or ERROR_TYPES[m.type]}{mark} " if m.is_omission \
                else text[sp.start:sp.end] + mark
            spans.append(ft.TextSpan(label, style, on_click=lambda e, eid=m.error_id: ctx.go(
                ctx.with_query("/explorer", case=variant.variant_id.rsplit('_', 1)[0], variant=variant.kind,
                               mode="explain", error=eid))))
            pos = sp.end
        spans.append(ft.TextSpan(text[pos:]))
        blocks.append(ft.Column([_section_label(s, ctx), ft.Text(spans=spans, size=15, color=ctx.p.text)], spacing=4))
    return ft.Column(blocks, spacing=14)


def _challenge_state(ctx: C.Ctx, variant_id: str) -> dict:
    st = ctx.state.setdefault("challenge", {})
    return st.setdefault(variant_id, {"marks": set(), "missing": set(), "revealed": False})


def _note_challenge(ctx: C.Ctx, variant) -> ft.Control:
    d, st = ctx.data, _challenge_state(ctx, variant.variant_id)
    revealed = st["revealed"]
    blocks = []
    for s in SECTIONS:
        text = d.notes[variant.variant_id][s]
        errs = [sp for sp in d.spans(variant.variant_id, s) if not sp.mutation.is_omission]
        spans = []
        for i, (a, b) in enumerate(sentences(text)):
            key = (s, i)
            marked = key in st["marks"]
            hit = next((sp for sp in errs if sp.start < b and sp.end > a), None)
            style = ft.TextStyle()
            if marked:
                style = ft.TextStyle(bgcolor=ctx.p.accent_soft, decoration=ft.TextDecoration.UNDERLINE,
                                     decoration_color=ctx.p.accent, decoration_thickness=2)
            if revealed and hit:
                fg, bg, bd = ctx.p.tier[hit.mutation.tier]
                style = ft.TextStyle(bgcolor=bg, decoration=ft.TextDecoration.UNDERLINE, decoration_color=bd,
                                     decoration_thickness=3)

            def toggle(e, key=key):
                if st["revealed"]:
                    return
                st["marks"].symmetric_difference_update({key})
                ctx.rerender()

            suffix = (" ✔" if marked else " ✖") if revealed and hit else ""
            spans.append(ft.TextSpan(text[a:b] + suffix + " ", style, on_click=toggle))
        miss_on = s in st["missing"]
        has_omission = any(sp.mutation.is_omission for sp in d.spans(variant.variant_id, s))

        def toggle_missing(e, s=s):
            if st["revealed"]:
                return
            st["missing"].symmetric_difference_update({s})
            ctx.rerender()

        chip_text = "Something's missing here" + (" ✓" if miss_on else "")
        chip_color = ctx.p.accent if miss_on else ctx.p.text_muted
        if revealed and has_omission:
            chip_text, chip_color = ("Missing fact found ✔" if miss_on else "A fact was left out here ✖"), ctx.p.tier["High"][0]
        chip = ft.Container(C.body(chip_text, ctx, size=12, color=chip_color), on_click=toggle_missing,
                            border=ft.Border.all(1, chip_color), border_radius=999,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=3))
        if text:
            body_text = ft.Text(spans=spans, size=15, color=ctx.p.text)
        else:
            body_text = C.body("(empty)", ctx, size=14, muted=True, italic=True)
        blocks.append(ft.Column([ft.Row([_section_label(s, ctx), chip], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        wrap=True), body_text], spacing=4))
    return ft.Column(blocks, spacing=14)


# ---------------------------------------------------------------- findings pane


def _risk_matrix(sev: int, lik: int, ctx: C.Ctx) -> ft.Control:
    from ...schema import risk_tier

    rows = []
    for s in range(5, 0, -1):
        cells = [ft.Container(C.mono(str(s), ctx, 11, color=ctx.p.text_muted), width=16)]
        for l in range(1, 6):
            fg, bg, bd = ctx.p.tier[risk_tier(s * l)]
            here = (s, l) == (sev, lik)
            cells.append(ft.Container(
                ft.Text(str(s * l) if here else "", size=11, weight=ft.FontWeight.W_700, color="#FFFFFF"),
                width=26, height=26, bgcolor=fg if here else bg, border_radius=4,
                border=ft.Border.all(2, ctx.p.text) if here else None, alignment=ft.Alignment.CENTER,
                tooltip=f"Severity {s} × likelihood {l} = {s * l} ({risk_tier(s * l)})"))
        rows.append(ft.Row(cells, spacing=3))
    rows.append(ft.Row([ft.Container(width=16)] + [ft.Container(C.mono(str(l), ctx, 11, color=ctx.p.text_muted),
                                                                width=26, alignment=ft.Alignment.CENTER)
                                                   for l in range(1, 6)], spacing=3))
    rows.append(C.body("Severity ↑ · Likelihood →", ctx, size=12, muted=True))
    return ft.Column(rows, spacing=3, tight=True)


def _judge_card(ctx: C.Ctx, j: str, m, selected_judge: str) -> ft.Control:
    from ...schema import risk_tier

    v = ctx.data.verdict(j, m.error_id)
    if v is None:
        icon, head, detail = ft.Icons.HOURGLASS_EMPTY, f"{JUDGES[j]} · not yet run", \
            "This judge has not been run on this note yet."
        color = ctx.p.text_muted
    elif v["detected"]:
        f = v["finding"] or {}
        grade = ""
        if f.get("severity") and f.get("likelihood"):
            sc = f["severity"] * f["likelihood"]
            grade = f", graded {risk_tier(sc)} ({f['severity']} × {f['likelihood']})"
        icon, head, color = ft.Icons.CHECK_CIRCLE, f"{JUDGES[j]} · detected{grade}", ctx.p.ok
        bits = []
        if f.get("rationale"):
            bits.append(f"“{f['rationale']}”")
        if f.get("transcript_evidence"):
            bits.append(f"Quoted evidence: “{f['transcript_evidence']}”")
        if v.get("type_agree") is False:
            bits.append(f"Labelled the error as {f.get('type', 'UNSPECIFIED')}.")
        detail = " ".join(bits) or "Detected (no rationale given)."
    else:
        icon, head, color = ft.Icons.CANCEL, f"{JUDGES[j]} · missed", ctx.p.miss
        detail = "No finding from this judge matched this error." if not v.get("no_output") else \
            "The judge's output for this note could not be parsed, so the error counts as missed."
    sel = j == selected_judge
    return ft.Container(ft.Row([
        ft.Icon(icon, color=color, size=22),
        ft.Column([ft.Text(head, size=15, weight=ft.FontWeight.W_700, color=ctx.p.text),
                   C.body(detail, ctx, size=14, muted=True)], spacing=4, expand=True),
    ], vertical_alignment=ft.CrossAxisAlignment.START),
        border=ft.Border.all(1.5 if sel else 1, ctx.p.accent if sel else ctx.p.border),
        bgcolor=ctx.p.accent_soft if sel else None, border_radius=10, padding=14)


def _error_detail(ctx: C.Ctx, case, variant, m, judge: str) -> ft.Control:
    fg, bg, bd = ctx.p.tier[m.tier]
    turns = m.evidence_turns
    turn_text = {t.turn: t for t in case.transcript}
    diff = ft.Container(ft.Column([
        ft.Container(C.mono(f"− {m.original_text.strip()}", ctx, color=ctx.p.ok), bgcolor=ctx.p.surface_alt, padding=10),
        ft.Container(C.mono(f"+ {m.mutated_text.strip() or '(removed from the note)'}", ctx, color=fg),
                     bgcolor=bg, padding=10),
    ], spacing=0), border_radius=8, clip_behavior=ft.ClipBehavior.HARD_EDGE, border=ft.Border.all(1, ctx.p.border))
    proof = ft.Column([C.body(f"{turn_text[t].speaker} (turn {t}): “{turn_text[t].text}”", ctx, size=14)
                       for t in turns if t in turn_text], spacing=6)
    back = C.link("← All errors in this note", ctx, lambda e: ctx.go(ctx.with_query("/explorer", error=None)), 14)
    return ft.Column([
        back,
        ft.Row([C.tier_badge(m.tier, ctx, m.risk_score), C.mono(m.type, ctx, 12, color=ctx.p.text_muted),
                C.mono(m.error_id, ctx, 12, color=ctx.p.text_muted)], wrap=True, spacing=10),
        C.h2(PLAIN_TYPE[m.type], ctx, size=22),
        C.body(m.description, ctx, muted=True),
        ft.Divider(height=1, color=ctx.p.border),
        C.eyebrow("What changed", ctx, ctx.p.text_muted), diff,
        C.eyebrow("The proof", ctx, ctx.p.text_muted),
        C.body(f"Transcript turn{'s' if len(turns) > 1 else ''} {', '.join(map(str, turns))}, highlighted in the "
               "transcript.", ctx, size=14, muted=True), proof,
        C.eyebrow("Why it matters", ctx, ctx.p.text_muted),
        ft.ResponsiveRow([
            ft.Container(_risk_matrix(m.seeded_severity, m.seeded_likelihood, ctx), col={"xs": 12, "sm": 6}),
            ft.Column([C.body(f"Severity {m.seeded_severity} × likelihood {m.seeded_likelihood} = {m.risk_score}.",
                              ctx, size=14, weight=ft.FontWeight.W_600),
                       C.body(m.seeded_rationale, ctx, size=14, muted=True),
                       C.body("Answer-key grading drafted for clinician review.", ctx, size=12, muted=True,
                              italic=True)], col={"xs": 12, "sm": 6}, spacing=6),
        ], spacing=12),
        C.eyebrow("How each judge saw it", ctx, ctx.p.text_muted),
        *[_judge_card(ctx, j, m, judge) for j in JUDGES],
    ], spacing=12)


def _error_list(ctx: C.Ctx, case, variant, judge: str) -> ft.Control:
    d = ctx.data
    items: list[ft.Control] = []
    if not variant.mutations:
        items.append(C.body("This is the clean note: no errors were planted. Anything a judge flags here is a "
                            "candidate false positive, awaiting clinician review.", ctx, size=14, muted=True))
    for m in sorted(variant.mutations, key=lambda m: -m.risk_score):
        v = d.verdict(judge, m.error_id)
        status = "not yet run" if v is None else ("detected" if v["detected"] else "missed")
        items.append(ft.Container(ft.Row([
            C.tier_badge(m.tier, ctx, m.risk_score),
            ft.Column([C.body(m.description, ctx, size=14, weight=ft.FontWeight.W_600),
                       C.body(f"{ERROR_TYPES[m.type]} · {'subtle' if m.subtle else 'obvious'} · {judge} {status}", ctx,
                              size=13, muted=True)],
                      spacing=2, expand=True),
            ft.Icon(ft.Icons.CHEVRON_RIGHT, color=ctx.p.text_muted),
        ]), padding=10, border_radius=10, border=ft.Border.all(1, ctx.p.border),
            on_click=lambda e, eid=m.error_id: ctx.go(ctx.with_query("/explorer", mode="explain", error=eid))))
    flags = d.flags_for(judge, variant.variant_id)
    items.append(C.eyebrow(f"Judge flags not in the answer key ({len(flags) if d.has_any_results else '–'})", ctx,
                           ctx.p.text_muted))
    if not d.has_any_results or judge not in d.matches:
        items.append(C.pending_block("Judges not yet run",
                                     "When the judges have run, findings that match no planted error appear here "
                                     "for clinician adjudication.", ctx))
    elif not flags:
        items.append(C.body(f"{judge} raised no other findings on this note.", ctx, size=14, muted=True))
    for f in flags:
        fi = f["finding"]
        items.append(ft.Container(ft.Column([
            C.flag_badge(ctx, "Judge flag, not in answer key · awaiting clinician review"),
            C.body(f"“{fi.get('note_span') or '(omission)'}”", ctx, size=14, weight=ft.FontWeight.W_600),
            C.body(fi.get("rationale", ""), ctx, size=13, muted=True),
        ], spacing=6), padding=12, border_radius=10, bgcolor=ctx.p.flag[1], border=ft.Border.all(1, ctx.p.flag[2])))
    return ft.Column(items, spacing=10)


def _challenge_panel(ctx: C.Ctx, case, variant) -> ft.Control:
    st = _challenge_state(ctx, variant.variant_id)
    n_marked = len(st["marks"]) + len(st["missing"])

    def reveal(e):
        st["revealed"] = True
        ctx.rerender()

    def reset(e):
        st.update(marks=set(), missing=set(), revealed=False)
        ctx.rerender()

    if not st["revealed"]:
        return ft.Column([
            C.h2("Can you spot the errors?", ctx, size=22),
            C.body("Read the transcript, then click any sentence in the note you think is wrong. If something "
                   "important was left out of a section, tap “Something's missing here”.", ctx, size=14,
                   muted=True),
            C.body("Some notes have no planted errors at all.", ctx, size=14, muted=True),
            C.body(f"{n_marked} marked", ctx, size=14, weight=ft.FontWeight.W_600),
            ft.Row([ft.FilledButton("Reveal", icon=ft.Icons.VISIBILITY, on_click=reveal),
                    ft.TextButton("Clear", on_click=reset)]),
        ], spacing=12)

    d = ctx.data
    caught, rows = 0, []
    for m in sorted(variant.mutations, key=lambda m: -m.risk_score):
        if m.is_omission:
            ok = m.section in st["missing"]
        else:
            ok = any(sp.mutation.error_id == m.error_id and any(
                sp.start < b and sp.end > a for i, (a, b) in enumerate(sentences(d.notes[variant.variant_id][m.section]))
                if (m.section, i) in st["marks"]) for sp in d.spans(variant.variant_id, m.section))
        caught += ok
        rows.append(ft.Container(ft.Row([
            ft.Icon(ft.Icons.CHECK_CIRCLE if ok else ft.Icons.CANCEL, color=ctx.p.ok if ok else ctx.p.miss, size=20),
            C.tier_badge(m.tier, ctx),
            C.body(m.description, ctx, size=14, expand=True),
        ]), on_click=lambda e, eid=m.error_id: ctx.go(ctx.with_query("/explorer", mode="explain", error=eid)),
            padding=8, border_radius=8, border=ft.Border.all(1, ctx.p.border)))
    total = len(variant.mutations)
    if total:
        headline = f"You caught {caught} of {total} planted error{'s' if total != 1 else ''}."
    else:
        headline = "This note had no planted errors."
    extra = n_marked - caught
    return ft.Column([
        C.h2(headline, ctx, size=22),
        C.body(f"{extra} of your marks matched no planted error." if extra > 0 else "None of your marks were false "
               "alarms." if n_marked else "You didn't mark anything.", ctx, size=14, muted=True),
        *rows,
        C.body("A judge has to do this for every note, at scale. Tap an error to see what it was, why it matters "
               "and how each judge did.", ctx, size=14, muted=True),
        ft.Row([ft.FilledButton("See how the judges did", icon=ft.Icons.ARROW_FORWARD,
                                on_click=lambda e: ctx.go(ctx.with_query("/explorer", mode="explain"))),
                ft.TextButton("Try again", on_click=reset)], wrap=True),
    ], spacing=10)


# ---------------------------------------------------------------- page


def build(ctx: C.Ctx) -> ft.Control:
    d = ctx.data
    case, variant, cases = _resolve(ctx)
    mode = ctx.query.get("mode") or ("explain" if ctx.query.get("error") else "challenge")
    judge = ctx.query.get("judge") if ctx.query.get("judge") in JUDGES else "J2"
    selected = ctx.query.get("error") if mode == "explain" else None
    m = next((x for x in variant.mutations if x.error_id == selected), None)

    n_err = len(variant.mutations)
    n_flags = len(d.flags_for(judge, variant.variant_id))
    if mode == "explain":
        note_sub = f"{n_err} planted error{'s' if n_err != 1 else ''}" + \
                   (f" · {n_flags} judge flag{'s' if n_flags != 1 else ''}" if d.has_any_results else "")
        note = _note_explain(ctx, variant, judge, selected)
        right = _error_detail(ctx, case, variant, m, judge) if m else _error_list(ctx, case, variant, judge)
        right_title, right_sub = ("Error", "") if m else ("Findings", f"judge: {JUDGES[judge]}")
    else:
        note_sub = "click what looks wrong"
        note = _note_challenge(ctx, variant)
        right = _challenge_panel(ctx, case, variant)
        right_title, right_sub = "Challenge", ""
    highlight = set(m.evidence_turns) if m else set()

    panes = ft.ResponsiveRow([
        _transcript(ctx, case, highlight),
        _pane(f"AI-style note · {VARIANT_LABEL[variant.kind]}", note_sub, note, ctx),
        _pane(right_title, right_sub, right, ctx),
    ], spacing=18, run_spacing=18, vertical_alignment=ft.CrossAxisAlignment.START)

    header = [C.h2("Case Explorer", ctx), C.body(
        "Read the consultation, then the note written from it. In challenge mode, find the planted errors yourself; "
        "in explain mode, see each error, why it matters, and how each judge did.", ctx, muted=True)]
    if not d.has_any_results:
        header.append(C.pending_block("Judge verdicts pending",
                                      "The judges have not been run yet, so the planted errors and answer key are "
                                      "shown but judge verdicts are not.", ctx))
    if not case.clinician_reviewed:
        header.append(C.body("This case is a draft awaiting clinician review.", ctx, size=13, muted=True, italic=True))
    parts = [*header, _controls(ctx, case, variant, cases, mode, judge)]
    if mode == "explain":
        parts.append(_key_row(ctx))
    parts.append(panes)
    return ft.Column(parts, spacing=16)
