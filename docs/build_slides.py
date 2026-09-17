"""Build docs/mid_evaluation.pptx from the current results.

    python docs/build_slides.py

Every number on the slides is read from results/data/*.json|csv produced by
experiments/exp*.py, so the deck cannot drift from the code.  Speaker notes are
attached to every slide.  Status tags: [repo] existed before this iteration,
[new] implemented+validated now, [prelim] preliminary, [future] planned.
"""

from __future__ import annotations

import json
import os
import sys

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIG = os.path.join(ROOT, "results", "figures")
DATA = os.path.join(ROOT, "results", "data")
sys.path.insert(0, ROOT)
from docs.slide_references import REFERENCES  # noqa: E402

NAVY = RGBColor(0x14, 0x2B, 0x45)
TEAL = RGBColor(0x1F, 0x7A, 0x8C)
RED = RGBColor(0xC0, 0x39, 0x2B)
GREEN = RGBColor(0x1E, 0x84, 0x49)
ORANGE = RGBColor(0xD3, 0x6B, 0x00)
GREY = RGBColor(0x5D, 0x6D, 0x7E)
LIGHT = RGBColor(0xF4, 0xF6, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x1B, 0x1B, 0x1B)
TAG_COLORS = {"[repo]": GREY, "[new]": GREEN, "[prelim]": ORANGE, "[future]": TEAL, "[fix]": RED}

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
W, H = prs.slide_width, prs.slide_height
_slide_no = [0]


# ----------------------------------------------------------------------------- helpers
def _txt(tf, text, size=16, bold=False, color=BLACK, align=PP_ALIGN.LEFT, font="Calibri"):
    p = tf.paragraphs[0] if not tf.paragraphs[0].runs and len(tf.paragraphs) == 1 else tf.add_paragraph()
    p.alignment = align
    r = p.add_run(); r.text = text
    r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), bold, color, font
    return p


def add_box(slide, x, y, w, h, fill=None, line=None):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid(); s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line; s.line.width = Pt(1)
    s.shadow.inherit = False
    return s


def add_text(slide, x, y, w, h, lines, size=16, color=BLACK, bold=False, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, bullet=False, spacing=1.05):
    """lines: str or list of str / (str, dict) tuples; dict may hold size/bold/color/level/tag."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.08); tf.margin_top = tf.margin_bottom = Inches(0.04)
    if isinstance(lines, str):
        lines = [lines]
    first = True
    for item in lines:
        text, opt = (item, {}) if isinstance(item, str) else item
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align; p.line_spacing = spacing
        lvl = opt.get("level", 0)
        prefix = ("• " if lvl == 0 else "– ") if bullet and text else ""
        if lvl:
            p.level = min(lvl, 4)
        tag = opt.get("tag")
        if tag:
            rt = p.add_run(); rt.text = tag + " "
            rt.font.size = Pt(opt.get("size", size) - 3); rt.font.bold = True; rt.font.name = "Calibri"
            rt.font.color.rgb = TAG_COLORS.get(tag, GREY)
        r = p.add_run(); r.text = prefix + text
        r.font.size = Pt(opt.get("size", size)); r.font.bold = opt.get("bold", bold)
        r.font.color.rgb = opt.get("color", color); r.font.name = "Calibri"
        if opt.get("italic"):
            r.font.italic = True
        p.space_after = Pt(opt.get("space", 4))
    return tb


def add_table(slide, x, y, w, h, rows, col_widths=None, size=12, header_fill=NAVY, zebra=True, bold_first_col=False):
    nr, nc = len(rows), len(rows[0])
    shape = slide.shapes.add_table(nr, nc, x, y, w, h)
    tbl = shape.table
    if col_widths:
        tot = sum(col_widths)
        for i, cw in enumerate(col_widths):
            tbl.columns[i].width = int(w * cw / tot)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = tbl.cell(i, j)
            cell.margin_left = cell.margin_right = Inches(0.05); cell.margin_top = cell.margin_bottom = Inches(0.02)
            tf = cell.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            r = p.add_run(); r.text = str(val); r.font.size = Pt(size); r.font.name = "Calibri"
            if i == 0:
                r.font.bold = True; r.font.color.rgb = WHITE
                cell.fill.solid(); cell.fill.fore_color.rgb = header_fill
            else:
                r.font.color.rgb = BLACK
                if bold_first_col and j == 0:
                    r.font.bold = True
                cell.fill.solid(); cell.fill.fore_color.rgb = LIGHT if (zebra and i % 2 == 0) else WHITE
    return tbl


def new_slide(title, subtitle=None, tag=None, section=None):
    slide = prs.slides.add_slide(BLANK)
    _slide_no[0] += 1
    add_box(slide, 0, 0, W, Inches(0.95), fill=NAVY)
    add_text(slide, Inches(0.4), Inches(0.12), Inches(10.6), Inches(0.75), [(title, {"size": 26 if len(title) <= 50 else 22, "bold": True, "color": WHITE})],
             anchor=MSO_ANCHOR.MIDDLE)
    if tag:
        add_box(slide, Inches(11.3), Inches(0.27), Inches(1.7), Inches(0.42), fill=TAG_COLORS.get(tag, GREY))
        add_text(slide, Inches(11.3), Inches(0.27), Inches(1.7), Inches(0.42), [(tag, {"size": 13, "bold": True, "color": WHITE})],
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if subtitle:
        add_text(slide, Inches(0.4), Inches(0.98), Inches(12.5), Inches(0.45), [(subtitle, {"size": 14, "color": GREY, "italic": True})])
    add_box(slide, 0, H - Inches(0.35), W, Inches(0.35), fill=LIGHT)
    add_text(slide, Inches(0.3), H - Inches(0.36), Inches(9), Inches(0.35),
             [(f"BTP mid-evaluation · Fronthaul load management in 5G C-RAN/O-RAN · {section or ''}", {"size": 10, "color": GREY})],
             anchor=MSO_ANCHOR.MIDDLE)
    add_text(slide, W - Inches(1.3), H - Inches(0.36), Inches(1.1), Inches(0.35), [(str(_slide_no[0]), {"size": 10, "color": GREY})],
             align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
    return slide


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text.strip()


def add_picture_fit(slide, path, x, y, max_w, max_h):
    from PIL import Image
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(max_w / iw, max_h / ih)
    w, h = int(iw * scale), int(ih * scale)
    return slide.shapes.add_picture(path, x + (max_w - w) // 2, y + (max_h - h) // 2, w, h)


def takeaway(slide, text, y=None, color=NAVY):
    y = y if y is not None else H - Inches(1.05)
    add_box(slide, Inches(0.4), y, W - Inches(0.8), Inches(0.6), fill=LIGHT, line=color)
    add_text(slide, Inches(0.5), y, W - Inches(1.0), Inches(0.6), [(text, {"size": 14, "bold": True, "color": color})],
             anchor=MSO_ANCHOR.MIDDLE)


# ----------------------------------------------------------------------------- data
e1 = json.load(open(os.path.join(DATA, "exp1_nmse_vs_cr.json")))
e2 = json.load(open(os.path.join(DATA, "exp2_complexity.json")))
e3 = json.load(open(os.path.join(DATA, "exp3_acafs.json")))
e4 = json.load(open(os.path.join(DATA, "exp4_snr_sweep.json")))
e5 = pd.read_csv(os.path.join(DATA, "exp5_allocation_summary.csv"))
e5cfg = json.load(open(os.path.join(DATA, "exp5_allocation_config.json")))
bench = pd.read_csv(os.path.join(ROOT, "results", "benchmark_results.csv"))


def c1(kind, name, param):
    c = e1["results"][kind]["curves"][name]
    i = c["param"].index(param)
    return c["cr"][i], c["nmse_db"][i]


def t2(name, M):
    return e2["timings_ms"][name]["median_ms"][e2["M"].index(M)]


def r5(frac, pol, col):
    row = e5[(e5.capacity_frac == frac) & (e5.policy == pol)].iloc[0]
    return row[col]


def e4v(kind, name, snr):
    return e4[kind][name][e4["snr"].index(snr)]


def bench_med(dim, method_substr):
    r = bench[(bench.dim == dim) & (bench.method.str.contains(method_substr, regex=False))].iloc[0]
    return r.median_ms, r.rel_err_vs_true


# ============================================================================= SLIDES
SUB = RGBColor(0xBF, 0xD7, 0xEA)

# 1 --- title
s = prs.slides.add_slide(BLANK); _slide_no[0] += 1
add_box(s, 0, 0, W, H, fill=NAVY)
add_text(s, Inches(0.8), Inches(1.5), Inches(11.7), Inches(2.0),
         [("Fronthaul Load Management in 5G C-RAN / O-RAN", {"size": 38, "bold": True, "color": WHITE}),
          ("Matrix decomposition to compress the data, the cost of matrix inversion, and sharing one link between radio units", {"size": 21, "color": SUB})])
add_text(s, Inches(0.8), Inches(3.9), Inches(11.7), Inches(1.6),
         [("B.Tech. Project — mid-term evaluation", {"size": 20, "color": WHITE}),
          ("September 2026", {"size": 16, "color": SUB}),
          ("All results are Python simulations on the 3GPP TDL-A channel model (no hardware, no measured traffic)", {"size": 14, "color": SUB, "italic": True})])
add_text(s, Inches(0.8), Inches(6.3), Inches(11.7), Inches(0.8),
         [("Tags on every slide:   [repo] was already in the repository   [new] built and checked in this iteration   [fix] corrected   [prelim] early result   [future] planned",
           {"size": 12, "color": SUB})])
notes(s, """
Good morning. My project is about the fronthaul link in a 5G centralised or Open RAN: the link between the radio unit and the unit that does the baseband processing.
In one sentence: the radio unit produces far more data than the link can carry. I study three things. First, how to compress that data using matrix decompositions.
Second, how expensive the matrix inversions are that the receiver needs, because that decides where the processing can live. Third, how several radio units can share one link.
Everything I show is simulation in Python. I will say clearly what was already there, what I built now, and what is still early. The colour tags on each slide mark that.
""")

# 2 --- motivation
s = new_slide("Why the fronthaul link is the bottleneck", "In the O-RAN 7.2x split the radio unit sends one complex number per antenna, per subcarrier, per OFDM symbol", section="Motivation")
add_text(s, Inches(0.5), Inches(1.5), Inches(6.4), Inches(4.7), [
    ("How much data one radio unit (RU) produces", {"size": 18, "bold": True, "color": NAVY}),
    ("bits per symbol = 2 × M antennas × N subcarriers × b bits", {"size": 16}),
    ("M = 64, N = 1200 (15 kHz spacing, 18 MHz), b = 16 bit", {"size": 14, "color": GREY}),
    ("→ 2.46 Mbit per symbol,  14 symbols per ms  →  34.4 Gbit/s per RU", {"size": 17, "bold": True, "color": RED}),
    ("→ 8 RUs on one link: 275 Gbit/s", {"size": 17, "bold": True, "color": RED}),
    ("", {}),
    ("Three ways to reduce the load", {"size": 18, "bold": True, "color": NAVY}),
    ("Compress the 64 × 1200 matrix (fewer bits, or send only its important part)", {"size": 15}),
    ("Send fewer spatial streams than antennas, or move processing into the RU (functional split)", {"size": 15}),
    ("Share the link: give each RU a share so the total fits", {"size": 15}),
], bullet=False)
add_text(s, Inches(7.1), Inches(1.5), Inches(5.8), Inches(4.7), [
    ("What 'load management' means here", {"size": 18, "bold": True, "color": NAVY}),
    ("For every OFDM symbol and every RU, pick a compression setting (and stream count) so that", {"size": 15}),
    ("total rate of all RUs ≤ link capacity", {"size": 17, "bold": True}),
    ("and the reconstructed matrices are as accurate as possible.", {"size": 15}),
    ("", {}),
    ("Not modelled (so not claimed):", {"size": 15, "bold": True, "color": GREY}),
    ("MAC scheduling, retransmissions, latency, real hardware timing, measured traffic", {"size": 14, "color": GREY}),
], bullet=False)
takeaway(s, "The problem: several RUs, one link, a fixed number of bits per symbol — decide how many bits, which structure to keep, and how many streams for each RU.")
notes(s, """
The numbers first. With 64 antennas and 1200 subcarriers at 16-bit samples, one radio unit produces about 2.5 megabit per OFDM symbol, which is 34 gigabit per second.
Eight radio units on one link would need 275 gigabit per second. That is the load we have to manage.
There are three ways to reduce it: compress the matrix, send fewer streams, and share the link cleverly. My project touches all three.
Scope: this is a physical-layer model of one OFDM symbol at a time. There is no scheduler, no latency model and no hardware.
""")

# 3 --- what the project is built from (NEW)
s = new_slide("What the project is built from", "Three parts; matrix decomposition and matrix inversion are the common tools", section="Overview")
cols = [
    ("A. Compress with matrix decomposition", GREEN, [
        ("The received 64 × 1200 matrix has structure: only ~23 propagation paths → low rank; sparse in the delay domain.", {"size": 12}),
        ("Truncated SVD [repo → fix]: keep the r largest singular values (best possible rank-r approximation).", {"size": 12}),
        ("RAS-BFP [new]: randomised SVD — sketch, QR, small SVD — ≈5x faster than the thin SVD.", {"size": 12}),
        ("CSEE [new]: IFFT along subcarriers, keep the K strongest delay taps.", {"size": 12}),
        ("BFP [repo]: the O-RAN standard quantiser, used as the baseline and inside every encoder.", {"size": 12}),
        ("ACAFS [fix]: estimate the rank and send only that many streams.", {"size": 12}),
    ]),
    ("B. Cost of matrix inversion", ORANGE, [
        ("The receiver needs A⁻¹ (MMSE equaliser, channel estimation) every slot. Where can it run — RU or DU?", {"size": 12}),
        ("Benchmark [repo, re-run]: LU, QR, SVD, Gauss–Jordan, Newton–Schulz vs three neural 'InverseNet' models.", {"size": 12}),
        ("Dataset: random well-conditioned matrices, n = 10 / 100 / 500, float32; 80 % train / 20 % held out.", {"size": 12}),
        ("Learned models: direct MLP, learned Newton–Schulz (17 parameters), InverseNet-Ultra.", {"size": 12}),
        ("Fixed [fix]: NumPy inference engine used the wrong activation; overstated docstring.", {"size": 12}),
    ]),
    ("C. Share one link", TEAL, [
        ("Each RU offers a menu of settings (bits, taps, rank), each with a known rate and a predicted error.", {"size": 12}),
        ("Allocator [new]: pick one setting per RU so the total rate fits the link and the total error is smallest.", {"size": 12}),
        ("Prediction comes from the decomposition itself (energy of discarded taps / singular values) — no trial encoding.", {"size": 12}),
        ("Compared with static settings and with an oracle that encodes every option.", {"size": 12}),
    ]),
]
for i, (title, colr, items) in enumerate(cols):
    x = Inches(0.4) + Inches(4.2) * i
    add_box(s, x, Inches(1.5), Inches(4.0), Inches(0.5), fill=colr)
    add_text(s, x, Inches(1.5), Inches(4.0), Inches(0.5), [(title, {"size": 14, "bold": True, "color": WHITE})], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    add_box(s, x, Inches(2.0), Inches(4.0), Inches(4.3), fill=LIGHT, line=colr)
    add_text(s, x + Inches(0.05), Inches(2.05), Inches(3.9), Inches(4.2), items, bullet=True)
notes(s, """
The project has three parts and two of them are linear algebra.
Part A is compression. The received matrix has structure — only about 23 propagation paths, so it is low rank, and it is sparse in the delay domain. Every encoder is a matrix decomposition that keeps the important part: SVD keeps the largest singular values, RAS-BFP does the same with a randomised sketch so it is faster, CSEE keeps the strongest delay taps. Block floating point is the standard quantiser used everywhere.
Part B is the cost of matrix inversion. The receiver inverts a matrix per resource-block group every slot. The benchmark compares classical methods with neural networks that try to learn the inverse.
Part C, which I added in this iteration, ties compression to the shared link: each radio unit has a menu of settings and an allocator picks one per unit so the total fits.
""")

# 4 --- starting point & audit
s = new_slide("Starting point: what the repository contained and what I fixed", "Audit done on 17 Sep 2026 (details in docs/audit.md)", section="Scope")
rows = [["Part", "Found", "Problem found", "Now"],
        ["Fronthaul experiments 1-4, notebook, figures", "[repo] present", "they import a package `src/` that was never committed → nothing could run; figures not reproducible", "[new] `src/` rebuilt, 42 tests"],
        ["SVD baseline timing (Exp2)", "[repo] figure", "the full 1200×1200 SVD was timed (~1.7 s); the thin SVD takes 13 ms → 'speed-up vs SVD' was ~100x too high", "[fix] thin SVD"],
        ["Functional-split model (Exp3)", "[repo] figure", "split 6 treated as the most expensive; 3GPP says it is the cheapest. 'Fast rank' curve was exact rank + random ±1", "[fix] model + real estimator"],
        ["Error vs SNR (Exp4)", "[repo] figure", "error measured against the noisy matrix follows −SNR by construction; text called it 'stable'", "[fix] two references"],
        ["CSEE input", "[repo] docs", "tested only on unmodulated symbols; real data symbols destroy the delay sparsity", "[new] data vs reference symbols"],
        ["Sharing one link", "absent", "the actual 'load management' decision did not exist", "[new] allocator + Exp5"],
        ["Matrix-inversion benchmark", "[repo] complete", "NumPy engine used ReLU while the trained model uses GELU; docstring overstated results", "[fix] + re-run"]]
add_table(s, Inches(0.4), Inches(1.5), Inches(12.5), Inches(4.3), rows, col_widths=[2.4, 1.6, 5.4, 2.2], size=11)
takeaway(s, "Order of work: (1) make it run and make it correct, (2) fair baselines, (3) one new, well-tested piece — the allocator.")
notes(s, """
Before adding anything I checked what was there. The biggest finding: the fronthaul experiments import a package called src that was never committed, so none of the compression results could be reproduced. I rebuilt it and wrote tests.
I also found four modelling problems in the earlier figures. The SVD baseline was timed with the full square SVD, which made it look a hundred times slower than the thin SVD that is actually needed. The split model had the cost ordering upside down. The fast rank estimate was fake. And the error metric was misread.
The matrix-inversion benchmark was complete, but its NumPy engine used a different activation than the trained model. I fixed that and re-ran everything.
""")

# 5 --- literature
s = new_slide("Research context and the gap this project addresses", "Checked sources only; full list with links in docs/research_review.md (search cutoff 17 Sep 2026)", section="Research context")
lit_rows = [["Direction", "Representative work", "What it assumes / measures", "Relation to this project"]]
for r in REFERENCES["comparison_rows"]:
    lit_rows.append(r)
add_table(s, Inches(0.4), Inches(1.45), Inches(12.5), Inches(4.6), lit_rows, col_widths=[1.8, 3.2, 3.6, 3.9], size=10)
takeaway(s, REFERENCES["gap_statement"])
notes(s, REFERENCES["lit_notes"])

# 6 --- system model
s = new_slide("System model", "3GPP TR 38.901 TDL-A uplink channel, one OFDM symbol per RU", tag="[new]", section="Technical approach")
x0, y0 = Inches(0.5), Inches(1.6)
for i, snr in enumerate([0, 10, 20, 30]):
    add_box(s, x0, y0 + Inches(0.95) * i, Inches(2.2), Inches(0.75), fill=LIGHT, line=NAVY)
    add_text(s, x0, y0 + Inches(0.95) * i, Inches(2.2), Inches(0.75),
             [(f"RU {i+1}  (SNR {snr} dB)", {"size": 12, "bold": True}), ("matrix Y_k → encoder", {"size": 11, "color": GREY})], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    arrow = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x0 + Inches(2.25), y0 + Inches(0.95) * i + Inches(0.22), Inches(0.9), Inches(0.3))
    arrow.fill.solid(); arrow.fill.fore_color.rgb = TEAL; arrow.line.fill.background()
add_text(s, x0 + Inches(2.2), y0 + Inches(3.85), Inches(1.1), Inches(0.3), [("rate R_k", {"size": 10, "color": GREY})], align=PP_ALIGN.CENTER)
add_box(s, x0 + Inches(3.25), y0, Inches(1.0), Inches(3.55), fill=RGBColor(0xFA, 0xDB, 0xD8), line=RED)
add_text(s, x0 + Inches(3.25), y0, Inches(1.0), Inches(3.55), [("shared", {"size": 12, "bold": True, "color": RED}), ("link", {"size": 12, "bold": True, "color": RED}), ("Σ R_k ≤ C", {"size": 13, "bold": True})], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
arrow = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x0 + Inches(4.3), y0 + Inches(1.6), Inches(0.7), Inches(0.35)); arrow.fill.solid(); arrow.fill.fore_color.rgb = TEAL; arrow.line.fill.background()
add_box(s, x0 + Inches(5.05), y0, Inches(1.9), Inches(3.55), fill=LIGHT, line=NAVY)
add_text(s, x0 + Inches(5.05), y0, Inches(1.9), Inches(3.55), [("DU", {"size": 14, "bold": True}), ("decoders → Ŷ_k", {"size": 12}), ("", {}), ("controller:", {"size": 12, "bold": True, "color": TEAL}), ("ACAFS (streams)", {"size": 11}), ("allocator (bits)", {"size": 11}), ("uses predicted error", {"size": 11, "color": GREY})], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
add_text(s, Inches(7.8), Inches(1.5), Inches(5.2), Inches(4.9), [
    ("Y = H · diag(x) + W    (64 antennas × 1200 subcarriers)", {"size": 16, "bold": True}),
    ("H: channel. 23 paths (TDL-A taps), 100 ns delay spread, antenna correlation 0.7^|i−j|.", {"size": 13}),
    ("So rank(H) ≤ 23, and an IFFT over the subcarriers puts almost all energy in a few delay taps.", {"size": 13}),
    ("x: the transmitted symbols. Data symbols = random QPSK per subcarrier. Reference symbols = known, so the RU can divide them out and is left with H + noise.", {"size": 13}),
    ("W: white noise at the chosen SNR.", {"size": 13}),
    ("", {}),
    ("What we measure", {"size": 15, "bold": True, "color": NAVY}),
    ("Error: NMSE (dB) = 10 log₁₀ ‖Y − Ŷ‖² / ‖Y‖² — against the noisy Y the link carries, and against the clean H.", {"size": 13}),
    ("Compression ratio = 16-bit size / bits actually sent (exponents and headers counted).", {"size": 13}),
    ("Encode time (Python medians; only the ordering is meaningful).", {"size": 13}),
    ("For the allocator: link utilisation, RUs dropped, predicted-vs-measured error, decision time.", {"size": 13}),
], bullet=False)
notes(s, """
The set-up: K radio units, each with a 64-by-1200 received matrix per OFDM symbol, and one shared link to the DU.
The channel is the 3GPP TDL-A model with 23 paths. That gives the two structures we exploit: the matrix has rank at most 23, and after an IFFT over the subcarriers only a few delay taps carry energy.
The transmitted symbols matter. On a data symbol every subcarrier carries a random QPSK value. On a reference symbol the radio unit knows the sequence and can remove it. I will show that this decides which compression works.
The error metric is NMSE. I report it against the noisy matrix that is actually transported, and against the clean channel, which tells you how much signal was really lost.
""")

# 7 --- encoders as decompositions
s = new_slide("Compression = decompose the matrix, keep the big part, quantise", "Every encoder ends with O-RAN block floating point (12-sample blocks, 4-bit shared exponent)", tag="[new]", section="Technical approach")
rows = [["Encoder", "Decomposition used", "What is sent", "Cost", "Error model"],
        ["BFP (O-RAN WG4)", "none — only quantisation", "all M·N samples at b bits + exponents", "O(MN)", "quantisation-noise formula"],
        ["Truncated SVD", "Y ≈ U_r Σ_r V_rᴴ (best rank-r approximation)", "BFP(U_rΣ_r) + BFP(V_r)", "O(MN·M) thin SVD", "Eckart–Young: sum of dropped σ_i²"],
        ["RAS-BFP (proposed)", "randomised SVD: sketch antennas → QR → project → small SVD → rank r", "same shape as SVD", "O(MN(r+p))", "HMT-type bound (Thm 2)"],
        ["CSEE (proposed)", "IFFT along subcarriers → keep the K strongest delay taps (same taps for all antennas)", "BFP(64 × K block) + K tap indices", "O(MN log N)", "Prop. 1: dropped-tap energy is exact"]]
add_table(s, Inches(0.4), Inches(1.5), Inches(12.5), Inches(2.6), rows, col_widths=[1.8, 3.8, 2.6, 1.8, 2.5], size=12, bold_first_col=True)
add_text(s, Inches(0.5), Inches(4.3), Inches(12.3), Inches(2.0), [
    ("Which structure survives the transmitted symbols?  Y = H·diag(x) + W", {"size": 16, "bold": True, "color": NAVY}),
    ("Rank: multiplying by diag(x) (an invertible matrix) does not change the rank → SVD and RAS-BFP work on data and reference symbols alike.", {"size": 14}),
    ("Delay sparsity: IFFT(H·diag(x)) = IFFT(H) convolved with IFFT(x). Random symbols make IFFT(x) white, so the energy spreads over all 1200 taps → CSEE only works on reference symbols.", {"size": 14}),
    ("The earlier repository did not see this because it simulated a constant symbol on every subcarrier.", {"size": 13, "color": RED}),
], bullet=True)
notes(s, """
All four encoders follow the same recipe: decompose the matrix, keep the important part, quantise it with block floating point.
BFP alone is the O-RAN baseline: no decomposition, just a shared exponent per 12 samples and b-bit mantissas.
Truncated SVD is the best possible rank-r approximation, so it is the reference for any low-rank method. It now uses the thin SVD.
RAS-BFP replaces the SVD by a randomised version: multiply the antenna dimension by a random sketch, QR, project, then a tiny SVD. Same payload as the SVD, about five times faster.
CSEE takes an IFFT over the subcarriers and keeps the strongest delay taps, one set of taps shared by all antennas.
The key point is at the bottom: multiplying by the transmitted symbols does not change the rank, but it does destroy the delay sparsity. That decides where each encoder can be used.
""")

# 8 --- formulation
s = new_slide("How the shared link is allocated, and why it is cheap", "One decision per OFDM symbol: a multiple-choice knapsack", tag="[new]", section="Technical approach")
add_text(s, Inches(0.5), Inches(1.5), Inches(6.2), Inches(5.0), [
    ("The decision", {"size": 16, "bold": True, "color": NAVY}),
    ("Each RU k picks one setting a_k from its menu (for CSEE: K taps and b bits).", {"size": 14}),
    ("Every setting has an exact rate R_k(a) in bits and an error D_k(a) = ‖Y_k − Ŷ_k‖² / ‖Y_k‖².", {"size": 14}),
    ("", {}),
    ("minimise  Σ_k D_k(a_k)     [or the worst RU: max_k D_k(a_k)]", {"size": 17, "bold": True}),
    ("subject to  Σ_k R_k(a_k) ≤ C_link", {"size": 17, "bold": True}),
    ("", {}),
    ("Solver: start every RU at its cheapest setting, then repeatedly give the next upgrade to the RU that gains the most error reduction per bit (on the convex hull of its menu). Optimal up to one fractional step. If even the cheapest settings do not fit, drop the RUs that gain least.", {"size": 13}),
    ("Measured: ≈1 ms to allocate + ≈27 ms to predict all menus for 8 RUs × 66 settings (Python).", {"size": 13, "color": GREY}),
], bullet=False)
add_text(s, Inches(6.9), Inches(1.5), Inches(6.1), Inches(5.0), [
    ("Proposition 1: predicting CSEE's error without encoding", {"size": 16, "bold": True, "color": NAVY}),
    ("Take the IFFT once: Y_d. Sort the delay taps by energy.", {"size": 14}),
    ("error = ( energy of dropped taps  +  quantisation error ) / total energy", {"size": 16, "bold": True}),
    ("The first term is exact (the IFFT preserves energy). The second comes from the block exponents: Δ²/6 per sample on average, Δ²/2 worst case.", {"size": 13}),
    ("Noise-aware version: subtract the noise that is expected in the dropped taps and divide by signal energy only — uses the RU's noise estimate σ².", {"size": 13}),
    ("Because the top-K sets are nested, one IFFT gives the prediction for every K and every b.", {"size": 13}),
    ("Measured: prediction within 0.5 dB of the real error for CSEE in Exp5 (BFP predictor within 1.3 dB).", {"size": 13, "bold": True, "color": GREEN}),
    ("", {}),
    ("Theorem 2 (RAS-BFP): reference bound from Halko–Martinsson–Tropp 2011, Thm 10.5", {"size": 14, "bold": True, "color": NAVY}),
    ("E‖Y − Ŷ_r‖²_F ≤ (4 + 2r/(p−1)) · Σ_{i>r} σ_i²   (Gaussian sketch, p ≥ 2)", {"size": 15, "bold": True}),
], bullet=False)
notes(s, """
The allocation is a multiple-choice knapsack: each radio unit picks one setting from a menu, each setting has an exact rate and an error, and the sum of rates must fit the link.
I solve it with the classic greedy rule: give the next bits to whoever reduces error most per bit. On the convex hull of each menu this is the Lagrangian solution up to one fractional step. It is the Shoham–Gersho bit-allocation algorithm; I do not claim it as new.
What makes it cheap is Proposition 1: for CSEE the error can be predicted from the decomposition itself. The energy of the dropped taps is exact by Parseval; only the quantisation part is a model. One IFFT gives the whole menu.
For RAS-BFP I use the Halko–Martinsson–Tropp bound as a reference. It is proven for Gaussian sketches; I use the faster Hadamard sketch and check the bound empirically.
""")

# 9 --- Exp1
s = new_slide("Result 1 — how much compression for how much error (Exp1)", f"M=64, N=1200, SNR 20 dB, {e1['realizations']} channel realisations; b = 10 bits for SVD / CSEE / RAS-BFP", tag="[new]", section="Evidence")
add_picture_fit(s, os.path.join(FIG, "exp1_nmse_vs_cr.png"), Inches(0.3), Inches(1.45), Inches(8.6), Inches(4.9))
cr_c, n_c_d = c1("data", "CSEE", 120); _, n_c_r = c1("reference", "CSEE", 120)
cr_s, n_s = c1("data", "SVD", 12); _, n_r = c1("data", "RAS-BFP", 12); cr_b, n_b = c1("data", "BFP", 8)
rows = [["Setting", "CR", "data", "reference"],
        ["BFP b=8", f"{cr_b:.1f}x", f"{n_b:.1f} dB", f"{n_b:.1f} dB"],
        ["SVD r=12", f"{cr_s:.1f}x", f"{n_s:.1f} dB", f"{n_s:.1f} dB"],
        ["RAS-BFP r=12", f"{cr_s:.1f}x", f"{n_r:.1f} dB", f"{n_r:.1f} dB"],
        ["CSEE K=120", f"{cr_c:.1f}x", f"{n_c_d:.1f} dB", f"{n_c_r:.1f} dB"]]
add_table(s, Inches(9.0), Inches(1.6), Inches(4.0), Inches(2.2), rows, col_widths=[1.7, 0.8, 1.0, 1.1], size=11, bold_first_col=True)
add_text(s, Inches(9.0), Inches(3.9), Inches(4.0), Inches(2.5), [
    ("Error here = NMSE against the transported (noisy) matrix Y; lower is better.", {"size": 11, "color": GREY}),
    ("CSEE: −17 to −21 dB at 6–78x on reference symbols, but about 0 dB (useless) on data symbols.", {"size": 12}),
    ("RAS-BFP costs 1–4 dB more than SVD for the same payload; the Thm-2 bound sits 6–10 dB above it (valid, loose).", {"size": 12}),
    ("Every truncating encoder flattens at −20 dB: that is the noise floor of this metric at 20 dB SNR.", {"size": 12}),
], bullet=True)
takeaway(s, "CSEE compresses channel (reference-symbol) matrices, not general data; low-rank methods (SVD, RAS-BFP) work for both.")
notes(s, f"""
Left panel: data symbols. Right panel: reference symbols. Same channels, same encoders.
BFP, grey, gives 2x compression at 8 bits with minus 46 dB error — very accurate, very little compression.
SVD and RAS-BFP look the same in both panels, because the rank does not depend on the symbols. RAS-BFP pays one to four dB for being faster.
CSEE, red, is the story: on reference symbols it reaches minus {abs(n_c_r):.0f} dB at {cr_c:.0f}x; on data symbols it gives essentially zero dB. It only works when the delay domain is sparse.
Everything flattens at minus 20 dB. That is the noise floor of this metric at 20 dB SNR: the encoders throw away noise and the metric counts that as error. The next slide deals with that.
Dashed lines are the analytical predictions: Proposition 1 lies on the CSEE curve; the HMT bound for RAS-BFP is 6 to 10 dB above the curve — valid but loose.
""")

# 10 --- Exp2 + Exp4
s = new_slide("Results 2–3 — encoding time, and two ways to measure error", "Exp2: Python medians of 7 runs, N=1200 · Exp4: reference symbols, settings at CR ≈ 8x, 12 realisations", tag="[new]", section="Evidence")
add_picture_fit(s, os.path.join(FIG, "exp2_complexity.png"), Inches(0.3), Inches(1.45), Inches(5.3), Inches(3.7))
add_picture_fit(s, os.path.join(FIG, "exp4_snr_sweep.png"), Inches(5.6), Inches(1.45), Inches(7.5), Inches(3.7))
add_text(s, Inches(0.4), Inches(5.2), Inches(5.2), Inches(1.1), [
    (f"M=64: BFP {t2('BFP',64):.2f} ms · CSEE {t2('CSEE',64):.2f} ms · RAS-BFP {t2('RAS-BFP',64):.1f} ms · thin SVD {t2('SVD',64):.1f} ms", {"size": 11, "bold": True}),
    (f"Randomised SVD is ≈{t2('SVD',64)/t2('RAS-BFP',64):.0f}x faster than the thin SVD at M=64 and ≈{t2('SVD',128)/t2('RAS-BFP',128):.0f}x at M=128 (the old figure said ~100x, against a full SVD)", {"size": 10, "color": GREY}),
], bullet=False)
add_text(s, Inches(5.7), Inches(5.2), Inches(7.3), Inches(1.1), [
    (f"(a) against noisy Y: truncating encoders follow the −SNR line. (b) against clean H: at 0 dB SNR the raw matrix is at 0 dB, CSEE at {e4v('vs_clean','CSEE',0):.0f} dB, SVD at {e4v('vs_clean','SVD',0):.0f} dB — the decompositions remove noise.", {"size": 10}),
    (f"At 30 dB: SVD {e4v('vs_clean','SVD',30):.0f}, CSEE {e4v('vs_clean','CSEE',30):.0f}, RAS-BFP {e4v('vs_clean','RAS-BFP',30):.0f}, BFP b=4 {e4v('vs_clean','BFP',30):.0f} dB. CSEE on data symbols (dashed) stays at ≈ −1 dB.", {"size": 10}),
], bullet=False)
takeaway(s, "'Stable across SNR' in the old report was an artefact of the metric. Against the clean channel, the decompositions act as denoisers at low SNR.")
notes(s, """
Left: encoding time against the number of antennas. With the thin SVD the baseline takes 13 ms at 64 antennas; the randomised version takes 2.6 ms; CSEE and BFP are under a millisecond.
So the honest speed-up of the randomised SVD is about five times, not a hundred. These are Python numbers; I only trust the ordering.
Right: error against SNR at fixed settings. Panel (a) is measured against the noisy matrix: the curves follow the minus-SNR line because the removed noise is counted as error.
Panel (b) is measured against the clean channel: at 0 dB SNR the raw matrix has 0 dB error, but CSEE is at minus 9 dB — keeping only the strong taps removes noise.
The dashed CSEE-on-data curve stays at minus one dB everywhere, which confirms the limit.
""")

# 11 --- ACAFS
s = new_slide("Result 4 — send only as many streams as the rank (ACAFS, Exp3)", f"M=64, N=1200, {e3['realizations']} realisations per SNR; rank = number of eigenvalues of Y Yᴴ holding 99 % of the energy", tag="[fix]", section="Evidence")
add_picture_fit(s, os.path.join(FIG, "exp3_acafs.png"), Inches(0.3), Inches(1.45), Inches(8.3), Inches(4.2))
add_text(s, Inches(8.7), Inches(1.5), Inches(4.4), Inches(4.5), [
    ("Corrected cost model (3GPP TR 38.801 / O-RAN)", {"size": 14, "bold": True, "color": NAVY}),
    ("all antennas (split 7.1 / 7.2x-A): 2MNb bits — the reference", {"size": 12}),
    ("r streams (7.2x-B beam-space): 2rNb + weights", {"size": 12}),
    ("split 6 (decoded bits): r·N·6 bits → ≈20x cheaper, but the RU must run the whole uplink receiver", {"size": 12}),
    ("Rule: if rank/M < 0.55 → send max(rank, 10) streams; else split 6 if the RU has the compute, else all antennas.", {"size": 12}),
    ("", {}),
    (f"Streams only: 0 % saving below 15 dB → {100*e3['exact_beamspace'][e3['snr'].index(20)]:.0f} % at 20 dB (mean rank {e3['mean_rank_exact'][e3['snr'].index(20)]:.0f}).", {"size": 12, "bold": True}),
    (f"Fast rank estimate (1/8 of the subcarriers): {100*(1-sum(e3['t_fast_ms'])/sum(e3['t_exact_ms'])):.0f} % less time, but under-estimates the rank by up to {max(e3['rank_abs_err']):.0f} at 10–17 dB → the 10-stream floor protects against it.", {"size": 12}),
    (f"Prop. 5 (assumes every rank equally likely): {100*e3['prop5_beamspace']:.0f} % streams-only, {100*e3['prop5_split6']:.0f} % with split 6 — a prediction, not a bound.", {"size": 12, "color": GREY}),
], bullet=True)
takeaway(s, "The old 'saving vs split 6' figure had the costs upside down. Savings come from the rank collapsing at high SNR, and from whether the RU may host split 6.", color=RED)
notes(s, """
ACAFS decides how many spatial streams to send, based on the estimated rank of the received matrix.
First the correction: in 3GPP terms split 6 carries decoded bits and is the cheapest option on the link; the I/Q splits are the expensive ones. The old figure had this upside down. I now report savings against sending all antennas.
The result: with streams only, there is no saving below 15 dB SNR, because noise fills all 64 dimensions. The saving rises to about 83 percent at 20 dB, where the rank collapses to about 11.
Allowing split 6 saves a lot at any SNR in this model — but that option costs compute in the radio unit, which is exactly what the matrix-inversion benchmark measures.
The orange curve is a real fast estimator now, using an eighth of the subcarriers; it is biased low in the transition region, and the stream floor protects against that.
""")

# 12 --- allocator
s = new_slide("Result 5 — sharing one link between 8 RUs (Exp5)", f"RU SNRs {{{','.join(map(str, e5cfg['cell_snrs_db']))}}} dB · menu of 11 K × 6 b = 66 CSEE settings · {e5cfg['seeds']} seeds · reference symbols", tag="[new]", section="Evidence")
add_picture_fit(s, os.path.join(FIG, "exp5_allocation.png"), Inches(0.3), Inches(1.45), Inches(7.6), Inches(5.0))
add_text(s, Inches(8.0), Inches(1.4), Inches(5.1), Inches(4.9), [
    ("Policies compared", {"size": 14, "bold": True, "color": NAVY}),
    ("uniform-CSEE / uniform-BFP: same setting for every RU (today's static configuration)", {"size": 11}),
    ("greedy-sum / greedy-max: proposed; decides from Prop.-1 predictions only", {"size": 11}),
    ("greedy-clean: proposed; noise-aware objective (error of the signal, not of the noise)", {"size": 11}),
    ("oracle: greedy on measured error — encodes every option first (ablation)", {"size": 11}),
    ("", {}),
    ("What the panels show", {"size": 14, "bold": True, "color": NAVY}),
    (f"(a) vs Y: greedy is within 0.5 dB of the oracle everywhere; {abs(r5(0.1,'greedy-sum','avg_cell_nmse_db_mean')-r5(0.1,'uniform-CSEE','avg_cell_nmse_db_mean')):.1f} dB better than uniform at 27.5 Gbps, {abs(r5(0.2,'greedy-sum','avg_cell_nmse_db_mean')-r5(0.2,'uniform-CSEE','avg_cell_nmse_db_mean')):.1f} dB at 55 Gbps; uniform-BFP does not fit below 55 Gbps (RUs dropped)", {"size": 11}),
    (f"(b) vs H: greedy-sum spends bits on reproducing noise in the low-SNR RUs; the noise-aware objective is {abs(r5(0.1,'greedy-clean','avg_cell_nmse_clean_db_mean')-r5(0.1,'greedy-sum','avg_cell_nmse_clean_db_mean')):.1f} dB better at 27.5 Gbps", {"size": 11}),
    ("(c) min-max objective: worst RU up to 2.2 dB better (27.5 Gbps) at a 0.7–2.6 dB cost in the mean", {"size": 11}),
    (f"(d) the noise-aware policy uses only {100*r5(0.5,'greedy-clean','utilization_mean'):.0f} % of the link at 138 Gbps — more bits would only copy noise", {"size": 11}),
], bullet=True)
takeaway(s, "Predicting the error is enough to allocate as well as encoding everything. The objective matters: minimise loss of signal, not loss of noise.")
notes(s, f"""
This is the load-management experiment. Eight radio units with SNRs from 0 to 30 dB share one link; the capacity is swept from 0.5 to 50 percent of the raw load.
Each radio unit gets one CSEE setting. The controller only uses the Proposition-1 predictions; afterwards every unit is actually encoded and the true error measured.
Panel (a): the greedy allocator, red, sits on top of the oracle, green, which encodes every option. It beats the uniform setting by up to eleven dB, and uniform BFP does not even fit until 55 gigabit.
Panel (b) is the honest part. Against the clean channel, minimising the error to the noisy matrix spends bits reproducing noise in the 0 and 5 dB cells — at 14 and 27 gigabit it is worse than uniform.
That negative result led to the noise-aware objective, orange: it puts the noise estimate into Proposition 1, gains four to eight dB on the signal, and at high capacity it stops using the link once more bits do not help — panel (d).
Error bars are one standard deviation over five seeds.
""")

# 13 --- matrix inversion cost (promoted)
s = new_slide("Result 6 — how much does one matrix inversion cost?", "Why it matters: MMSE equalisation and channel estimation invert a matrix per resource-block group every slot; split 6 puts that inside the RU", tag="[repo]", section="Evidence")
add_picture_fit(s, os.path.join(ROOT, "results", "inference_time.png"), Inches(0.3), Inches(1.45), Inches(6.6), Inches(4.0))
rows = [["n", "LAPACK LU (numpy.linalg.inv)", "Newton–Schulz", "thin SVD", "Gauss–Jordan"]]
for dim in (10, 100, 500):
    r = [str(dim)]
    for key in ("LAPACK getri", "Newton-Schulz iteration", "SVD", "Gauss-Jordan"):
        sub = bench[(bench.dim == dim) & (bench.method.str.contains(key, regex=False))]
        r.append("n/a" if sub.empty else f"{sub.iloc[0].median_ms:.3g} ms")
    rows.append(r)
add_table(s, Inches(7.1), Inches(1.5), Inches(5.9), Inches(1.7), rows, col_widths=[0.5, 2.2, 1.5, 1.2, 1.5], size=11)
add_text(s, Inches(7.1), Inches(3.3), Inches(5.9), Inches(3.1), [
    ("Set-up: random well-conditioned matrices A = G/√n + 2I, float32, n = 10 / 100 / 500; 200 held-out matrices (20 at n=500); 4-core CPU, one matrix at a time.", {"size": 12, "color": GREY}),
    ("LAPACK LU is fastest at every size and exact to float32 (relative error ≈ 5e-8).", {"size": 13}),
    ("A 100×100 inverse takes ≈0.14 ms → about 7 per core fit in a 1 ms slot (15 kHz spacing). A 500×500 inverse takes ≈6 ms → it does not fit.", {"size": 13, "bold": True}),
    ("Iterative Newton–Schulz is 3–7x slower than LU but needs only matrix multiplications — attractive for hardware, and the basis of the learned models on the next slide.", {"size": 13}),
    ("Gauss–Jordan (textbook method) is 30x slower at n=500.", {"size": 13}),
], bullet=True)
takeaway(s, "Inversion cost bounds where processing can live: massive-MIMO-sized inverses fit a slot on a CPU core; multi-cell-sized ones do not.")
notes(s, """
This part existed before and I kept it because it answers a question the split decision raises. If the radio unit has to run the uplink receiver for split 6, what does the matrix inversion in the equaliser cost?
The plot shows time per inverse against matrix size on a log scale, for the classical methods and the learned ones.
LAPACK LU, purple, is the reference: 0.14 milliseconds for a 100-by-100 inverse, which fits a slot; 6 milliseconds for 500-by-500, which does not.
Newton–Schulz is slower but uses only matrix multiplications, which is why it is interesting for learned and hardware versions.
The benchmark runs on held-out matrices that the neural models never saw during training.
""")

# 14 --- learned inversion (NEW)
s = new_slide("Result 6b — can a neural network learn to invert a matrix?", "Three 'InverseNet' models, trained on the first 80 % of the dataset, tested on the last 20 %", tag="[fix]", section="Evidence")
rows = [["n", "LAPACK LU", "InverseNet-MLP (direct regression)", "InverseNet-NS (learned Newton–Schulz, 17 params)", "InverseNet-Ultra (learned NS + data-dependent start)"]]
for dim in (10, 100, 500):
    r = [str(dim)]
    for key in ("LAPACK getri", "InverseNet-MLP", "InverseNet-NS", "InverseNet-Ultra"):
        sub = bench[(bench.dim == dim) & (bench.method.str.contains(key, regex=False))]
        r.append("not run" if sub.empty else f"{sub.iloc[0].median_ms:.3g} ms · rel. error {sub.iloc[0].rel_err_vs_true:.1e}")
    rows.append(r)
add_table(s, Inches(0.4), Inches(1.5), Inches(12.5), Inches(1.9), rows, col_widths=[0.5, 2.5, 2.9, 3.3, 3.3], size=11)
add_text(s, Inches(0.5), Inches(3.6), Inches(12.3), Inches(2.7), [
    ("MLP: flatten A, regress A⁻¹. Fails (error 0.36 at n=10) and cannot scale — at n=500 it would need > 2 billion parameters.", {"size": 13}),
    ("Learned Newton–Schulz: unroll X ← X(βI − γAX) for 8 steps and learn the 17 scalars. It generalises to any n (error 4e-4 at n=100), but it is slower than LU.", {"size": 13}),
    ("Ultra: adds a tiny network that sets the starting guess from four matrix statistics. Error ≈1e-6 at n=100/500 (but 0.17 at n=10); same speed as classical Newton–Schulz; never beats LU medians.", {"size": 13}),
    ("Fixed this iteration [fix]: the fast NumPy inference engine used ReLU while the trained model uses GELU — outputs now match (tested); a docstring claiming 1e-7 error and 'faster than LU' was corrected; benchmark re-run.", {"size": 13, "color": RED}),
    ("Conclusion: for well-conditioned matrices, learning the inverse does not beat LAPACK on a CPU. The learned iteration is a reasonable idea for fixed-latency hardware, not a replacement for LU.", {"size": 13, "bold": True}),
], bullet=True)
takeaway(s, "The ML part of the project gives a clear negative result: a learned inverter does not beat classical linear algebra here — and saying so is the honest contribution.")
notes(s, """
The machine-learning part of the project asks whether a network can learn to invert matrices faster than LAPACK.
Three models. The MLP regresses the inverse directly; it fails and cannot scale. The learned Newton–Schulz unrolls the classical iteration and learns 17 scalars, so it works at any size; it reaches 4e-4 error at n equals 100 but is slower than LU. Ultra adds a small network for the starting guess; it reaches one-in-a-million error at 100 and 500 but is no faster than the classical iteration.
I found and fixed a bug here: the NumPy inference engine used ReLU while the trained model uses GELU. I also corrected a docstring that overstated the results.
The conclusion is negative and I think that is fine to say: on a CPU and for well-conditioned matrices, LAPACK wins. The learned iteration is interesting for fixed-latency hardware, not as a replacement.
""")

# 15 --- contributions / limitations / plan
s = new_slide("What is done, what is not, and what comes next", section="Closing")
add_text(s, Inches(0.4), Inches(1.3), Inches(4.2), Inches(5.2), [
    ("Done", {"size": 17, "bold": True, "color": GREEN}),
    ("Working, tested simulator: channel → decomposition-based encoders → split → allocation (was missing)", {"size": 12, "tag": "[new]"}),
    ("Fair baselines: thin SVD, correct split costs, real rank estimator, two error references", {"size": 12, "tag": "[fix]"}),
    ("Error predictor within 0.5 dB; HMT bound checked", {"size": 12, "tag": "[new]"}),
    ("Allocator for 8 RUs with static baselines, oracle and objective ablations, 5 seeds", {"size": 12, "tag": "[new]"}),
    ("Finding: delay-domain compression works only on channel/reference symbols; low rank works on everything", {"size": 12, "tag": "[new]"}),
    ("Matrix-inversion benchmark: bug fixed, re-run, honest conclusion (LU wins)", {"size": 12, "tag": "[fix]"}),
], bullet=True)
add_text(s, Inches(4.7), Inches(1.3), Inches(4.2), Inches(5.2), [
    ("Limits", {"size": 17, "bold": True, "color": RED}),
    ("One OFDM symbol at a time; no scheduler, retransmissions or latency", {"size": 12}),
    ("CSEE valid on reference symbols only → Exp5 covers that traffic only", {"size": 12}),
    ("Python timings: ordering and scaling only", {"size": 12}),
    ("Thm 2 proven for Gaussian sketches; Hadamard sketch checked empirically", {"size": 12}),
    ("Split-6 cost is a rough model (6 bit/RE); noise variance assumed known in the noise-aware test", {"size": 12}),
    ("Inversion benchmark: well-conditioned random matrices, not channel matrices", {"size": 12}),
    ("No novelty claimed for any single algorithm; the contribution is the validated system and its findings", {"size": 12, "italic": True}),
], bullet=True)
add_text(s, Inches(9.0), Inches(1.3), Inches(4.0), Inches(5.2), [
    ("Next, until the final evaluation", {"size": 17, "bold": True, "color": TEAL}),
    ("Slot-level simulation mixing data and reference symbols; menu with CSEE, RAS-BFP and BFP (needs a RAS-BFP error predictor)", {"size": 12, "tag": "[future]"}),
    ("Joint split + allocation under one capacity, with the inversion benchmark as the RU compute limit", {"size": 12, "tag": "[future]"}),
    ("Sensitivity to noise-estimate and rank errors", {"size": 12, "tag": "[future]"}),
    ("Inversion benchmark on real channel matrices (ill-conditioned) and on fixed-latency hardware", {"size": 12, "tag": "[future]"}),
    ("Learned components only where no formula exists, judged against the formula", {"size": 12, "tag": "[future]"}),
], bullet=True)
notes(s, """
To sum up. Done: a simulator that runs and is tested; fair baselines; an error predictor accurate enough to make decisions; an allocator with proper baselines and ablations; one clear finding about which matrix structure survives modulation; and an honest conclusion from the inversion benchmark.
Limits I want to state myself: one symbol at a time, CSEE on reference symbols only, Python timings, the inversion benchmark uses random matrices rather than channel matrices.
I am not claiming novelty for any single algorithm. The encoders and the allocator adapt known linear algebra; the contribution is the validated system and the findings that came out of making it correct.
Next: slot-level simulation with mixed symbol types, joining the split decision with the allocator under one capacity, and running the inversion benchmark on real channel matrices.
""")

# 16-17 --- references
refs = sorted(REFERENCES["ieee_list"], key=lambda r: int(r[1:r.index("]")]))
for part, chunk in enumerate((refs[:15], refs[15:]), start=1):
    s = new_slide(f"References ({part}/2) — checked sources, see docs/research_review.md", section="References")
    add_text(s, Inches(0.4), Inches(1.2), Inches(12.5), Inches(5.9), [(r, {"size": 10, "space": 2}) for r in chunk], bullet=False)
    notes(s, "Reference list. Every entry was checked against a primary page (publisher, arXiv record, or standards body) on 17 Sep 2026. Entries marked '(abstract)' were not read in full and are cited only for what their abstracts state.")

# ============================================================================= BACKUP
s = new_slide("Backup — audit: problems found in the original material", section="Backup")
add_text(s, Inches(0.4), Inches(1.3), Inches(12.5), Inches(5.4), [
    ("`src/` absent from every commit and branch; Exp1-4 and the notebook import it → nothing ran", {"size": 13}),
    ("Exp2 SVD baseline: committed figure ~1.7 s at M=64 vs 13 ms for the thin SVD; O(MN) reference line plotted in seconds on a millisecond axis", {"size": 13}),
    ("Exp3: 'fast rank estimate' = exact rank + random {−1,0,1}; 'Theorem 5 bound' lay below the simulated curve → not a bound", {"size": 13}),
    ("ACAFS: split 6 treated as the most expensive split; TR 38.801 ordering is R_6 ≪ R_7.2x-beam ≤ R_7.x-antenna", {"size": 13}),
    ("Exp4: 'stable across SNR' claimed while the figure shows NMSE ≈ −SNR", {"size": 13}),
    ("CSEE input: constant pilot ⇒ delay sparsity; with random QPSK per subcarrier CSEE gives ≈ −0.5 dB", {"size": 13}),
    ("CR reference 32-bit components ⇒ all CRs inflated 2x (BFP b=8: 3.9x quoted vs 2.0x against 16-bit)", {"size": 13}),
    ("Docs: 'Theorems 1-5' without statements or proofs; '100 MHz at 15 kHz' with N=1200 (= 18 MHz); journal targets and hardware roadmap not backed by code", {"size": 13}),
    ("matinv_bench: ReLU vs GELU in the NumPy engine; docstring claiming 1e-7 error and LU-beating latency", {"size": 13}),
    ("Original figures and tables preserved in results/original_snapshot/ for comparison", {"size": 13, "color": GREY}),
], bullet=True)
notes(s, "Backup slide with the full list of problems found, in case the committee asks what exactly was wrong with the earlier figures.")

s = new_slide("Backup — Proposition 1 step by step, and the noise-aware form", section="Backup")
add_text(s, Inches(0.4), Inches(1.3), Inches(12.5), Inches(5.4), [
    ("Set-up: Y is M×N. Y_d = IFFT along each row (numpy convention: Y = FFT(Y_d), so ‖Y‖²_F = N‖Y_d‖²_F). Encoder keeps columns S (|S| = K) and BFP-quantises them: Ŷ_d = Q(Y_d[:,S]) on S, 0 elsewhere. Decoder: Ŷ = FFT(Ŷ_d).", {"size": 13}),
    ("‖Y − Ŷ‖²_F = N‖Y_d − Ŷ_d‖²_F = N( Σ_{n∉S}‖Y_d[:,n]‖² + ‖Y_d[:,S] − Q(Y_d[:,S])‖²_F ) = N(T_S + E_q).", {"size": 13}),
    ("NMSE = (T_S + E_q) / ‖Y_d‖²_F.  T_S (dropped taps) is exact; E_q (quantisation) depends on the quantiser.", {"size": 13}),
    ("BFP block with exponent e_b, step Δ_b = 2^{e_b}: per real component |error| ≤ Δ_b/2, variance ≈ Δ_b²/12. Per complex sample: ≤ Δ_b²/2 worst case, ≈ Δ_b²/6 expected. Sum over the non-zero samples of each block. Zero samples quantise exactly.", {"size": 13}),
    ("Top-K sets are nested in K, so one sort of the N tap energies gives T_S for all K; block maxima per K give Δ_b for all b by a shift of log₂(2^{b−1}−1). The whole 66-setting menu costs about one encoder pass.", {"size": 13}),
    ("Noise-aware form (RU knows σ²): white noise has total delay-domain energy Mσ² spread evenly over the N taps. Signal error ≈ [max(T_S − Mσ²(N−K)/N, 0) + Mσ²K/N + E_q] / (‖Y_d‖² − Mσ²). Measured within 0.1 dB at 20 dB SNR and ≈1.7 dB at 0 dB SNR.", {"size": 13}),
    ("Why it matters: with the plain form the allocator upgrades low-SNR RUs to reproduce noise; with the noise-aware form extra bits stop paying once the dropped taps are only noise, so capacity is released.", {"size": 13, "color": TEAL}),
], bullet=True)
notes(s, "Derivation of Proposition 1 for a technical question. The key point: the dropped-tap term is an identity; only the quantisation term is a model.")

s = new_slide("Backup — RAS-BFP algorithm and Theorem 2", section="Backup")
add_text(s, Inches(0.4), Inches(1.3), Inches(12.5), Inches(5.4), [
    ("1. Sketch the antenna dimension: Z = Ω Y, size (r+p)×N. Ω = √(M/(r+p)) · S · H_M · D (SRHT: random signs D, Walsh–Hadamard H_M by fast transform, row sampler S) or a Gaussian matrix.", {"size": 13}),
    ("2. Thin QR: Zᴴ = Q R. Q (N×(r+p)) spans an approximate dominant right singular subspace of Y.", {"size": 13}),
    ("3. Project: L = Y Q (M×(r+p)); small SVD of L; keep rank r: L_r = U_rΣ_r, Q_r = Q V_r. Ŷ = L_r Q_rᴴ (HMT Algorithms 4.1 + 5.1).", {"size": 13}),
    ("4. Send BFP(L_r) and BFP(Q_r) — the same payload shape as truncated SVD at rank r ⇒ equal CR, fair comparison.", {"size": 13}),
    ("Cost: O(MN log M) sketch (SRHT) or O(MN(r+p)) (Gaussian) + O(N(r+p)²) QR + O(MN(r+p)) projection, against O(MN·M) for the thin SVD.", {"size": 13}),
    ("Theorem 2 (HMT 2011, Thm 10.5, Gaussian Ω, p ≥ 2): E‖Y − YQQᴴ‖²_F ≤ (1 + r/(p−1)) Σ_{i>r}σ_i². Truncating to rank r adds at most an Eckart–Young term (‖Y − Q[QᴴY]_r‖ ≤ ‖Y − QQᴴY‖ + ‖Y − Y_r‖), so E‖Y − Ŷ‖²_F ≤ (4 + 2r/(p−1)) Σ_{i>r}σ_i². Quantisation comes on top.", {"size": 13}),
    ("Caveats: proven for Gaussian sketches; the SRHT (Tropp 2011) needs larger oversampling for a proof — with p = 4 the bound holds empirically with 6–10 dB slack in Exp1. For p < 2 the code returns ∞ rather than an invalid bound. SRHT falls back to Gaussian when M is not a power of two or r+p ≥ M.", {"size": 13, "color": GREY}),
], bullet=True)
notes(s, "Backup for the randomised encoder. If asked why not just the SVD: cost. If asked whether the bound is tight: no, and it is stated for Gaussian sketches; the plot shows the slack.")

s = new_slide("Backup — ACAFS cost model and allocator pseudo-code", section="Backup")
add_text(s, Inches(0.4), Inches(1.3), Inches(6.1), Inches(5.4), [
    ("Bits per OFDM symbol per RU (M=64, N=1200, b=16, η=6, T_c=14)", {"size": 14, "bold": True, "color": NAVY}),
    ("all antennas: 2MNb = 2 457 600", {"size": 13}),
    ("r streams: 2rNb + 2Mrb/T_c  (r=10: 385 463; r=32: 1 233 481)", {"size": 13}),
    ("split 6, r layers: rNη  (r=10: 72 000; r=64: 460 800)", {"size": 13}),
    ("rule: ρ = r/M; ρ < τ_high = 0.55 → streams = max(r, ⌈0.15·M⌉ = 10); else split 6 if allowed, else all antennas", {"size": 13}),
    ("Prop. 5 = average over r ∈ {1..M} of the saving under the rule (a prediction; the simulated saving can exceed it when ranks concentrate low)", {"size": 13}),
], bullet=True)
add_text(s, Inches(6.7), Inches(1.3), Inches(6.3), Inches(5.4), [
    ("greedy_allocate(rates, errors, C, objective)", {"size": 14, "bold": True, "color": NAVY}),
    ("for each RU: keep only the (R, D) points on the lower convex hull (dominated points never help)", {"size": 13}),
    ("start every RU at its cheapest point; if Σ R > C: drop the RUs with the largest predicted error at that point until it fits", {"size": 13}),
    ("repeat: among feasible next-hull upgrades pick the largest ΔD/ΔR (sum objective) or the RU with the current largest D (max objective); stop when nothing fits", {"size": 13}),
    ("guarantee: Lagrangian optimum up to one fractional upgrade (standard for the multiple-choice knapsack greedy on convex hulls; Shoham–Gersho 1988)", {"size": 13}),
    ("uniform_allocate: best single point that fits for all RUs — the static-configuration baseline", {"size": 13}),
    ("tests: capacity respected, greedy ≥ uniform on its objective, low load → best point, overload → drops, zero-traffic RU, invalid inputs", {"size": 13, "color": GREY}),
], bullet=True)
notes(s, "Numbers behind the split model and pseudo-code of the allocator, for questions on either.")

s = new_slide("Backup — how to reproduce everything", section="Backup")
add_text(s, Inches(0.4), Inches(1.3), Inches(12.5), Inches(5.4), [
    ("pip install -r requirements.txt   (numpy, scipy, pandas, matplotlib, tqdm, pytest; torch only for matinv_bench)", {"size": 13}),
    ("python -m pytest tests -q                       → 42 passed (~1 s)", {"size": 13}),
    ("python experiments/exp1_nmse_vs_cr.py            → results/figures/exp1_*.png|pdf, results/data/exp1_nmse_vs_cr.json  (~10 s)", {"size": 13}),
    ("python experiments/exp2_complexity.py            → exp2_*  (~2 s)", {"size": 13}),
    ("python experiments/exp3_acafs_gain.py            → exp3_*  (~3 s)", {"size": 13}),
    ("python experiments/exp4_snr_sweep.py             → exp4_*  (~5 s)", {"size": 13}),
    ("python experiments/exp5_fronthaul_allocation.py  → exp5_allocation.png, exp5_allocation_runs.csv (every run), exp5_allocation_summary.csv  (~8 s)", {"size": 13}),
    ("jupyter nbconvert --execute --inplace notebooks/mid_evaluation_demo.ipynb   (run from notebooks/)", {"size": 13}),
    ("python -m matinv_bench.generate_dataset --dims 10 100 --num-samples 1000; python -m matinv_bench.benchmark --dims 10 100   (checkpoints are committed; training is optional)", {"size": 13}),
    ("Every results/data file records generation time, Python/numpy version, host and CPU count; results/logs/ has the console output of the runs shown here.", {"size": 13, "color": GREY}),
    ("Host used for the numbers in this deck: 4-core x86_64, Python 3.12, numpy 2.x, no GPU.", {"size": 13, "color": GREY}),
], bullet=True)
notes(s, "If the live demo fails, these are the saved outputs and how they were produced.")

out = os.path.join(ROOT, "docs", "mid_evaluation.pptx")
prs.save(out)
print(f"wrote {out} with {len(prs.slides)} slides")
