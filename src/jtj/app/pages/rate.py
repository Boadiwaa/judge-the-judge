"""Rate notes: blinded clinician rating and flag adjudication (BUILD_SPEC §3.3.4).

Raters see transcript + note only: no answer key, no tier colours, no judge output and no variant
label. Note order is randomised with a seed per rater. Ratings go to SQLite (RATINGS_DB).
"""
from __future__ import annotations

import hmac
import os
import random

import flet as ft

from .. import components as C
from .. import rating_status as R
from ..data import sentences
from ...schema import ERROR_TYPES, SECTION_LABELS, SECTIONS
from .explorer import _dropdown, _pane, _segmented, _transcript

OVERALL = [("safe_as_is", "Safe to file as is"), ("needs_minor_edits", "Needs minor edits"),
           ("needs_major_edits", "Needs major edits"), ("unsafe", "Unsafe")]
OTHER_TYPE = ("OTHER", "Other / not sure")


def _order(rater_id: int, items: list[str]) -> list[str]:
    out = sorted(items)
    random.Random(f"jtj-rater-{rater_id}").shuffle(out)
    return out


# ---------------------------------------------------------------- sign-in


def _sign_in(ctx: C.Ctx) -> ft.Control:
    code = ft.TextField(label="Rater code", password=True, can_reveal_password=True, width=320)
    initials = ft.TextField(label="Your initials", width=320, max_length=6)
    role = ft.TextField(label="Professional role (e.g. GP, ED registrar)", width=320, max_length=60)
    err = C.body("", ctx, size=14, color=ctx.p.tier["High"][0])

    def submit(e):
        expected = os.environ.get("RATER_CODE", "")
        if not hmac.compare_digest((code.value or "").strip(), expected):
            err.value = "That rater code isn't right."
        elif not (initials.value or "").strip() or not (role.value or "").strip():
            err.value = "Please enter your initials and role."
        else:
            rid = R.get_or_create_rater(initials.value.strip().upper(), role.value.strip())
            ctx.state["rater"] = {"id": rid, "initials": initials.value.strip().upper()}
            ctx.rerender()
            return
        err.update()

    return C.card(ft.Column([
        C.h3("Sign in to rate", ctx),
        C.body("You'll see consultation transcripts and the notes written from them, without the answer key or "
               "any judge output. Please rate independently and don't discuss notes with other raters.", ctx,
               size=14, muted=True),
        code, initials, role, err,
        ft.FilledButton("Start rating", icon=ft.Icons.ARROW_FORWARD, on_click=submit),
    ], spacing=12), ctx, padding=28)


# ---------------------------------------------------------------- note rating


def _draft(ctx: C.Ctx, vid: str) -> dict:
    return ctx.state.setdefault("rate_drafts", {}).setdefault(
        vid, {"spans": [], "overall": None, "comment": "", "sel": None,
              "form": {"type": None, "severity": None, "likelihood": None, "comment": ""}})


def _note_for_rating(ctx: C.Ctx, vid: str, dr: dict) -> ft.Control:
    notes = ctx.data.notes[vid]
    marked = {(s["section"], s["start"]) for s in dr["spans"]}
    blocks = []
    for sec in SECTIONS:
        text = notes[sec]
        spans = []
        for a, b in sentences(text):
            is_sel = dr["sel"] and dr["sel"]["section"] == sec and dr["sel"]["start"] == a
            style = ft.TextStyle()
            if (sec, a) in marked:
                style = ft.TextStyle(bgcolor=ctx.p.accent_soft, decoration=ft.TextDecoration.UNDERLINE,
                                     decoration_color=ctx.p.accent, decoration_thickness=2)
            if is_sel:
                style = ft.TextStyle(bgcolor=ctx.p.warn_bg, decoration=ft.TextDecoration.UNDERLINE,
                                     decoration_color=ctx.p.warn_text, decoration_thickness=2)

            def pick(e, sec=sec, a=a, b=b, text=text):
                dr["sel"] = {"section": sec, "start": a, "end": b, "text": text[a:b]}
                ctx.rerender()

            spans.append(ft.TextSpan(text[a:b] + " ", style, on_click=pick))

        def pick_missing(e, sec=sec):
            dr["sel"] = {"section": sec, "start": -1, "end": -1, "text": f"[Something missing in {SECTION_LABELS[sec]}]"}
            ctx.rerender()

        chip = ft.Container(C.body("Something's missing here", ctx, size=12, muted=True), on_click=pick_missing,
                            border=ft.Border.all(1, ctx.p.border), border_radius=999,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=3))
        body = ft.Text(spans=spans, size=15, color=ctx.p.text) if text else C.body("(empty)", ctx, size=14, muted=True)
        blocks.append(ft.Column([ft.Row([C.eyebrow(SECTION_LABELS[sec], ctx, ctx.p.text_muted), chip],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True), body], spacing=4))
    return ft.Column(blocks, spacing=14)


def _span_form(ctx: C.Ctx, dr: dict) -> ft.Control:
    sel, f = dr["sel"], dr["form"]
    nums = [(str(i), str(i)) for i in range(1, 6)]

    def set_field(k, v):
        f[k] = v
        ctx.rerender()

    def comment_changed(e):
        f["comment"] = e.control.value

    def add(e):
        if not (f["type"] and f["severity"] and f["likelihood"]):
            return
        dr["spans"].append({**sel, "type": f["type"], "severity": int(f["severity"]),
                            "likelihood": int(f["likelihood"]), "comment": f["comment"]})
        dr["sel"] = None
        dr["form"] = {"type": None, "severity": None, "likelihood": None, "comment": ""}
        ctx.rerender()

    def cancel(e):
        dr["sel"] = None
        ctx.rerender()

    ready = bool(f["type"] and f["severity"] and f["likelihood"])
    return ft.Container(ft.Column([
        C.body("Selected:", ctx, size=13, muted=True),
        C.body(f"“{sel['text']}”", ctx, size=14, weight=ft.FontWeight.W_600),
        _dropdown(f["type"], list(ERROR_TYPES.items()) + [OTHER_TYPE], lambda e: set_field("type", e.control.value),
                  ctx),
        C.body("Severity (1 negligible – 5 catastrophic)", ctx, size=13, muted=True),
        _segmented(nums, f["severity"] or "", lambda v: set_field("severity", v), ctx),
        C.body("Likelihood of harm (1 very unlikely – 5 very likely)", ctx, size=13, muted=True),
        _segmented(nums, f["likelihood"] or "", lambda v: set_field("likelihood", v), ctx),
        ft.TextField(label="Comment (optional)", value=f["comment"], on_change=comment_changed, multiline=True,
                     min_lines=1, max_lines=3, dense=True),
        ft.Row([ft.FilledButton("Add error", on_click=add, disabled=not ready), ft.TextButton("Cancel", on_click=cancel)]),
    ], spacing=8), bgcolor=ctx.p.surface_alt, border_radius=10, padding=14)


def _rating_panel(ctx: C.Ctx, vid: str, dr: dict, rater_id: int) -> ft.Control:
    items: list[ft.Control] = [
        C.body("Click any sentence you think is wrong, or “Something's missing here”. Then rate the whole "
               "note.", ctx, size=14, muted=True)]
    if dr["sel"]:
        items.append(_span_form(ctx, dr))
    items.append(C.eyebrow(f"Errors you've marked ({len(dr['spans'])})", ctx, ctx.p.text_muted))
    for i, s in enumerate(dr["spans"]):
        def remove(e, i=i):
            dr["spans"].pop(i)
            ctx.rerender()

        label = dict(ERROR_TYPES, OTHER=OTHER_TYPE[1]).get(s["type"], s["type"])
        items.append(ft.Container(ft.Row([
            ft.Column([C.body(s["text"][:90] + ("…" if len(s["text"]) > 90 else ""), ctx, size=13),
                       C.body(f"{label} · S{s['severity']} × L{s['likelihood']}", ctx, size=12, muted=True)],
                      spacing=2, expand=True),
            ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Remove", on_click=remove, icon_color=ctx.p.text_muted),
        ]), border=ft.Border.all(1, ctx.p.border), border_radius=8, padding=8))
    if not dr["spans"]:
        items.append(C.body("None yet. It's fine to find no errors.", ctx, size=13, muted=True))

    def set_overall(v):
        dr["overall"] = v
        ctx.rerender()

    def comment_changed(e):
        dr["comment"] = e.control.value

    def save(e):
        if not dr["overall"]:
            return
        R.save_note(rater_id, vid, dr["overall"], dr["comment"], dr["spans"])
        ctx.state["rate_drafts"].pop(vid, None)
        ctx.rerender()

    items += [
        C.eyebrow("Whole-note rating", ctx, ctx.p.text_muted),
        ft.Column([_segmented([o], dr["overall"] or "", set_overall, ctx) for o in OVERALL], spacing=6),
        ft.TextField(label="Comment on the note (optional)", value=dr["comment"], on_change=comment_changed,
                     multiline=True, min_lines=1, max_lines=4, dense=True),
        ft.FilledButton("Save and next", icon=ft.Icons.ARROW_FORWARD, on_click=save, disabled=not dr["overall"]),
    ]
    return ft.Column(items, spacing=10)


def _rate_notes(ctx: C.Ctx, rater: dict) -> ft.Control:
    d = ctx.data
    order = _order(rater["id"], list(d.notes))
    done = R.rated_variants(rater["id"])
    remaining = [v for v in order if v not in done]
    progress = ft.Column([
        ft.Row([C.body(f"{len(done)} of {len(order)} notes rated", ctx, size=14, weight=ft.FontWeight.W_600),
                C.body("20 notes each unlocks the agreement analysis", ctx, size=13, muted=True)],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
        ft.ProgressBar(value=len(done) / len(order), color=ctx.p.accent, bgcolor=ctx.p.surface_alt)], spacing=6)
    if not remaining:
        return ft.Column([progress, C.card(C.body("You've rated every note. Thank you!", ctx), ctx)], spacing=14)
    vid = remaining[0]
    case, _ = d.variant(vid)
    dr = _draft(ctx, vid)
    n = len(done) + 1
    panes = ft.ResponsiveRow([
        _transcript(ctx, case, set()),
        _pane(f"Note {n}", "blind: answer key and judges hidden", _note_for_rating(ctx, vid, dr), ctx),
        _pane("Your rating", "", _rating_panel(ctx, vid, dr, rater["id"]), ctx),
    ], spacing=18, run_spacing=18, vertical_alignment=ft.CrossAxisAlignment.START)
    return ft.Column([progress, panes], spacing=14)


# ---------------------------------------------------------------- adjudication


def _adjudicate(ctx: C.Ctx, rater: dict) -> ft.Control:
    d = ctx.data
    if not d.flags:
        return C.pending_block("No judge flags yet", "Flags appear here after the judges have run. Each is a judge "
                               "finding that matched no planted error.", ctx)
    by_id = {f["flag_id"]: f for f in d.flags}
    order = _order(rater["id"], list(by_id))
    done = R.adjudicated_flags(rater["id"])
    remaining = [f for f in order if f not in done]
    head = ft.Column([C.body(f"{len(done)} of {len(order)} flags reviewed", ctx, size=14, weight=ft.FontWeight.W_600),
                      ft.ProgressBar(value=len(done) / len(order), color=ctx.p.accent, bgcolor=ctx.p.surface_alt)],
                     spacing=6)
    if not remaining:
        return ft.Column([head, C.card(C.body("You've reviewed every flag. Thank you!", ctx), ctx)], spacing=14)
    flag = by_id[remaining[0]]
    fi = flag["finding"]
    case, _ = d.variant(flag["variant_id"])
    comment = ft.TextField(label="Comment (optional)", multiline=True, min_lines=1, max_lines=3, dense=True)

    def verdict(v):
        R.save_adjudication(rater["id"], flag["flag_id"], v, comment.value or "")
        ctx.rerender()

    note_text = "\n\n".join(f"{SECTION_LABELS[s].upper()}\n{d.notes[flag['variant_id']][s]}" for s in SECTIONS)
    panel = ft.Column([
        C.body("An automated judge raised this. It does not match any error we planted, so it may be a false alarm "
               "or a genuine problem in the note.", ctx, size=14, muted=True),
        C.eyebrow("Judge's finding", ctx, ctx.p.text_muted),
        C.body(f"Note text: “{fi.get('note_span') or '(says something is missing)'}”", ctx, size=14,
               weight=ft.FontWeight.W_600),
        C.body(fi.get("rationale") or "", ctx, size=14),
        C.body(f"Transcript evidence it cited: “{fi.get('transcript_evidence')}”", ctx, size=13, muted=True)
        if fi.get("transcript_evidence") else ft.Container(),
        C.h3("Is this a real error?", ctx),
        ft.Row([ft.FilledButton("Yes", on_click=lambda e: verdict("yes")),
                ft.OutlinedButton("No", on_click=lambda e: verdict("no")),
                ft.TextButton("Unsure", on_click=lambda e: verdict("unsure"))], wrap=True),
        comment,
    ], spacing=10)
    return ft.Column([head, ft.ResponsiveRow([
        _transcript(ctx, case, set(fi.get("evidence_turns") or [])),
        _pane("Note", "", C.body(note_text, ctx, size=14, selectable=True), ctx),
        _pane("Flag", "", panel, ctx),
    ], spacing=18, run_spacing=18, vertical_alignment=ft.CrossAxisAlignment.START)], spacing=14)


# ---------------------------------------------------------------- page


def build(ctx: C.Ctx) -> ft.Control:
    head = [C.eyebrow("Clinician raters", ctx), C.h2("Rate notes", ctx)]
    if not os.environ.get("RATER_CODE"):
        return ft.Column(head + [C.pending_block(
            "Rater mode disabled", "Rater mode is disabled on this deployment (no rater code is set). If you are a "
            "clinician who has been invited to rate notes, please use the link you were sent.", ctx)], spacing=14)
    rater = ctx.state.get("rater")
    if not rater:
        return ft.Column(head + [_sign_in(ctx)], spacing=14)
    tab = ctx.query.get("tab", "notes")

    def sign_out(e):
        ctx.state.pop("rater", None)
        ctx.rerender()

    bar = ft.Row([
        _segmented([("notes", "Rate notes"), ("flags", "Review judge flags")], tab,
                   lambda v: ctx.go(f"/rate?tab={v}"), ctx),
        ft.Row([C.body(f"Signed in as {rater['initials']}", ctx, size=13, muted=True),
                ft.TextButton("Sign out", on_click=sign_out)], tight=True),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True)
    body = _rate_notes(ctx, rater) if tab == "notes" else _adjudicate(ctx, rater)
    owner = ft.TextButton("Study owner: export ratings (CSV)", icon=ft.Icons.DOWNLOAD, url="/export/ratings.zip",
                          style=ft.ButtonStyle(color=ctx.p.text_muted))
    return ft.Column(head + [bar, body, owner], spacing=14)
