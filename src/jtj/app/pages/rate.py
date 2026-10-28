"""Rate notes (clinician rater mode). Access gate only for now; the rating flow is phase 6."""
from __future__ import annotations

import os

import flet as ft

from .. import components as C


def build(ctx: C.Ctx) -> ft.Control:
    enabled = bool(os.environ.get("RATER_CODE"))
    msg = ("Rater mode is being built. Clinicians will rate notes blind to the answer key and the judges, in a "
           "randomised order, and review judge flags one at a time.") if enabled else (
        "Rater mode is disabled on this deployment (no rater code is set). If you are a clinician who has been "
        "invited to rate notes, please use the link you were sent.")
    return ft.Column([
        C.eyebrow("Clinician raters", ctx), C.h2("Rate notes", ctx),
        C.pending_block("Not available yet" if enabled else "Rater mode disabled", msg, ctx),
        C.body("Ratings are stored only for this study, and are used to measure how well the judges agree with "
               "clinicians.", ctx, size=14, muted=True),
    ], spacing=14)
