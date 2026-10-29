"""App smoke tests (BUILD_SPEC §7): every page builds without exceptions with (a) no results and
(b) full results. The "full results" here are synthetic judge outputs generated in a temp dir for the
test only; they are never written to data/ and never shown in the app.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import flet as ft
import pytest

from jtj import protocol
from jtj.app import components as C
from jtj.app import theme
from jtj.app.data import AppData, load
from jtj.app.main import PAGES
from jtj.metrics import compute_all
from jtj.mutate import build_variant_notes, load_cases
from jtj.schema import TIERS

QUERIES = [{}, {"mode": "explain"}, {"mode": "explain", "error": "case_07_a_e2"}, {"variant": "clean", "mode": "explain"},
           {"type": "LATERALITY"}, {"tier": "High+"}, {"setting": "REMOTE", "mode": "challenge"},
           {"missed": "J2", "mode": "explain"}, {"error": "does_not_exist"}, {"subtle": "subtle"},
           {"subtle": "obvious", "type": "DRUG_NAME", "missed": "J1"}]
PAGE_QUERIES = {"/explorer": QUERIES, "/protocol": [{}, {"section": "external-validity"}, {"section": "nope"}]}


def make_ctx(data: AppData, narrow=False, dark=False, query=None):
    page = SimpleNamespace(theme_mode=ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT,
                           platform_brightness=ft.Brightness.LIGHT)
    return C.Ctx(page=page, data=data, p=theme.DARK if dark else theme.LIGHT, narrow=narrow, go=lambda r: None,
                 rerender=lambda: None, query=query or {}, state={}, after=[])


@pytest.fixture(scope="module")
def empty():
    d = load()
    return AppData(cases=d.cases, notes=d.notes, summary=d.summary)


@pytest.fixture(scope="module")
def full(tmp_path_factory):
    """Synthetic judge outputs: each judge 'finds' a deterministic subset of errors plus one stray flag."""
    tmp = tmp_path_factory.mktemp("outputs")
    cases = load_cases()
    for j, keep in (("J0", 3), ("J1", 2), ("J2", 1)):
        (tmp / j).mkdir()
        for c in cases:
            for v in c.variants:
                fs = [{"type": m.type, "note_span": m.mutated_text, "transcript_evidence": m.original_text,
                       "severity": m.seeded_severity, "likelihood": max(1, m.seeded_likelihood - 1),
                       "rationale": "test"} for i, m in enumerate(v.mutations) if i % keep == 0]
                fs.append({"type": "UNSPECIFIED", "note_span": "stray flag text for testing", "rationale": "test"})
                (tmp / j / f"{v.variant_id}.json").write_text(json.dumps({"output": {"findings": fs}}))
    res = compute_all(cases, tmp, n_boot=50)
    notes = {}
    for c in cases:
        notes.update(build_variant_notes(c))
    from jtj.metrics import answer_key_summary

    d = AppData(cases=cases, notes=notes, summary=answer_key_summary(cases), metrics=res["metrics"],
                matches=res["matches"], flags=res["flags"])
    assert d.complete
    return d


@pytest.mark.parametrize("route", list(PAGES))
@pytest.mark.parametrize("narrow,dark", [(False, False), (True, True)])
def test_pages_build_without_results(empty, route, narrow, dark):
    for q in PAGE_QUERIES.get(route, [{}]):
        assert PAGES[route](make_ctx(empty, narrow, dark, q)) is not None


@pytest.mark.parametrize("route", list(PAGES))
def test_pages_build_with_full_results(full, route):
    for q in PAGE_QUERIES.get(route, [{}]):
        assert PAGES[route](make_ctx(full, query=q)) is not None
    assert set(full.metrics["per_judge"]["J1"]["by_subtlety"]) == {"subtle", "obvious"}


def test_challenge_reveal_scoring(empty):
    """Marking the sentence with the wrong side and the missing-allergy section catches 2 of 3."""
    from jtj.app.pages import explorer
    from jtj.app.data import sentences

    ctx = make_ctx(empty, query={"case": "case_07", "variant": "a"})
    st = explorer._challenge_state(ctx, "case_07_a")
    text = empty.notes["case_07_a"]["examination"]
    idx = next(i for i, (a, b) in enumerate(sentences(text)) if "right lateral malleolus" in text[a:b])
    st["marks"].add(("examination", idx))
    st["missing"].add("medications_allergies")
    st["revealed"] = True
    panel = explorer._challenge_panel(ctx, *empty.variant("case_07_a"))
    title = panel.controls[0].value
    assert title == "You caught 2 of 3 planted errors."


def test_every_seeded_error_is_locatable_in_its_note(empty):
    for c in empty.cases:
        for v in c.variants:
            for m in v.mutations:
                spans = [s for s in empty.spans(v.variant_id, m.section) if s.mutation.error_id == m.error_id]
                assert spans, m.error_id


def _lum(hex_):
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.mark.parametrize("pal", [theme.LIGHT, theme.DARK], ids=["light", "dark"])
def test_tier_and_text_colours_meet_wcag_aa(pal):
    for t in TIERS:
        fg, bg, _ = pal.tier[t]
        assert contrast(fg, bg) >= 4.5, (t, contrast(fg, bg))
    assert contrast(pal.flag[0], pal.flag[1]) >= 4.5
    assert contrast(pal.text, pal.surface) >= 4.5
    assert contrast(pal.text_muted, pal.surface) >= 4.5
    assert contrast(pal.warn_text, pal.warn_bg) >= 4.5
    assert contrast(pal.on_accent, pal.accent) >= 4.5


def test_protocol_markdown_has_all_sections_and_prompts(empty):
    md = protocol.markdown(empty.cases)
    for heading in ("Background", "Related work", "Error taxonomy", "Matching rule", "Sample size",
                    "External validity: why seeded errors", "Limitations", "References"):
        assert f"## {heading}" in md
    assert "J2 · Step 2 user" in md and "246 high-risk errors" in md
    assert "`DRUG_NAME`" in md and "subtle vs obvious" in md


def test_protocol_deep_link_shows_section_first(empty):
    page = PAGES["/protocol"](make_ctx(empty, query={"section": "external-validity"}))
    first = page.controls[1].content.controls[0]  # controls[0] is the page header
    assert first.value == "External validity: why seeded errors"


def test_related_work_citations_resolve_to_references():
    import re

    cited = {int(n) for n in re.findall(r"\[(\d+)\]", protocol.RELATED_WORK)}
    assert cited == set(range(1, len(protocol.REFERENCES) + 1))  # every reference cited, none missing


@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
def test_heatmap_cells_meet_wcag_aa(empty, dark):
    from jtj.app.pages.scorecard import _cell_color

    ctx = make_ctx(empty, dark=dark)
    for i in range(11):
        bg, fg = _cell_color(i / 10, ctx)
        assert contrast(fg, bg) >= 4.5, (i, bg, fg)


def test_web_shell_has_title_preview_and_icons():
    """The custom index.html replaces Flet's defaults, and every file it or the manifest points to exists."""
    import json
    import re

    assets = Path(__file__).resolve().parents[1] / "src" / "jtj" / "app" / "assets"
    html = (assets / "index.html").read_text()
    assert "<title>Judge the Judge</title>" in html and "Flet application" not in html
    for tag in ("og:title", "og:description", "og:image", "twitter:card"):
        assert f'"{tag}"' in html
    local = re.findall(r'(?:href|src)="((?:icons/)?[\w.-]+\.png)"', html)
    local += [i["src"] for i in json.loads((assets / "manifest.json").read_text())["icons"]]
    assert local and all((assets / p).exists() for p in local), local
    assert (assets / "og-image.png").exists() and (assets / "favicon.png").exists()
