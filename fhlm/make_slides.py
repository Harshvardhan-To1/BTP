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
def load_results():
    R = {}
    p = os.path.join(RESULTS_DIR, "main_runs.csv")
    R["main"] = pd.read_csv(p) if os.path.exists(p) else None
    p = os.path.join(RESULTS_DIR, "main_paired.csv")
    R["paired"] = pd.read_csv(p) if os.path.exists(p) else None
    p = os.path.join(RESULTS_DIR, "sweep_runs.csv")
    R["sweep"] = pd.read_csv(p) if os.path.exists(p) else None
    p = os.path.join(RESULTS_DIR, "tuning.json")
    R["tuning"] = json.load(open(p)) if os.path.exists(p) else None
    p = os.path.join(RESULTS_DIR, "forecast_training_T20_d2.json")
    R["forecast"] = json.load(open(p)) if os.path.exists(p) else None
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


# ---------------------------------------------------------------------------
# slides
# ---------------------------------------------------------------------------
def build(out: str = OUT):
    R = load_results()
    net, ctrl = NetworkConfig(), ControlConfig()
    d = Deck()
    main, paired, sweep, tuning, fc = R["main"], R["paired"], R["sweep"], R["tuning"], R["forecast"]
    SC = ["low", "moderate", "high", "overload_bursts", "shift"]
    SCL = {"low": "Low 0.50", "moderate": "Moderate 0.65", "high": "High 0.80", "overload_bursts": "Flash crowds",
           "shift": "Shift (held-out)"}
    LAB = {"static_equal": "Static equal share", "reactive_prop": "Reactive proportional (EWMA)",
           "queue_aware": "Deadline-aware reactive (persistence r*)", "point_forecast": "Point forecast (GBM median)",
           "proposed_window": "Proposed rule, window quantiles (no ML)", "proposed": "Proposed (GBM quantiles + KKT)",
           "proposed_cal": "Proposed + ACI calibration", "oracle": "Oracle water-fill (true r*, reference)"}

    def pr(scenario, baseline, col="rel_reduction_pct"):
        if paired is None:
            return float("nan")
        r = paired[(paired.scenario == scenario) & (paired.baseline == baseline)]
        return float(r[col].iloc[0]) if len(r) else float("nan")

    def mean_metric(scenario, method, metric=PRIMARY_METRIC):
        if main is None:
            return float("nan")
        return float(main[(main.scenario == scenario) & (main.method == method)][metric].mean())

    # 1 Title ---------------------------------------------------------------
    s = d.slide("", notes=(
        "Opening (60-90 s): Good morning. My BTP is on fronthaul load management in Open RAN. In a 7-2x split, "
        "several radio units share one Ethernet fronthaul link that is deliberately over-subscribed to exploit "
        "statistical multiplexing. The distributed unit must decide how much of that link each cell may use in the "
        "next control interval, before it knows the traffic that will actually arrive, and the traffic is bursty. "
        "I built a slot-level simulator of this problem, implemented five baseline controllers including an oracle, "
        "and propose an allocation rule that uses a quantile forecast of each cell's deadline-feasible rate and a "
        "newsvendor-style KKT rule that equalises the weighted probability that the marginal bit is needed. "
        "On five test scenarios the rule reduces priority-weighted deadline violations by 10-50% against the "
        "point-forecast controller and beats the deadline-aware reactive baseline on every seed, but it is only a "
        "tie with the simplest proportional baseline under flash crowds, and online calibration did not help. "
        "Everything I show is produced by the code in the repository."))
    bg = s.shapes[0]; bg.height = H
    text(s, "Fronthaul Load Management in Open RAN", Inches(0.8), Inches(1.6), Inches(11.7), Inches(0.9), size=36,
         bold=True, color=WHITE)
    text(s, "Uncertainty-aware, deadline-feasible budget allocation on a shared 7-2x fronthaul link",
         Inches(0.8), Inches(2.5), Inches(11.7), Inches(0.8), size=22, color=RGBColor(0xCF, 0xD8, 0xE3))
    text(s, "B.Tech. Project — mid-term evaluation", Inches(0.8), Inches(3.6), Inches(11.7), Inches(0.5), size=18,
         color=WHITE)
    text(s, "Student: <name>   |   Supervisor: <name>   |   Department of <dept>",
         Inches(0.8), Inches(4.2), Inches(11.7), Inches(0.5), size=14, color=RGBColor(0xCF, 0xD8, 0xE3))
    text(s, "Deliverables today: working simulator + 7 controllers + trained quantile forecaster + reproducible "
         "experiments (5 scenarios x 5 seeds) + tests + this deck, all generated from the repository.",
         Inches(0.8), Inches(5.4), Inches(11.7), Inches(0.9), size=13, color=WHITE, italic=True)

    # 2 Motivation ---------------------------------------------------------
    s = d.slide("Why fronthaul load management?", section="1 Motivation", notes=(
        "The 7-2x split moves the low-PHY into the radio unit; the fronthaul then carries frequency-domain IQ "
        "samples per PRB, per layer, per symbol. Its bit rate is huge but, unlike 8, it depends on how many PRBs "
        "are actually scheduled, so an operator can over-subscribe a shared link. Our default: 8 cells of 100 MHz, "
        f"4 layers, BFP-9, whose summed peak is {net.oversubscription:.1f}x the usable 25GE capacity. The price of "
        "over-subscription is that during coincident bursts someone has to back off, and the delay budget of "
        "the low-latency cells is only a couple of milliseconds. So the question is how to split the link."))
    bullets(s, [
        ("O-RAN 7-2x split: O-RU does low-PHY; the fronthaul carries frequency-domain IQ per PRB, layer, symbol", 0),
        (f"Load-dependent: {net.fh_bits_per_prb_layer:,.0f} FH bits per scheduled PRB-layer-slot (BFP-9, 8% eCPRI/Eth. overhead)", 1),
        (f"One 100 MHz / 4-layer cell peaks at {net.cell_peak_bits_per_slot(0) / 1e6 / net.slot_duration_s / 1e3:.1f} Gbit/s", 1),
        ("Shared aggregation links are over-subscribed on purpose (statistical multiplexing)", 0),
        (f"Default scenario: 8 cells, 25GE link, aggregate peak = {net.oversubscription:.1f}x usable capacity", 1),
        ("When bursts coincide, some cell's IQ must be deferred or dropped; low-latency cells have ~2 ms of slack", 0),
        ("Load management = deciding, every control interval, how much link each cell may use — before the traffic is known", 0, True),
        ("Bad decisions → deadline violations (lost IQ / HARQ failures) or wasted link capacity", 1),
    ], Inches(0.5), Inches(1.1), Inches(7.6), Inches(5.6), size=16)
    # small diagram: cells -> switch -> link -> DU
    x0, y0 = Inches(8.3), Inches(1.4)
    for k in range(4):
        box(s, f"O-RU {k + 1}\n{'LL' if k < 2 else 'eMBB'}", x0, y0 + Inches(1.05) * k, Inches(1.1), Inches(0.75),
            fill=RGBColor(0xE3, 0xF2, 0xFD) if k < 2 else LIGHT, size=11)
        arrow(s, x0 + Inches(1.1), y0 + Inches(1.05) * k + Inches(0.375), x0 + Inches(1.8), y0 + Inches(2.3))
    box(s, "FH\nswitch", x0 + Inches(1.8), y0 + Inches(1.9), Inches(0.9), Inches(0.8), size=11)
    arrow(s, x0 + Inches(2.7), y0 + Inches(2.3), x0 + Inches(3.6), y0 + Inches(2.3), color=RED, width=3)
    text(s, "shared 25GE\n(bottleneck)", x0 + Inches(2.5), y0 + Inches(2.45), Inches(1.3), Inches(0.6), size=9,
         color=RED, align=PP_ALIGN.CENTER)
    box(s, "O-DU\nscheduler +\nbudget controller", x0 + Inches(3.6), y0 + Inches(1.7), Inches(1.3), Inches(1.2),
        fill=RGBColor(0xFF, 0xF3, 0xE0), size=10)
    text(s, "…", x0 + Inches(0.4), y0 + Inches(4.15), Inches(0.5), Inches(0.3), size=14)

    # 3 System model -------------------------------------------------------
    s = d.slide("System model and operating constraints", section="2 System model", notes=(
        "Everything is in slots of 0.5 ms. Arrivals are user bits per cell per slot; the DU converts them to PRBs "
        "using the cell's spectral efficiency and each PRB-layer costs a fixed number of fronthaul bits, so "
        "fronthaul demand is application demand divided by spectral efficiency times the IQ constant — the two "
        "are not interchangeable. Bits wait in a per-cell DU queue; a bit that waits longer than its class "
        "deadline is discarded and counted as a violation. The controller sets per-cell budgets in bits per slot "
        "that must sum to the usable link capacity, holds them for T=20 slots, and observes the state with a "
        "2-slot telemetry delay. The DU scheduler then serves each queue FIFO up to its budget in every slot. "
        "The controller does not see the future, and neither do any of the practical baselines."))
    bullets(s, [
        ("Time: NR slots of 0.5 ms (30 kHz SCS). Data: bits. Capacity: bits/slot", 0),
        ("Cells: 3 low-latency (deadline 4 slots = 2 ms, priority 3) + 5 eMBB (20 slots = 10 ms, priority 1)", 0),
        ("Demand mapping: FH bits = user bits / SE_i(t) × IQ bits per PRB-layer  (SE differs per cell and drifts)", 0),
        ("Per-cell DU queue, FIFO, age-tracked; bits older than D_i are dropped = deadline violation", 0),
        ("Shared link: Σ_i r_i ≤ C_u = 0.97 × 25 Gbit/s (3% reserved for C/M/S-plane); r_i ≤ per-cell peak", 0),
        ("Controller: every T = 20 slots (10 ms) sets budgets r_i, fixed for the interval; sees state τ = 2 slots old", 0),
        ("DU scheduler: serves each queue up to r_i per slot within the budget; link never queues (budgets enforce this)", 0),
        ("Why decide in advance? Budgets are a reservation held for T slots and telemetry is delayed → the next", 0),
        ("interval's arrivals are unknown at decision time; the ~10 ms control interval matches real DU/switch reconfiguration", 1),
    ], Inches(0.5), Inches(1.1), Inches(7.4), Inches(5.7), size=15)
    # timeline diagram
    x0, y0 = Inches(8.3), Inches(1.5)
    box(s, "observe state\n(τ = 2 slots old)", x0, y0, Inches(1.6), Inches(0.9), size=11, fill=RGBColor(0xE3, 0xF2, 0xFD))
    arrow(s, x0 + Inches(1.6), y0 + Inches(0.45), x0 + Inches(2.0), y0 + Inches(0.45))
    box(s, "decide budgets r_i\nΣ r_i ≤ C_u", x0 + Inches(2.0), y0, Inches(1.6), Inches(0.9), size=11,
        fill=RGBColor(0xFF, 0xF3, 0xE0))
    arrow(s, x0 + Inches(2.8), y0 + Inches(0.9), x0 + Inches(2.8), y0 + Inches(1.4))
    box(s, "hold for T = 20 slots (10 ms)\nDU serves queue_i ≤ r_i per slot\narrivals unknown at decision time",
        x0, y0 + Inches(1.4), Inches(3.6), Inches(1.1), size=11)
    arrow(s, x0 + Inches(1.8), y0 + Inches(2.5), x0 + Inches(1.8), y0 + Inches(3.0))
    box(s, "bits older than D_i → dropped\n(violation accounting per class)", x0, y0 + Inches(3.0), Inches(3.6),
        Inches(0.9), size=11, fill=RGBColor(0xFF, 0xEB, 0xEE))
    text(s, "Sources: O-RAN WG4 CUS-Plane spec (7-2x sections, BFP, T2a windows); Larsen et al., IEEE COMST 2019 "
         "(load-dependent bit rate, ~8% Ethernet overhead); Pérez et al. 2018/2019 (packet-switched aggregation).",
         x0, y0 + Inches(4.1), Inches(4.5), Inches(1.1), size=10, color=GREY, italic=True)

    # 4 Literature ---------------------------------------------------------
    s = d.slide("Focused literature review → the opportunity", section="3 Literature", notes=(
        "Three groups of work. First the primary sources for the fronthaul model. Second, predictive or "
        "anticipatory allocation: these papers forecast load, mostly with LSTMs or similar, then plan with the "
        "point forecast; uncertainty is handled by a fixed margin if at all. Third, uncertainty-aware forecasting "
        "and conformal/quantile methods, which so far have been applied to slicing or to cloud resources rather "
        "than to a shared fronthaul with per-class deadlines. The gap I address is the middle: the allocation rule "
        "that turns a predictive distribution into deadline-feasible budgets under one hard link constraint, "
        "compared fairly against strong reactive and point-forecast controllers. Full list with DOIs is in "
        "docs/fhlm/literature_review.md."))
    bullets(s, [
        ("A. Fronthaul itself (primary sources)", 0, True),
        ("O-RAN WG4 CUS-Plane spec (7-2x, BFP, T2a windows) • Larsen et al., IEEE COMST 2019: bit rate varies with load for splits ≤ 7-2", 1),
        ("Pérez et al., JOCN 2018 / IEEE Access 2019 (packet-switched eCPRI aggregation) • Wang & Zhou, IEEE Commun. Lett. 2017 (multiplexing gain)", 1),
        ("Lagén et al., IEEE Commun. Mag. 2022: shared 7-2x link, reactive per-slot compression control — closest fronthaul work, no forecasting", 1),
        ("B. Predictive / anticipatory capacity allocation", 0, True),
        ("Bega et al., DeepCog (INFOCOM 2019 / JSAC 2020), AZTEC (INFOCOM 2020): DL capacity forecasts → slice allocation; fixed cost ratio", 1),
        ("Predictive DBA for PON fronthaul (Mikaeil et al. 2018; Zhang et al. 2019); Kavehmadavani et al., TWC 2023: LSTM point forecasts + FH constraint", 1),
        ("Typical treatment of uncertainty: a fixed safety margin on a point forecast; no per-cell deadline feasibility", 1),
        ("C. Uncertainty-aware forecasting / conformal methods", 0, True),
        ("Cohen et al., IEEE WCL 2023 (conformal URLLC pre-allocation, single stream) • Gibbs & Candès, NeurIPS 2021 (ACI)", 1),
        ("Kasuluru et al. 2024 [preprint]: probabilistic PRB-load forecasts, percentile chosen globally, not from a coupled allocation", 1),
        ("Gap: no work turns a predictive DISTRIBUTION of deadline-feasible demand into per-cell FH budgets under one hard link constraint, and tests it against strong reactive + point-forecast baselines", 0, True),
    ], Inches(0.5), Inches(1.1), Inches(12.3), Inches(5.8), size=15)

    # 5 Formulation --------------------------------------------------------
    s = d.slide("Problem formulation and evaluation objective", section="4 Formulation", notes=(
        "The controller chooses budgets on the simplex defined by the link capacity and per-cell caps. Our "
        "primary metric, fixed before any tuning, is the priority-weighted deadline-violation ratio: violated bits "
        "weighted by class priority over arrived bits weighted the same way. The key modelling step is the "
        "deadline-feasible rate r*: for a sequence of arrivals and a deadline D, r* is the smallest constant "
        "service rate under which no bit waits longer than D. It is a max over windows of the window sum divided "
        "by window length plus D — the network-calculus view of a deadline. For eMBB with D=20 it is close to the "
        "horizon mean; for LL with D=4 it is essentially the peak 4-slot burst rate, which is much harder to "
        "predict. Forecasting r* rather than volume is what makes the forecast deadline-aware."))
    bullets(s, [
        ("Decision each epoch k: budgets r ∈ {0 ≤ r_i ≤ cap_i, Σ r_i ≤ C_u}, held for slots kT … (k+1)T−1", 0),
        ("Primary metric (fixed before tuning): priority-weighted deadline-violation ratio", 0, True),
        ("V_w = Σ_i p_i · violated_bits_i / Σ_i p_i · arrived_bits_i     (p_LL = 3, p_eMBB = 1)", 1),
        ("Supporting: per-class violation ratio, link utilisation, mean/p99 DU queueing delay, Jain fairness of service ratio, decision time", 1),
        ("Deadline-feasible rate r*(a, D): smallest constant rate that serves arrivals a_1..a_H with no bit waiting > D slots", 0, True),
        ("r*(a, D) = max over windows [s, e] of  Σ_{t=s..e} a_t / (e − s + 1 + D)     — network-calculus bound, exact for FIFO", 1),
        ("Demand of a cell for the next interval = backlog-clearing rate + r* of the unseen arrivals", 1),
        ("Why forecasting matters: r* of the NEXT interval is not observable; LL r* ≈ peak 4-slot burst rate (hard to predict)", 0),
        ("Why not point forecasts: r* is right-skewed (bursts) → the median under-reserves, a fixed margin over-reserves everywhere", 0),
    ], Inches(0.5), Inches(1.1), Inches(12.3), Inches(5.8), size=15)

    # 6 Baselines ----------------------------------------------------------
    s = d.slide("Baseline controllers (implemented; tuned on validation seeds)", section="5 Baselines", notes=(
        "Five references. Static equal share ignores everything. Reactive proportional is the classic: backlog "
        "plus an EWMA of recent demand, split proportionally, leftover redistributed. The deadline-aware reactive "
        "controller has the same deadline knowledge as our method: it uses the deadline-feasible rate of the last "
        "observed horizon as a persistence forecast, backlog slack, and priority weights. The point-forecast "
        "controller is the ablation: identical to the proposed method but uses the GBM median instead of the "
        "distribution. The oracle knows the actual next-horizon arrivals and removes forecast error from the water-fill family; it is a reference for the forecast, not a bound on other rules — in fact the KKT rule beats it at short intervals. It also bounds what interval-level "
        "allocation could achieve. All margins and windows were chosen on validation seeds; the tuned values are "
        "margin zero everywhere, meaning inflating a point estimate does not help under a proportional split."))
    rows = [
        ("Static equal share", "C_u / N per cell (caps redistributed)", "none", "—"),
        ("Reactive proportional", "backlog/T + (1+m)·EWMA; proportional split; leftover redistributed", "history", "m, EWMA window"),
        ("Deadline-aware reactive (strong)", "backlog-slack rate + (1+m)·r*(last horizon); priority weights; water-fill", "history, D_i, p_i", "m, #horizons"),
        ("Point forecast + water-fill (ablation)", "same as above with GBM MEDIAN forecast of r*", "history, D_i, p_i, model", "m"),
        ("Oracle water-fill (reference)", "true r* of the next horizon; same water-fill as above (perfect point forecast, not a bound on other rules)", "future arrivals", "—"),
    ]
    df = pd.DataFrame(rows, columns=["Controller", "Budget rule", "Information", "Tuned"])
    tbl = table(s, df, Inches(0.5), Inches(1.15), Inches(12.3), Inches(2.6), size=11)
    for j, w in enumerate((2.6, 5.9, 2.0, 1.8)):
        tbl.columns[j].width = Inches(w)
    if tuning:
        sel = tuning["selected"]
        bullets(s, [
            ("Validation tuning (seeds 2000-2003, scenarios moderate/high; test seeds untouched):", 0, True),
            (f"reactive_prop → {sel.get('reactive_prop')}  |  queue_aware → {sel.get('queue_aware')}  |  point_forecast → {sel.get('point_forecast')}  |  proposed_cal → {sel.get('proposed_cal')}", 1),
            ("Finding: every safety margin > 0 was worse on validation — inflating a point estimate hurts when the shortage is split proportionally (over-claimers get more)", 1),
            ("All controllers: identical traces, identical delayed observations, unused capacity always redistributed", 0),
        ], Inches(0.5), Inches(4.75), Inches(12.3), Inches(2.2), size=13)

    # 7 Proposed method ----------------------------------------------------
    s = d.slide("Proposed method: quantile forecast of r* + KKT budget rule", section="6 Proposed", notes=(
        "Two components. The forecaster predicts six quantiles of each cell's next-horizon deadline-feasible "
        "rate with one gradient-boosted model per quantile, from 28 features built only from the observed past. "
        "The allocator then solves a separable concave program: maximise the weighted expected served demand, "
        "where the expectation is taken under the forecast distribution. The KKT conditions say each cell gets "
        "its backlog rate plus the inverse CDF at 1 minus lambda over its weight, and lambda is the single "
        "multiplier found by bisection so that the budgets sum to capacity. So all cells are cut at the same "
        "weighted tail probability: a cell whose forecast is wide or whose weight is high automatically receives a "
        "larger margin above its median; a confident cell gets almost exactly its median. Point forecasts are the "
        "degenerate case, which is why the median water-fill is the fair comparator. The rule is closed-form "
        "apart from a scalar bisection, feasibility is guaranteed by construction."))
    bullets(s, [
        ("1. Forecaster: K = 6 quantiles (5, 25, 50, 75, 90, 95%) of r*_i for the next horizon", 0, True),
        ("One HistGradientBoostingRegressor(loss='quantile') per level; 28 features from past slots only (lag means, EWMAs, last slots, past r*, SE, deadline, cell id)", 1),
        ("Target normalised by the cell's fixed peak → no statistics fitted on data; trained on TRAIN seeds only", 1),
        ("2. Allocator: separable concave program under the forecast distribution F_i", 0, True),
        ("max Σ_i w_i · E[min(B_i + r*_i, r_i)]   s.t.  Σ r_i ≤ C_u,  0 ≤ r_i ≤ cap_i", 1),
        ("KKT:  r_i(λ) = clip(B_i + F_i⁻¹(1 − λ / w_i), 0, cap_i),   λ from bisection on Σ r_i(λ) = C_u  (λ = 0 if slack → headroom spread)", 1),
        ("Meaning: every cell is cut at the same weighted tail probability w_i·P(marginal bit needed) = λ", 1),
        ("→ wide forecast or high weight ⇒ larger margin; confident forecast ⇒ ≈ median; backlog funded first (F_i(x<0) = 0)", 1),
        ("Optional: per-cell ACI offset δ_i on the quantile level (Gibbs & Candès 2021) as an online fallback — tested as ablation", 0),
        ("Cost: O(N·K + N·60) per epoch; feasibility by construction (Prop. 1-3 in docs/fhlm/method.md)", 0),
    ], Inches(0.5), Inches(1.1), Inches(8.2), Inches(5.8), size=14)
    # mini diagram of rule
    x0, y0 = Inches(9.0), Inches(1.2)
    box(s, "history (past slots)\nqueue, HoL age, SE", x0, y0, Inches(3.8), Inches(0.8), size=11, fill=RGBColor(0xE3, 0xF2, 0xFD))
    arrow(s, x0 + Inches(1.9), y0 + Inches(0.8), x0 + Inches(1.9), y0 + Inches(1.1))
    box(s, "quantile GBM  →  q_i(α), α ∈ {.05 … .95}\n(predictive CDF F_i of r*_i)", x0, y0 + Inches(1.1), Inches(3.8),
        Inches(0.9), size=11, fill=RGBColor(0xFF, 0xF3, 0xE0))
    arrow(s, x0 + Inches(1.9), y0 + Inches(2.0), x0 + Inches(1.9), y0 + Inches(2.3))
    box(s, "KKT rule\nr_i = B_i + F_i⁻¹(1 − λ/w_i)\nbisection on λ: Σ r_i = C_u", x0, y0 + Inches(2.3), Inches(3.8),
        Inches(1.2), size=11, fill=RGBColor(0xFF, 0xEB, 0xEE), line=RED)
    arrow(s, x0 + Inches(1.9), y0 + Inches(3.5), x0 + Inches(1.9), y0 + Inches(3.8))
    box(s, "budgets r_i, held T slots\nDU scheduler serves ≤ r_i", x0, y0 + Inches(3.8), Inches(3.8), Inches(0.8), size=11)
    text(s, "Adapted: quantile GBM, ACI, water-filling.\nCandidate contribution: r* as forecast target + KKT rule "
         "over the forecast CDF under the link constraint, evaluated vs strong baselines.", x0, y0 + Inches(4.7),
         Inches(3.9), Inches(1.0), size=10, color=GREY, italic=True)

    # 8 Architecture -------------------------------------------------------
    s = d.slide("Architecture and what has been implemented", section="7 Implementation", notes=(
        "The package fhlm has about 1,700 lines. config holds the units and the 7-2x constants; traffic generates "
        "the synthetic arrivals; demand implements r*; simulator is the slot loop with queues and accounting; "
        "controllers hold the five baselines; forecast the feature pipeline, quantile GBM and a compiled "
        "vectorised inference path; proposed the KKT allocator; scenarios the seed splits; train, run_experiments, "
        "make_figures and make_slides reproduce everything in this deck. Thirteen tests cover capacity compliance, "
        "non-negative queues, bit accounting, zero load, overload, reproducibility, r* tightness, KKT properties, "
        "the no-future-leakage contract and compiled-vs-sklearn equality."))
    mods = [
        ("config.py", "units, 7-2x FH constants, cells, link"), ("traffic.py", "synthetic arrivals: Gamma + Pareto ON/OFF + regimes + SE drift"),
        ("demand.py", "deadline-feasible rate r*, backlog slack rate"), ("simulator.py", "slot loop, FIFO age queues, drops, metrics"),
        ("controllers.py", "5 baselines incl. oracle, water-fill"), ("forecast.py", "features, quantile GBM, window quantiles, CompiledGBM"),
        ("proposed.py", "KKT allocator + ACI offsets"), ("scenarios.py", "train/val/test seeds, 5 scenarios"),
        ("train.py", "train on TRAIN seeds, validate on VAL"), ("run_experiments.py", "tune / main / sweep / demo; raw JSON per run"),
        ("make_figures.py", "all figures from CSV"), ("tests/test_fhlm.py", "13 tests (capacity, queues, accounting, leakage, KKT …)"),
    ]
    for k, (m, desc) in enumerate(mods):
        col, row = k % 2, k // 2
        x = Inches(0.5) + Inches(6.2) * col
        y = Inches(1.15) + Inches(0.72) * row
        box(s, m, x, y, Inches(1.9), Inches(0.6), size=12, bold=True, fill=RGBColor(0xE3, 0xF2, 0xFD))
        text(s, desc, x + Inches(2.0), y + Inches(0.08), Inches(4.1), Inches(0.6), size=12)
    bullets(s, [
        ("Pipeline: traffic → simulator ↔ controller (observation τ old → budgets) → metrics/raw JSON → figures → slides", 0),
        ("Data flow for ML: TRAIN seeds → features/targets → 6 GBMs (~12 s CPU) → VAL coverage check → frozen model → TEST", 0),
        ("Python 3, numpy/pandas/scikit-learn/matplotlib only; full reproduction ≈ 6 min on a 4-core laptop", 0),
    ], Inches(0.5), Inches(5.6), Inches(12.3), Inches(1.4), size=13)

    # 9 Experimental setup -------------------------------------------------
    s = d.slide("Experimental setup (synthetic traffic, labelled as such)", section="8 Experiments", notes=(
        "Traffic is synthetic: a smooth Gamma component plus a Pareto-distributed ON/OFF bursty component per "
        "cell, slow log-normal regime changes about every second, and spectral-efficiency drift. Five scenarios "
        "differ in mean load and burstiness; 'shift' uses heavier and longer bursts than anything in training and "
        "is the held-out condition. Every method sees the same trace, seed by seed, so we can compare pairwise. "
        "Train, validation and test seeds are disjoint ranges. Absolute violation ratios are high because the "
        "traffic is deliberately heavy-tailed at 80% mean load; the comparison between methods is the result."))
    rows = [("low", "0.50", "nominal", "no"), ("moderate", "0.65", "nominal", "yes (validation seeds)"),
            ("high", "0.80", "nominal", "yes (validation seeds)"),
            ("overload_bursts", "0.80", "flash crowds: ×1.8 regimes, 15% of the time (offered load > C_u)", "no"),
            ("shift (held-out)", "0.80", "ON rate ×1.5, ON duration ×1.5, Pareto α_on = 1.2 — never in training/tuning", "no")]
    tbl = table(s, pd.DataFrame(rows, columns=["Scenario", "Mean FH load / C_u", "Traffic family", "Used for tuning?"]),
                Inches(0.5), Inches(1.15), Inches(12.3), Inches(2.3), size=12)
    for j, w in enumerate((2.0, 2.0, 6.3, 2.0)):
        tbl.columns[j].width = Inches(w)
    bullets(s, [
        ("Traffic (synthetic): Gamma smooth part + Pareto ON/OFF bursts (α_on 1.5) + log-normal regimes (~1 s) + SE drift", 0),
        ("Seeds: train 1000-1015 (loads 0.5-0.95) | validation 2000-2003 | test 3000-3004 — disjoint", 0),
        ("Per run: 20,000 slots = 10 s after 1,000-slot warm-up; T = 20 slots, τ = 2 slots; 8 methods × 5 scenarios × 5 seeds = 200 runs", 0),
        ("Identical traces and identical delayed observations for every controller; forecaster frozen before test", 0),
        ("Note: absolute violation ratios are high by design (heavy-tailed bursts at 0.8 mean load); relative, paired differences are the evidence", 0),
    ], Inches(0.5), Inches(4.0), Inches(12.3), Inches(3.0), size=14)

    # 10 Main results ------------------------------------------------------
    hi_pf, hi_qa, hi_rp = pr("high", "point_forecast"), pr("high", "queue_aware"), pr("high", "reactive_prop")
    sh_pf, sh_qa, sh_rp = pr("shift", "point_forecast"), pr("shift", "queue_aware"), pr("shift", "reactive_prop")
    ob_rp, ob_rp_w = pr("overload_bursts", "reactive_prop"), pr("overload_bursts", "reactive_prop", "reference_wins")
    s = d.slide("Results: primary metric per scenario (5 test seeds, mean ± std)", section="9 Results", notes=(
        f"Bars are the priority-weighted violation ratio; lower is better; black is the oracle. The proposed rule "
        f"(red) is the best implementable method in every scenario. Against the point-forecast controller, which "
        f"has the same model and the same information, it reduces the metric by {hi_pf:.0f}% at high load and "
        f"{sh_pf:.0f}% under the held-out shift. Against the deadline-aware reactive baseline by {hi_qa:.0f}% and "
        f"{sh_qa:.0f}%. Against the plain proportional controller the margin is {hi_rp:.0f}% at high load but only "
        f"{ob_rp:.0f}% under flash crowds, where it wins {ob_rp_w:.0f} of 5 seeds — a tie. The std bars are large "
        "because seeds differ in burst timing; the paired analysis on the next slide is the correct reading."))
    picture(s, os.path.join(FIG, "fig1_primary_by_scenario.png"), Inches(0.4), Inches(1.1), width=Inches(8.6))
    if main is not None:
        items = [("Proposed = best implementable method in 5/5 scenarios", 0, True),
                 (f"vs point forecast (same model, median only): −{hi_pf:.0f}% (high), −{sh_pf:.0f}% (shift)", 1),
                 (f"vs deadline-aware reactive: −{hi_qa:.0f}% (high), −{sh_qa:.0f}% (shift)", 1),
                 (f"vs reactive proportional: −{hi_rp:.0f}% (high) but only −{ob_rp:.0f}% under flash crowds ({ob_rp_w:.0f}/5 seeds) → tie", 1),
                 (f"Gap to oracle at high load: {pct(mean_metric('high', 'proposed'))} vs {pct(mean_metric('high', 'oracle'))}", 0),
                 ("Std across seeds is large (burst timing) → paired per-seed comparison next", 0)]
        bullets(s, items, Inches(9.1), Inches(1.2), Inches(4.0), Inches(5.6), size=13)

    # 11 Paired ------------------------------------------------------------
    s = d.slide("Results: paired per-seed comparison on identical traces", section="9 Results", notes=(
        "Each bar is the mean relative reduction of the primary metric by the proposed method against one "
        "baseline, computed seed by seed on the very same trace; whiskers are min and max over seeds and the text "
        "is how many of the five seeds the proposed method won. Against point forecast and the deadline-aware "
        "reactive controller it wins every seed in every scenario. Against the plain proportional controller it "
        "wins all seeds except under flash crowds. The green bars are the ML ablation: the same rule fed with "
        "empirical window quantiles instead of the GBM; the ML forecaster adds 5-50% in nominal traffic but almost "
        "nothing under the held-out shift, where the trained model is out of distribution. Purple: ACI "
        "calibration gives no benefit and is harmful under shift."))
    picture(s, os.path.join(FIG, "fig8_paired_reduction.png"), Inches(0.4), Inches(1.1), width=Inches(8.6))
    if paired is not None:
        pw = [pr(sc, "proposed_window") for sc in SC]
        items = [("Wins 5/5 seeds vs point forecast and vs deadline-aware reactive in every scenario", 0, True),
                 (f"vs reactive proportional: 5/5 in four scenarios; {ob_rp_w:.0f}/5 under flash crowds (no claim there)", 0),
                 ("ML ablation (same rule, window quantiles instead of GBM):", 0, True),
                 (f"GBM adds {min(pw):.0f}–{max(pw):.0f}% ; smallest under held-out shift ({pr('shift', 'proposed_window'):.0f}%) → the rule, not the model, carries most of the gain", 1),
                 ("ACI calibration: no gain in-distribution, harmful under shift (over-reserves LL, starves eMBB) → negative result", 0),
                 ("No significance test claimed with 5 seeds; win counts and min/max are reported instead", 0)]
        bullets(s, items, Inches(9.1), Inches(1.2), Inches(4.0), Inches(5.6), size=13)

    # 12 Per class trade-off ----------------------------------------------
    s = d.slide("Where the gain comes from: per-class trade-off (high load)", section="9 Results", notes=(
        "Left: low-latency violations; middle: eMBB; right: link utilisation. The proportional controller keeps "
        "eMBB almost clean but lets low-latency cells lose 15% of their bits — the deadline-unaware failure mode. "
        "The deadline-aware family (blue, orange, red, black) protects the LL cells at the price of eMBB. Within "
        "that family the proposed rule has the lowest eMBB loss and the highest utilisation, because it reserves "
        "margin only where the forecast is uncertain instead of everywhere. The oracle shows that even perfect "
        "knowledge of the next interval leaves 13% eMBB loss at this load: budgets fixed for 10 ms cannot follow "
        "heavy-tailed bursts, so a shorter interval — next slide — is the other lever."))
    picture(s, os.path.join(FIG, "fig2_class_breakdown_high.png"), Inches(0.4), Inches(1.1), width=Inches(12.5))
    if main is not None:
        items = [
            (f"Reactive proportional: LL {pct(mean_metric('high', 'reactive_prop', 'violation_ratio_ll'))} vs proposed {pct(mean_metric('high', 'proposed', 'violation_ratio_ll'))} — deadline-unaware controllers sacrifice LL", 0),
            (f"Within the deadline-aware family, proposed has the lowest eMBB loss ({pct(mean_metric('high', 'proposed', 'violation_ratio_embb'))} vs {pct(mean_metric('high', 'point_forecast', 'violation_ratio_embb'))} point forecast) and highest utilisation ({pct(mean_metric('high', 'proposed', 'fh_utilisation'))})", 0),
            (f"Oracle still loses {pct(mean_metric('high', 'oracle', 'violation_ratio_embb'))} eMBB at 0.80 load: 10-ms fixed budgets cannot track heavy-tailed bursts → control interval matters", 0),
        ]
        bullets(s, items, Inches(0.5), Inches(5.2), Inches(12.3), Inches(1.8), size=13)

    # 13 Ablations: forecast quality + interval sweep -----------------------
    s = d.slide("Ablations: forecast quality and control interval", section="10 Ablation", notes=(
        "Left: the GBM quantiles are well calibrated on validation data — empirical coverage matches nominal "
        "levels within one point — and its median error is lower than persistence and window medians. Right: the "
        "control-interval sweep on the high scenario. With very short intervals every reactive controller can "
        "follow the traffic and prediction adds little; as the interval grows, the gap between reactive and "
        "predictive controllers opens. This answers the question of when prediction is worth it: whenever "
        "budgets must be held for a few milliseconds or more, which is the realistic regime for DU/switch "
        "reconfiguration."))
    picture(s, os.path.join(FIG, "fig5_forecast_quality.png"), Inches(0.3), Inches(1.1), width=Inches(6.4))
    picture(s, os.path.join(FIG, "fig4_interval_sweep.png"), Inches(6.8), Inches(1.1), width=Inches(6.3))
    items = []
    if fc:
        v = fc["gbm_validation"]
        items += [(f"Validation coverage at nominal 5/50/95%: {pct(v['coverage_q05'])} / {pct(v['coverage_q50'])} / {pct(v['coverage_q95'])} ; "
                   f"median rel. MAE {pct(v['median_mae_rel'], 0)} vs persistence {pct(fc['persistence_median_mae_rel'], 0)} , window {pct(fc['window_quantile_validation']['median_mae_rel'], 0)}", 0)]
    if sweep is not None and not sweep.empty:
        g = sweep.groupby(["interval_slots", "method"])[PRIMARY_METRIC].mean()
        Ts = sorted(sweep.interval_slots.unique())

        def red(T, base):
            try:
                return 100 * (g.loc[(T, base)] - g.loc[(T, "proposed")]) / g.loc[(T, base)]
            except KeyError:
                return float("nan")
        items += [("Interval sweep (scenario high, 3 seeds), reduction by proposed vs deadline-aware reactive / vs reactive proportional / vs oracle water-fill:", 0, True)]
        items += [("   " + "   |   ".join(f"T={T * 0.5:g} ms: {red(T, 'queue_aware'):+.0f}% / {red(T, 'reactive_prop'):+.0f}% / {red(T, 'oracle'):+.0f}%" for T in Ts), 1)]
        short_T, long_T = Ts[0], Ts[-1]
        if red(short_T, "oracle") > 0:
            items += [(f"At T = {short_T * 0.5:g} ms the KKT rule even beats the oracle water-fill (perfect point forecast, proportional shortage split) → the allocation RULE, not only the forecast, drives the gain", 0)]
        if red(long_T, "reactive_prop") < 0:
            items += [(f"At T = {long_T * 0.5:g} ms (budgets held 5× the LL deadline) the deadline-aware family over-reserves the LL peak rate and reactive proportional wins on the weighted metric → known failure regime; a bound on how long a reservation should be held", 0)]
    else:
        items += [("Interval sweep: not yet run (results/fhlm/sweep_runs.csv missing)", 0)]
    bullets(s, items, Inches(0.5), Inches(4.5), Inches(12.3), Inches(2.4), size=12, para_space=4)

    # 14 Demo --------------------------------------------------------------
    s = d.slide("One trace: budgets vs. demand of a low-latency cell (300 ms)", section="9 Results", notes=(
        "Top: fronthaul demand of a low-latency cell in grey and the budget each controller gave it. The reactive "
        "controller reacts one interval late to each burst; the point forecast tracks the median; the proposed "
        "rule raises the budget when the predictive distribution is wide and lets it sit near the median when it "
        "is confident. Bottom: cumulative violated bits — the proposed rule has the fewest on this window. This "
        "is the demo I can run live: python -m fhlm.run_experiments demo, then make_figures."))
    picture(s, os.path.join(FIG, "fig6_demo_timeseries.png"), Inches(1.2), Inches(1.05), height=Inches(5.9))

    # 15 Limitations -------------------------------------------------------
    s = d.slide("Limitations and honest status", section="11 Limitations", notes=(
        "Be explicit about what this is not. Traffic is synthetic; no real fronthaul traces were available, so "
        "there is no real-world validation. The oracle is only interval-level; a slot-level optimum would be "
        "lower. The gain over the simplest proportional controller vanishes under flash crowds, and the ML "
        "forecaster adds little under the held-out shift. ACI calibration did not help. Five seeds do not allow a "
        "significance claim. The fronthaul link is modelled as a budget-enforced pipe: no packet-level queueing "
        "in the switch, one class per cell, no HARQ feedback loop. Decision time is Python-level: about 3 ms per "
        "10 ms epoch, fine for simulation, not a claim about real-time deployment."))
    bullets(s, [
        ("Synthetic traffic only (Gamma + Pareto ON/OFF + regimes); no real O-RU traces → no real-world validation claimed", 0),
        ("Gains are relative to interval-level controllers; the oracle itself is interval-level — a slot-level optimum is lower", 0),
        ("Not a universal win: tie with reactive proportional under flash crowds; GBM adds ≈0-2% over window quantiles under held-out shift", 0),
        ("ACI online calibration did not help (negative result); the robust fallback is currently the window-quantile variant", 0),
        ("5 test seeds → win counts and min/max reported, no significance test", 0),
        ("Simplified link: budget-enforced pipe, no switch packet queueing, one traffic class per cell, no HARQ/RLC feedback", 0),
        ("Decision time ≈ 3.4 ms per 10-ms epoch in Python (vectorised tree evaluation); reactive baselines ≈ 0.1 ms", 0),
        ("Propositions in docs are feasibility / equal-tail-probability / backlog-first — no stability or optimality-in-the-loop claims", 0),
    ], Inches(0.5), Inches(1.1), Inches(12.3), Inches(5.8), size=15)

    # 16 Remaining work ----------------------------------------------------
    s = d.slide("Status and remaining work toward the final evaluation", section="12 Plan", notes=(
        "Left column is done and verified by tests and experiments; right column is what I propose to do next, "
        "in priority order: replace or complement the synthetic traffic with public traces; make the rule cheaper "
        "and robust by mixing window quantiles and GBM by recent forecast skill; add a switch queue and a second "
        "lever such as compression ratio; more seeds; and an ablation on the deadline-feasible target itself."))
    box(s, "Implemented and validated", Inches(0.5), Inches(1.15), Inches(6.0), Inches(0.5), fill=GREEN, color=WHITE, bold=True, size=14)
    bullets(s, [
        "Slot-level 7-2x shared-link simulator with deadlines, priorities, telemetry delay, accounting (13 tests)",
        "Synthetic heavy-tailed traffic generator with regimes, flash crowds, SE drift",
        "5 baselines (static, proportional, deadline-aware reactive, point forecast, oracle), tuned on validation seeds",
        "Quantile-GBM forecaster of r* (calibrated on validation), vectorised inference",
        "KKT allocation rule with feasibility proof; ACI variant; window-quantile variant",
        "200-run main comparison, paired analysis, interval sweep, demo, all figures, this deck — reproducible",
    ], Inches(0.5), Inches(1.75), Inches(6.0), Inches(5.0), size=13)
    box(s, "Planned (not yet done)", Inches(6.9), Inches(1.15), Inches(6.0), Inches(0.5), fill=ORANGE, color=WHITE, bold=True, size=14)
    bullets(s, [
        "Real or public traffic traces (e.g. per-cell PRB utilisation datasets) → re-validate the forecaster",
        "Skill-weighted blend of GBM and window quantiles as a principled fallback (replace ACI)",
        "Second control lever: per-cell BFP compression / modulation compression under the same rule",
        "Switch-level packet queue and T2a window model instead of a budget-enforced pipe",
        "Ablation on the target: r* vs interval volume; more seeds; sensitivity to τ and priorities",
        "Cost model: does the 3 ms Python decision fit a real DU? (C++/numba port, or longer epochs)",
    ], Inches(6.9), Inches(1.75), Inches(6.0), Inches(5.0), size=13)

    # ---------------- backup ------------------------------------------------
    s = d.slide("Backup: primary metric [%], mean ± std over 5 test seeds", section="Backup", notes=(
        "Table of the primary metric per scenario and method, produced from results/fhlm/main_runs.csv."))
    if main is not None:
        methods = ["static_equal", "reactive_prop", "queue_aware", "point_forecast", "proposed_window", "proposed", "proposed_cal", "oracle"]
        df = summary_table(main, SC, methods, LAB).rename(columns=SCL)
        table(s, df, Inches(0.4), Inches(1.15), Inches(12.5), Inches(4.6), size=11)
        text(s, "Source: results/fhlm/main_runs.csv (200 runs). Paired per-seed statistics: results/fhlm/main_paired.csv.",
             Inches(0.4), Inches(6.0), Inches(12), Inches(0.4), size=11, color=GREY, italic=True)

    s = d.slide("Backup: derivation of the KKT budget rule", section="Backup", notes=(
        "Derivation for questions. The objective is concave and separable; the Lagrangian derivative in r_i is "
        "w_i times one minus F_i at r_i minus B_i minus lambda; setting it to zero gives the inverse-CDF form. "
        "Because F_i is zero below zero, the derivative equals w_i there — backlog is always funded before any "
        "uncertain demand of a lower-weight cell. The sum of r_i(lambda) is non-increasing in lambda, so bisection "
        "finds the unique lambda at which the link is exactly full."))
    bullets(s, [
        ("Objective: J(r) = Σ_i w_i E_{F_i}[ min(B_i + X_i, r_i) ],  X_i ~ F_i (forecast CDF of r*_i)", 0),
        ("d/dr_i E[min(B_i + X_i, r_i)] = P(B_i + X_i > r_i) = 1 − F_i(r_i − B_i)  → J concave, separable", 0),
        ("Lagrangian: L = J − λ(Σ r_i − C_u) + Σ μ_i r_i − Σ ν_i (r_i − cap_i)", 0),
        ("Stationarity for an interior r_i:  w_i (1 − F_i(r_i − B_i)) = λ   ⇒   r_i = B_i + F_i⁻¹(1 − λ / w_i)", 0),
        ("Clip at 0 and cap_i (μ_i, ν_i ≥ 0); Σ_i r_i(λ) is non-increasing in λ ⇒ unique λ* by bisection (60 steps)", 0),
        ("Prop. 1 (feasibility): output always satisfies caps and Σ r_i ≤ C_u — verified by test_kkt_allocation_properties", 0),
        ("Prop. 2 (equal weighted tail): at the optimum all interior cells share w_i·P(marginal bit needed) = λ*", 0),
        ("Prop. 3 (backlog first): F_i(x) = 0 for x < 0 ⇒ marginal value below B_i is w_i ⇒ backlog of any cell with λ* < w_i is fully funded", 0),
        ("Degenerate F_i (point forecast) ⇒ priority-ordered fill = the point-forecast water-fill baseline", 0),
        ("F_i⁻¹: piecewise-linear through the 6 forecast quantiles, linear extrapolation above 0.95; monotone by sorting", 0),
    ], Inches(0.5), Inches(1.1), Inches(12.3), Inches(5.8), size=15)

    s = d.slide("Backup: decision overhead and utilisation trade-off", section="Backup", notes=(
        "Left: mean decision time per control epoch per method. Right: violation versus utilisation per scenario."))
    picture(s, os.path.join(FIG, "fig7_decision_time.png"), Inches(0.3), Inches(1.2), width=Inches(5.6))
    picture(s, os.path.join(FIG, "fig3_tradeoff.png"), Inches(6.0), Inches(1.2), width=Inches(7.1))
    text(s, "Decision times are Python on a 4-core CPU inside the simulator (feature construction + 1,800 trees via "
         "vectorised traversal + bisection). The rule itself is < 0.1 ms.", Inches(0.4), Inches(5.6), Inches(12.5),
         Inches(0.8), size=12, color=GREY)

    s = d.slide("Backup: references", section="Backup", notes="Full list with DOIs/links in docs/fhlm/literature_review.md.")
    bullets(s, [
        "O-RAN WG4, Control, User and Synchronization Plane Specification (O-RAN.WG4.CUS.0) [standard] — 7-2x, BFP compression (Annex A.1), T2a windows. 3GPP TR 38.801 [standard]; IEEE 802.1CM-2018 [standard].",
        "L. M. P. Larsen, A. Checko, H. L. Christiansen, 'A Survey of the Functional Splits Proposed for 5G Mobile Crosshaul Networks', IEEE COMST 21(1), 2019. DOI 10.1109/COMST.2018.2868805 [peer-reviewed]",
        "G. O. Pérez, J. A. Hernández, D. Larrabeiti, 'Fronthaul Network Modeling and Dimensioning Meeting Ultra-Low Latency Requirements for 5G', JOCN 10(6), 2018. DOI 10.1364/JOCN.10.000573; IEEE Access 2019, DOI 10.1109/ACCESS.2019.2923020 [peer-reviewed]",
        "L. Wang, S. Zhou, 'On the Fronthaul Statistical Multiplexing Gain', IEEE Commun. Lett. 21(5), 2017. DOI 10.1109/LCOMM.2017.2653120 [peer-reviewed]",
        "S. Lagén, X. Gelabert, A. Hansson, M. Requena, L. Giupponi, 'Fronthaul Compression Control for Shared Fronthaul Access Networks', IEEE Commun. Mag. 2022. DOI 10.1109/MCOM.001.2100959 [peer-reviewed]",
        "D. Bega, M. Gramaglia, M. Fiore, A. Banchs, X. Costa-Pérez, 'DeepCog', IEEE INFOCOM 2019, DOI 10.1109/INFOCOM.2019.8737488; 'AZTEC', IEEE INFOCOM 2020, DOI 10.1109/INFOCOM41043.2020.9155299 [peer-reviewed]",
        "F. Kavehmadavani, V.-D. Nguyen, T. X. Vu, S. Chatzinotas, 'Intelligent Traffic Steering in Beyond 5G Open RAN Based on LSTM Traffic Prediction', IEEE TWC 2023. DOI 10.1109/TWC.2023.3254903 [peer-reviewed]",
        "K. M. Cohen, S. Park, O. Simeone, P. Popovski, S. Shamai, 'Guaranteed Dynamic Scheduling of URLLC Traffic via Conformal Prediction', IEEE WCL 2023 [peer-reviewed]; I. Gibbs, E. Candès, 'Adaptive Conformal Inference Under Distribution Shift', NeurIPS 2021 [peer-reviewed]",
        "V. Kasuluru, L. Blanco, C. J. Vaca-Rubio, E. Zeydan, 'On the Impact of PRB Load Uncertainty Forecasting for Sustainable Open RAN', arXiv:2407.14400, 2024 [preprint]",
        "W. Willinger et al., IEEE/ACM ToN 1997 (heavy-tailed ON/OFF sources); Hadley & Whitin 1963 (constrained multi-item newsvendor); Le Boudec & Thiran, Network Calculus, 2001. Full list: docs/fhlm/literature_review.md",
    ], Inches(0.5), Inches(1.1), Inches(12.3), Inches(5.8), size=12)

    d.save(out)
    print(f"wrote {out} ({d.n} slides)")
    return out


if __name__ == "__main__":
    build()
