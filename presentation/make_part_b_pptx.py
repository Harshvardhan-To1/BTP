"""Build the Part B slide deck: python presentation/make_part_b_pptx.py

Numbers are those of results/fhlm/main_summary.csv, transformer_summary.csv,
transformer_paired_*.csv, bayes_forecast_quality.csv and hybrid_bpn2*.json.
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "presentation" / "part_b_final.pptx"
FIG = ROOT / "results" / "fhlm" / "figures"

NAVY = RGBColor(0x0B, 0x2A, 0x4A)
ACCENT = RGBColor(0xD6, 0x3A, 0x2F)
GREEN = RGBColor(0x1E, 0x8E, 0x3E)
GREY = RGBColor(0x55, 0x55, 0x55)
LIGHT = RGBColor(0xEE, 0xF3, 0xF8)
SOFTGREEN = RGBColor(0xF4, 0xF8, 0xEC)
SOFTRED = RGBColor(0xFD, 0xEC, 0xEA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
FOOTER = "Fronthaul Load Management in O-RAN  |  Part B  |  M. Yadav & H. Choudhary"


def _text(slide, x, y, w, h, lines, size=18, color=NAVY, bold=False, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate([lines] if isinstance(lines, str) else lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.size, r.font.bold, r.font.color.rgb = Pt(size), bold, color
    return tb


def _bullets(slide, x, y, w, h, items, size=18):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        sub = item.startswith("  ")
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(5)
        r = p.add_run()
        r.text = ("–  " if sub else "•  ") + item.strip()
        r.font.size = Pt(size - 3 if sub else size)
        r.font.color.rgb = GREY if sub else NAVY
        if sub:
            p.level = 1
    return tb


def _box(slide, x, y, w, h, title, body, fill=LIGHT, edge=NAVY, size=15):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.color.rgb = edge
    s.line.width = Pt(1.5)
    s.adjustments[0] = 0.06
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = title
    r.font.size, r.font.bold, r.font.color.rgb = Pt(size + 2), True, edge
    for line in body:
        p = tf.add_paragraph()
        r = p.add_run()
        r.text = line
        r.font.size, r.font.color.rgb = Pt(size), NAVY
    return s


def _table(slide, x, y, w, rows, col_w=None, size=14, highlight_row=None, row_h=0.4, left=False):
    n_r, n_c = len(rows), len(rows[0])
    shape = slide.shapes.add_table(n_r, n_c, Inches(x), Inches(y), Inches(w), Inches(row_h * n_r))
    t = shape.table
    if col_w:
        for j, cw in enumerate(col_w):
            t.columns[j].width = Inches(cw)
    for i in range(n_r):
        t.rows[i].height = Inches(row_h)
    highlights = highlight_row if isinstance(highlight_row, (list, tuple)) else [highlight_row]
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.margin_top = c.margin_bottom = Inches(0.03)
            para = c.text_frame.paragraphs[0]
            para.alignment = PP_ALIGN.LEFT if (left or not j) else PP_ALIGN.CENTER
            run = para.add_run()
            run.text = str(val)
            f = run.font
            f.size = Pt(size)
            c.fill.solid()
            if i == 0:
                c.fill.fore_color.rgb = NAVY
                f.color.rgb, f.bold = WHITE, True
            elif i in highlights:
                c.fill.fore_color.rgb = RGBColor(0xDF, 0xF2, 0xE3)
                f.color.rgb, f.bold = GREEN, True
            else:
                c.fill.fore_color.rgb = WHITE if i % 2 else LIGHT
                f.color.rgb = NAVY
    return t


def _image(slide, name, x, y, w=None, h=None):
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    return slide.shapes.add_picture(str(FIG / name), Inches(x), Inches(y), **kw)


def fig_fit(s, name, x, y, max_w, max_h):
    from PIL import Image
    w, h = Image.open(FIG / name).size
    if max_w * h / w <= max_h:
        _image(s, name, x, y, w=max_w)
    else:
        width = max_h * w / h
        _image(s, name, x + (max_w - width) / 2, y, h=max_h)


def slide(title, subtitle=None, notes=None):
    s = prs.slides.add_slide(BLANK)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(1.05))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    _text(s, 0.5, 0.12, 12.3, 0.6, title, size=28, color=WHITE, bold=True)
    if subtitle:
        _text(s, 0.5, 0.62, 12.3, 0.4, subtitle, size=15, color=RGBColor(0xBF, 0xD4, 0xEA))
    accent = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(1.05), prs.slide_width, Inches(0.06))
    accent.fill.solid()
    accent.fill.fore_color.rgb = ACCENT
    accent.line.fill.background()
    _text(s, 0.5, 7.05, 10, 0.35, FOOTER, size=11, color=GREY)
    _text(s, 12.0, 7.05, 0.9, 0.35, str(len(prs.slides)), size=11, color=GREY, align=PP_ALIGN.RIGHT)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def takeaway(s, text, y=6.35):
    b = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(y), Inches(12.33), Inches(0.6))
    b.fill.solid()
    b.fill.fore_color.rgb = SOFTRED
    b.line.color.rgb = ACCENT
    tf = b.text_frame
    tf.word_wrap = True
    r = tf.paragraphs[0].add_run()
    r.text = text
    r.font.size, r.font.bold, r.font.color.rgb = Pt(18), True, ACCENT


def section(title, subtitle, notes=None):
    s = prs.slides.add_slide(BLANK)
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = NAVY
    bg.line.fill.background()
    _text(s, 0.8, 2.6, 11.7, 1.0, title, size=40, color=WHITE, bold=True)
    line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(3.75), Inches(3.0), Inches(0.08))
    line.fill.solid()
    line.fill.fore_color.rgb = ACCENT
    line.line.fill.background()
    _text(s, 0.8, 4.0, 11.7, 1.0, subtitle, size=22, color=RGBColor(0xBF, 0xD4, 0xEA))
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


# 1. Title
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid()
bg.fill.fore_color.rgb = NAVY
bg.line.fill.background()
_text(s, 0.8, 1.2, 11.7, 1.4, "Part B: Sharing One Fronthaul Link Well", size=40, color=WHITE, bold=True)
_text(s, 0.8, 2.6, 11.7, 1.4,
      ["Deadline-feasible, uncertainty-aware budget allocation across O-RAN 7-2x cells:",
       "the KKT newsvendor rule, a Bayesian Transformer forecaster, and the back-pressure newsvendor"],
      size=22, color=RGBColor(0xBF, 0xD4, 0xEA))
line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(4.2), Inches(3.0), Inches(0.08))
line.fill.solid()
line.fill.fore_color.rgb = ACCENT
line.line.fill.background()
_text(s, 0.8, 4.5, 11.7, 1.2, ["Mayank Yadav    Harshvardhan Choudhary", "B.Tech. Project — Final Evaluation, November 2026"],
      size=20, color=WHITE)
s.notes_slide.notes_text_frame.text = (
    "Part B is about sharing one fronthaul link between several cells. Part A made the data smaller; "
    "Part B decides who may send how much when the link is too small for everyone's peak.")

# 2. Roadmap
s = slide("Part B at a glance", "Three steps, each building on the previous one",
          notes="Give the audience the map. B1 is the main method and the NCC paper. The extended study found two "
                "stronger controllers. B2 tried a better forecaster (Transformer) and showed the gap is structural. "
                "B3 changed the decision structure and now beats both strongest baselines in all 10 scenarios.")
cards = [
    ("B1  KKT newsvendor rule", ["Forecast r* as a range (GBM)", "Split the link at equal weighted risk",
                                 "Best of 12 controllers, 2 families", "NCC 2027 submission"], LIGHT, NAVY),
    ("Extended study", ["MDP view + Markov-fluid theory", "3rd traffic family (Markov)",
                        "CEM policy & predictive MaxWeight", "beat the KKT rule in 9/10"], SOFTRED, ACCENT),
    ("B2  Bayesian Transformer", ["LCQT: patch + cross-cell attention", "Bayesian mixture, differentiable KKT",
                                  "Best KKT variant, small gain", "→ the gap is structural"], LIGHT, NAVY),
    ("B3  Back-pressure newsvendor", ["Back-pressure base + KKT margins", "Contains both strongest baselines",
                                      "Beats them in 10/10 scenarios", "of 3 traffic families"], SOFTGREEN, GREEN),
]
for i, (t, b, fill, edge) in enumerate(cards):
    _box(s, 0.5 + i * 3.1, 1.5, 2.95, 3.9, t, b, fill=fill, edge=edge, size=15)
takeaway(s, "Keep the structure, learn only what is uncertain — then fix the structure where it is wrong.", y=5.8)

# 3. Problem
s = slide("The problem: one link, eight cells, decide in advance",
          notes="8 cells share one 25GE link. Their total peak is 2.44 times the link on purpose (statistical "
                "multiplexing). Every 10 ms a coordinator sets per-cell budgets held for the interval, on telemetry "
                "that is 1 ms old. Why not every slot: near-RT RIC/E2 loops are at least 10 ms, switch shaping is not "
                "reconfigured per slot, and DU schedulers cannot consult each other within a slot.")
_bullets(s, 0.5, 1.4, 7.0, 4.6, [
    "8 cells: 3 low-latency (LL, deadline 2 ms, weight 3) + 5 eMBB (10 ms, weight 1)",
    "One 25GE link, 3 % for control → C = 12.125 Mbit per 0.5 ms slot",
    "Aggregate cell peak = 2.44 × C (statistical multiplexing)",
    "Every T = 10 ms: per-cell budgets r_i, held for the interval",
    "Telemetry is τ = 1 ms old; the future is never seen",
    "Bits waiting longer than their deadline are dropped = violations",
], size=18)
_box(s, 7.8, 1.4, 5.0, 3.1, "Why decide in advance?",
     ["• Near-RT RIC / E2 loop ≥ 10 ms",
      "• Switch shaping not changed per slot",
      "• DU schedulers cannot coordinate",
      "  inside the sub-ms pipeline",
      "⇒ commit for T + τ without seeing traffic"], size=16)
_box(s, 7.8, 4.7, 5.0, 1.4, "Question",
     ["Given a forecast range of each cell's need,", "how should the link be split?"],
     fill=SOFTRED, edge=ACCENT, size=16)
takeaway(s, "Someone must lose data when bursts coincide; the controller decides who.")

# 4. System model
s = slide("System model", "Fronthaul load follows scheduled resource blocks, not user bits",
          notes="beta is the cost of one PRB-layer per slot. It is where Part A enters: the BFP mantissa width b. "
                "With BFP-9 it is 3387 bits. Demand of a cell = user bits / spectral efficiency x beta. The link never "
                "queues because budgets add up to at most C; congestion shows up as DU queueing and drops. The score "
                "V_w was fixed before any tuning.")
_box(s, 0.5, 1.4, 6.1, 2.2, "Cost of one PRB-layer per slot (Part A enters here)",
     ["β(b) = (12·2·b + 8) · 14 · 1.08",
      "β(9) = 3,387 bits;  BFP-6: 0.68×,  BFP-12: 1.32×,  BFP-14: 1.54×",
      "Cell peak = 273 PRBs × 4 layers × β ≈ 7.4 Gbit/s"], size=15)
_box(s, 0.5, 3.8, 6.1, 2.2, "Fronthaul demand and decision",
     ["d_i(t) = ⌈a_i(t) / η_i(t)⌉ · β   (user bits ÷ spectral eff.)",
      "Σ_i r_i ≤ C,   0 ≤ r_i ≤ cap_i",
      "FIFO DU queue per cell; drop after D_i slots"], size=15)
_box(s, 6.83, 1.4, 6.0, 4.6, "Primary metric (fixed before tuning)",
     ["Priority-weighted violation ratio",
      "",
      "V_w = Σ w_i · violated_i / Σ w_i · arrived_i",
      "    = (3·LL dropped + eMBB dropped)",
      "       / (3·LL arrived + eMBB arrived)",
      "",
      "Lower is better.",
      "Also reported: per-class violations, unweighted ratio,",
      "utilisation, delay, Jain fairness, decision time."],
     fill=SOFTGREEN, edge=GREEN, size=15)
takeaway(s, "Two cells with the same user traffic can differ 2–3× in fronthaul load.")

section("B1: The KKT Newsvendor Rule", "Forecast the right quantity, as a range, and split at equal risk",
        notes="Section 1: the main method of the NCC paper.")

# 6. r*
s = slide("Key idea 1: forecast the deadline-feasible rate r*",
          notes="r* is the smallest constant rate at which no bit misses its deadline. Long deadline: close to the "
                "mean. Short deadline: close to the peak burst rate. Example: one burst of 8 units, average 1. With "
                "D = 1 slot, r* = 8/2 = 4. With D = 7, r* = 8/8 = 1. For the 2 ms cells r* is often 2-3x the mean and "
                "skewed, which is why one predicted number is a poor basis for a reservation.")
_box(s, 0.5, 1.4, 12.3, 1.3, "Smallest constant rate at which no bit misses its deadline",
     ["r*(a, D) = max over windows [s, e] of  Σ_{t=s..e} a_t  /  (e − s + 1 + D)      (network-calculus service curve; tight in tests)"],
     size=16)
_bullets(s, 0.5, 2.9, 6.3, 3.3, [
    "Long deadline → r* ≈ mean rate",
    "Short deadline → r* ≈ peak burst rate",
    "Example: burst of 8, mean 1",
    "  D = 1 slot → r* = 4;  D = 7 slots → r* = 1",
    "2 ms class: r* is 2–3× the mean and right-skewed",
], size=18)
_box(s, 7.0, 2.9, 5.8, 3.2, "Demand of every deadline-aware controller",
     ["need_i = B_i + r*_i",
      "B_i = backlog_i / slack_i  (what is already queued)",
      "r*_i = what has not arrived yet",
      "",
      "Controllers differ only in how they",
      "estimate r*_i and split a shortage."], fill=SOFTGREEN, edge=GREEN, size=15)
takeaway(s, "A single number is a poor basis for reserving a skewed quantity ⇒ forecast a range.")

# 7. Forecaster
s = slide("Key idea 2: a quantile forecaster", "Six gradient-boosted tree models, one per quantile level",
          notes="Target: r* of the coming horizon normalised by the cell peak. 28 features from the past only. One "
                "HistGradientBoosting quantile model per level 5/25/50/75/90/95 %, 300 trees, 15 leaves, 12 s on a CPU. "
                "Seeds are disjoint: train 1000-1015, validation 2000-2003, test 3000-3019. Calibration within a point.")
_bullets(s, 0.5, 1.4, 6.6, 4.6, [
    "Target: y_i = r*(next horizon) / cell peak",
    "28 features, past only: horizon means, EWMAs, last 4 slots, r* of last 3 horizons, spectral eff., D/H, cell id",
    "6 models (α = 5/25/50/75/90/95 %), 300 trees, 15 leaves",
    "101k rows, 12 s training on CPU",
    "Seeds: train 1000–1015, val 2000–2003, test 3000–3019",
], size=17)
_table(s, 7.3, 1.45, 5.5, [
    ["Validation", "GBM", "Baseline"],
    ["Coverage at 5 / 50 / 95 %", "5.6 / 50.7 / 94.9", "—"],
    ["Median rel. error", "37 %", "52 % (persist.)"],
    ["Pinball loss", "0.0224", "0.0293 (window)"],
], col_w=[2.4, 1.6, 1.5], size=13)
fig_fit(s, "fig5_forecast_quality.png", 7.3, 3.3, 5.5, 2.9)
takeaway(s, "Well calibrated, cheap and CPU-only.")

# 8. KKT rule
s = slide("Key idea 3: the KKT (constrained newsvendor) rule",
          notes="Maximise the expected weighted served need under the forecast. It is separable and concave, so the "
                "KKT conditions give the global optimum in closed form. One number lambda (a price of capacity) is "
                "found by bisection so budgets sum to C. Toy: lambda = 0.6, LL cell funded to its 80 % quantile "
                "(1 - 0.6/3), eMBB to its 40 % quantile. Say: every cell is cut at the same weighted risk; margins are "
                "derived, not tuned.")
_box(s, 0.5, 1.4, 12.3, 1.5, "Objective for one interval (forecast distribution F_i of r*_i)",
     ["max_r  Σ_i w_i · E[ min(B_i + r*_i, r_i) ]    s.t.  Σ_i r_i ≤ C,  0 ≤ r_i ≤ cap_i",
      "Concave; slope = w_i · P(the next bit of budget is needed)"], size=16)
_box(s, 0.5, 3.1, 6.1, 2.9, "Closed-form solution",
     ["r_i(λ) = clip( B_i + F_i⁻¹(1 − λ / w_i), 0, cap_i )",
      "",
      "• one price λ for all cells, 60-step bisection",
      "• λ = 0 if the link is not full",
      "• tens of μs for 8 cells"], fill=SOFTGREEN, edge=GREEN, size=15)
_box(s, 6.83, 3.1, 6.0, 2.9, "Toy example (C = 10, λ = 0.6)",
     ["LL (w = 3): level 1 − 0.6/3 = 0.8 → 80 % quantile",
      "eMBB (w = 1): level 1 − 0.6 = 0.4 → 40 % quantile",
      "",
      "Wide forecast or high priority → more margin;",
      "confident forecast → about its median."], size=15)
takeaway(s, "Every cell is cut at the same weighted risk: margins are derived, not tuned.")

# 9. Properties and loop
s = slide("Properties and the control loop",
          notes="Four propositions, all for one interval: feasibility, equal weighted tail probability, backlog first, "
                "and a linear miscalibration bound. No closed-loop optimality or stability claim. Walk the loop left to "
                "right.")
_table(s, 0.5, 1.4, 12.3, [
    ["Proposition", "In plain words"],
    ["1  Feasibility", "Whatever the forecast, budgets fit the caps and Σ r_i ≤ C: the link is never overloaded"],
    ["2  Equal weighted risk", "w_i (1 − F_i(r_i − B_i)) = λ for every cell; a point forecast reduces it to a priority fill"],
    ["3  Backlog first", "Queued bits are funded before uncertain demand of equal or lower weight"],
    ["4  Miscalibration", "Forecast off by ε (Kolmogorov) ⇒ loss ≤ 2 ε w_max C: linear, so it degrades gently"],
], col_w=[3.0, 9.3], size=14, left=True)
_text(s, 0.5, 3.7, 12.3, 0.4, "Control loop (every 10 ms)", size=18, bold=True)
steps = ["Delayed state\n(1 ms old)", "28 features\nper cell", "6 GBM quantiles\nof r*", "KKT rule\nbisection on λ",
         "Budgets r_i\nheld 10 ms", "DU queues,\ndrops after D"]
for i, t in enumerate(steps):
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.5 + i * 2.1), Inches(4.25), Inches(1.85), Inches(1.0))
    b.fill.solid()
    b.fill.fore_color.rgb = SOFTGREEN if i == 3 else LIGHT
    b.line.color.rgb = GREEN if i == 3 else NAVY
    tf = b.text_frame
    tf.word_wrap = True
    for k, ln in enumerate(t.split("\n")):
        p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = ln
        r.font.size, r.font.color.rgb, r.font.bold = Pt(13), NAVY, k == 0
    if i < len(steps) - 1:
        a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(2.37 + i * 2.1), Inches(4.6), Inches(0.21), Inches(0.3))
        a.fill.solid()
        a.fill.fore_color.rgb = ACCENT
        a.line.fill.background()
takeaway(s, "Properties of one interval — no closed-loop optimality claim.", y=5.6)

# 10. Controllers and protocol
s = slide("Baselines and evaluation protocol", "All baselines tuned on validation seeds; identical traces for every controller",
          notes="The point forecast is the key ablation: same model, one number. The fixed global quantile checks that "
                "'just use a quantile' is not the trick. Margin 0 was best for every baseline. Family S is bursty "
                "synthetic with a held-out shift; Family G is built only from 3GPP models. 20 test seeds, paired "
                "bootstrap and Holm-corrected Wilcoxon tests.")
_table(s, 0.5, 1.4, 7.4, [
    ["Controller", "Estimate of r*", "Split"],
    ["Static equal", "none", "C / N"],
    ["Reactive proportional", "EWMA, no deadlines", "proportional"],
    ["MaxWeight", "priority × queue", "max-weight"],
    ["Deadline-aware reactive", "last observed r*", "water-fill"],
    ["Point forecast", "GBM median", "water-fill"],
    ["Fixed global quantile", "GBM, level 0.75", "water-fill"],
    ["Proposed (window)", "last 30 intervals, no ML", "KKT"],
    ["Proposed", "GBM quantiles", "KKT"],
    ["Oracle / Oracle + KKT", "true r*", "WF / KKT"],
], col_w=[2.6, 2.8, 2.0], size=12, highlight_row=8, row_h=0.37)
_box(s, 8.1, 1.4, 4.7, 2.3, "Family S (synthetic, bursty)",
     ["Gamma + Pareto ON/OFF bursts", "low 0.50, moderate 0.65, high 0.80,",
      "flash crowds, held-out shift"], size=14)
_box(s, 8.1, 3.85, 4.7, 2.3, "Family G (3GPP only)",
     ["TR 38.901 UMa, TS 38.214 CQI", "FTP Model 3 (eMBB), XR video (LL)",
      "Demand = PRB scheduler output"], fill=SOFTGREEN, edge=GREEN, size=14)
takeaway(s, "20 test seeds × 10 s, paired bootstrap CIs, Holm-corrected Wilcoxon tests.")

# 11. Main result
s = slide("B1 result, Family S: V_w [%] (mean of 20 test seeds)",
          notes="The proposed rule is the best implementable controller in all five scenarios. The std across seeds is "
                "mostly shared burst timing, so read the paired comparison. Against the point forecast: -11 to -43 %, "
                "every seed. Weak spot: only -4 % against reactive proportional under flash crowds (16/20, p = 0.03).")
_table(s, 0.5, 1.35, 8.1, [
    ["Method", "low", "mod.", "high", "flash", "shift"],
    ["Static equal", "4.45", "9.65", "15.46", "19.15", "22.31"],
    ["Reactive proportional", "0.83", "4.11", "9.20", "12.27", "11.70"],
    ["MaxWeight", "0.90", "4.85", "11.54", "15.24", "12.31"],
    ["Deadline-aware reactive", "0.52", "4.24", "11.03", "14.51", "12.56"],
    ["Point forecast", "0.27", "3.23", "9.70", "13.33", "11.30"],
    ["Fixed global quantile", "0.34", "4.35", "11.76", "15.09", "12.85"],
    ["Window quantiles (no ML)", "0.25", "2.57", "8.72", "12.67", "10.22"],
    ["Proposed (GBM + KKT)", "0.15", "2.15", "8.00", "11.76", "10.04"],
    ["Oracle water-fill", "0.07", "1.62", "6.89", "10.16", "6.69"],
], col_w=[3.1, 1.0, 1.0, 1.0, 1.0, 1.0], size=13, highlight_row=8, row_h=0.4)
_box(s, 8.8, 1.35, 4.0, 4.6, "Paired vs proposed",
     ["vs point forecast: −11 to −43 %", "vs fixed quantile: −22 to −54 %",
      "vs deadline-aware: −19 to −70 %", "vs MaxWeight: −18 to −83 %",
      "all 20/20 seeds, p < 0.01", "",
      "Weak: vs reactive prop. under", "flash crowds only −4 %", "(16/20, p = 0.03)"],
     fill=SOFTGREEN, edge=GREEN, size=14)
takeaway(s, "Best implementable controller in all five scenarios.")

# 12. Where the gain comes from
s = slide("Where the gain comes from (scenario high)",
          notes="Deadline-unaware controllers sacrifice the LL cells. Every deadline-aware controller protects LL and "
                "pays with eMBB. Among them the proposed rule loses the least eMBB and uses the link most, because it "
                "adds margin only where the forecast is wide. One global level wastes a third of the allocation.")
fig_fit(s, "fig2_class_breakdown_high.png", 0.5, 1.35, 12.3, 3.6)
_bullets(s, 0.5, 5.0, 12.3, 1.3, [
    "Unaware controllers starve LL (14.7 %, 20.6 %); aware ones pay with eMBB",
    "Proposed: lowest eMBB loss (12.3 %) and highest utilisation (72.2 %) in the deadline-aware family",
], size=16)
takeaway(s, "Margin only where the forecast is wide.", y=6.4)

# 13. Ablations
s = slide("Ablations: what carries the gain?",
          notes="Range vs number matters; the per-cell level matters; ML helps on nominal traffic but only 2 % under "
                "shift, so most of the gain is the rule. Online ACI calibration hurt, because in a coupled split LL "
                "misses are caused by the shortage split, not by forecast bias.")
_table(s, 0.5, 1.4, 12.3, [
    ["Ablation (same everything else)", "Effect of the proposed choice", "Reading"],
    ["Range vs single number (median)", "−11 % to −43 %, 20/20 seeds", "Representing uncertainty matters"],
    ["Per-cell KKT level vs one global level", "−22 % to −54 %", "Level must be set per cell by the link"],
    ["GBM vs window quantiles (no ML)", "−7 % to −37 %; only −2 % under shift", "Most of the gain is the rule"],
    ["Online ACI calibration on/off", "1–9 % worse; 10 % worse under shift", "Per-stream correction does not transfer"],
], col_w=[4.0, 4.3, 4.0], size=14, row_h=0.55, left=True)
_box(s, 0.5, 4.4, 12.3, 1.6, "Family G (3GPP) reproduces it",
     ["High load: 8.01 % — −11 % vs point forecast, −31 % vs deadline-aware, −50 % vs reactive prop., 20/20 seeds;",
      "also best under the unweighted ratio. Oracle + KKT gap: 24–40 % of the remaining loss at high load is forecast error."],
     fill=SOFTGREEN, edge=GREEN, size=15)
takeaway(s, "ML is useful, not necessary: the r* target and the KKT split do most of the work.")

# 14. Caveats
s = slide("Honest caveats and operating regime",
          notes="Say these before you are asked. The gain is a priority trade: with every bit equal, proportional loses "
                "fewer bits in Family S. The rule wins for intervals up to a few times the shortest deadline and fresh "
                "telemetry. Compression sets the load regime; allocation matters between 0.5 and 0.8 load.")
_table(s, 0.5, 1.4, 6.4, [
    ["LL weight (S high)", "1", "2", "3", "5"],
    ["Reactive prop.", "6.55", "8.13", "9.20", "10.56"],
    ["Proposed", "6.58", "8.35", "8.00", "6.93"],
], col_w=[2.4, 1.0, 1.0, 1.0, 1.0], size=14, highlight_row=None)
_table(s, 0.5, 3.0, 6.4, [
    ["Interval T", "2 ms", "5 ms", "10 ms", "20 ms"],
    ["Reactive prop.", "3.91", "7.42", "8.91", "11.80"],
    ["Proposed", "3.07", "5.07", "7.71", "13.15"],
], col_w=[2.4, 1.0, 1.0, 1.0, 1.0], size=14)
_text(s, 0.5, 4.3, 6.4, 1.8,
      ["• Needs an LL weight ≥ 2–3 (priority trade)",
       "• Loses at T = 20 ms; near tie at τ = 5 ms",
       "• Sweeps use 10 seeds (hence 7.71 vs 8.00)"], size=15)
fig_fit(s, "fig9_compression_vs_allocation.png", 7.1, 1.4, 5.7, 3.3)
_text(s, 7.1, 4.8, 5.7, 1.3,
      ["Part A × B: BFP 6/9/12/14 bits → load 0.44/0.65/0.86/0.99.",
       "Allocation matters at 0.5–0.8; at ≈ 1.0 nothing helps."], size=15)
takeaway(s, "Compression sets the regime; allocation decides the loss inside it.")

section("Extended Study", "Theory, a third traffic family, and stronger controllers",
        notes="This was added after the NCC submission for the 11-page manuscript.")

# 16. Extended study
s = slide("Extended study: stronger controllers exist",
          notes="The real problem is an intractable POMDP. Three approximation families were implemented: one-step "
                "stochastic programs (our KKT rule), Lyapunov drift (predictive MaxWeight), and direct policy search "
                "(CEM). Theory: r* linked to effective bandwidth; bounds valid but 25-100x conservative, which argues "
                "for learning. Result: the KKT rule wins the NCC comparison set, but CEM and predictive MaxWeight beat "
                "it in 9/10 scenarios.")
_bullets(s, 0.5, 1.35, 5.4, 4.8, [
    "Real problem: a POMDP — intractable",
    "Three approximation families:",
    "  one-step stochastic program (KKT rule)",
    "  Lyapunov drift: predictive MaxWeight",
    "  policy search: CEM, 3 parameters",
    "Family M: Markov-modulated traffic",
    "Theory: r* linked to effective bandwidth;",
    "  bounds valid but 25–100× loose",
], size=17)
_table(s, 6.1, 1.35, 6.7, [
    ["V_w [%]", "KKT (GBM)", "Pred. MW", "CEM"],
    ["S moderate", "2.15", "1.62", "1.77"],
    ["S high", "8.00", "6.15", "6.57"],
    ["S flash", "11.76", "9.69", "10.20"],
    ["G high", "8.01", "11.36", "7.17"],
    ["M high", "4.94", "4.79", "3.93"],
    ["M shift", "5.52", "4.80", "4.17"],
], col_w=[2.2, 1.5, 1.5, 1.5], size=14)
_text(s, 6.1, 4.4, 6.7, 1.7,
      ["λ diagnostic: link full ~100 % of intervals; λ* ≥ w_eMBB in 50–58 %",
       "→ eMBB already at its lowest quantile; re-tuning the weight gains 1–4 %"], size=15)
takeaway(s, "CEM best in 6/10, predictive MaxWeight in 3/10: the gap is structural, not a constant.")

section("B2: A Bayesian Transformer Forecaster",
        "Can a better forecaster close the gap? (Family S)",
        notes="Part B2 asks whether the gap to CEM and predictive MaxWeight is forecast error. Answer: mostly not.")

# 18. LCQT architecture
s = slide("LCQT: link-aware cross-cell quantile Transformer", "A drop-in replacement for the GBM forecaster",
          notes="Built on PatchTST (patches), iTransformer (attention across variates), TFT (multi-quantile output), "
                "MC dropout and deep ensembles, and decision-focused learning. Our modifications: deadline-aware patch "
                "tokens carrying r* of each patch; FiLM on deadline and priority so one network serves both classes; "
                "cross-cell attention over the 8 cells sharing the link; non-crossing quantile head; a Bayesian "
                "mixture layer; and a differentiable KKT layer. Each block is prior art; we found no paper combining "
                "them. 63k parameters, about 6 minutes of CPU training.")
steps = [("Patch tokens", "16 patches × 22 slots\n+ r*, mean, max"), ("Temporal encoder", "2 layers, d = 48,\n4 heads"),
         ("FiLM", "deadline D/H,\npriority p"), ("Cross-cell attn.", "over the 8 cells\non the link"),
         ("Non-crossing head", "6 quantiles\nq_k = q_k−1 + softplus"), ("Bayesian mixture", "3 seeds × 8 dropout\n→ mixture F̂_i")]
for i, (t, b) in enumerate(steps):
    hot = i in (3, 5)
    _box(s, 0.5 + i * 2.08, 1.45, 1.92, 1.9, t, b.split("\n"),
         fill=SOFTRED if hot else LIGHT, edge=ACCENT if hot else NAVY, size=12)
_box(s, 0.5, 3.6, 6.1, 2.5, "Differentiable KKT layer (DF-LCQT)",
     ["Forward: bisection for λ*;  backward: implicit gradient",
      "∂λ*/∂q = − (∂g/∂q) / (∂g/∂λ),  g = Σ r_i − C",
      "Loss = Σ p_i (D_i+1)(B_i + r*_i − r_i)⁺ + β · pinball",
      "Contexts logged closed-loop, one DAgger round"], size=14)
_table(s, 6.83, 3.6, 6.0, [
    ["", "LCQT"],
    ["Parameters", "63 k (44 k without cross-cell)"],
    ["Training", "40 epochs, early stop on validation"],
    ["Time", "≈ 6 min, 4-core CPU"],
    ["Data", "same seeds and target as GBM"],
], col_w=[1.6, 4.4], size=14)
takeaway(s, "Each block is prior art; we found no paper that combines them for a shared link.")

# 19. Forecast quality
s = slide("B2 forecast quality", "Same validation rows for every model; shift = held-out test (out of distribution)",
          notes="The Transformer cuts pinball loss by 4.5 % and the 90 % interval width by 8 % at higher coverage than "
                "GBM. Cross-cell layer and priority weighting do not improve the forecast. The Bayesian layer moves "
                "coverage towards nominal under shift but cannot remove under-coverage there. DF-LCQT gives up "
                "accuracy on purpose.")
_table(s, 0.5, 1.4, 12.3, [
    ["Model", "Pinball", "Pinball LL", "90 % cov.", "90 % width", "Shift 90 % cov.", "Shift LL q95 cov."],
    ["GBM (B1)", "0.0224", "0.0259", "0.894", "1.51", "—", "—"],
    ["LCQT", "0.0214", "0.0251", "0.902", "1.36", "0.795", "0.855"],
    ["LCQT + MC dropout (16)", "0.0214", "0.0251", "0.911", "1.41", "0.802", "0.870"],
    ["Deep ensemble (3)", "0.0212", "0.0248", "0.912", "1.37", "0.806", "0.864"],
    ["Ensemble × MC (3×8)", "0.0213", "0.0249", "0.919", "1.40", "0.808", "0.873"],
    ["DF-LCQT (decision-focused)", "0.0224", "0.0273", "0.907", "1.38", "0.830", "0.822"],
], col_w=[3.3, 1.4, 1.5, 1.4, 1.5, 1.6, 1.6], size=13, highlight_row=5)
_bullets(s, 0.5, 4.45, 12.3, 1.8, [
    "Transformer: pinball −4.5 %, 90 % interval −8 % at higher coverage than GBM",
    "Cross-cell layer and priority-weighted loss: no forecast gain (equal within noise)",
    "Bayesian layer improves calibration under shift (LL q95: 0.855 → 0.873) but cannot remove under-coverage",
], size=16)
takeaway(s, "A better forecast — but only modestly better.", y=6.4)

# 20. Closed loop
s = slide("B2 closed loop: V_w [%] on Family S (20 test seeds)",
          notes="The Bayesian LCQT is the best KKT-rule variant and improves the proposed method on every seed at low to "
                "high load (-20.8 / -6.1 / -1.4 %). Flash and shift are not significant. The gains are small at high "
                "load, while CEM and predictive MaxWeight are still 14-28 % better: the gap is structural.")
_table(s, 0.5, 1.35, 7.6, [
    ["Controller", "low", "mod.", "high", "flash", "shift"],
    ["GBM + KKT (B1)", "0.15", "2.15", "8.00", "11.76", "10.04"],
    ["LCQT median + water-fill", "0.25", "3.14", "9.76", "13.47", "11.51"],
    ["LCQT + KKT", "0.13", "2.05", "7.91", "11.81", "10.06"],
    ["Bayesian LCQT + KKT", "0.12", "2.02", "7.89", "11.78", "10.02"],
    ["DF-LCQT + KKT", "0.18", "2.26", "7.93", "11.62", "10.15"],
    ["CEM policy", "0.13", "1.77", "6.57", "10.20", "9.73"],
    ["Predictive MaxWeight", "0.14", "1.62", "6.15", "9.69", "10.25"],
    ["Oracle + KKT", "0.05", "0.88", "4.77", "8.10", "5.84"],
], col_w=[2.9, 0.94, 0.94, 0.94, 0.94, 0.94], size=13, highlight_row=4, row_h=0.4)
_table(s, 8.3, 1.35, 4.5, [
    ["Bayesian vs GBM", "Change", "Wins"],
    ["low", "−20.8 %", "20/20"],
    ["moderate", "−6.1 %", "20/20"],
    ["high", "−1.4 %", "20/20"],
    ["flash", "+0.2 % (n.s.)", "9/20"],
    ["shift", "−0.2 % (n.s.)", "14/20"],
], col_w=[1.6, 1.7, 1.2], size=13)
_text(s, 8.3, 4.0, 4.5, 2.2,
      ["• Patch Transformer: the main gain",
       "• Bayesian mixture: small, consistent",
       "• Cross-cell, priority loss: no gain",
       "• DF-LCQT: −1.2 % flash, +14 % low"], size=15)
takeaway(s, "Best KKT variant, but CEM / predictive MaxWeight stay 14–28 % better: the gap is structural.")

# 21. B2 assessment
s = slide("B2: honest assessment",
          notes="What improved: every seed at low to high load, best calibration under shift, cheaper per decision than "
                "GBM (2.7 vs 3.5 ms) without the Bayesian layer, and a working, unit-tested differentiable KKT layer. "
                "What did not: small gains at high load, the decision-focused validation gain did not transfer, the "
                "Bayesian layer costs 17-21 ms in Python, and only Family S was run. Next step: keep the forecaster, "
                "change the decision structure — that is B3.")
_box(s, 0.5, 1.4, 6.0, 4.7, "What improved",
     ["• Bayesian LCQT beats GBM + KKT on every seed",
      "  at low–high load; never loses significantly",
      "• Best calibration under shift",
      "• LCQT alone is cheaper per decision",
      "  than GBM (2.7 vs 3.5 ms)",
      "• Differentiable KKT layer works and is",
      "  unit-tested (matches numpy to 1e-6)"], fill=SOFTGREEN, edge=GREEN, size=15)
_box(s, 6.83, 1.4, 6.0, 4.7, "What did not",
     ["• Gains small at high load (−1.4 %)",
      "• Decision-focused gain on validation did not",
      "  transfer to test at low/moderate load",
      "• Bayesian layer: 17–21 ms in Python",
      "  (> the 10 ms interval) — needs compiling",
      "• Family S only"], fill=SOFTRED, edge=ACCENT, size=15)
takeaway(s, "Next: keep the forecaster, change the decision structure (B3).")

section("B3: The Back-Pressure Newsvendor", "One policy class that contains both strongest baselines",
        notes="Part B3 changes the decision rule, not the forecaster.")

# 23. Why KKT loses
s = slide("Why the KKT rule loses to back-pressure (S high)",
          notes="A budget is a per-cell cap. Capacity reserved for a 2 ms cell's upper quantile and not used is lost. "
                "The KKT rule over-protects LL (3.4 %), starves eMBB (12.3 %) and uses the link least (72.2 %). "
                "Back-pressure fills in queue order with median demands and wastes less, but ignores deadlines and "
                "uncertainty. Idea: fill the base in back-pressure order, then spend the leftover on newsvendor margins.")
_table(s, 0.5, 1.4, 8.0, [
    ["Controller", "V_w", "LL viol.", "eMBB viol.", "Util."],
    ["KKT rule (GBM)", "8.00", "3.4", "12.3", "72.2"],
    ["CEM class-level", "6.57", "6.0", "7.1", "74.7"],
    ["Pred. MaxWeight (CEM-tuned)", "5.98", "6.0", "5.9", "75.5"],
    ["BPN v1", "5.23", "5.5", "4.9", "76.1"],
    ["BPN v2", "5.32", "5.8", "4.8", "76.1"],
    ["Oracle + KKT", "4.77", "0.1", "9.2", "74.8"],
], col_w=[3.4, 1.15, 1.15, 1.15, 1.15], size=14, highlight_row=[4, 5])
_box(s, 8.8, 1.4, 4.0, 4.6, "Diagnosis",
     ["A budget is a per-cell cap:", "reserved-but-unused capacity", "is lost.", "",
      "KKT over-protects LL and", "starves eMBB.", "",
      "Back-pressure wastes less but", "ignores deadlines and", "uncertainty."],
     fill=SOFTRED, edge=ACCENT, size=15)
takeaway(s, "Idea: fill the base in back-pressure order, then spend the leftover on newsvendor margins.")

# 24. BPN design
s = slide("BPN: back-pressure base + KKT margins", "8 parameters, learned by CEM on training seeds only",
          notes="Stage 1: base demand mixes MaxWeight's drain rate with the deadline-aware backlog rate (a), plus a "
                "class base quantile. Shortage shared by a pressure score raised to eta: eta = 0 is class-weighted "
                "water-fill (reservation), large eta is strict back-pressure order. Stage 2: leftover capacity by the "
                "KKT rule. With the right parameters it becomes exactly predictive MaxWeight or the CEM class-level "
                "policy (unit-tested). Equal search effort for the baselines. The learned eta recovers the regime map.")
_box(s, 0.5, 1.4, 7.0, 2.4, "Stage 1 — base, in back-pressure order",
     ["b_i = a · Q_i/T + (1 − a) · B_i      (drain rate vs deadline backlog)",
      "d_i = b_i + (1 + μ) · F̂_i⁻¹(p⁰_class)",
      "Shortage ∝ v_class · (π_i / π̄)^η,  π_i = Q_i + ℓ·H·median_i",
      "η = 0: class-weighted water-fill;  η = η_max: strict back-pressure"], size=14)
_box(s, 0.5, 3.95, 7.0, 1.3, "Stage 2 — leftover by the KKT rule",
     ["r_i = max( r_i⁽¹⁾,  b_i + F̂_i⁻¹(1 − λ/ω_class) ),   Σ r_i = C"], fill=SOFTGREEN, edge=GREEN, size=14)
_text(s, 0.5, 5.35, 7.0, 0.9,
      ["Contains predictive MaxWeight and the CEM class-level policy exactly (unit-tested).",
       "Baselines re-tuned with the same CEM search: equal tuning effort."], size=14)
_table(s, 7.8, 1.4, 5.0, [
    ["Learned", "η", "a", "(p⁰_LL, p⁰_eMBB)"],
    ["S (bursty)", "6 (greedy)", "0.98", "(0.41, 0.45)"],
    ["G (3GPP)", "0", "0.31", "(0.94, 0.73)"],
    ["M (Markov)", "0", "0.34", "(0.84, 0.31)"],
], col_w=[1.3, 1.2, 0.8, 1.7], size=13)
_box(s, 7.8, 3.2, 5.0, 2.0, "The search recovers the regime map",
     ["Short bursts (S) → back-pressure", "Long bursts (FTP files, XR frames) → reservation"],
     fill=SOFTGREEN, edge=GREEN, size=14)
takeaway(s, "One policy class, both strongest baselines inside it: the search can only match or beat them.")

# 25. BPN results S
s = slide("B3 result, Family S: V_w [%] (20 test seeds)",
          notes="With the same forecaster, BPN beats both strongest baselines in every scenario. At high load it is "
                "within 6-10 % of the oracle-informed KKT rule. The Transformer from B2 now pays off more. Note: on "
                "Family S, BPN v1 is slightly better than v2 at high load (5.23 vs 5.32); v2 is the version that also "
                "works on Family G.")
_table(s, 0.5, 1.35, 12.3, [
    ["Forecaster", "Controller", "low", "moderate", "high", "flash", "shift"],
    ["GBM", "KKT rule (B1)", "0.15", "2.15", "8.00", "11.76", "10.04"],
    ["GBM", "Pred. MaxWeight (CEM-tuned)", "0.16", "1.66", "5.98", "9.36", "10.46"],
    ["GBM", "CEM class-level (re-searched)", "0.13", "1.73", "6.58", "10.23", "9.76"],
    ["GBM", "BPN v1 (6 param.)", "0.10", "1.21", "5.23", "8.58", "9.23"],
    ["GBM", "BPN v2 (8 param.)", "0.10", "1.21", "5.32", "8.70", "9.26"],
    ["LCQT", "BPN v2", "0.08", "1.16", "5.25", "8.59", "9.24"],
    ["Bayesian LCQT", "BPN v1", "0.08", "1.11", "5.05", "8.34", "8.92"],
    ["Bayesian LCQT", "BPN v2", "0.07", "1.12", "5.21", "8.55", "9.12"],
    ["—", "Oracle + KKT (true r*)", "0.05", "0.88", "4.77", "8.10", "5.84"],
], col_w=[2.2, 3.6, 1.3, 1.3, 1.3, 1.3, 1.3], size=13, highlight_row=8, row_h=0.4)
takeaway(s, "Same forecaster: BPN beats both baselines everywhere; within 6–10 % of the oracle at high load.",
         y=5.7)

# 26. Generalisation
s = slide("B3 generalisation: Families G (3GPP) and M (Markov)", "V_w [%], GBM forecaster",
          notes="BPN v1 lost on Family G because its stage 1 is always strict back-pressure, so it cannot represent "
                "reservation, which wins on long 3GPP bursts. v2 contains the reservation policy and fixes it. "
                "Training costs (BPN v2 vs best baseline): S 0.0387/0.0436, G 0.0527/0.0555, M 0.0196/0.0226.")
_table(s, 0.5, 1.35, 12.3, [
    ["Controller", "G moderate", "G high", "M moderate", "M high", "M shift"],
    ["KKT rule (B1)", "5.08", "8.01", "0.92", "4.94", "5.52"],
    ["Pred. MaxWeight (CEM-tuned)", "6.75", "10.02", "1.61", "4.82", "4.82"],
    ["CEM class-level (re-searched)", "4.51", "7.05", "0.94", "3.94", "4.22"],
    ["BPN v1", "5.67", "8.92", "0.63", "3.71", "3.72"],
    ["BPN v2", "4.24", "6.81", "0.68", "3.62", "3.82"],
    ["Oracle + KKT", "3.47", "6.06", "0.03", "1.84", "2.31"],
], col_w=[3.8, 1.7, 1.7, 1.7, 1.7, 1.7], size=14, highlight_row=5)
_bullets(s, 0.5, 4.4, 12.3, 1.8, [
    "BPN v1 lost on G: strict back-pressure cannot represent reservation, which wins on long FTP bursts",
    "v2 contains the reservation policy and fixes it",
    "Training cost (BPN v2 / best baseline): S 0.0387 / 0.0436,  G 0.0527 / 0.0555,  M 0.0196 / 0.0226",
], size=16)
takeaway(s, "v2 is the version that generalises across all three families.", y=6.4)

# 27. BPN vs best
s = slide("BPN v2 vs the best baseline in each scenario",
          notes="Best baseline means the better of predictive MaxWeight and CEM class-level, each in its best tuning. "
                "BPN v2 wins all 10 scenarios across 3 families on paired tests, all p <= 0.024. The grey bars show "
                "how far behind the original KKT rule was.")
fig_fit(s, "fig_bpn_vs_best.png", 0.5, 1.3, 7.0, 4.9)
_table(s, 7.8, 1.3, 5.0, [
    ["Scenario", "vs best baseline", "Wins"],
    ["S low", "−23.7 %", "15/20"],
    ["S moderate", "−25.3 %", "20/20"],
    ["S high", "−11.0 %", "20/20"],
    ["S flash", "−7.0 %", "20/20"],
    ["S shift", "−4.8 %", "20/20"],
    ["G moderate", "−5.9 %", "20/20"],
    ["G high", "−3.4 %", "19/20"],
    ["M moderate", "−23.3 %", "20/20"],
    ["M high", "−7.9 %", "20/20"],
    ["M shift", "−8.2 %", "20/20"],
], col_w=[1.8, 1.9, 1.3], size=13, row_h=0.4)
takeaway(s, "10/10 scenarios, 3 families, all p ≤ 0.024 (Holm–Wilcoxon).")

# 28. B3 assessment
s = slide("B3: what is now claimable, and what is still needed",
          notes="Claimable: beats both strongest baselines in their best tuning in all 10 scenarios, with equal search "
                "effort on training seeds only; the learned exponent is interpretable; 2.2-3.5 ms per decision in "
                "Python. Still needed: real traces, a deep-RL (PPO) baseline and drift-plus-penalty, sensitivity over "
                "T, tau and load, transfer between families, and there is no optimality proof for the hybrid.")
_box(s, 0.5, 1.4, 6.0, 4.7, "Claimable",
     ["• Beats both strongest baselines, each in",
      "  its best tuning, in 10/10 scenarios",
      "• Equal search effort, training seeds only;",
      "  baselines are special cases of the policy",
      "• Learned η explains when to reserve and",
      "  when to back-pressure: interpretable",
      "• 2.2–3.5 ms per decision (Python)",
      "  (Bayesian forecaster: ≈ 20 ms)"], fill=SOFTGREEN, edge=GREEN, size=15)
_box(s, 6.83, 1.4, 6.0, 4.7, "Still needed",
     ["• Real per-cell PRB / fronthaul traces",
      "• Deep-RL xApp (PPO) baseline; Lyapunov",
      "  drift-plus-penalty with deadline queues",
      "• BPN over T, τ and load (only T = 10 ms,",
      "  τ = 1 ms so far)",
      "• Policy learned per family; transfer untested",
      "• No optimality proof for the hybrid"], fill=SOFTRED, edge=ACCENT, size=15)
takeaway(s, "A controller that beats the strongest baselines — with its limits stated.")

# 29. Summary
s = slide("Part B summary",
          notes="Read the table top to bottom: it is the story of Part B. Then the take-away.")
_table(s, 0.5, 1.4, 12.3, [
    ["Step", "Headline result"],
    ["B1  KKT newsvendor rule", "Best of 12 controllers in all scenarios of 2 families: −11 to −43 % vs forecast median, every seed"],
    ["Ablations", "Most of the gain is the r* target + KKT split; ML useful, not necessary; ACI calibration hurt"],
    ["Caveats", "Needs LL weight ≥ 2–3; T ≤ a few × the shortest deadline; allocation matters at load 0.5–0.8"],
    ["Extended study", "r* linked to effective bandwidth; CEM and pred. MaxWeight beat the KKT rule in 9/10: structural gap"],
    ["B2  Bayesian Transformer", "Best KKT variant (−21 / −6 / −1.4 % at low / moderate / high); confirms the gap is structural"],
    ["B3  Back-pressure newsvendor", "Beats both strongest baselines in 10/10 scenarios of 3 families (−3 to −25 %)"],
], col_w=[3.4, 8.9], size=14, highlight_row=6, row_h=0.55, left=True)
takeaway(s, "Keep the structure, learn only what is uncertain — and let the search pick the structure.", y=5.75)

# 30. Limitations and future
s = slide("Limitations and future work",
          notes="Say the limits calmly. Then future work and thank the audience.")
_box(s, 0.5, 1.4, 6.0, 4.6, "What we do not claim",
     ["• No real-world validation (3 simulated families)",
      "• Simplified link: budget-enforced pipe, no switch",
      "  queue, no HARQ, downlink only",
      "• No closed-loop optimality or stability proof",
      "• KKT rule: only −4 % vs proportional in flash crowds",
      "• B2 on Family S only; Bayesian layer too slow",
      "  in Python for a 10 ms interval",
      "• BPN learned per family, at T = 10 ms, τ = 1 ms"],
     fill=SOFTRED, edge=ACCENT, size=15)
_box(s, 6.83, 1.4, 6.0, 4.6, "Next",
     ["• Measured per-cell PRB traces",
      "• PPO xApp baseline; BPN sweeps over T, τ, load",
      "• Cross-family transfer of the learned policy",
      "• Compiled O-DU implementation (C++ / batched)",
      "• Coupled calibration (adjust λ)",
      "• Compression width as a per-cell knob",
      "  inside the allocation rule (Part A + B)"],
     fill=SOFTGREEN, edge=GREEN, size=15)
takeaway(s, "Thank you — questions?")

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print(f"wrote {OUT} ({len(prs.slides)} slides)")
