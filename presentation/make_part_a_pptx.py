"""Build the Part A slide deck: python presentation/make_part_a_pptx.py"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "presentation" / "part_a_final.pptx"
FIG = ROOT / "results"

NAVY = RGBColor(0x0B, 0x2A, 0x4A)
ACCENT = RGBColor(0xD6, 0x3A, 0x2F)
GREEN = RGBColor(0x1E, 0x8E, 0x3E)
GREY = RGBColor(0x55, 0x55, 0x55)
LIGHT = RGBColor(0xEE, 0xF3, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
FOOTER = "Fronthaul Load Management in O-RAN  |  Part A  |  M. Yadav & H. Choudhary"


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
        p.space_after = Pt(6)
        r = p.add_run()
        r.text = ("–  " if sub else "•  ") + item.strip()
        r.font.size = Pt(size - 3 if sub else size)
        r.font.color.rgb = GREY if sub else NAVY
        if sub:
            p.level = 1
    return tb


def _box(slide, x, y, w, h, title, body, fill=LIGHT, edge=NAVY, size=16):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.color.rgb = edge
    s.line.width = Pt(1.5)
    s.adjustments[0] = 0.08
    tf = s.text_frame
    tf.word_wrap = True
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


def _table(slide, x, y, w, rows, col_w=None, size=14, highlight_row=None):
    n_r, n_c = len(rows), len(rows[0])
    shape = slide.shapes.add_table(n_r, n_c, Inches(x), Inches(y), Inches(w), Inches(0.42 * n_r))
    t = shape.table
    if col_w:
        for j, cw in enumerate(col_w):
            t.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.text = str(val)
            para = c.text_frame.paragraphs[0]
            para.alignment = PP_ALIGN.CENTER if j else PP_ALIGN.LEFT
            f = para.runs[0].font
            f.size = Pt(size)
            c.fill.solid()
            if i == 0:
                c.fill.fore_color.rgb = NAVY
                f.color.rgb, f.bold = WHITE, True
            elif i == highlight_row:
                c.fill.fore_color.rgb = RGBColor(0xDF, 0xF2, 0xE3)
                f.color.rgb, f.bold = GREEN, True
            else:
                c.fill.fore_color.rgb = WHITE if i % 2 else LIGHT
                f.color.rgb = NAVY
    return t


def _image(slide, rel, x, y, w=None, h=None):
    path = FIG / rel
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), **kw)


def fig_full(s, rel, top=1.35, max_h=4.85, max_w=12.3):
    from PIL import Image
    w, h = Image.open(FIG / rel).size
    if max_w * h / w <= max_h:
        _image(s, rel, 0.5, top, w=max_w)
    else:
        width = max_h * w / h
        _image(s, rel, 0.5 + (max_w - width) / 2, top, h=max_h)


def slide(title, subtitle=None):
    s = prs.slides.add_slide(BLANK)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(1.05))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    _text(s, 0.5, 0.15, 12.3, 0.6, title, size=30, color=WHITE, bold=True)
    if subtitle:
        _text(s, 0.5, 0.62, 12.3, 0.4, subtitle, size=15, color=RGBColor(0xBF, 0xD4, 0xEA))
    accent = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(1.05), prs.slide_width, Inches(0.06))
    accent.fill.solid()
    accent.fill.fore_color.rgb = ACCENT
    accent.line.fill.background()
    _text(s, 0.5, 7.05, 10, 0.35, FOOTER, size=11, color=GREY)
    _text(s, 12.0, 7.05, 0.9, 0.35, str(len(prs.slides)), size=11, color=GREY, align=PP_ALIGN.RIGHT)
    return s


def takeaway(s, text, y=6.35):
    b = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(y), Inches(12.33), Inches(0.6))
    b.fill.solid()
    b.fill.fore_color.rgb = RGBColor(0xFD, 0xEC, 0xEA)
    b.line.color.rgb = ACCENT
    tf = b.text_frame
    tf.word_wrap = True
    r = tf.paragraphs[0].add_run()
    r.text = text
    r.font.size, r.font.bold, r.font.color.rgb = Pt(18), True, ACCENT


# 1. Title
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid()
bg.fill.fore_color.rgb = NAVY
bg.line.fill.background()
_text(s, 0.8, 1.2, 11.7, 1.4, "Part A: Making the Fronthaul Lighter and the DU Faster",
      size=40, color=WHITE, bold=True)
_text(s, 0.8, 2.95, 11.7, 1.2,
      ["Structure-aware IQ compression, RMT-guided warm-start complex inversion,",
       "and a fused C/AVX-512 RZF precoder kernel for O-RAN 7-2x"],
      size=22, color=RGBColor(0xBF, 0xD4, 0xEA))
line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(4.2), Inches(3.0), Inches(0.08))
line.fill.solid()
line.fill.fore_color.rgb = ACCENT
line.line.fill.background()
_text(s, 0.8, 4.5, 11.7, 1.2, ["Mayank Yadav    Harshvardhan Choudhary", "B.Tech. Project — Final Evaluation, November 2026"],
      size=20, color=WHITE)

# 2. Motivation
s = slide("Why Part A?", "Two bottlenecks of a 5G/6G O-RAN cell")
_box(s, 0.5, 1.45, 6.0, 3.0, "1. The fronthaul is huge",
     ["• Raw 64-antenna cell: ≈ 15.4 Gbit/s",
      "• DU-side precoding over 100 MHz, 64 streams: 118 Gbit/s",
      "• O-RAN BFP only shortens numbers: ≈ 4×",
      "→ need compression that exploits channel structure"])
_box(s, 6.83, 1.45, 6.0, 3.0, "2. The DU has 0.5 ms per slot",
     ["• RZF precoder per PRB: G = HHᴴ + αI,  W = Hᴴ G⁻¹",
      "• 273 PRBs × complex K×K inverse every slot",
      "• numpy + LAPACK: 3.2 ms for K = 16 → misses the slot 6×",
      "→ need fast, accurate complex inversion"])
_text(s, 0.5, 4.75, 12.3, 1.2,
      ["Our answer: compress the data with its own structure, and invert the complex channel",
       "matrices with an RMT-guided method running on hand-optimised kernels."], size=20, bold=True)
takeaway(s, "Part A attacks both bottlenecks: fewer bits on the link, and a precoder that fits in the slot.")

# 3. Contributions
s = slide("Our Part A contributions at a glance")
cards = [
    ("CSEE & RAS-BFP", ["13–16× compression", "vs ≈ 4× for O-RAN BFP", "3–6× faster than SVD"]),
    ("ACAFS", ["Rank-adaptive functional split", "55–75 % bandwidth cut", "at high SNR"]),
    ("RMT-WS inversion", ["Complex Hermitian Grams", "6 GEMMs vs > 10 for", "Neumann-type methods"]),
    ("Warm-start tracking", ["2.7× fewer GEMMs, 30× lower", "loss at pedestrian speed;", "never diverges at 120 km/h"]),
    ("Fused C/AVX-512 kernel", ["Whole RZF precoder", "10–15× faster than numpy+LAPACK", "fits the 0.5 ms slot"]),
    ("RU-side precoding", ["−72 % fronthaul", "at 99.7 % of exact", "RZF sum-rate"]),
]
for i, (t, b) in enumerate(cards):
    _box(s, 0.5 + (i % 3) * 4.15, 1.45 + (i // 3) * 2.45, 3.95, 2.25, t, b,
         fill=LIGHT if i % 2 == 0 else RGBColor(0xF4, 0xF8, 0xEC), edge=NAVY if i % 2 == 0 else GREEN)
takeaway(s, "From compression theory to a slot-feasible precoder: a complete DU-side toolchain.")

# 4. Compression methods
s = slide("Structure-aware IQ compression", "Y = H ⊙ X + W ∈ ℂ^(M×N),  M = 64 antennas,  N = 1200 subcarriers, 3GPP TDL-A")
_box(s, 0.5, 1.45, 6.0, 3.6, "CSEE — delay-domain sparse encoder",
     ["1. IFFT along subcarriers → delay domain",
      "2. Keep top-K taps (channel is sparse in delay)",
      "3. Per-antenna BFP, FFT back at the receiver",
      "",
      "Theorem 1: NMSE ≤ σ²_tail/σ²_Y + (Δ²/12)·K/(MN σ²_Y)",
      "Complexity O(MN log N)"])
_box(s, 6.83, 1.45, 6.0, 3.6, "RAS-BFP — randomised sketch + QR",
     ["1. SRHT sketch Z = ΩY ∈ ℂ^(r×N)",
      "2. Thin QR of Zᴴ, project L = YQ",
      "3. Send BFP(L), BFP(Q);  Y ≈ LQᴴ",
      "",
      "Theorem 2: ‖Y − LQᴴ‖² ≤ (1+ε)‖Y − Y_r‖²  w.h.p.",
      "Theorem 4: optimal rank r* = ⌊√(B/(b(M+N)))⌉,  O(rMN)"], edge=GREEN)
takeaway(s, "Both encoders come with provable error bounds and lower complexity than SVD.", y=5.35)

# 5. Compression results
s = slide("Compression: 4× more than the O-RAN standard",
          "M = 64, N = 1200, SNR 20 dB, TDL-A")
_table(s, 0.5, 1.45, 6.3, [
    ["Method", "Compression", "Encode time"],
    ["O-RAN BFP (b = 8)", "3.9×", "3.1 ms"],
    ["Truncated SVD (r = 12)", "16.2×", "18–30 ms"],
    ["CSEE (ours)", "12.7×", "5.2 ms"],
    ["RAS-BFP (ours)", "16.2×", "7.2 ms"],
], col_w=[2.8, 1.75, 1.75], size=16, highlight_row=4)
_bullets(s, 0.5, 3.85, 6.3, 2.4, [
    "13–16× compression at ≈ −20 dB NMSE",
    "RAS-BFP: SVD-level compression, 3–4× faster",
    "CSEE: 4–6× faster than SVD; ≈ 63× at the K = 60 knee",
    "Stable NMSE across SNR −5 to 30 dB",
], size=17)
_image(s, "figures/exp1_nmse_vs_cr.png", 7.0, 1.4, w=5.9)
takeaway(s, "RAS-BFP matches SVD compression at a fraction of its encode time.")

# 6. ACAFS
s = slide("ACAFS: rank-adaptive functional split", "Per-UE rank fraction r/M picks the O-RAN split on the fly")
_table(s, 0.5, 1.5, 5.5, [
    ["Rank fraction r/M", "Split"],
    ["< 0.15", "7.2x"],
    ["0.15 – 0.55", "7.1"],
    ["≥ 0.55", "6"],
], col_w=[3.0, 2.5], size=17)
_bullets(s, 0.5, 3.4, 5.6, 2.8, [
    "Theorem 5: closed-form bandwidth saving vs a fixed Split 6",
    "≈ 33 % saving for uniformly spread ranks",
    "55–75 % saving at high SNR (rank collapse)",
    "Decision per UE, from the rank the encoder already computes",
], size=17)
_image(s, "figures/exp3_acafs.png", 6.4, 1.4, w=6.5)
takeaway(s, "The split adapts to the channel instead of being fixed at deployment.")

# 7. Complex workload
s = slide("The real DU workload: complex RZF precoding",
          "We built the full complex-valued pipeline, not a toy benchmark")
_box(s, 0.5, 1.45, 6.0, 4.6, "Realistic complex channels (cmatinv/)",
     ["• 3GPP TR 38.901 UMa NLOS path loss + shadowing",
      "   (near-far user powers)",
      "• TDL-A 23-tap profile over 100 MHz",
      "• Per-user angular-spread spatial correlation",
      "• Rician line-of-sight option",
      "• Clarke/Jakes aging ρ = J₀(2π f_D T): 3–120 km/h",
      "• M = 64/128 antennas, K = 8/16/32 layers,",
      "   273 PRBs, 30 kHz slots, 3.5 GHz"])
_box(s, 6.83, 1.45, 6.0, 4.6, "Per PRB, every 0.5 ms slot",
     ["G = HHᴴ + αI  ∈ ℂ^(K×K)   (complex Hermitian)",
      "W = Hᴴ G⁻¹   ∈ ℂ^(M×K)",
      "",
      "× 273 PRBs inside one slot",
      "",
      "Our question:",
      "Can the whole complex precoder run inside",
      "the slot on a CPU DU — and can inversion",
      "exploit the channel's statistics?"], edge=GREEN)

# 8. RMT-WS
s = slide("RMT-WS: random-matrix-guided warm-start inversion", "Our complex inversion method")
_bullets(s, 0.5, 1.4, 7.3, 4.8, [
    "Equilibrate  Ĝ = D^(−½) G D^(−½)  — removes the near-far spread",
    "Eigensolve-free spectral interval from Marchenko–Pastur + moment match:",
    "  v = ‖Ĝ‖²_F / K − 1,   [a, b] = 1 + v/s̄ ∓ 2√v   (only K² work)",
    "Cold start: Chebyshev polynomial on [a, b], then Newton–Schulz",
    "  X ← X(2I − ĜX): quadratic convergence, pure GEMMs",
    "Tracking: next slot starts from the previous inverse",
    "Residual certificate ‖(I − ĜX)z‖/‖z‖ picks the Newton steps per PRB",
    "  or falls back to a cold start — always safe",
], size=18)
_box(s, 8.1, 1.45, 4.75, 4.6, "Why it fits the DU",
     ["✔ Adapts to correlated and",
      "   near-far channels automatically",
      "✔ No eigen-decomposition",
      "✔ Only matrix multiplies:",
      "   GPU / NPU / tensor-core friendly",
      "✔ Cost adapts to user speed",
      "✔ Built-in accuracy certificate"], fill=RGBColor(0xF4, 0xF8, 0xEC), edge=GREEN)
takeaway(s, "Random-matrix theory gives the inverse a head start; the certificate keeps it safe.")

# 9. Cold start
s = slide("Cold-start inversion: fewer GEMMs",
          "Complex GEMMs (K³ MACs) needed for ≤ 1 % RZF sum-rate loss")
_table(s, 0.5, 1.45, 6.6, [
    ["Method", "64/16", "128/16", "64/32"],
    ["Neumann (Wu / Prabhu)", "> 8", "> 8", "> 8"],
    ["Joint Newton–Neumann (Shao)", "> 10", "> 10", "> 10"],
    ["Newton–Schulz, classical init", "> 10", "> 10", "> 10"],
    ["Block conjugate gradient", "7", "5", "12"],
    ["Gauss–Seidel", "6", "4", "> 12"],
    ["Cheb-MP + Newton–Schulz (ours)", "6", "5", "9"],
], col_w=[3.3, 1.1, 1.1, 1.1], size=15, highlight_row=6)
_bullets(s, 7.4, 1.6, 5.4, 4.0, [
    "Beats every Neumann / Newton-type scheme in every configuration",
    "Best of all methods at heavy load (K/M = 0.5): 9 vs 12 GEMMs",
], size=16)
takeaway(s, "Our initialisation converges in 6 GEMMs where classical series need more than 10.")

s = slide("Cold start: residual and sum-rate loss vs GEMM budget")
fig_full(s, "v2/exp6_inversion_accuracy.png")
takeaway(s, "Red curve (ours) reaches 1 % loss first in every antenna/user configuration.")

# 10. Tracking
s = slide("Warm-start tracking across user speeds",
          "K = 16, M = 64, sum-rate loss vs exact RZF / GEMMs per slot per PRB")
_table(s, 0.5, 1.45, 7.2, [
    ["Speed", "Warm Gauss–Seidel ×4", "Warm CG ×4", "RMT-WS (ours)"],
    ["3 km/h", "0.009 % / 4", "0.013 % / 5", "0.006 % / 2.25"],
    ["30 km/h", "0.63 % / 4", "0.96 % / 5", "0.43 % / 5.2"],
    ["120 km/h", "2.9 % / 4", "5.5 % / 5", "0.12 % / 6.25"],
], col_w=[1.3, 2.3, 1.7, 1.9], size=15, highlight_row=None)
_bullets(s, 0.5, 3.5, 12.3, 2.8, [
    "3 km/h: 2.7× fewer GEMMs and 30× lower loss than a cold start",
    "30 km/h: lowest loss of all warm-started methods",
    "120 km/h: 24× lower loss than warm Gauss–Seidel",
    "Fixed 1- or 2-step warm starts diverge at 120 km/h — RMT-WS never does",
], size=17)
takeaway(s, "One method, every speed: cheap when users are slow, safe when they are fast.")

s = slide("Tracking: accuracy vs cost at 3, 30 and 120 km/h")
fig_full(s, "v2/exp7_tracking.png")
takeaway(s, "RMT-WS (red star) sits at the low-cost, low-loss corner at every speed.")

# 11. Doppler law + certificate
s = slide("A closed-form speed law and a safety certificate")
_box(s, 0.5, 1.45, 6.2, 2.6, "Doppler-to-warm-start law",
     ["r₀ ≈ c · 2√(K/(M−K)) · √(1−ρ),   1−ρ ≈ (π f_D T)²",
      "• r₀ grows linearly with speed (measured slope 1.00)",
      "• Predicts the Newton steps needed: ⌈log₂(ln ε / ln r₀)⌉",
      "• Warm start valid up to ≈ 39 km/h (64/16),",
      "   60 km/h (K = 8), 23 km/h (K = 32)"])
_box(s, 0.5, 4.2, 6.2, 2.0, "Certified safety",
     ["• Tail bound  P(r̂² ≤ (1−d) r²) ≤ exp(−p d² s / 2)",
      "• Audit of 480 PRB cases, 3–120 km/h:",
      "   0 accepted-but-non-contractive cases at r̂ ≤ 0.3"], edge=GREEN, fill=RGBColor(0xF4, 0xF8, 0xEC))
_image(s, "v2/exp12_doppler_law.png", 6.9, 1.45, w=6.0)
takeaway(s, "A design rule: the DU knows in advance up to which speed the warm start pays off.", y=6.35)

# 12. Low precision
s = slide("Robust at low precision", "GEMM operands rounded to b mantissa bits, wide accumulate (tensor-core / NPU style)")
_table(s, 0.5, 1.45, 6.4, [
    ["Setting", "Direct Gauss–Jordan", "Cheb + 3 Newton (ours)"],
    ["8 mantissa bits", "0.88 %", "0.15 %"],
    ["6 mantissa bits", "5.1 %", "1.4 %"],
    ["Ill-cond., 10 bits", "1.2 %", "0.49 %"],
], col_w=[2.4, 2.0, 2.0], size=16)
_bullets(s, 7.2, 1.5, 5.6, 4.0, [
    "Sum-rate loss vs float64 exact",
    "6× lower loss at 8 bits, 3.6× at 6 bits",
    "Newton iteration self-corrects rounding errors",
    "Tracker at 8 bits: 0.70 % vs 0.54 % at full precision (30 km/h)",
], size=17)
takeaway(s, "Our method is ready for low-precision accelerators where direct inversion degrades.")

s = slide("Low precision: loss vs mantissa bits")
fig_full(s, "v2/exp8_low_precision.png")
takeaway(s, "Newton refinement keeps the loss low where direct inversion degrades.")

# 13. Kernel design
s = slide("Kernel programming: a fused complex RZF precoder in C",
          "kernels/cmat_kernels.c — batched complex64, AVX-512, OpenMP; Python binding cmatinv/fastkernels.py")
_bullets(s, 0.5, 1.4, 6.6, 4.9, [
    "One pass per PRB: load H once → Gram → inverse → Wᵀ + power scaling",
    "  everything stack / L1-resident, no DRAM intermediates",
    "Hermitian symmetry: Gram on the lower triangle only",
    "Split re/im planes so complex arithmetic vectorises",
    "In-place Gauss–Jordan sweep: K rank-1 updates, no sqrt/divide chains",
    "  inverse 6.4k → 2.9k cycles per PRB (K = 16)",
    "Register-blocked W = Hᴴ X: 0.81 → 0.42 ms per slot",
    "AVX-512 code generation: 1.3–1.5× single thread, 2× on 4 threads",
    "Fused Newton step returns the exact residual for free",
], size=17)
code = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(7.3), Inches(1.45), Inches(5.55), Inches(4.75))
code.fill.solid()
code.fill.fore_color.rgb = RGBColor(0x1E, 0x1E, 0x1E)
code.line.fill.background()
_text(s, 7.45, 1.55, 5.3, 4.6, [
    "// inner loop of the sweep inverse",
    "for (int i = 0; i < K; i++) {",
    "  if (i == k) continue;",
    "  float fr = ckr[i]*piv, fi = cki[i]*piv;",
    "  float *ar = xr + i*K, *ai = xi + i*K;",
    "  #pragma omp simd",
    "  for (int j = 0; j < K; j++) {",
    "    ar[j] -= fr*rkr[j] - fi*rki[j];",
    "    ai[j] -= fr*rki[j] + fi*rkr[j];",
    "  }",
    "  ar[k] = -fr; ai[k] = -fi;",
    "}",
    "",
    "gcc -O3 -march=native -fopenmp",
    "    -mprefer-vector-width=512",
], size=13, color=RGBColor(0xD4, 0xD4, 0xD4))

# 14. Kernel results
s = slide("Kernel results: the whole precoder now fits in the slot",
          "273 PRBs, complex64, 4-core AVX-512 Xeon, median of 40 runs")
_table(s, 0.5, 1.45, 6.4, [
    ["K, M", "numpy+LAPACK", "Our kernel", "Speed-up"],
    ["8, 64", "1.08 ms", "0.070 ms", "15×"],
    ["16, 64", "3.21 ms", "0.226 ms", "14×"],
    ["32, 64", "12.2 ms", "0.97 ms", "12.5×"],
    ["16, 128", "4.71 ms", "0.41 ms", "11.6×"],
    ["32, 128", "16.3 ms", "1.60 ms", "10×"],
], col_w=[1.2, 1.9, 2.0, 1.3], size=15, highlight_row=2)
_bullets(s, 7.2, 1.5, 5.6, 4.0, [
    "K = 8, 16 (M = 64) and K = 16, M = 128 fit a 0.5 ms slot",
    "Near-linear thread scaling: 0.92 → 0.45 → 0.23 ms",
    "Accuracy: sum-rate loss < 10⁻⁵ % vs float64",
], size=16)
takeaway(s, "10–15× faster: from 6× over the slot budget to under half of it.")

s = slide("Whole-precoder time per slot (273 PRBs)")
fig_full(s, "v2/exp17_pipeline_kernel.png")
takeaway(s, "Our fused kernels (green, red) run under the 0.5 ms line for K ≤ 16; numpy+LAPACK never does.")

# 15. Fronthaul
s = slide("Where should precoding run? A 72 % fronthaul saving",
          "100 MHz, M = 64, K = 16, BFP-9 IQ")
_table(s, 0.5, 1.45, 12.3, [
    ["Architecture", "Fronthaul", "Sum-rate vs exact"],
    ["DU precodes, sends 64 streams", "118.4 Gbit/s", "100 %"],
    ["RU precodes, 16 layers + 8-bit weights", "32.8 Gbit/s (−72 %)", "99.7 %"],
    ["RU precodes, 16 layers + 6-bit weights", "32.0 Gbit/s (−73 %)", "96.7 %"],
], col_w=[6.0, 3.6, 2.7], size=16, highlight_row=2)
_bullets(s, 0.5, 3.55, 12.3, 2.6, [
    "Mobility requires refreshing the weights every slot",
    "  every 4 slots: only 70 % of the rate at 30 km/h",
    "Per-slot weights are exactly what our fast kernel delivers",
    "RU-side precoding cuts the link load by 3.6×",
], size=17)
takeaway(s, "Fast per-slot precoding unlocks a 72 % lighter fronthaul at 99.7 % of the rate.")

s = slide("Fronthaul rate and sum-rate by architecture")
fig_full(s, "v2/exp10_fronthaul.png")
takeaway(s, "RU-side precoding with per-slot weights: −72 % fronthaul at 99.7 % rate.")

# 16. Summary
s = slide("Part A summary")
_table(s, 0.5, 1.45, 12.3, [
    ["Contribution", "Headline result"],
    ["CSEE / RAS-BFP compression", "13–16× vs ≈ 4× for O-RAN BFP; 3–6× faster than SVD; provable error bounds"],
    ["ACAFS adaptive split", "55–75 % bandwidth saving at high SNR"],
    ["RMT-WS cold start", "6 GEMMs vs > 10 for Neumann / Newton-type; best at K/M = 0.5"],
    ["RMT-WS tracking", "2.7× fewer GEMMs, 30× lower loss at 3 km/h; safe up to 120 km/h"],
    ["Speed law + certificate", "Closed-form warm-start envelope; 0 unsafe decisions in 480 cases"],
    ["Low precision", "6× lower loss than direct inversion at 8 bits"],
    ["Fused C/AVX-512 precoder", "10–15× faster than numpy+LAPACK; K ≤ 16 fits the 0.5 ms slot"],
    ["RU-side precoding", "−72 % fronthaul at 99.7 % of exact sum-rate"],
], col_w=[3.6, 8.7], size=16)
takeaway(s, "Part A delivers a lighter link and a slot-feasible precoder — the foundation for Part B.", y=5.75)

# 17. Next steps
s = slide("Next: taking RMT-WS to GPU and tensor cores")
_bullets(s, 0.5, 1.45, 12.3, 4.5, [
    "RMT-WS is pure matrix multiplication — the native operation of GPUs, NPUs and tensor cores",
    "K = 16 Gram matrices match a 16 × 16 tensor-core tile exactly",
    "Our low-precision results show the method keeps its accuracy at 8 bits",
    "Plan: CUDA port of the fused precoder; benchmark against cuBLAS / cuSOLVER batched",
    "Near-RT RIC deployment of ACAFS as an xApp",
    "Compression width as a per-cell knob for the Part B allocation rule",
], size=20)
takeaway(s, "Thank you — questions?", y=6.0)

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print(f"wrote {OUT} ({len(prs.slides)} slides)")
