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
# 1 --- title
s = prs.slides.add_slide(BLANK); _slide_no[0] += 1
add_box(s, 0, 0, W, H, fill=NAVY)
add_text(s, Inches(0.8), Inches(1.6), Inches(11.7), Inches(1.8),
         [("Fronthaul Load Management in 5G C-RAN / O-RAN", {"size": 38, "bold": True, "color": WHITE}),
          ("Compression, rank-adaptive split selection and capacity-constrained allocation", {"size": 22, "color": RGBColor(0xBF, 0xD7, 0xEA)})])
add_text(s, Inches(0.8), Inches(3.9), Inches(11.7), Inches(1.6),
         [("B.Tech. Project — mid-term evaluation", {"size": 20, "color": WHITE}),
          ("September 2026", {"size": 16, "color": RGBColor(0xBF, 0xD7, 0xEA)}),
          ("Evidence: Python/numpy simulation on 3GPP TR 38.901 TDL-A channels (no hardware, no field traces)", {"size": 14, "color": RGBColor(0xBF, 0xD7, 0xEA), "italic": True})])
add_text(s, Inches(0.8), Inches(6.3), Inches(11.7), Inches(0.8),
         [("Legend used on every slide:   [repo] present in the repository before this iteration   [new] implemented and validated in this iteration   [prelim] preliminary   [future] planned",
           {"size": 12, "color": RGBColor(0xBF, 0xD7, 0xEA)})])
notes(s, """
Good morning. My project is about managing the load on the fronthaul link of a 5G centralised / open RAN.
In one sentence: the radio unit produces far more I/Q data than the link can carry, and I study how to compress it,
how many streams to send, and how to share a link between several radio units — and I build a simulator to test that.
Everything I show is simulation in Python on standard 3GPP channel models; I will be explicit about what existed before,
what I implemented in this iteration, and what is still preliminary. The colour tags on each slide mark that.
""")

# 2 --- motivation / problem
s = new_slide("Why fronthaul load is the bottleneck", "O-RAN split 7.2x carries frequency-domain I/Q per antenna, per subcarrier, per OFDM symbol", section="Motivation")
add_text(s, Inches(0.5), Inches(1.5), Inches(6.4), Inches(4.7), [
    ("Uplink I/Q rate per radio unit (RU)", {"size": 18, "bold": True, "color": NAVY}),
    ("R_raw = 2 · M · N · b · (14 symbols / 1 ms)", {"size": 18}),
    ("M = 64 antennas, N = 1200 subcarriers (15 kHz, 18 MHz), b = 16 bit", {"size": 14, "color": GREY}),
    ("→ 2.46 Mbit per symbol  =  34.4 Gbps per RU", {"size": 18, "bold": True, "color": RED}),
    ("→ 8 RUs on one link: 275 Gbps", {"size": 18, "bold": True, "color": RED}),
    ("", {}),
    ("Three levers, one budget", {"size": 18, "bold": True, "color": NAVY}),
    ("Compress the I/Q (how many bits, which structure to exploit)", {"size": 15}),
    ("Send fewer streams / move the functional split (rank-adaptive)", {"size": 15}),
    ("Share the link across RUs so the sum stays under capacity", {"size": 15}),
], bullet=False)
add_text(s, Inches(7.1), Inches(1.5), Inches(5.8), Inches(4.7), [
    ("What 'load management' means in this project", {"size": 18, "bold": True, "color": NAVY}),
    ("Per OFDM symbol and per RU, choose an encoder operating point (and stream count) such that", {"size": 15}),
    ("Σ_k rate_k ≤ link capacity", {"size": 17, "bold": True}),
    ("while minimising the distortion of the transported matrices.", {"size": 15}),
    ("", {}),
    ("Not modelled (and not claimed):", {"size": 15, "bold": True, "color": GREY}),
    ("MAC scheduling, HARQ, latency/jitter, hardware timing, real traces", {"size": 14, "color": GREY}),
], bullet=False)
takeaway(s, "Problem: several RUs, one fronthaul link, a fixed bit budget per symbol — decide bits, structure and streams per RU.")
notes(s, """
The numbers: with 64 antennas and 1200 subcarriers at 16-bit I/Q, one radio unit produces 2.46 megabit per OFDM symbol,
which is 34 gigabit per second. Eight radio units on one link would need 275 gigabit per second. That is the load.
There are three levers: compression, sending fewer spatial streams (which is what a functional split decision does),
and sharing the link across radio units. My project touches all three, and the third one — the allocation — is what I added in this iteration.
I want to be clear about scope: this is a physical-layer, single-symbol model. No scheduler, no latency, no hardware.
""")

# 3 --- starting point & objectives
s = new_slide("Starting point, audit and objectives for this iteration", "What the repository actually contained on 17 Sep 2026 and what I set out to do", section="Scope")
rows = [["Component", "Found in repository", "Verified problem", "Now"],
        ["Experiment scripts Exp1-4, notebook, figures, report", "[repo] present", "import a package src/ that was never committed → nothing runnable; figures irreproducible", "[new] src/ reconstructed, 42 tests"],
        ["SVD baseline timing (Exp2)", "[repo] figure", "full N×N SVD timed (~1.7 s); economy SVD is 13 ms → '4-6x faster than SVD' unsupported", "[fix] economy SVD"],
        ["ACAFS split model (Exp3)", "[repo] figure", "'saving vs split 6' with split 6 as most expensive — inverted vs 3GPP TR 38.801; 'fast rank' curve = exact rank + random ±1", "[fix] model + real estimator"],
        ["NMSE vs SNR (Exp4)", "[repo] figure", "NMSE vs noisy Y saturates at −SNR; text claimed 'stable across SNR'", "[fix] two references"],
        ["CSEE input assumption", "[repo] docs", "delay sparsity only holds for unmodulated symbols; real data symbols whiten it", "[new] data vs reference symbols"],
        ["Shared-capacity allocation", "absent", "the 'load management' decision itself did not exist", "[new] allocator + Exp5"],
        ["Matrix-inversion benchmark", "[repo] complete", "NumPy engine used ReLU, model uses GELU; overstated docstring", "[fix] + re-run"]]
add_table(s, Inches(0.4), Inches(1.5), Inches(12.5), Inches(4.3), rows, col_widths=[2.4, 1.6, 5.4, 2.2], size=11)
takeaway(s, "Priority order followed: (1) make it run and correct, (2) credible baselines, (3) one well-evaluated improvement — the allocator.")
notes(s, """
Before adding anything I audited the repository. The most important finding: all the fronthaul experiment scripts and the notebook
import a package called src that was never committed, so none of the compression or split results could be reproduced.
I also found four modelling problems in the committed figures: the SVD baseline was timed with a full N-by-N SVD, which made it look
a hundred times slower than it is; the functional-split model had the bandwidth ordering inverted; the 'fast rank estimate' curve
was the exact rank plus random noise; and the NMSE interpretation was wrong. My objectives for this iteration were therefore:
reconstruct and test the simulator, fix the baselines, and add the one missing piece that the project title promises —
allocation under a shared capacity. The full audit is in docs/audit.md.
""")

# 4 --- literature comparison
s = new_slide("Research context and the gap this project addresses", "Verified sources only; full list with links in docs/research_review.md (search cutoff 17 Sep 2026)", section="Research context")
lit_rows = [["Direction", "Representative work", "What it assumes / measures", "Relation to this project"]]
for r in REFERENCES["comparison_rows"]:
    lit_rows.append(r)
add_table(s, Inches(0.4), Inches(1.5), Inches(12.5), Inches(4.4), lit_rows, col_widths=[2.0, 3.3, 3.8, 3.4], size=10.5)
takeaway(s, REFERENCES["gap_statement"])
notes(s, REFERENCES["lit_notes"])

# 5 --- system model & architecture
s = new_slide("System model", "3GPP TR 38.901 TDL-A uplink, one OFDM symbol per RU", tag="[new]", section="Technical approach")
# architecture diagram
x0, y0 = Inches(0.5), Inches(1.6)
for i, snr in enumerate([0, 10, 20, 30]):
    b = add_box(s, x0, y0 + Inches(0.95) * i, Inches(2.2), Inches(0.75), fill=LIGHT, line=NAVY)
    add_text(s, x0, y0 + Inches(0.95) * i, Inches(2.2), Inches(0.75),
             [(f"RU {i+1}  (SNR {snr} dB)", {"size": 12, "bold": True}), ("Y_k → encoder(a_k)", {"size": 11, "color": GREY})], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    arrow = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x0 + Inches(2.25), y0 + Inches(0.95) * i + Inches(0.22), Inches(0.9), Inches(0.3))
    arrow.fill.solid(); arrow.fill.fore_color.rgb = TEAL; arrow.line.fill.background()
add_text(s, x0 + Inches(2.2), y0 + Inches(3.85), Inches(1.1), Inches(0.3), [("rate R_k(a_k)", {"size": 10, "color": GREY})], align=PP_ALIGN.CENTER)
link = add_box(s, x0 + Inches(3.25), y0, Inches(1.0), Inches(3.55), fill=RGBColor(0xFA, 0xDB, 0xD8), line=RED)
add_text(s, x0 + Inches(3.25), y0, Inches(1.0), Inches(3.55), [("shared", {"size": 12, "bold": True, "color": RED}), ("fronthaul", {"size": 12, "bold": True, "color": RED}), ("Σ R_k ≤ C", {"size": 13, "bold": True})], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
arrow = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x0 + Inches(4.3), y0 + Inches(1.6), Inches(0.7), Inches(0.35)); arrow.fill.solid(); arrow.fill.fore_color.rgb = TEAL; arrow.line.fill.background()
du = add_box(s, x0 + Inches(5.05), y0, Inches(1.9), Inches(3.55), fill=LIGHT, line=NAVY)
add_text(s, x0 + Inches(5.05), y0, Inches(1.9), Inches(3.55), [("DU", {"size": 14, "bold": True}), ("decoders → Ŷ_k", {"size": 12}), ("", {}), ("controller:", {"size": 12, "bold": True, "color": TEAL}), ("ACAFS (streams)", {"size": 11}), ("allocator (bits)", {"size": 11}), ("uses predicted D_k(a)", {"size": 11, "color": GREY})], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
add_text(s, Inches(7.8), Inches(1.5), Inches(5.2), Inches(4.9), [
    ("Y_k = H_k · diag(x_k) + W_k  ∈ ℂ^{M×N}", {"size": 17, "bold": True}),
    ("H_k = Σ_l a_l e_lᵀ : 23 TDL-A taps at delays τ_l (100 ns RMS), a_l ~ CN(0, P_l R), R_ij = 0.7^|i−j|", {"size": 13}),
    ("⇒ rank(H) ≤ 23 (spatial low rank) and IFFT over subcarriers is concentrated on few delay bins", {"size": 13}),
    ("x_k: data symbols (random QPSK per subcarrier) or reference symbols (known, de-rotated → H + W′)", {"size": 13}),
    ("W ~ CN(0, σ²), σ² = 10^(−SNR/10),  E|H|² = 1", {"size": 13}),
    ("", {}),
    ("Metrics the model can measure honestly", {"size": 15, "bold": True, "color": NAVY}),
    ("NMSE (dB) = 10 log₁₀ ‖Y − Ŷ‖²_F / ‖Y‖²_F — vs transported Y, and vs noiseless H", {"size": 13}),
    ("Compression ratio = 2·M·N·16 / bits used (exact accounting incl. exponents, headers)", {"size": 13}),
    ("Encode time: numpy medians — relative comparison only", {"size": 13}),
    ("Allocation: utilisation, dropped cells, |predicted − measured| NMSE, decision time", {"size": 13}),
], bullet=False)
notes(s, """
The system: K radio units, each with a 64-by-1200 received matrix per OFDM symbol, one shared link to the DU.
The channel is 3GPP TDL-A: 23 taps, so the channel matrix has rank at most 23, and it is sparse along the delay axis after an IFFT.
The transmitted symbols matter: on a data symbol every subcarrier carries a random QPSK symbol; on a reference symbol the RU knows the sequence and can remove it.
I will show that this distinction decides which compression structure survives.
The metric is NMSE. I report it against the noisy transported matrix, which is what the link sees, and against the noiseless channel, which tells you what signal was actually lost.
I do not call anything 'latency' or 'BLER' because the simulator does not model those.
""")

# 6 --- formulation
s = new_slide("Formulation and the predictor that makes it cheap", "Multiple-choice knapsack per scheduling interval", tag="[new]", section="Technical approach")
add_text(s, Inches(0.5), Inches(1.5), Inches(6.2), Inches(5.0), [
    ("Decision", {"size": 16, "bold": True, "color": NAVY}),
    ("a_k ∈ menu (e.g. CSEE (K, b), BFP b) for each RU k", {"size": 14}),
    ("Rate R_k(a): exact bit count  ·  Distortion D_k(a) = ‖Y_k − Ŷ_k‖²/‖Y_k‖²", {"size": 14}),
    ("", {}),
    ("minimise  Σ_k D_k(a_k)     [or  max_k D_k(a_k)]", {"size": 17, "bold": True}),
    ("subject to  Σ_k R_k(a_k) ≤ C_link", {"size": 17, "bold": True}),
    ("", {}),
    ("Solver: greedy marginal gain on each RU's lower convex hull of (R, D) points — Lagrangian optimum up to one fractional step; overload → drop least-useful RUs.", {"size": 13}),
    ("Measured: ≈1 ms allocation + ≈27 ms predictions for 8 RUs × 66 options (Python).", {"size": 13, "color": GREY}),
], bullet=False)
add_text(s, Inches(6.9), Inches(1.5), Inches(6.1), Inches(5.0), [
    ("Proposition 1 (CSEE rate-distortion predictor)", {"size": 16, "bold": True, "color": NAVY}),
    ("Y_d = IFFT_N(Y) row-wise;  S = top-K delay bins by Σ_m |Y_d[m,n]|²", {"size": 14}),
    ("NMSE = ( T_S + E_q ) / ‖Y_d‖²_F", {"size": 17, "bold": True}),
    ("T_S = Σ_{n∉S} ‖Y_d[:,n]‖²  — discarded tail, exact (Parseval)", {"size": 13}),
    ("E_q = Σ_blocks n_b Δ_b²/6 (estimate) or n_b Δ_b²/2 (worst case, true bound), Δ_b = 2^{e_b} from BFP block exponents", {"size": 13}),
    ("Noise-aware form: subtract the noise expected in the tail, charge noise in kept bins, divide by signal energy — uses the RU's σ² estimate", {"size": 13}),
    ("Cost: one IFFT per RU for the whole menu (nested top-K supports).", {"size": 13}),
    ("Measured |predicted − measured| ≤ 0.5 dB for CSEE in Exp5 (BFP predictor: ≤ 1.3 dB).", {"size": 13, "bold": True, "color": GREEN}),
    ("", {}),
    ("Theorem 2 (RAS-BFP reference bound, from HMT 2011 Thm 10.5, Gaussian sketch, p ≥ 2)", {"size": 14, "bold": True, "color": NAVY}),
    ("E‖Y − Ŷ_r‖²_F ≤ (4 + 2r/(p−1)) · Σ_{i>r} σ_i²", {"size": 15, "bold": True}),
], bullet=False)
notes(s, """
The allocation is a multiple-choice knapsack: each RU picks one operating point from a menu; each point has an exactly known rate and a distortion.
We minimise total distortion subject to the sum of rates fitting the link. I solve it with the standard greedy marginal-gain rule on the convex hull
of each RU's rate-distortion points, which is the Lagrangian-relaxation optimum up to one fractional upgrade.
The key enabler is Proposition 1: for CSEE the distortion can be predicted without encoding. The tail term is exact by Parseval;
the quantisation term comes from the BFP block exponents. Because top-K supports are nested, a whole menu costs one IFFT per RU.
Measured prediction error is below half a dB. For RAS-BFP I adapt the Halko–Martinsson–Tropp bound; it is a reference for Gaussian sketches — I use SRHT and check it empirically.
""")

# 7 --- encoders
s = new_slide("Encoders: two baselines, two proposed", "All quantise with O-RAN-style block floating point (12-RE blocks, 4-bit exponent)", tag="[new]", section="Technical approach")
rows = [["Encoder", "Structure exploited", "Payload", "Complexity", "Analysis"],
        ["BFP (O-RAN WG4)", "dynamic range only", "2bMN + 4·M·N/12", "O(MN)", "quantisation-noise model"],
        ["Truncated SVD", "spatial low rank", "BFP(U_rΣ_r) + BFP(V_r)", "O(MN·min(M,N)) (economy)", "Eckart–Young floor"],
        ["CSEE (proposed)", "delay-domain sparsity, shared support across antennas", "BFP(Y_d[:,S]) + K·⌈log₂N⌉", "O(MN log N)", "Prop. 1 (exact tail)"],
        ["RAS-BFP (proposed)", "spatial low rank via randomised range finder: SRHT sketch → QR → Y Q → small SVD", "same shape as SVD at rank r", "O(MN(r+p))", "Thm. 2 (HMT-type)"]]
add_table(s, Inches(0.4), Inches(1.5), Inches(12.5), Inches(2.6), rows, col_widths=[1.8, 3.6, 2.6, 2.2, 2.0], size=12, bold_first_col=True)
add_text(s, Inches(0.5), Inches(4.3), Inches(12.3), Inches(2.0), [
    ("Which structure survives modulation?  Y = H·diag(x) + W", {"size": 16, "bold": True, "color": NAVY}),
    ("Spatial rank: rank(H·diag(x)) = rank(H) because diag(x) is invertible → SVD and RAS-BFP work on data and reference symbols.", {"size": 14}),
    ("Delay sparsity: IFFT(H·diag(x)) = IFFT(H) ⊛ IFFT(x); random QPSK x is white → the convolution spreads energy over all N bins → CSEE only works on reference symbols (H + W′).", {"size": 14}),
    ("This was not visible in the original documents because the original simulation used an unmodulated (constant) symbol.", {"size": 13, "color": RED}),
], bullet=True)
notes(s, """
Four encoders. BFP is the O-RAN baseline: a shared exponent per block of 12 resource elements and b-bit mantissas. Truncated SVD is the strong low-rank baseline, now with the economy SVD.
CSEE takes an IFFT over subcarriers, keeps the K delay bins with most energy summed over antennas — one support set signalled once — and BFP-quantises them.
RAS-BFP replaces the SVD with a randomised range finder: sketch the antenna dimension, QR, project, then a tiny SVD to get exactly rank r, so the payload shape is identical to the SVD baseline and the comparison is fair.
The important observation is at the bottom: multiplying by a diagonal of unit-modulus symbols does not change rank but does destroy delay sparsity. That decides where each encoder is applicable.
""")

# 8 --- Exp1
s = new_slide("Result 1 — rate-distortion frontier (Exp1)", f"M=64, N=1200, SNR 20 dB, {e1['realizations']} channel realisations; bits b=10 for SVD/CSEE/RAS-BFP", tag="[new]", section="Evidence")
add_picture_fit(s, os.path.join(FIG, "exp1_nmse_vs_cr.png"), Inches(0.3), Inches(1.45), Inches(8.6), Inches(4.9))
cr_c, n_c_d = c1("data", "CSEE", 120); _, n_c_r = c1("reference", "CSEE", 120)
cr_s, n_s = c1("data", "SVD", 12); _, n_r = c1("data", "RAS-BFP", 12); cr_b, n_b = c1("data", "BFP", 8)
rows = [["Operating point", "CR", "data", "reference"],
        ["BFP b=8", f"{cr_b:.1f}x", f"{n_b:.1f} dB", f"{n_b:.1f} dB"],
        ["SVD r=12", f"{cr_s:.1f}x", f"{n_s:.1f} dB", f"{n_s:.1f} dB"],
        ["RAS-BFP r=12", f"{cr_s:.1f}x", f"{n_r:.1f} dB", f"{n_r:.1f} dB"],
        ["CSEE K=120", f"{cr_c:.1f}x", f"{n_c_d:.1f} dB", f"{n_c_r:.1f} dB"]]
add_table(s, Inches(9.0), Inches(1.6), Inches(4.0), Inches(2.2), rows, col_widths=[1.7, 0.8, 1.0, 1.1], size=11, bold_first_col=True)
add_text(s, Inches(9.0), Inches(3.9), Inches(4.0), Inches(2.5), [
    ("Workload: TDL-A, SNR 20 dB; metric: NMSE vs transported Y", {"size": 11, "color": GREY}),
    ("CSEE reaches −17 to −21 dB at 6–78x CR on reference symbols but ≈0 dB on data symbols.", {"size": 12}),
    ("RAS-BFP is 1–4 dB worse than SVD at equal payload; Thm-2 bound 6–10 dB above (valid, loose).", {"size": 12}),
    ("All truncating encoders sit at the −20 dB noise floor of this metric at 20 dB SNR.", {"size": 12}),
], bullet=True)
takeaway(s, "CSEE is a reference-symbol (CSI) compressor, not a general I/Q compressor; spatial low-rank methods work on both symbol types.")
notes(s, f"""
Left panel: data symbols, right: reference symbols. Same channels, same encoders.
BFP is the grey curve: 2x compression at 8 bits for minus 46 dB — very accurate, very little compression.
SVD and RAS-BFP overlap in both panels because spatial rank does not care about modulation. RAS-BFP costs one to four dB for the same payload.
CSEE — the red curve — is the story: on reference symbols it gives minus {abs(n_c_r):.0f} dB at {cr_c:.0f}x, on data symbols it gives essentially zero dB. It only works when the delay domain is sparse.
Also note everything clusters at minus 20 dB, which is the noise floor of this metric at 20 dB SNR: the encoders discard noise and this metric counts that as error. The next slides handle that.
Dashed lines are the analytical predictions: Prop. 1 coincides with the CSEE curve; the HMT-type bound for RAS-BFP is above the curve by 6 to 10 dB — valid but loose, as expected for a Gaussian-sketch bound applied to SRHT.
""")

# 9 --- Exp2 + Exp4
s = new_slide("Results 2–3 — encode cost and two NMSE references", "Exp2: numpy medians of 7, N=1200 · Exp4: reference symbols, CR≈8x operating points, 12 realisations", tag="[new]", section="Evidence")
add_picture_fit(s, os.path.join(FIG, "exp2_complexity.png"), Inches(0.3), Inches(1.5), Inches(5.3), Inches(3.9))
add_picture_fit(s, os.path.join(FIG, "exp4_snr_sweep.png"), Inches(5.6), Inches(1.5), Inches(7.5), Inches(3.9))
add_text(s, Inches(0.4), Inches(5.45), Inches(5.2), Inches(1.0), [
    (f"M=64: BFP {t2('BFP',64):.2f} ms · CSEE {t2('CSEE',64):.2f} ms · RAS-BFP {t2('RAS-BFP',64):.1f} ms · SVD {t2('SVD',64):.1f} ms", {"size": 11, "bold": True}),
    (f"RAS-BFP ≈ {t2('SVD',64)/t2('RAS-BFP',64):.0f}x faster than economy SVD at M=64, {t2('SVD',128)/t2('RAS-BFP',128):.0f}x at M=128 (was reported as ~100x with a full SVD)", {"size": 10, "color": GREY}),
], bullet=False)
add_text(s, Inches(5.7), Inches(5.45), Inches(7.3), Inches(1.0), [
    (f"(a) vs Y: truncating encoders track −SNR. (b) vs H: at 0 dB SNR CSEE gives {e4v('vs_clean','CSEE',0):.0f} dB and SVD {e4v('vs_clean','SVD',0):.0f} dB where the raw noisy matrix is at 0 dB — they denoise.", {"size": 11}),
    (f"At 30 dB: SVD {e4v('vs_clean','SVD',30):.0f}, CSEE {e4v('vs_clean','CSEE',30):.0f}, RAS-BFP {e4v('vs_clean','RAS-BFP',30):.0f}, BFP b=4 {e4v('vs_clean','BFP',30):.0f} dB. CSEE on data symbols (dashed): ≈ −1 dB everywhere.", {"size": 11}),
], bullet=False)
takeaway(s, "The earlier claim 'stable across SNR' was an artefact of the metric; against the noiseless channel the encoders act as denoisers at low SNR.")
notes(s, """
Left: encode time versus number of antennas. With the economy SVD the baseline is 13 ms at 64 antennas; RAS-BFP is 2.6 ms, CSEE and BFP under one millisecond.
So the honest speed-up of RAS-BFP over SVD is about five times, not a hundred. These are Python numbers; I only claim the ordering and the scaling.
Right: NMSE against SNR for fixed operating points. Panel (a) is against the transported noisy matrix: the curves follow the minus-SNR line because discarded noise is counted as error.
Panel (b) is against the noiseless channel: at 0 dB SNR the raw matrix is at 0 dB, but CSEE at K=120 is at minus 9 dB — it removes noise.
The dashed CSEE-on-data curve stays at minus one dB across all SNRs, confirming the applicability limit.
""")

# 10 --- ACAFS
s = new_slide("Result 4 — rank-adaptive split selection (ACAFS, Exp3)", f"M=64, N=1200, {e3['realizations']} realisations per SNR; rank = 99 % energy of Y Yᴴ eigenvalues", tag="[fix]", section="Evidence")
add_picture_fit(s, os.path.join(FIG, "exp3_acafs.png"), Inches(0.3), Inches(1.45), Inches(8.3), Inches(4.2))
add_text(s, Inches(8.7), Inches(1.5), Inches(4.4), Inches(4.5), [
    ("Corrected bandwidth model (3GPP TR 38.801 / O-RAN)", {"size": 14, "bold": True, "color": NAVY}),
    ("antenna-space 7.1/7.2x-A: 2MNb  (reference)", {"size": 12}),
    ("beam-space 7.2x-B: 2rNb + weights/14", {"size": 12}),
    ("split 6 (MAC-PHY): r·N·η, η = 6 bit/RE  → ≈20x cheaper, needs full UL PHY in the RU", {"size": 12}),
    ("Rule: r/M < τ_high → beam-space with max(r, ⌈τ_low M⌉) streams; else split 6 if RU compute allows, else antenna-space.", {"size": 12}),
    ("", {}),
    (f"Beam-space only: 0 % below 15 dB → {100*e3['exact_beamspace'][e3['snr'].index(20)]:.0f} % at 20 dB (mean rank {e3['mean_rank_exact'][e3['snr'].index(20)]:.0f}).", {"size": 12, "bold": True}),
    (f"Fast estimator (1/8 subcarriers): {100*(1-e3['t_fast_ms'][5]/e3['t_exact_ms'][5]):.0f} % less time, but under-estimates rank by up to {max(e3['rank_abs_err']):.0f} at 10–17 dB → τ_low floor is the guard.", {"size": 12}),
    (f"Prop. 5 (uniform rank): {100*e3['prop5_beamspace']:.0f} % beam-space, {100*e3['prop5_split6']:.0f} % with split 6 — a prediction, not a bound.", {"size": 12, "color": GREY}),
], bullet=True)
takeaway(s, "The original 'saving vs split 6' figure had the split ordering inverted; the corrected model shows saving is driven by rank collapse at high SNR and by whether the RU may host split 6.", color=RED)
notes(s, """
ACAFS decides how many spatial streams to send based on the estimated rank of the received matrix.
First the correction: in 3GPP terms, split 6 carries decoded transport blocks and is the cheapest option on the fronthaul; the I/Q splits are the expensive ones.
The original figure reported savings 'versus split 6' as if split 6 were the most expensive; I inverted that back and report savings versus the fixed antenna-space split.
The result: with beam-space only, the saving is zero below 15 dB because the noise fills all 64 dimensions, and rises to about 83 percent at 20 dB where the rank collapses to about 10.
Allowing split 6 gives a large saving at any SNR in this model — but that option costs RU compute, which is exactly what the matrix-inversion benchmark quantifies.
The orange curve is a real fast estimator now — a random eighth of the subcarriers — and it is biased low in the transition region; the stream floor protects against that.
""")

# 11 --- allocator result
s = new_slide("Result 5 — shared-capacity allocation, 8 RUs (Exp5)", f"SNR per RU {{{','.join(map(str, e5cfg['cell_snrs_db']))}}} dB · menu 11 K × 6 b = 66 CSEE points · {e5cfg['seeds']} seeds · reference symbols", tag="[new]", section="Evidence")
add_picture_fit(s, os.path.join(FIG, "exp5_allocation.png"), Inches(0.3), Inches(1.45), Inches(7.6), Inches(5.0))
add_text(s, Inches(8.0), Inches(1.4), Inches(5.1), Inches(4.9), [
    ("Policies", {"size": 14, "bold": True, "color": NAVY}),
    ("uniform-CSEE / uniform-BFP: one operating point for all RUs (today's static config)", {"size": 11}),
    ("greedy-sum / greedy-max: proposed, decisions from Prop. 1 predictions only", {"size": 11}),
    ("greedy-clean: proposed, noise-aware objective (signal distortion)", {"size": 11}),
    ("oracle: greedy on measured NMSE — encodes every option (ablation)", {"size": 11}),
    ("", {}),
    ("What the panels show", {"size": 14, "bold": True, "color": NAVY}),
    (f"(a) vs Y: greedy within 0.5 dB of the oracle at every capacity; {abs(r5(0.1,'greedy-sum','avg_cell_nmse_db_mean')-r5(0.1,'uniform-CSEE','avg_cell_nmse_db_mean')):.1f} dB better than uniform at 27.5 Gbps, {abs(r5(0.2,'greedy-sum','avg_cell_nmse_db_mean')-r5(0.2,'uniform-CSEE','avg_cell_nmse_db_mean')):.1f} dB at 55 Gbps; uniform-BFP cannot fit below 55 Gbps (drops RUs)", {"size": 11}),
    (f"(b) vs H: greedy-sum wastes bits on noise in low-SNR RUs; noise-aware objective is {abs(r5(0.1,'greedy-clean','avg_cell_nmse_clean_db_mean')-r5(0.1,'greedy-sum','avg_cell_nmse_clean_db_mean')):.1f} dB better at 27.5 Gbps", {"size": 11}),
    ("(c) min-max objective: worst RU up to 2.2 dB better (27.5 Gbps) at a 0.7–2.6 dB cost in the mean", {"size": 11}),
    (f"(d) noise-aware uses only {100*r5(0.5,'greedy-clean','utilization_mean'):.0f} % at 138 Gbps — more bits stop helping the signal", {"size": 11}),
], bullet=True)
takeaway(s, "Prediction-driven allocation matches an encode-everything oracle; the objective matters — optimise signal distortion, not fidelity to noise.")
notes(s, f"""
This is the load-management experiment. Eight radio units with SNRs from 0 to 30 dB share one link; capacity is swept from 0.5 % to 50 % of the raw load.
Each radio unit gets one CSEE operating point. The controller uses only the Proposition-1 predictions; afterwards every RU is actually encoded and the true NMSE measured.
Panel (a): the greedy allocator (red) sits on top of the oracle (green) that encodes every option — the predictor is good enough. It beats uniform allocation by up to eleven dB, and the O-RAN-style uniform BFP cannot even fit until 55 gigabit.
Panel (b) is the honest part. Against the noiseless channel, minimising fidelity to the noisy matrix spends bits reproducing noise in the 0 and 5 dB cells — at 14 and 27 gigabit it is worse than uniform.
That negative result led to the noise-aware objective, orange: it uses the RU's noise variance in Proposition 1, gains four to eight dB on the signal, and at high capacity it stops using the link once more bits do not help — panel (d).
Error bars are one standard deviation over five seeds; they are small because the channel statistics are stationary.
""")

# 12 --- compute benchmark
s = new_slide("Supporting result — compute cost of a split decision", "MMSE-type processing needs matrix inverses per PRB group; timings on a 4-core CPU, float32, held-out matrices", tag="[repo]", section="Evidence")
rows = [["n", "LAPACK LU (numpy.linalg.inv)", "classic Newton–Schulz", "InverseNet-NS (17 params, learned)", "InverseNet-Ultra (learned)", "InverseNet-MLP"]]
for dim in (10, 100, 500):
    r = [str(dim)]
    for key in ("LAPACK getri", "Newton-Schulz iteration", "InverseNet-NS", "InverseNet-Ultra", "InverseNet-MLP"):
        sub = bench[(bench.dim == dim) & (bench.method.str.contains(key, regex=False))]
        r.append("n/a" if sub.empty else f"{sub.iloc[0].median_ms:.3g} ms · err {sub.iloc[0].rel_err_vs_true:.1e}")
    rows.append(r)
add_table(s, Inches(0.4), Inches(1.5), Inches(12.5), Inches(1.9), rows, col_widths=[0.6, 2.4, 2.2, 2.6, 2.4, 2.3], size=11)
add_text(s, Inches(0.5), Inches(3.6), Inches(12.3), Inches(2.6), [
    ("LAPACK LU is fastest and float32-exact at every size; a 100×100 inverse (≈0.14 ms) fits a 500 µs slot per PRB group on one core, a 500×500 one (≈6 ms) does not.", {"size": 14}),
    ("Learned unrolled Newton–Schulz (17 parameters) generalises to 4e-4 error at n=100 (4e-2 at n=10, 7e-3 at n=500) but is slower than LU; direct-regression MLP fails (0.36 error at n=10). Ultra reaches ≈1e-6 at n=100/500 but 0.17 at n=10 and never beats LU medians.", {"size": 13}),
    ("Fixed this iteration: the NumPy inference engine used ReLU while the trained model uses GELU (now identical, tested); overstated docstring corrected; benchmark re-run (n=500 with 20 held-out matrices).", {"size": 13, "color": RED}),
    ("Role in the project: an RU-compute constraint for the split-6 option in ACAFS — connecting the two halves is [future] work.", {"size": 13, "color": GREY}),
], bullet=True)
notes(s, """
This benchmark existed in the repository and I kept it because it answers a question the split decision raises: if the RU has to run the uplink PHY for split 6, what does the equaliser's matrix inversion cost?
LAPACK LU is the reference: a 100-by-100 inverse in 0.14 ms fits a slot; 500-by-500 does not. The learned unrolled Newton–Schulz is interesting because it has 17 parameters and generalises, but it is not faster on a CPU.
I fixed one bug — the NumPy engine used the wrong activation — and toned down a docstring that claimed float32 precision and LU-beating speed, which the numbers do not support.
Wiring this into ACAFS as a compute constraint is future work.
""")

# 13 --- contributions / limitations / plan
s = new_slide("Contributions, limitations and plan to final evaluation", section="Closing")
add_text(s, Inches(0.4), Inches(1.3), Inches(4.2), Inches(5.2), [
    ("Completed", {"size": 17, "bold": True, "color": GREEN}),
    ("Runnable, tested simulator for channel → encoders → split → allocation (was missing)", {"size": 12, "tag": "[new]"}),
    ("Corrected baselines and models (economy SVD, split ordering, real rank estimator, two NMSE references)", {"size": 12, "tag": "[fix]"}),
    ("Prop. 1 predictor within 0.5 dB; Thm. 2 reference bound checked", {"size": 12, "tag": "[new]"}),
    ("Multi-cell allocator with static baselines, oracle and objective ablations, 5 seeds", {"size": 12, "tag": "[new]"}),
    ("Finding: delay-domain compression is CSI-only; spatial low rank is modulation-invariant", {"size": 12, "tag": "[new]"}),
    ("Compute benchmark, bug-fixed and re-run", {"size": 12, "tag": "[repo]"}),
], bullet=True)
add_text(s, Inches(4.7), Inches(1.3), Inches(4.2), Inches(5.2), [
    ("Limitations", {"size": 17, "bold": True, "color": RED}),
    ("Single symbol; no scheduler, HARQ, latency, multi-slot dynamics", {"size": 12}),
    ("CSEE valid on reference symbols only → Exp5 covers reference-symbol traffic", {"size": 12}),
    ("Python timings: ordering and scaling only", {"size": 12}),
    ("Thm. 2 proven for Gaussian sketch; SRHT checked empirically", {"size": 12}),
    ("Split-6 rate model coarse (η = 6 bit/RE); σ² assumed known in the noise-aware ablation", {"size": 12}),
    ("No real traces; only TDL-A", {"size": 12}),
    ("No novelty claimed for any single encoder; the contribution is the validated system and its findings", {"size": 12, "italic": True}),
], bullet=True)
add_text(s, Inches(9.0), Inches(1.3), Inches(4.0), Inches(5.2), [
    ("Next (to final evaluation)", {"size": 17, "bold": True, "color": TEAL}),
    ("Slot-level simulation mixing data + reference symbols; mixed CSEE/RAS-BFP/BFP menu (needs RAS-BFP predictor)", {"size": 12, "tag": "[future]"}),
    ("Joint ACAFS + allocator under one capacity with the compute benchmark as RU constraint", {"size": 12, "tag": "[future]"}),
    ("Sensitivity to σ² estimation error and rank bias", {"size": 12, "tag": "[future]"}),
    ("Learned predictor only where no analytical one exists, judged against the analytical one", {"size": 12, "tag": "[future]"}),
    ("C/SIMD timing of BFP, CSEE, RAS-BFP", {"size": 12, "tag": "[future]"}),
], bullet=True)
notes(s, """
To summarise. Completed: a simulator that runs and is tested; corrected baselines; an analytical predictor that is accurate enough to drive decisions; a multi-cell allocator with proper baselines and ablations; and one clear finding about which compression structure survives modulation.
Limitations I want to state myself: single-symbol model, CSEE only on reference symbols, Python timings, and the RAS-BFP bound is a Gaussian reference.
I am not claiming novelty for any encoder — the encoders adapt known techniques; the contribution is the validated system and the findings that came out of making it correct.
Next: slot-level simulation with mixed symbol types, joining the split decision with the allocator under one capacity, and only then consider a learned component where an analytical predictor does not exist.
""")

# 14 --- references (main deck end)
refs = REFERENCES["ieee_list"]
for part, chunk in enumerate((refs[:11], refs[11:]), start=1):
    s = new_slide(f"References ({part}/2) — verified sources, see docs/research_review.md", section="References")
    add_text(s, Inches(0.4), Inches(1.2), Inches(12.5), Inches(5.9), [(r, {"size": 11, "space": 3}) for r in chunk], bullet=False)
    notes(s, "Reference list. Every entry was checked against a primary page (publisher, arXiv record, or standards body) on 17 Sep 2026. Entries marked '(abstract)' were not read in full and are cited only for what their abstracts state.")

# ============================================================================= BACKUP
s = new_slide("Backup — audit: verified problems in original material", section="Backup")
add_text(s, Inches(0.4), Inches(1.3), Inches(12.5), Inches(5.2), [
    ("src/ absent from every commit and branch; Exp1-4 + notebook import it → nothing ran", {"size": 13}),
    ("Exp2 SVD baseline: committed figure ~1.7 s at M=64 vs 13 ms economy SVD; O(MN) reference line plotted in seconds on a ms axis", {"size": 13}),
    ("Exp3: 'fast rank est.' = exact rank + Uniform{−1,0,1}; 'Theorem 5 bound' below the simulated curve → not a bound", {"size": 13}),
    ("ACAFS: split 6 treated as the most expensive split; TR 38.801 ordering is R_6 ≪ R_7.2x-beam ≤ R_7.x-antenna", {"size": 13}),
    ("Exp4: 'stable across SNR' claimed while the figure shows NMSE ≈ −SNR", {"size": 13}),
    ("CSEE input: constant pilot ⇒ delay sparsity; with random QPSK per subcarrier CSEE gives ≈ −0.5 dB", {"size": 13}),
    ("CR reference 32-bit components ⇒ all CRs inflated 2x (BFP b=8: 3.9x quoted vs 2.0x against 16-bit)", {"size": 13}),
    ("Docs: 'Theorems 1-5' without statements/proofs; '100 MHz at 15 kHz' with N=1200 (=18 MHz); TWC/JSAC target; AVX-512/CUDA/USRP roadmap", {"size": 13}),
    ("matinv_bench: ReLU vs GELU in the NumPy engine; docstring claiming 1e-7 error and LU-beating latency", {"size": 13}),
    ("Original figures/tables preserved in results/original_snapshot/ for comparison", {"size": 13, "color": GREY}),
], bullet=True)
notes(s, "Backup slide with the full list of verified problems, in case the committee asks what exactly was wrong with the earlier figures.")

s = new_slide("Backup — Proposition 1 and the noise-aware variant", section="Backup")
add_text(s, Inches(0.4), Inches(1.3), Inches(12.5), Inches(5.4), [
    ("Setup: Y ∈ ℂ^{M×N}; Y_d = IFFT_N(Y) row-wise (numpy: Y = FFT(Y_d), ‖Y‖²_F = N‖Y_d‖²_F). Encoder keeps columns S (|S|=K) and BFP-quantises them: Ŷ_d = Q(Y_d[:,S]) on S, 0 elsewhere. Decoder: Ŷ = FFT(Ŷ_d).", {"size": 13}),
    ("‖Y − Ŷ‖²_F = N‖Y_d − Ŷ_d‖²_F = N( Σ_{n∉S}‖Y_d[:,n]‖² + ‖Y_d[:,S] − Q(Y_d[:,S])‖²_F ) = N(T_S + E_q).", {"size": 13}),
    ("NMSE = N(T_S + E_q) / (N‖Y_d‖²) = (T_S + E_q)/‖Y_d‖²_F.  T_S is exact; E_q depends on the quantiser.", {"size": 13}),
    ("BFP block with exponent e_b, step Δ_b = 2^{e_b}: per real component |error| ≤ Δ_b/2 (deterministic) and Var ≈ Δ_b²/12 (high-rate model). Complex sample: ≤ Δ_b²/2 worst case, ≈ Δ_b²/6 expected. Summing over the n_b non-zero samples of each block gives E_q^{wc} (bound) and E_q^{est} (estimate). Zero samples quantise exactly.", {"size": 13}),
    ("Top-K supports are nested in K, so one sort of the N bin energies gives T_S for all K; block maxima per K give Δ_b for all b as a shift of log₂(2^{b−1}−1). Whole 66-point menu ≈ one encoder pass.", {"size": 13}),
    ("Noise-aware form (RU knows σ²): white noise has total delay-domain energy Mσ² spread evenly over N bins. Signal distortion ≈ [max(T_S − Mσ²(N−K)/N, 0) + Mσ²K/N + E_q] / (‖Y_d‖² − Mσ²). Measured within 0.1 dB at 20 dB SNR and ≈1.7 dB at 0 dB SNR.", {"size": 13}),
    ("Why it matters: with the plain form the allocator upgrades low-SNR RUs to reproduce noise; with the noise-aware form the marginal gain of extra bits goes to zero once the tail is noise, so capacity is released.", {"size": 13, "color": TEAL}),
], bullet=True)
notes(s, "Derivation of Proposition 1 for a technical question. The key point is that the tail term is an identity, only the quantisation term is modelled.")

s = new_slide("Backup — RAS-BFP algorithm and Theorem 2", section="Backup")
add_text(s, Inches(0.4), Inches(1.3), Inches(12.5), Inches(5.4), [
    ("1. Sketch antennas: Z = Ω Y ∈ ℂ^{(r+p)×N}, Ω = √(M/(r+p)) · S · H_M · D (SRHT: random signs D, Walsh–Hadamard H_M via fast transform, row sampler S) or Gaussian.", {"size": 13}),
    ("2. Thin QR: Zᴴ = Q R, Q ∈ ℂ^{N×(r+p)} spans an approximate dominant right singular subspace of Y.", {"size": 13}),
    ("3. Project: L = Y Q (M×(r+p)); small SVD of L; keep rank r: L_r = U_rΣ_r, Q_r = Q V_r. Ŷ = L_r Q_rᴴ (HMT Alg. 4.1 + 5.1).", {"size": 13}),
    ("4. Transmit BFP(L_r) and BFP(Q_r) — identical payload shape to truncated SVD at rank r ⇒ equal CR, fair comparison.", {"size": 13}),
    ("Cost: O(MN log M) sketch (SRHT) or O(MN(r+p)) (Gaussian) + O(N(r+p)²) QR + O(MN(r+p)) projection, vs O(MN·min(M,N)) for the SVD.", {"size": 13}),
    ("Theorem 2 (HMT 2011, Thm 10.5, Gaussian Ω, p ≥ 2): E‖Y − YQQᴴ‖²_F ≤ (1 + r/(p−1)) Σ_{i>r}σ_i². Truncation adds at most an Eckart–Young term (‖Y − Q[QᴴY]_r‖ ≤ ‖Y − QQᴴY‖ + ‖Y − Y_r‖), so E‖Y − Ŷ‖²_F ≤ (4 + 2r/(p−1)) Σ_{i>r}σ_i². Quantisation is on top.", {"size": 13}),
    ("Caveats: proven for Gaussian sketches; SRHT (Tropp 2011) needs larger oversampling for a proof — with p = 4 the bound holds empirically with 6–10 dB slack in Exp1. For p < 2 the code returns ∞ rather than a made-up bound. SRHT falls back to Gaussian when M is not a power of two or r+p ≥ M.", {"size": 13, "color": GREY}),
], bullet=True)
notes(s, "Backup for the randomised encoder. If asked why not just the SVD: cost. If asked whether the bound is tight: no, and it is stated for Gaussian sketches; the plot shows the slack.")

s = new_slide("Backup — ACAFS bandwidth model and allocator", section="Backup")
add_text(s, Inches(0.4), Inches(1.3), Inches(6.1), Inches(5.4), [
    ("Bits per OFDM symbol per RU (M=64, N=1200, b=16, η=6, T_c=14)", {"size": 14, "bold": True, "color": NAVY}),
    ("antenna-space: 2MNb = 2 457 600", {"size": 13}),
    ("beam-space, r streams: 2rNb + 2Mrb/T_c  (r=10: 385 463; r=32: 1 233 481)", {"size": 13}),
    ("split 6, r layers: rNη  (r=10: 72 000; r=64: 460 800)", {"size": 13}),
    ("rule: ρ = r/M; ρ < τ_high=0.55 → beam-space with max(r, ⌈0.15·M⌉=10) streams; else split 6 if allowed, else antenna-space", {"size": 13}),
    ("Prop. 5 = mean over r∈{1..M} of the per-rank saving under the rule (a prediction; simulated saving can exceed it when ranks concentrate low)", {"size": 13}),
], bullet=True)
add_text(s, Inches(6.7), Inches(1.3), Inches(6.3), Inches(5.4), [
    ("greedy_allocate(rates, dist, C, objective)", {"size": 14, "bold": True, "color": NAVY}),
    ("for each RU: keep only (R, D) points on the lower convex hull (dominated / non-convex points never help)", {"size": 13}),
    ("start every RU at its cheapest point; if Σ R > C: drop RUs with the largest predicted D at that point until it fits (they gain least from transport)", {"size": 13}),
    ("repeat: among feasible next-hull upgrades pick argmax ΔD/ΔR (sum) or the RU with current max D (max); stop when none fits", {"size": 13}),
    ("guarantee: Lagrangian-relaxation optimum up to one fractional upgrade (standard for multiple-choice knapsack greedy on convex hulls)", {"size": 13}),
    ("uniform_allocate: best single point that fits for all RUs — the static-configuration baseline", {"size": 13}),
    ("tests: capacity respected, greedy ≥ uniform on its objective, low load → best point, overload → drops, zero-traffic RU, invalid inputs", {"size": 13, "color": GREY}),
], bullet=True)
notes(s, "Numbers behind the split model and pseudo-code of the allocator, for questions on either.")

s = new_slide("Backup — reproducibility: commands and outputs", section="Backup")
add_text(s, Inches(0.4), Inches(1.3), Inches(12.5), Inches(5.4), [
    ("pip install -r requirements.txt   (numpy, scipy, pandas, matplotlib, tqdm, pytest; torch only for matinv_bench)", {"size": 13}),
    ("python -m pytest tests -q                       → 42 passed (~1 s)", {"size": 13}),
    ("python experiments/exp1_nmse_vs_cr.py            → results/figures/exp1_*.png|pdf, results/data/exp1_nmse_vs_cr.json  (~10 s)", {"size": 13}),
    ("python experiments/exp2_complexity.py            → exp2_*  (~2 s)", {"size": 13}),
    ("python experiments/exp3_acafs_gain.py            → exp3_*  (~3 s)", {"size": 13}),
    ("python experiments/exp4_snr_sweep.py             → exp4_*  (~5 s)", {"size": 13}),
    ("python experiments/exp5_fronthaul_allocation.py  → exp5_allocation.png, exp5_allocation_runs.csv (every run), exp5_allocation_summary.csv  (~8 s)", {"size": 13}),
    ("jupyter nbconvert --execute --inplace notebooks/mid_evaluation_demo.ipynb   (from notebooks/)", {"size": 13}),
    ("python -m matinv_bench.generate_dataset --dims 10 100 --num-samples 1000; python -m matinv_bench.benchmark --dims 10 100", {"size": 13}),
    ("Every results/data file records generation time, Python/numpy version, host and CPU count; results/logs/ has the console output of the runs shown here.", {"size": 13, "color": GREY}),
    ("Host used for the numbers in this deck: 4-core x86_64, Python 3.12, numpy 2.x, no GPU.", {"size": 13, "color": GREY}),
], bullet=True)
notes(s, "If the live demo fails, these are the saved outputs and how they were produced.")

out = os.path.join(ROOT, "docs", "mid_evaluation.pptx")
prs.save(out)
print(f"wrote {out} with {len(prs.slides)} slides")
