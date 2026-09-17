"""Build the mid-evaluation deck (editable .pptx) from the saved results.

    python -m fhlm.make_slides            # -> docs/fhlm/BTP_midterm_fronthaul_load_management.pptx

Every number on the slides is read from results/fhlm/*.csv|json produced by
run_experiments.py / train.py; figures are the PNGs from make_figures.py.
Slides carry speaker notes. Nothing is hard-coded from memory.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu

from .run_experiments import RESULTS_DIR, PRIMARY_METRIC
from .config import NetworkConfig, ControlConfig

FIG = os.path.join(RESULTS_DIR, "figures")
OUT = "docs/fhlm/BTP_midterm_fronthaul_load_management.pptx"

NAVY = RGBColor(0x1F, 0x3A, 0x5F)
TEAL = RGBColor(0x00, 0x7C, 0x91)
RED = RGBColor(0xC6, 0x28, 0x28)
GREY = RGBColor(0x55, 0x55, 0x55)
LIGHT = RGBColor(0xF2, 0xF4, 0xF7)
GREEN = RGBColor(0x2E, 0x7D, 0x32)
ORANGE = RGBColor(0xEF, 0x6C, 0x00)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

W, H = Inches(13.333), Inches(7.5)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = W, H
        self.blank = self.prs.slide_layouts[6]
        self.n = 0

    def slide(self, title: str, notes: str = "", section: str = ""):
        s = self.prs.slides.add_slide(self.blank)
        self.n += 1
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, Inches(0.9))
        bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
        tb = s.shapes.add_textbox(Inches(0.4), Inches(0.12), Inches(10.6), Inches(0.7))
        tb.text_frame.word_wrap = True
        p = tb.text_frame.paragraphs[0]
        p.text = title
        p.font.size, p.font.bold, p.font.color.rgb = Pt(24), True, WHITE
        if section:
            sb = s.shapes.add_textbox(Inches(10.9), Inches(0.28), Inches(2.3), Inches(0.4))
            q = sb.text_frame.paragraphs[0]
            q.text, q.alignment = section, PP_ALIGN.RIGHT
            q.font.size, q.font.color.rgb = Pt(11), RGBColor(0xCF, 0xD8, 0xE3)
        fb = s.shapes.add_textbox(Inches(0.4), Inches(7.05), Inches(12.5), Inches(0.35))
        q = fb.text_frame.paragraphs[0]
        q.text = f"BTP mid-evaluation  |  Fronthaul load management  |  {self.n}"
        q.font.size, q.font.color.rgb = Pt(9), GREY
        q.alignment = PP_ALIGN.RIGHT
        if notes:
            s.notes_slide.notes_text_frame.text = notes
        return s

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.prs.save(path)


def bullets(slide, items: List, left, top, width, height, size=16, color=None, para_space=6):
    """items: str or (str, level) or (str, level, bold)"""
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for it in items:
        text, level, bold = (it, 0, False) if isinstance(it, str) else (it + (False,))[:3]
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.text = ("• " if level == 0 else "– ") + text if text else ""
        p.level = level
        p.font.size = Pt(size - 2 * level)
        p.font.bold = bold
        p.font.color.rgb = color or RGBColor(0x22, 0x22, 0x22)
        p.space_after = Pt(para_space)
    return tb


def text(slide, s, left, top, width, height, size=14, bold=False, color=None, align=PP_ALIGN.LEFT, italic=False):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    lines = s.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.font.size, p.font.bold, p.font.italic = Pt(size), bold, italic
        p.font.color.rgb = color or RGBColor(0x22, 0x22, 0x22)
        p.alignment = align
    return tb


def box(slide, s, left, top, width, height, fill=LIGHT, size=13, bold=False, color=None, line=None,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, align=PP_ALIGN.CENTER):
    sh = slide.shapes.add_shape(shape, left, top, width, height)
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.color.rgb = RGBColor(0xB0, 0xB8, 0xC4); sh.line.width = Pt(0.75)
    else:
        sh.line.color.rgb = line; sh.line.width = Pt(1.25)
    tf = sh.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, line_ in enumerate(s.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line_
        p.font.size, p.font.bold = Pt(size), bold
        p.font.color.rgb = color or RGBColor(0x22, 0x22, 0x22)
        p.alignment = align
    return sh


def arrow(slide, x1, y1, x2, y2, color=GREY, width=1.5):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = color
    c.line.width = Pt(width)
    # arrowhead via XML
    ln = c.line._get_or_add_ln()
    from pptx.oxml.ns import qn
    tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    return c


def picture(slide, path, left, top, width=None, height=None):
    if not os.path.exists(path):
        return box(slide, f"[figure missing: {os.path.basename(path)}]", left, top, width or Inches(6),
                   height or Inches(3), fill=RGBColor(0xFF, 0xF3, 0xE0))
    return slide.shapes.add_picture(path, left, top, width=width, height=height)


def table(slide, df: pd.DataFrame, left, top, width, height, size=11, header_fill=NAVY, fmt=None):
    rows, cols = df.shape[0] + 1, df.shape[1]
    tbl = slide.shapes.add_table(rows, cols, left, top, width, height).table
    for j, c in enumerate(df.columns):
        cell = tbl.cell(0, j)
        cell.text = str(c)
        cell.fill.solid(); cell.fill.fore_color.rgb = header_fill
        for p in cell.text_frame.paragraphs:
            p.font.size, p.font.bold, p.font.color.rgb = Pt(size), True, WHITE
    for i in range(df.shape[0]):
        for j in range(cols):
            v = df.iat[i, j]
            cell = tbl.cell(i + 1, j)
            cell.text = fmt(v, df.columns[j]) if fmt else (f"{v:.3g}" if isinstance(v, float) else str(v))
            cell.fill.solid(); cell.fill.fore_color.rgb = WHITE if i % 2 else LIGHT
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(size)
    return tbl


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def _csv(name):
    p = os.path.join(RESULTS_DIR, name)
    return pd.read_csv(p) if os.path.exists(p) else None


def _json(name):
    p = os.path.join(RESULTS_DIR, name)
    return json.load(open(p)) if os.path.exists(p) else None


def load_results():
    R = {"main": _csv("main_runs.csv"), "paired": _csv("main_paired.csv"), "sweep": _csv("sweep_runs.csv"),
         "comp": _csv("compression_runs.csv"), "tuning": _json("tuning.json"),
         "forecast": _json("forecast_training_T20_d2.json")}
    p = "results/benchmark_results.csv"           # Part A: matrix-inversion benchmark (earlier work)
    R["matinv"] = pd.read_csv(p) if os.path.exists(p) else None
    return R


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def summary_table(main: pd.DataFrame, scenarios, methods, labels) -> pd.DataFrame:
    g = main.groupby(["scenario", "method"])[PRIMARY_METRIC].agg(["mean", "std"])
    rows = []
    for m in methods:
        row = {"Method": labels[m]}
        for s in scenarios:
            mu, sd = g.loc[(s, m), "mean"], g.loc[(s, m), "std"]
            row[s] = f"{100 * mu:.2f} ± {100 * sd:.2f}"
        rows.append(row)
    return pd.DataFrame(rows)


def matinv_table(bench: pd.DataFrame) -> pd.DataFrame:
    """Median time (ms) and relative error for a few methods at n = 100 and 500."""
    keep = {
        "LAPACK getri (numpy.linalg.inv)": "LU via LAPACK (numpy.linalg.inv)",
        "LU decomposition (scipy lu_factor/lu_solve)": "LU (scipy)",
        "QR decomposition": "QR",
        "SVD": "SVD",
        "Newton-Schulz iteration": "Newton-Schulz iteration",
        "InverseNet-Ultra (learned high-order)": "Learned iteration (InverseNet-Ultra)",
        "InverseNet-MLP": "Direct neural net (InverseNet-MLP)",
    }
    rows = []
    for raw, nice in keep.items():
        row = {"Method": nice}
        for n in (100, 500):
            r = bench[(bench.method == raw) & (bench.dim == n)]
            if len(r):
                row[f"n={n}: median ms"] = f"{r.median_ms.iloc[0]:.2f}"
                row[f"n={n}: rel. error"] = f"{r.rel_err_vs_true.iloc[0]:.0e}"
            else:
                row[f"n={n}: median ms"] = "n/a"
                row[f"n={n}: rel. error"] = "n/a"
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# slides
# ---------------------------------------------------------------------------
def build(out: str = OUT):
    R = load_results()
    net, ctrl = NetworkConfig(), ControlConfig()
    d = Deck()
    main, paired, sweep, comp, tuning, fc, bench = (R["main"], R["paired"], R["sweep"], R["comp"], R["tuning"],
                                                    R["forecast"], R["matinv"])
    SC = ["low", "moderate", "high", "overload_bursts", "shift"]
    SCL = {"low": "Low 0.50", "moderate": "Moderate 0.65", "high": "High 0.80", "overload_bursts": "Flash crowds",
           "shift": "Shift (held-out)"}
    LAB = {"static_equal": "Static equal share", "reactive_prop": "Reactive proportional",
           "queue_aware": "Deadline-aware reactive", "point_forecast": "Point forecast + water-fill",
           "proposed_window": "Proposed rule, simple quantiles (no ML)", "proposed": "Proposed (GBM quantiles + KKT rule)",
           "proposed_cal": "Proposed + online calibration", "oracle": "Oracle water-fill (knows the future)"}

    SHORT_LAB = {"reactive_prop": "reactive prop.", "queue_aware": "deadline-aware", "point_forecast": "point forecast",
                 "proposed": "proposed", "proposed_window": "proposed (no ML)", "proposed_cal": "proposed + cal.",
                 "static_equal": "static", "oracle": "oracle"}

    def pr(scenario, baseline, col="rel_reduction_pct"):
        if paired is None:
            return float("nan")
        r = paired[(paired.scenario == scenario) & (paired.baseline == baseline)]
        return float(r[col].iloc[0]) if len(r) else float("nan")

    def mean_metric(scenario, method, metric=PRIMARY_METRIC):
        if main is None:
            return float("nan")
        return float(main[(main.scenario == scenario) & (main.method == method)][metric].mean())

    BLUE_FILL = RGBColor(0xE3, 0xF2, 0xFD)
    ORANGE_FILL = RGBColor(0xFF, 0xF3, 0xE0)
    RED_FILL = RGBColor(0xFF, 0xEB, 0xEE)

    # 1 Title ---------------------------------------------------------------
    s = d.slide("", notes=(
        "Opening (60-90 s): Good morning. My project is about fronthaul load management in Open RAN. The "
        "fronthaul is the link between the radio unit on the tower and the processing unit. It carries raw radio "
        "samples, so it is one of the most loaded links in the network. There are two ways to manage that load. "
        "The first is to make the data smaller: compress it. In the first part of my project I studied compression "
        "methods based on matrix decomposition, and I benchmarked how fast the matrix operations behind them "
        "(inversion, SVD, QR, learned iterations) actually run. The second way is to share one link well between "
        "several cells. In the second part I built a simulator of a shared link, five reference controllers, and a "
        "new allocation rule that uses a forecast of each cell's need, including how uncertain that forecast is. "
        "On five test scenarios the rule reduces priority-weighted deadline violations by 10 to 50 percent "
        "compared with the same controller using a plain forecast, and it beats the reactive controller on every "
        "test seed. I will also show where it does not help. Everything I show is produced by code in the repository."))
    bg = s.shapes[0]; bg.height = H
    text(s, "Fronthaul Load Management in Open RAN", Inches(0.8), Inches(1.5), Inches(11.7), Inches(0.9), size=36,
         bold=True, color=WHITE)
    text(s, "Part A: shrinking the load with matrix-decomposition compression\n"
            "Part B: sharing one fronthaul link between cells with forecast-aware budgets",
         Inches(0.8), Inches(2.45), Inches(11.7), Inches(1.2), size=20, color=RGBColor(0xCF, 0xD8, 0xE3))
    text(s, "B.Tech. Project — mid-term evaluation", Inches(0.8), Inches(3.9), Inches(11.7), Inches(0.5), size=18,
         color=WHITE)
    text(s, "Student: <name>   |   Supervisor: <name>   |   Department of <dept>",
         Inches(0.8), Inches(4.5), Inches(11.7), Inches(0.5), size=14, color=RGBColor(0xCF, 0xD8, 0xE3))
    text(s, "What exists today: compression study + matrix-maths benchmark (Part A); working simulator, 7 controllers, "
         "trained forecaster, 300+ experiment runs, tests and this deck (Part B). All generated from the repository.",
         Inches(0.8), Inches(5.5), Inches(11.7), Inches(0.9), size=13, color=WHITE, italic=True)

    # 2 The problem ---------------------------------------------------------
    s = d.slide("The problem: the fronthaul carries a lot of data", section="1 Motivation", notes=(
        "In Open RAN the radio unit does only the lowest layer of processing and sends frequency-domain radio "
        "samples to the distributed unit. This is the 7-2x split. The data rate is large, but it depends on how "
        "many resource blocks are scheduled, so it goes up and down with traffic. Operators use that: several "
        f"radio units share one Ethernet link that is smaller than their total peak — in our setup {net.oversubscription:.1f} "
        "times smaller. That works most of the time. When several cells burst at once, someone has to wait, and "
        "low-latency traffic can only wait about two milliseconds. So there are two questions: how do we make the "
        "data smaller, and how do we share the link when it is full?"))
    bullets(s, [
        ("In the 7-2x split, the radio unit (O-RU) sends radio samples (IQ data) to the processing unit (O-DU)", 0),
        (f"Every scheduled resource block costs about {net.fh_bits_per_prb_layer:,.0f} bits on the link (9-bit compression, 8% packet overhead)", 1),
        (f"One 100 MHz cell with 4 antenna layers can need up to {net.cell_peak_bits_per_slot(0) / net.slot_duration_s / 1e9:.1f} Gbit/s", 1),
        ("Several cells share one link that is smaller than their total peak — on purpose (statistical multiplexing)", 0),
        (f"Our setup: 8 cells on a 25 Gbit/s link; total peak = {net.oversubscription:.1f} × the link", 1),
        ("When bursts coincide, some data must wait or be dropped. Low-latency cells can wait ~2 ms at most", 0),
        ("Two ways to manage the load:", 0, True),
        ("A. Make the data smaller — compression (matrix decomposition, quantisation)", 1),
        ("B. Share the link well — decide every few milliseconds how much each cell may send", 1),
    ], Inches(0.5), Inches(1.1), Inches(7.6), Inches(5.7), size=16)
    x0, y0 = Inches(8.3), Inches(1.4)
    for k in range(4):
        box(s, f"O-RU {k + 1}\n{'low-latency' if k < 2 else 'eMBB'}", x0, y0 + Inches(1.05) * k, Inches(1.1), Inches(0.75),
            fill=BLUE_FILL if k < 2 else LIGHT, size=10)
        arrow(s, x0 + Inches(1.1), y0 + Inches(1.05) * k + Inches(0.375), x0 + Inches(1.8), y0 + Inches(2.3))
    box(s, "switch", x0 + Inches(1.8), y0 + Inches(1.9), Inches(0.9), Inches(0.8), size=11)
    arrow(s, x0 + Inches(2.7), y0 + Inches(2.3), x0 + Inches(3.6), y0 + Inches(2.3), color=RED, width=3)
    text(s, "shared 25 Gbit/s\nlink (bottleneck)", x0 + Inches(2.5), y0 + Inches(2.45), Inches(1.3), Inches(0.6), size=9,
         color=RED, align=PP_ALIGN.CENTER)
    box(s, "O-DU\nscheduler +\nbudget controller", x0 + Inches(3.6), y0 + Inches(1.7), Inches(1.3), Inches(1.2),
        fill=ORANGE_FILL, size=10)
    text(s, "…", x0 + Inches(0.4), y0 + Inches(4.15), Inches(0.5), Inches(0.3), size=14)

    # 3 Project overview ----------------------------------------------------
    s = d.slide("Project overview: two parts, two levers", section="Overview", notes=(
        "The project has two parts. Part A, done earlier, is about making the data smaller. I compared the "
        "standard O-RAN block-floating-point compression with methods that use matrix structure: truncated SVD, "
        "a randomised sketch-plus-QR low-rank encoder, and a delay-domain sparsity encoder. Because all of these "
        "rely on matrix decomposition or inversion, I also benchmarked how fast those operations run on a CPU, "
        "including learned iterative inverters. Part B, the main work of this term, is about sharing the link. "
        "Compression sets how much load reaches the link; the allocation rule decides who loses data when bursts "
        "coincide. At the end I show an experiment that connects the two."))
    box(s, "Part A — make the data smaller (earlier work)", Inches(0.5), Inches(1.2), Inches(6.0), Inches(0.55),
        fill=TEAL, color=WHITE, bold=True, size=14)
    bullets(s, [
        "Compression of the IQ matrix Y (64 antennas × 1200 subcarriers) per slot",
        "Baselines: O-RAN block floating point (BFP), truncated SVD",
        "Studied: RAS-BFP (random sketch + QR → low rank), CSEE (keep the strongest delay taps)",
        "ACAFS: pick the functional split per user from the channel rank",
        "Benchmark of the matrix maths behind it: LU, QR, SVD, Newton-Schulz, learned inverters (n = 10 … 500)",
        "Output: 4 figure suites, benchmark CSV, report. Compression source package is not in this repo (see status)",
    ], Inches(0.5), Inches(1.85), Inches(6.0), Inches(3.6), size=13)
    box(s, "Part B — share the link well (this term)", Inches(6.9), Inches(1.2), Inches(6.0), Inches(0.55),
        fill=NAVY, color=WHITE, bold=True, size=14)
    bullets(s, [
        "Slot-level simulator of 8 cells on one 25 Gbit/s link, with queues, deadlines and priorities",
        "Every 10 ms a controller sets how many bits per slot each cell may send",
        "5 reference controllers, from 'equal share' to 'knows the future'",
        "Proposed: forecast each cell's need as a range (quantiles), then split the link so that every cell is cut at the same weighted risk",
        "200 test runs on 5 traffic scenarios, ablations, 14 unit tests",
        "Output: raw metrics, figures, this deck — all regenerated by scripts",
    ], Inches(6.9), Inches(1.85), Inches(6.0), Inches(3.6), size=13)
    box(s, "How they connect: compression decides how much load reaches the link (Part A lever). "
           "Allocation decides how the loss is shared when bursts coincide (Part B lever). "
           "Slide 15 shows both levers on the same traffic.",
        Inches(0.5), Inches(5.35), Inches(12.4), Inches(1.1), fill=LIGHT, size=13)

    # 4 Part A: compression -------------------------------------------------
    s = d.slide("Part A: compressing IQ data with matrix decomposition", section="Part A", notes=(
        "The radio unit sees a matrix Y of 64 antennas by 1200 subcarriers every slot. Standard O-RAN "
        "compression, block floating point, just shortens the numbers: about 4 times smaller, very fast, almost "
        "lossless. To go further you have to use the structure of the matrix. Truncated SVD keeps the strongest "
        "directions and reaches 16 times, but the SVD is slow. RAS-BFP gets the same rank with a random sketch "
        "and a QR factorisation, 3 to 4 times faster. CSEE uses a different structure: the channel has few "
        "strong delay taps, so an inverse FFT along the subcarriers, keep the top K taps, quantise. It reaches "
        "13 to 60 times with about 4 to 6 times less compute than SVD. The figure shows error versus compression "
        "ratio at 20 dB SNR on a 3GPP TDL-A channel. These are from the earlier report and figure files; the "
        "compression source package is not in the repository, so I could not re-run them this term."))
    picture(s, "results/figures/exp1_nmse_vs_cr.png", Inches(0.4), Inches(1.1), width=Inches(6.3))
    bullets(s, [
        ("Setup: Y ∈ C^(64 × 1200) per slot, 3GPP TDL-A channel, SNR 20 dB (simulated)", 0),
        ("BFP (O-RAN standard): shared exponent + short mantissa. ~4× smaller, −46 dB error, ~3 ms", 0),
        ("Truncated SVD: keep the r strongest directions. ~16× at −21 dB, but 18-30 ms per slot", 0),
        ("RAS-BFP: random sketch Ω·Y → thin QR → Y ≈ L·Qᴴ, then BFP. ~16× at −18 dB, ~7 ms (3-4× faster than SVD)", 0),
        ("CSEE: IFFT along subcarriers → keep top-K delay taps → BFP. ~13× at −21 dB (~5 ms); ~63× at −19 dB with K = 60", 0),
        ("ACAFS: choose split 7.2x / 7.1 / 6 per user from the channel rank → in simulation 0 % saving below ~15 dB SNR, 55-75 % above (vs fixed split 6)", 0),
        ("Status: figures and report exist (results/figures, docs/mid_evaluation_report.md); the src/ package is missing from the repo, so these numbers are quoted, not re-run", 0, True),
    ], Inches(6.9), Inches(1.15), Inches(6.1), Inches(5.7), size=12, para_space=5)

    # 5 Part A: matrix maths cost --------------------------------------------
    s = d.slide("Part A: how fast is the matrix maths? (measured on CPU)", section="Part A", notes=(
        "All of these compression methods, and also MIMO equalisation and precoding, need matrix decompositions or "
        "inversions every slot. So I measured them. Left: encoder time versus number of antennas: SVD grows fastest, "
        "the sketch and delay-domain encoders stay one to two orders of magnitude below it. Right: inversion "
        "benchmark on well-conditioned random matrices, 200 held-out matrices per size. LU through LAPACK is the "
        "fastest accurate method. QR and SVD cost several times more with no accuracy gain here. A direct neural "
        "network that outputs the inverse fails: 50 percent error. A learned iteration that keeps the "
        "Newton-Schulz structure works, with errors around one in a million at n=100, and has a fixed, "
        "predictable cost, which matters for slot deadlines. Two lessons carry into Part B: a 500 microsecond slot "
        "leaves room for n=100 but not n=500 matrices, and predictable cost matters as much as speed."))
    picture(s, "results/figures/exp2_complexity.png", Inches(0.4), Inches(1.1), width=Inches(5.0))
    if bench is not None:
        tb = matinv_table(bench)
        tbl = table(s, tb, Inches(5.6), Inches(1.15), Inches(7.4), Inches(2.8), size=9)
        for j, w in enumerate((2.6, 1.2, 1.2, 1.2, 1.2)):
            tbl.columns[j].width = Inches(w)
    bullets(s, [
        ("Encoder time grows fastest for SVD; sketch (RAS-BFP) and delay-domain (CSEE) encoders stay 10-100× below it", 0),
        ("Inversion benchmark (right, medians, 200 held-out matrices per size, well-conditioned): LU via LAPACK is fastest and exact", 0),
        ("A direct neural net that outputs the inverse does not work (≈ 50 % error). A learned Newton-Schulz iteration does (≈ 1e-6 at n = 100) and has a fixed, predictable cost", 0),
        ("Lesson for slot deadlines (0.5 ms): n ≈ 100 matrices fit per slot on a CPU; n ≈ 500 do not → do them less often, incrementally, or on an accelerator", 0),
        ("Lesson for Part B: predictable compute time matters as much as average speed — the allocation rule below is a closed form plus one scalar search", 0),
    ], Inches(0.4), Inches(4.75), Inches(12.5), Inches(2.2), size=12, para_space=3)

    # 6 Part B: system model -------------------------------------------------
    s = d.slide("Part B: what is decided, when, and with what information", section="Part B — model", notes=(
        "Now the sharing problem. Time runs in slots of half a millisecond. Each cell has a queue in the "
        "processing unit. User bits are turned into resource blocks using the cell's spectral efficiency, and each "
        "resource block costs a fixed number of fronthaul bits — so fronthaul load is not the same as user "
        "traffic. A bit that waits in the queue longer than its class deadline is thrown away and counted as a "
        "violation. Every 20 slots, that is 10 milliseconds, the controller gives each cell a budget in bits per "
        "slot. The budgets must add up to the link capacity and are held for the whole interval. The controller "
        "sees the state with a 2-slot delay and never sees the future. Why decide in advance? Because the budget "
        "is a reservation that is held for 10 ms and telemetry is late; the next interval's traffic is unknown "
        "when the decision is made."))
    bullets(s, [
        ("Time: slots of 0.5 ms. Data: bits. Link: bits per slot", 0),
        ("8 cells: 3 low-latency (must be served within 4 slots = 2 ms, priority 3) and 5 eMBB (20 slots = 10 ms, priority 1)", 0),
        ("Fronthaul bits = user bits ÷ spectral efficiency × bits per resource block — so fronthaul load ≠ user traffic", 0),
        ("Each cell has a first-in-first-out queue in the O-DU; bits older than the deadline are dropped and counted", 0),
        ("Link rule: budgets add up to at most 97 % of 25 Gbit/s (3 % kept for control traffic); no cell gets more than its own peak", 0),
        ("Every T = 20 slots (10 ms) the controller sets the budgets; they are fixed for the interval", 0),
        ("The controller sees the state 2 slots late; it never sees future arrivals (checked by a unit test)", 0),
        ("Why decide in advance? A budget is a reservation held for 10 ms; the traffic in that window is not known yet", 0, True),
    ], Inches(0.5), Inches(1.1), Inches(7.4), Inches(5.7), size=15)
    x0, y0 = Inches(8.3), Inches(1.5)
    box(s, "look at the state\n(2 slots old)", x0, y0, Inches(1.6), Inches(0.9), size=11, fill=BLUE_FILL)
    arrow(s, x0 + Inches(1.6), y0 + Inches(0.45), x0 + Inches(2.0), y0 + Inches(0.45))
    box(s, "set budgets r_i\nΣ r_i ≤ link", x0 + Inches(2.0), y0, Inches(1.6), Inches(0.9), size=11, fill=ORANGE_FILL)
    arrow(s, x0 + Inches(2.8), y0 + Inches(0.9), x0 + Inches(2.8), y0 + Inches(1.4))
    box(s, "hold for 20 slots (10 ms)\neach queue is served up to r_i per slot\nnew arrivals are unknown",
        x0, y0 + Inches(1.4), Inches(3.6), Inches(1.1), size=11)
    arrow(s, x0 + Inches(1.8), y0 + Inches(2.5), x0 + Inches(1.8), y0 + Inches(3.0))
    box(s, "bits older than the deadline\nare dropped = violation", x0, y0 + Inches(3.0), Inches(3.6), Inches(0.9),
        size=11, fill=RED_FILL)
    text(s, "Sources: O-RAN WG4 CUS-plane spec (7-2x, BFP, timing windows); Larsen et al., IEEE COMST 2019 "
         "(bit rate depends on load, ~8 % Ethernet overhead); Pérez et al. 2018/2019 (packet-switched aggregation).",
         x0, y0 + Inches(4.1), Inches(4.5), Inches(1.1), size=10, color=GREY, italic=True)

    # 7 Literature -----------------------------------------------------------
    s = d.slide("What others have done, and the gap", section="Part B — literature", notes=(
        "Three groups of work. First, the standards and surveys that define the fronthaul model. Second, work "
        "that forecasts traffic and then plans capacity — mostly with neural networks and a single predicted "
        "number, with uncertainty handled by a fixed safety margin if at all. Third, work on forecasts with "
        "uncertainty, such as conformal prediction, applied to one traffic stream or to network slices. What I "
        "did not find is a method that turns a forecast distribution of deadline-sensitive demand into per-cell "
        "budgets under one shared link constraint, and tests it fairly against strong reactive and point-forecast "
        "controllers. The full list with DOIs is in the literature review file."))
    bullets(s, [
        ("A. The fronthaul itself (standards and surveys)", 0, True),
        ("O-RAN WG4 CUS-plane spec (7-2x, BFP, timing windows) • Larsen et al., IEEE COMST 2019: bit rate varies with load", 1),
        ("Pérez et al., JOCN 2018 / IEEE Access 2019 (packet aggregation) • Wang & Zhou, IEEE Commun. Lett. 2017 (multiplexing gain)", 1),
        ("Lagén et al., IEEE Commun. Mag. 2022: several 7-2x cells share one link, compression is adjusted per slot — reactive, no forecast", 1),
        ("B. Forecast first, then allocate capacity", 0, True),
        ("Bega et al., DeepCog (INFOCOM 2019 / JSAC 2020), AZTEC (INFOCOM 2020): deep-learning forecasts for network slices", 1),
        ("Predictive bandwidth allocation for PON fronthaul (Mikaeil et al. 2018; Zhang et al. 2019); Kavehmadavani et al., TWC 2023", 1),
        ("Common pattern: one predicted number + a fixed safety margin; no per-cell deadlines", 1),
        ("C. Forecasts with uncertainty", 0, True),
        ("Cohen et al., IEEE WCL 2023 (conformal prediction for one URLLC stream) • Gibbs & Candès, NeurIPS 2021 (adaptive conformal)", 1),
        ("Kasuluru et al. 2024 [preprint]: probabilistic PRB-load forecasts; the percentile is picked globally", 1),
        ("Gap: nobody turns a forecast RANGE of deadline-sensitive demand into per-cell budgets under one shared link, and checks it against strong reactive and point-forecast controllers", 0, True),
    ], Inches(0.5), Inches(1.1), Inches(12.3), Inches(5.8), size=14)

    # 8 Formulation ------------------------------------------------------------
    s = d.slide("What we measure, and what 'demand' means here", section="Part B — formulation", notes=(
        "The controller picks budgets that add up to the link capacity. Our main score, fixed before any tuning, is "
        "the priority-weighted violation ratio: dropped bits divided by arrived bits, with low-latency bits "
        "counting three times. The key modelling idea is the deadline-feasible rate, r-star. Given the arrivals "
        "of the next interval and a deadline D, r-star is the smallest constant service rate at which no bit "
        "waits longer than D. For eMBB with a 10 ms deadline it is close to the average rate; for low-latency "
        "cells with a 2 ms deadline it is basically the peak 2 ms burst rate, which is much harder to predict. "
        "We forecast r-star, not the volume. Its distribution is skewed: the typical value is low but "
        "occasionally very high. A single predicted number under-reserves; a fixed margin over-reserves everywhere."))
    bullets(s, [
        ("Decision every 10 ms: budgets r_i ≥ 0, Σ r_i ≤ link capacity, r_i ≤ cell peak", 0),
        ("Main score (fixed before tuning): priority-weighted deadline-violation ratio", 0, True),
        ("= (3 × dropped low-latency bits + dropped eMBB bits) / (3 × arrived low-latency bits + arrived eMBB bits)", 1),
        ("Also reported: violations per class, link utilisation, queueing delay, fairness (Jain index), decision time", 1),
        ("'Demand' of a cell = deadline-feasible rate r*: the smallest constant rate that serves the next arrivals with no bit waiting longer than its deadline D", 0, True),
        ("r* = max over time windows of (bits in window) / (window length + D)   — a standard network-calculus bound", 1),
        ("For eMBB (D = 10 ms) r* ≈ average rate. For low-latency cells (D = 2 ms) r* ≈ peak 2-ms burst rate → hard to predict", 1),
        ("Budget needed = rate to clear the current backlog in time + r* of the arrivals we have not seen yet", 1),
        ("Why a single predicted number is not enough: r* is skewed (usually low, sometimes very high). The median under-reserves; a fixed margin wastes capacity on every cell", 0),
    ], Inches(0.5), Inches(1.1), Inches(12.3), Inches(5.8), size=15)

    # 9 Baselines --------------------------------------------------------------
    s = d.slide("Reference controllers (all implemented and tuned on validation)", section="Part B — baselines", notes=(
        "Five references. Static equal share ignores everything. Reactive proportional is the classic: current "
        "backlog plus a running average of demand, split proportionally, spare capacity redistributed. The "
        "deadline-aware reactive controller knows the deadlines: it uses the r-star of the last observed interval "
        "as its estimate, plus priority weights and the same water-filling split. The point-forecast controller "
        "is our ablation: identical to the proposed method except it uses the forecast median instead of the "
        "whole range. The oracle knows the real arrivals of the next interval. Every tunable knob was chosen on "
        "validation seeds, never on test seeds. The chosen safety margins were all zero: inflating a single "
        "predicted number made things worse."))
    rows = [
        ("Static equal share", "link ÷ 8 per cell (spare capacity redistributed)", "nothing", "—"),
        ("Reactive proportional", "backlog / T + running average of demand; proportional split; spare redistributed", "history", "margin, window"),
        ("Deadline-aware reactive (strong)", "backlog-clearing rate + r* of the last interval; priority weights; water-fill", "history, deadlines, priorities", "margin, #intervals"),
        ("Point forecast + water-fill (ablation)", "same as above, but r* comes from the forecast MEDIAN", "+ trained model", "margin"),
        ("Oracle water-fill (reference)", "true r* of the next interval, same water-fill. Perfect point forecast; not a bound on other rules", "future arrivals", "—"),
    ]
    df = pd.DataFrame(rows, columns=["Controller", "How it sets budgets", "What it uses", "Tuned"])
    tbl = table(s, df, Inches(0.5), Inches(1.15), Inches(12.3), Inches(2.6), size=11)
    for j, w in enumerate((2.6, 5.9, 2.0, 1.8)):
        tbl.columns[j].width = Inches(w)
    if tuning:
        sel = tuning["selected"]
        bullets(s, [
            ("Tuning on validation seeds 2000-2003 (scenarios moderate/high); test seeds were never used:", 0, True),
            (f"reactive_prop → {sel.get('reactive_prop')}  |  queue_aware → {sel.get('queue_aware')}  |  point_forecast → {sel.get('point_forecast')}  |  proposed_cal → {sel.get('proposed_cal')}", 1),
            ("Finding: every safety margin above 0 was worse. Inflating a single number hurts when the shortage is split proportionally — the cells that over-claim get more", 1),
            ("Same traffic traces, same delayed observations, spare capacity always redistributed, for every controller", 0),
        ], Inches(0.5), Inches(4.75), Inches(12.3), Inches(2.2), size=13)

    # 10 Proposed method ------------------------------------------------------
    s = d.slide("Proposed method: forecast a range, cut every cell at equal risk", section="Part B — proposed", notes=(
        "Two parts. First, a forecaster: six gradient-boosted models, one per quantile, predict the 5th to 95th "
        "percentile of each cell's r-star for the next interval, from 28 features built only from the past. "
        "Second, the allocation rule. We want to maximise the weighted expected amount of demand that is served, "
        "under the forecast distribution, subject to the link constraint. This is a concave problem, and the KKT "
        "conditions give a closed form: each cell gets its backlog rate plus the inverse CDF of its forecast at "
        "one minus lambda over its weight. Lambda is a single number found by bisection so that the budgets add "
        "up to the link. In words: every cell is cut at the same weighted probability of needing one more bit. A "
        "cell with a wide forecast or high priority automatically gets more margin; a cell with a confident "
        "forecast gets about its median. A single-number forecast is the special case, which is why the "
        "median water-fill is the fair comparison."))
    bullets(s, [
        ("1. Forecaster: six quantiles (5, 25, 50, 75, 90, 95 %) of each cell's r* for the next interval", 0, True),
        ("One gradient-boosted tree model per quantile; 28 features from past slots only; trained on training seeds only", 1),
        ("Targets are divided by the cell's fixed peak, so nothing is fitted on test data", 1),
        ("2. Allocation rule: maximise the weighted expected served demand under the forecast", 0, True),
        ("max Σ_i w_i · E[min(backlog_i + r*_i, r_i)]   subject to   Σ r_i ≤ link,  0 ≤ r_i ≤ peak_i", 1),
        ("Solution (KKT):  r_i = backlog_i + F_i⁻¹(1 − λ / w_i), clipped to [0, peak_i];  λ found by bisection so that Σ r_i = link", 1),
        ("In words: every cell is cut at the same weighted risk of needing one more bit", 1),
        ("→ wide forecast or high priority ⇒ more margin; confident forecast ⇒ ≈ median; backlog is always funded first", 1),
        ("Optional: an online calibration step (ACI) that shifts a cell's quantile level after misses — tested as an ablation", 0),
        ("Cost: a few microseconds for 8 cells; budgets always feasible (proofs in docs/fhlm/method.md)", 0),
    ], Inches(0.5), Inches(1.1), Inches(8.2), Inches(5.8), size=14)
    x0, y0 = Inches(9.0), Inches(1.2)
    box(s, "past slots, queue, spectral efficiency", x0, y0, Inches(3.8), Inches(0.8), size=11, fill=BLUE_FILL)
    arrow(s, x0 + Inches(1.9), y0 + Inches(0.8), x0 + Inches(1.9), y0 + Inches(1.1))
    box(s, "quantile forecaster\n→ range of r*_i (5 % … 95 %)", x0, y0 + Inches(1.1), Inches(3.8), Inches(0.9), size=11,
        fill=ORANGE_FILL)
    arrow(s, x0 + Inches(1.9), y0 + Inches(2.0), x0 + Inches(1.9), y0 + Inches(2.3))
    box(s, "KKT rule\nr_i = backlog_i + F_i⁻¹(1 − λ/w_i)\none scalar λ: Σ r_i = link", x0, y0 + Inches(2.3), Inches(3.8),
        Inches(1.2), size=11, fill=RED_FILL, line=RED)
    arrow(s, x0 + Inches(1.9), y0 + Inches(3.5), x0 + Inches(1.9), y0 + Inches(3.8))
    box(s, "budgets r_i, held 10 ms\nO-DU serves each queue ≤ r_i", x0, y0 + Inches(3.8), Inches(3.8), Inches(0.8), size=11)
    text(s, "Borrowed: quantile boosting, ACI, water-filling.\nOur part: r* as the forecast target + the KKT rule "
         "over the forecast range under the link constraint, tested against strong baselines.", x0, y0 + Inches(4.7),
         Inches(3.9), Inches(1.0), size=10, color=GREY, italic=True)

    # 11 Experimental setup ----------------------------------------------------
    s = d.slide("Experimental setup (synthetic traffic, clearly labelled)", section="Part B — experiments", notes=(
        "The traffic is synthetic: a smooth part plus heavy-tailed on-off bursts per cell, slow load changes "
        "about every second, and drifting spectral efficiency. Five scenarios differ in average load and "
        "burstiness. 'Shift' uses heavier and longer bursts than anything the model saw in training — the "
        "held-out test. Training, validation and test seeds are separate ranges. Every controller sees exactly "
        "the same traffic, seed by seed, so we can compare them pairwise. Absolute violation numbers are high "
        "because the traffic is deliberately bursty at 80 percent load; the differences between controllers are "
        "the result."))
    rows = [("low", "0.50", "normal", "no"), ("moderate", "0.65", "normal", "yes (validation seeds)"),
            ("high", "0.80", "normal", "yes (validation seeds)"),
            ("overload_bursts", "0.80", "flash crowds: load ×1.8 for about 15 % of the time (more than the link can carry)", "no"),
            ("shift (held-out)", "0.80", "bursts 1.5× stronger and 1.5× longer, heavier tail — never seen in training or tuning", "no")]
    tbl = table(s, pd.DataFrame(rows, columns=["Scenario", "Mean load / link", "Traffic", "Used for tuning?"]),
                Inches(0.5), Inches(1.15), Inches(12.3), Inches(2.3), size=12)
    for j, w in enumerate((2.0, 2.0, 6.3, 2.0)):
        tbl.columns[j].width = Inches(w)
    bullets(s, [
        ("Traffic (synthetic): smooth Gamma part + heavy-tailed ON/OFF bursts + slow load changes (~1 s) + spectral-efficiency drift", 0),
        ("Seeds: training 1000-1015 (loads 0.5-0.95) | validation 2000-2003 | test 3000-3004 — no overlap", 0),
        ("Each run: 20,000 slots = 10 s after a 1,000-slot warm-up; T = 20 slots; 8 controllers × 5 scenarios × 5 seeds = 200 runs", 0),
        ("Same traffic and same delayed observations for every controller; the forecaster is frozen before testing", 0),
        ("Absolute violation ratios are high on purpose (bursty traffic at 0.8 load); the paired differences between controllers are the result", 0),
    ], Inches(0.5), Inches(4.0), Inches(12.3), Inches(3.0), size=14)

    # 12 Main results ---------------------------------------------------------
    hi_pf, hi_qa, hi_rp = pr("high", "point_forecast"), pr("high", "queue_aware"), pr("high", "reactive_prop")
    sh_pf, sh_qa, sh_rp = pr("shift", "point_forecast"), pr("shift", "queue_aware"), pr("shift", "reactive_prop")
    ob_rp, ob_rp_w = pr("overload_bursts", "reactive_prop"), pr("overload_bursts", "reactive_prop", "reference_wins")
    s = d.slide("Results: main score per scenario (5 test seeds, mean ± std)", section="Part B — results", notes=(
        f"Lower is better. Black is the oracle. The proposed rule, in red, is the best real controller in every "
        f"scenario. Against the point-forecast controller — same model, same information — it cuts the score by "
        f"{hi_pf:.0f} percent at high load and {sh_pf:.0f} percent under the held-out shift. Against the "
        f"deadline-aware reactive controller by {hi_qa:.0f} and {sh_qa:.0f} percent. Against the plain proportional "
        f"controller the margin is {hi_rp:.0f} percent at high load but only {ob_rp:.0f} percent under flash crowds, "
        f"where it wins {ob_rp_w:.0f} of 5 seeds — a tie. The error bars are wide because seeds differ in when the "
        "bursts happen; the next slide compares seed by seed."))
    picture(s, os.path.join(FIG, "fig1_primary_by_scenario.png"), Inches(0.4), Inches(1.1), width=Inches(8.6))
    if main is not None:
        bullets(s, [("Proposed = best real controller in 5 of 5 scenarios", 0, True),
                    (f"vs point forecast (same model, median only): −{hi_pf:.0f} % (high), −{sh_pf:.0f} % (shift)", 1),
                    (f"vs deadline-aware reactive: −{hi_qa:.0f} % (high), −{sh_qa:.0f} % (shift)", 1),
                    (f"vs reactive proportional: −{hi_rp:.0f} % (high) but only −{ob_rp:.0f} % under flash crowds ({ob_rp_w:.0f}/5 seeds) → a tie", 1),
                    (f"Gap to the oracle at high load: {pct(mean_metric('high', 'proposed'))} vs {pct(mean_metric('high', 'oracle'))}", 0),
                    ("Error bars are wide because burst timing differs by seed → compare seed by seed (next slide)", 0)],
                Inches(9.1), Inches(1.2), Inches(4.0), Inches(5.6), size=13)

    # 13 Paired ---------------------------------------------------------------
    s = d.slide("Results: seed-by-seed comparison on the same traffic", section="Part B — results", notes=(
        "Each bar is how much the proposed rule lowers the score compared with one baseline, computed seed by "
        "seed on the very same traffic; the whiskers are the best and worst seed, and the text says how many of "
        "the five seeds it won. Against the point-forecast and the deadline-aware reactive controllers it wins "
        "every seed in every scenario. Against the plain proportional controller it wins every seed except under "
        "flash crowds. Green is the machine-learning ablation: the same rule fed with simple empirical quantiles "
        "instead of the trained model. The model helps a lot on normal traffic but almost not at all under the "
        "held-out shift. Purple: online calibration gives nothing and hurts under shift."))
    picture(s, os.path.join(FIG, "fig8_paired_reduction.png"), Inches(0.4), Inches(1.1), width=Inches(8.6))
    if paired is not None:
        pw = [pr(sc, "proposed_window") for sc in SC]
        bullets(s, [("Wins 5/5 seeds vs point forecast and vs deadline-aware reactive in every scenario", 0, True),
                    (f"vs reactive proportional: 5/5 in four scenarios; {ob_rp_w:.0f}/5 under flash crowds (no claim there)", 0),
                    ("ML ablation (same rule, simple window quantiles instead of the trained model):", 0, True),
                    (f"the model adds {min(pw):.0f}-{max(pw):.0f} %; least under the held-out shift ({pr('shift', 'proposed_window'):.0f} %) → the rule, not the model, carries most of the gain", 1),
                    ("Online calibration: no gain on normal traffic, harmful under shift (it over-reserves for low-latency cells and starves eMBB) → negative result", 0),
                    ("With 5 seeds we do not claim statistical significance; we report win counts and best/worst seed", 0)],
                Inches(9.1), Inches(1.2), Inches(4.0), Inches(5.6), size=13)

    # 14 Per class trade-off --------------------------------------------------
    s = d.slide("Where the gain comes from: low-latency vs eMBB (high load)", section="Part B — results", notes=(
        "Left: low-latency violations; middle: eMBB; right: link utilisation. The proportional controller keeps "
        "eMBB almost clean but lets low-latency cells lose 15 percent of their bits — it does not know about "
        "deadlines. All deadline-aware controllers protect the low-latency cells and pay with eMBB. Within that "
        "group the proposed rule has the lowest eMBB loss and the highest utilisation, because it adds margin "
        "only where the forecast is uncertain instead of everywhere. Even the oracle loses 13 percent of eMBB "
        "bits here: budgets fixed for 10 ms simply cannot follow heavy bursts, which is why the control interval "
        "matters — see the ablation slide."))
    picture(s, os.path.join(FIG, "fig2_class_breakdown_high.png"), Inches(0.4), Inches(1.1), width=Inches(12.5))
    if main is not None:
        bullets(s, [
            (f"Reactive proportional: low-latency loss {pct(mean_metric('high', 'reactive_prop', 'violation_ratio_ll'))} vs {pct(mean_metric('high', 'proposed', 'violation_ratio_ll'))} for proposed — controllers that ignore deadlines sacrifice the low-latency cells", 0),
            (f"Among deadline-aware controllers, proposed has the lowest eMBB loss ({pct(mean_metric('high', 'proposed', 'violation_ratio_embb'))} vs {pct(mean_metric('high', 'point_forecast', 'violation_ratio_embb'))} for point forecast) and the highest utilisation ({pct(mean_metric('high', 'proposed', 'fh_utilisation'))})", 0),
            (f"Even the oracle loses {pct(mean_metric('high', 'oracle', 'violation_ratio_embb'))} of eMBB bits at 0.80 load: budgets fixed for 10 ms cannot follow heavy bursts → the control interval matters", 0),
        ], Inches(0.5), Inches(5.2), Inches(12.3), Inches(1.8), size=13)

    # 15 Bridge: compression x allocation --------------------------------------
    s = d.slide("Both levers on the same traffic: compression × allocation", section="A + B", notes=(
        "This experiment connects the two parts. Same user traffic, same seeds; only the compression setting "
        "changes: 6, 9, 12 or 14 mantissa bits, which changes how many fronthaul bits each resource block costs "
        "and therefore the load on the link. At 6 bits the load is 43 percent and almost nothing is lost, "
        "whatever the allocation rule — compression alone solves it, at the price of quantisation noise, which "
        "this experiment does not model. At 9 bits, the O-RAN default, the allocation rule matters most: the "
        "proposed rule loses about half as much as the reactive controllers. At 12 bits the link is at 83 "
        "percent and the proposed rule ties with the proportional one. At 14 bits the link is essentially full "
        "and no allocation rule helps; the proposed rule is even the worst, because protecting the low-latency "
        "cells costs too many eMBB bits. Message: compression decides which regime you are in; allocation "
        "helps most in the 50 to 80 percent regime."))
    picture(s, os.path.join(FIG, "fig9_compression_vs_allocation.png"), Inches(0.4), Inches(1.1), width=Inches(8.4))
    if comp is not None and not comp.empty:
        g = comp.groupby(["mantissa_bits", "method"])[PRIMARY_METRIC].mean()
        load = comp.groupby("mantissa_bits")["realised_load"].mean()
        items = [("Same user traffic, 3 seeds, scenario 'moderate'; only the BFP width changes", 0, True)]
        for b in sorted(comp.mantissa_bits.unique()):
            best = g.loc[b].idxmin()
            items.append((f"BFP-{b}: load {load[b]:.2f} → proposed {pct(g.loc[(b, 'proposed')], 2)}, reactive prop. {pct(g.loc[(b, 'reactive_prop')], 2)}; best = {SHORT_LAB[best]}", 1))
        items += [("Compression sets the regime; allocation helps most between ~0.5 and ~0.8 load", 0, True),
                  ("At ~1.0 load no allocation rule helps — compress more (Part A) or add capacity", 0),
                  ("Not modelled: the signal-quality cost of fewer bits (Part A's NMSE curves cover that side)", 0)]
        bullets(s, items, Inches(8.9), Inches(1.15), Inches(4.3), Inches(5.7), size=12, para_space=4)

    # 16 Ablations -------------------------------------------------------------
    s = d.slide("Ablations: forecast quality and control interval", section="Part B — ablation", notes=(
        "Left: the forecast quantiles are well calibrated on validation data — the 5 percent quantile is exceeded "
        "5.6 percent of the time, the 95 percent quantile 5.1 percent — and the median error is lower than "
        "simple persistence. Right: the control-interval sweep, forecasters retrained per interval. Two honest "
        "findings. At 2 ms the proposed rule is far ahead of every reactive controller and even of the oracle "
        "water-fill, which has a perfect single-number forecast — so the allocation rule itself does real work. "
        "At 20 ms, five times the low-latency deadline, reserving the low-latency peak rate for the whole interval "
        "wastes capacity and the plain proportional controller becomes better. So the method is for control "
        "intervals up to a few times the shortest deadline; our default of 10 ms is inside that range."))
    picture(s, os.path.join(FIG, "fig5_forecast_quality.png"), Inches(0.3), Inches(1.1), width=Inches(6.4))
    picture(s, os.path.join(FIG, "fig4_interval_sweep.png"), Inches(6.8), Inches(1.1), width=Inches(6.3))
    items = []
    if fc:
        v = fc["gbm_validation"]
        items += [(f"Validation: the 5 / 50 / 95 % quantiles are exceeded {pct(v['coverage_q05'])} / {pct(v['coverage_q50'])} / {pct(v['coverage_q95'])} of the time (well calibrated); "
                   f"median error {pct(v['median_mae_rel'], 0)} vs {pct(fc['persistence_median_mae_rel'], 0)} for persistence", 0)]
    if sweep is not None and not sweep.empty:
        g = sweep.groupby(["interval_slots", "method"])[PRIMARY_METRIC].mean()
        Ts = sorted(sweep.interval_slots.unique())

        def red(T, base):
            try:
                return 100 * (g.loc[(T, base)] - g.loc[(T, "proposed")]) / g.loc[(T, base)]
            except KeyError:
                return float("nan")
        items += [("Interval sweep (scenario high, 3 seeds). Reduction by proposed vs deadline-aware reactive / vs reactive proportional / vs oracle water-fill:", 0, True)]
        items += [("   " + "   |   ".join(f"T={T * 0.5:g} ms: {red(T, 'queue_aware'):+.0f}% / {red(T, 'reactive_prop'):+.0f}% / {red(T, 'oracle'):+.0f}%" for T in Ts), 1)]
        short_T, long_T = Ts[0], Ts[-1]
        if red(short_T, "oracle") > 0:
            items += [(f"At T = {short_T * 0.5:g} ms the rule even beats the oracle water-fill (perfect single-number forecast) → the allocation rule, not only the forecast, does the work", 0)]
        if red(long_T, "reactive_prop") < 0:
            items += [(f"At T = {long_T * 0.5:g} ms (5× the low-latency deadline) reserving the low-latency peak rate wastes capacity and reactive proportional wins → the method is for intervals up to a few times the shortest deadline", 0)]
    else:
        items += [("Interval sweep: not yet run (results/fhlm/sweep_runs.csv missing)", 0)]
    bullets(s, items, Inches(0.5), Inches(4.5), Inches(12.3), Inches(2.4), size=12, para_space=4)

    # 17 Limitations -----------------------------------------------------------
    s = d.slide("Limitations and honest status", section="Status", notes=(
        "What this is not. Part A: the compression results are quoted from the earlier report and figures; the "
        "source package is missing from the repository, so they were not re-run this term; the inversion "
        "benchmark is re-runnable. Part B: traffic is synthetic; the oracle is only interval-level; the gain over "
        "the simplest proportional controller vanishes under flash crowds and at long intervals; the learned "
        "model adds little under shift; online calibration hurt; five seeds do not allow a significance claim; "
        "the link is a budget-enforced pipe with no switch queue; decision time is Python-level, about 3 ms per "
        "10 ms epoch."))
    bullets(s, [
        ("Part A: compression numbers are quoted from the earlier report and saved figures; the src/ package is not in the repo, so they are not re-run. The matrix-inversion benchmark is re-runnable (needs PyTorch)", 0, True),
        ("Part A: benchmark matrices are random and well-conditioned; real channel matrices can be worse", 0),
        ("Part B: synthetic traffic only — no real radio-unit traces, so no real-world validation is claimed", 0, True),
        ("Not a universal win: tie with reactive proportional under flash crowds; loses to it at 20 ms intervals and at ~1.0 load; the ML model adds ≈ 2 % under the held-out shift", 0),
        ("Online calibration (ACI) did not help — reported as a negative result; the simple-quantile variant is the current fallback", 0),
        ("5 test seeds → we report win counts and best/worst seed, not p-values", 0),
        ("Simplified link: a budget-enforced pipe, no switch queue, one traffic class per cell, no HARQ feedback; 'violation' is a DU queueing deadline, not end-to-end latency", 0),
        ("Decision time ≈ 3.2 ms per 10-ms epoch in Python (reactive baselines ≈ 0.1 ms); a real DU would need a compiled version", 0),
        ("Proofs cover feasibility, equal weighted risk and backlog-first only — no stability or closed-loop optimality claims", 0),
    ], Inches(0.5), Inches(1.1), Inches(12.3), Inches(5.8), size=14)

    # 18 Remaining work --------------------------------------------------------
    s = d.slide("Status and remaining work toward the final evaluation", section="Plan", notes=(
        "Left column is done and checked by tests and experiments; right column is the plan in priority order. "
        "For Part A, restore the compression source package into the repository and re-run the four figure "
        "suites, then make the compression setting a second lever inside the allocation rule. For Part B, real "
        "or public traffic traces; a skill-weighted mix of the trained and the simple quantiles as the fallback; a "
        "switch queue; more seeds; and a compiled version of the decision."))
    box(s, "Done and checked", Inches(0.5), Inches(1.15), Inches(6.0), Inches(0.5), fill=GREEN, color=WHITE, bold=True, size=14)
    bullets(s, [
        "Part A: compression study (BFP, SVD, RAS-BFP, CSEE, ACAFS) — 4 figure suites + report",
        "Part A: matrix-inversion benchmark (LU, QR, SVD, Newton-Schulz, learned inverters; n = 10/100/500) — CSV + figure",
        "Part B: slot-level shared-link simulator with deadlines, priorities, telemetry delay (14 tests)",
        "Part B: 5 reference controllers, tuned on validation seeds; quantile forecaster, calibrated on validation",
        "Part B: KKT allocation rule with feasibility proof; 200-run comparison, seed-by-seed analysis, interval sweep",
        "A + B: compression × allocation experiment; all figures and this deck regenerated by scripts",
    ], Inches(0.5), Inches(1.75), Inches(6.0), Inches(5.0), size=13)
    box(s, "Planned (not done yet)", Inches(6.9), Inches(1.15), Inches(6.0), Inches(0.5), fill=ORANGE, color=WHITE, bold=True, size=14)
    bullets(s, [
        "Part A: restore the compression src/ package into the repo and re-run Exp 1-4; benchmark on realistic channel matrices",
        "A + B: make the compression width a second knob of the allocation rule (trade signal quality for load per cell)",
        "Part B: real or public traffic traces → re-check the forecaster",
        "Part B: skill-weighted mix of trained and simple quantiles as the fallback (instead of ACI)",
        "Part B: switch-level packet queue and timing window instead of a budget-enforced pipe; more seeds",
        "Compiled (C++/numba) decision so the 3 ms Python time fits a real DU",
    ], Inches(6.9), Inches(1.75), Inches(6.0), Inches(5.0), size=13)

    # ---------------- backup ------------------------------------------------
    s = d.slide("Backup: one trace — budgets vs demand of a low-latency cell", section="Backup", notes=(
        "Top: demand of one low-latency cell in grey and the budget each controller gave it. The reactive "
        "controller reacts one interval late to each burst; the point forecast tracks the median; the proposed "
        "rule raises the budget when the forecast range is wide. Bottom: cumulative dropped bits. "
        "Live demo: python -m fhlm.run_experiments demo, then python -m fhlm.make_figures."))
    picture(s, os.path.join(FIG, "fig6_demo_timeseries.png"), Inches(1.2), Inches(1.05), height=Inches(5.9))

    s = d.slide("Backup: code layout (Part B)", section="Backup", notes=(
        "The fhlm package: config holds units and 7-2x constants; traffic generates arrivals; demand implements "
        "r-star; simulator is the slot loop; controllers the baselines; forecast the features and quantile model; "
        "proposed the KKT rule; scenarios the seed splits; train, run_experiments, make_figures and make_slides "
        "reproduce everything. matinv_bench holds the Part A inversion benchmark."))
    mods = [
        ("config.py", "units, 7-2x fronthaul constants, cells, link"), ("traffic.py", "synthetic arrivals: smooth + bursts + slow changes"),
        ("demand.py", "deadline-feasible rate r*, backlog rate"), ("simulator.py", "slot loop, queues with ages, drops, metrics"),
        ("controllers.py", "5 reference controllers, water-fill"), ("forecast.py", "features, quantile boosting, fast tree evaluation"),
        ("proposed.py", "KKT rule + optional calibration"), ("scenarios.py", "train / validation / test seeds, 5 scenarios"),
        ("train.py", "train on training seeds, check on validation"), ("run_experiments.py", "tune / main / sweep / compression / demo"),
        ("make_figures.py, make_slides.py", "all figures and this deck from CSV"), ("matinv_bench/ (Part A)", "matrix-inversion benchmark: classical + learned"),
    ]
    for k, (m, desc) in enumerate(mods):
        col, row = k % 2, k // 2
        x = Inches(0.5) + Inches(6.2) * col
        y = Inches(1.15) + Inches(0.72) * row
        box(s, m, x, y, Inches(2.3), Inches(0.6), size=11, bold=True, fill=BLUE_FILL)
        text(s, desc, x + Inches(2.4), y + Inches(0.08), Inches(3.7), Inches(0.6), size=12)
    bullets(s, [
        ("Flow: traffic → simulator ↔ controller (observation 2 slots old → budgets) → metrics / raw JSON → figures → slides", 0),
        ("ML flow: training seeds → features / targets → 6 boosted models (~12 s CPU) → validation check → frozen model → test seeds", 0),
        ("Python 3 with numpy / pandas / scikit-learn / matplotlib; full reproduction ≈ 10 min on a 4-core laptop", 0),
    ], Inches(0.5), Inches(5.6), Inches(12.3), Inches(1.4), size=13)

    s = d.slide("Backup: main score [%], mean ± std over 5 test seeds", section="Backup", notes=(
        "Table of the main score per scenario and method, from results/fhlm/main_runs.csv."))
    if main is not None:
        methods = ["static_equal", "reactive_prop", "queue_aware", "point_forecast", "proposed_window", "proposed", "proposed_cal", "oracle"]
        df = summary_table(main, SC, methods, LAB).rename(columns=SCL)
        table(s, df, Inches(0.4), Inches(1.15), Inches(12.5), Inches(4.6), size=11)
        text(s, "Source: results/fhlm/main_runs.csv (200 runs). Seed-by-seed statistics: results/fhlm/main_paired.csv.",
             Inches(0.4), Inches(6.0), Inches(12), Inches(0.4), size=11, color=GREY, italic=True)

    s = d.slide("Backup: where the KKT rule comes from", section="Backup", notes=(
        "For questions. The objective is concave and separable. Its derivative in r_i is w_i times the "
        "probability that the cell needs more than r_i, minus lambda. Setting it to zero gives the inverse-CDF "
        "form. Because the forecast CDF is zero below zero, the derivative equals w_i for budgets below the "
        "backlog — backlog is always funded before uncertain demand of a lower-weight cell. The sum of budgets "
        "decreases as lambda grows, so bisection finds the single lambda at which the link is exactly full."))
    bullets(s, [
        ("Objective: J(r) = Σ_i w_i · E[ min(B_i + X_i, r_i) ],   X_i ~ forecast distribution F_i of r*_i, B_i = backlog rate", 0),
        ("Derivative: d/dr_i E[min(B_i + X_i, r_i)] = P(B_i + X_i > r_i) = 1 − F_i(r_i − B_i)   → J is concave and separable", 0),
        ("Lagrangian with the link constraint (λ) and the box constraints (μ_i, ν_i)", 0),
        ("Stationarity for an interior r_i:  w_i (1 − F_i(r_i − B_i)) = λ   ⇒   r_i = B_i + F_i⁻¹(1 − λ / w_i)", 0),
        ("Clip to [0, peak_i]; Σ_i r_i(λ) decreases in λ ⇒ one λ* by bisection (60 steps)", 0),
        ("Property 1 (feasibility): budgets always respect the caps and Σ r_i ≤ link — checked by test_kkt_allocation_properties", 0),
        ("Property 2 (equal weighted risk): at the optimum every interior cell has w_i · P(needs one more bit) = λ*", 0),
        ("Property 3 (backlog first): F_i(x) = 0 for x < 0 ⇒ the marginal value below B_i is w_i ⇒ backlog is funded before any uncertain demand of a cell with w ≤ λ*", 0),
        ("A single-number forecast (F_i a step) gives a priority-ordered fill = the point-forecast water-fill baseline", 0),
        ("F_i⁻¹: straight lines through the 6 forecast quantiles, extended linearly above 95 %; quantiles sorted to keep them monotone", 0),
    ], Inches(0.5), Inches(1.1), Inches(12.3), Inches(5.8), size=14)

    s = d.slide("Backup: decision time and violation-vs-utilisation trade-off", section="Backup", notes=(
        "Left: mean decision time per control epoch per method. Right: violation versus utilisation per scenario."))
    picture(s, os.path.join(FIG, "fig7_decision_time.png"), Inches(0.3), Inches(1.2), width=Inches(5.6))
    picture(s, os.path.join(FIG, "fig3_tradeoff.png"), Inches(6.0), Inches(1.2), width=Inches(7.1))
    text(s, "Decision times are Python on a 4-core CPU inside the simulator (feature construction + 1,800 trees with a "
         "vectorised traversal + bisection). The rule itself is < 0.1 ms.", Inches(0.4), Inches(5.6), Inches(12.5),
         Inches(0.8), size=12, color=GREY)

    s = d.slide("Backup: references", section="Backup", notes="Full list with DOIs/links in docs/fhlm/literature_review.md; Part A report in REPORT.md and docs/mid_evaluation_report.md.")
    bullets(s, [
        "O-RAN WG4, Control, User and Synchronization Plane Specification (O-RAN.WG4.CUS.0) [standard] — 7-2x, BFP compression (Annex A.1), T2a windows. 3GPP TR 38.801 [standard]; 3GPP TR 38.901 (TDL-A channel) [standard]; IEEE 802.1CM-2018 [standard].",
        "L. M. P. Larsen, A. Checko, H. L. Christiansen, 'A Survey of the Functional Splits Proposed for 5G Mobile Crosshaul Networks', IEEE COMST 21(1), 2019. DOI 10.1109/COMST.2018.2868805 [peer-reviewed]",
        "G. O. Pérez, J. A. Hernández, D. Larrabeiti, 'Fronthaul Network Modeling and Dimensioning Meeting Ultra-Low Latency Requirements for 5G', JOCN 10(6), 2018. DOI 10.1364/JOCN.10.000573; IEEE Access 2019, DOI 10.1109/ACCESS.2019.2923020 [peer-reviewed]",
        "L. Wang, S. Zhou, 'On the Fronthaul Statistical Multiplexing Gain', IEEE Commun. Lett. 21(5), 2017. DOI 10.1109/LCOMM.2017.2653120 [peer-reviewed]",
        "S. Lagén, X. Gelabert, A. Hansson, M. Requena, L. Giupponi, 'Fronthaul Compression Control for Shared Fronthaul Access Networks', IEEE Commun. Mag. 2022. DOI 10.1109/MCOM.001.2100959 [peer-reviewed]",
        "D. Bega, M. Gramaglia, M. Fiore, A. Banchs, X. Costa-Pérez, 'DeepCog', IEEE INFOCOM 2019, DOI 10.1109/INFOCOM.2019.8737488; 'AZTEC', IEEE INFOCOM 2020, DOI 10.1109/INFOCOM41043.2020.9155299 [peer-reviewed]",
        "F. Kavehmadavani, V.-D. Nguyen, T. X. Vu, S. Chatzinotas, 'Intelligent Traffic Steering in Beyond 5G Open RAN Based on LSTM Traffic Prediction', IEEE TWC 2023. DOI 10.1109/TWC.2023.3254903 [peer-reviewed]",
        "K. M. Cohen, S. Park, O. Simeone, P. Popovski, S. Shamai, 'Guaranteed Dynamic Scheduling of URLLC Traffic via Conformal Prediction', IEEE WCL 2023 [peer-reviewed]; I. Gibbs, E. Candès, 'Adaptive Conformal Inference Under Distribution Shift', NeurIPS 2021 [peer-reviewed]",
        "V. Kasuluru, L. Blanco, C. J. Vaca-Rubio, E. Zeydan, 'On the Impact of PRB Load Uncertainty Forecasting for Sustainable Open RAN', arXiv:2407.14400, 2024 [preprint]",
        "Eckart & Young 1936 (best low-rank approximation = truncated SVD); Halko, Martinsson, Tropp, SIAM Review 2011 (randomised sketching for low-rank factorisation); Willinger et al., IEEE/ACM ToN 1997 (heavy-tailed ON/OFF sources); Hadley & Whitin 1963 (constrained newsvendor); Le Boudec & Thiran, Network Calculus, 2001.",
    ], Inches(0.5), Inches(1.1), Inches(12.3), Inches(5.8), size=11)

    d.save(out)
    print(f"wrote {out} ({d.n} slides)")
    return out


if __name__ == "__main__":
    build()
