# BTP Mid-Term Evaluation Report (50% Progress)

**Project Title:** High-Performance Fronthaul Load Management in 5G/6G C-RAN  
**Target Publication:** IEEE Transactions on Wireless Communications (TWC) / JSAC  
**Evaluation Stage:** Mid-Term (50% Completion)  
**Date:** September 2026  

---

## 1. Executive Summary

Massive MIMO Cloud-RAN / O-RAN deployments push fronthaul I/Q rates to multi-Gbps per cell. This BTP develops **two low-latency compression encoders** and **one rank-adaptive functional-split controller**, with matching theory (Theorems 1–5), a full Python simulator on **3GPP TR 38.901 TDL-A**, and four publication-style experiment suites.

### 50% Progress Checklist

| # | Deliverable | Status |
|---|---|---|
| 1 | 3GPP TDL-A channel model (`src/channel/tdl_a.py`) | Done |
| 2 | Baselines: O-RAN BFP + Truncated SVD | Done |
| 3 | **CSEE** — Circulant / delay-domain encoder + Theorem 1 | Done |
| 4 | **RAS-BFP** — SRHT + QR sketched BFP + Theorems 2–4 | Done |
| 5 | **ACAFS** — Rank-adaptive split controller + Theorem 5 | Done |
| 6 | Experiments Exp1–Exp4 → `results/figures/` | Done |
| 7 | Live demo notebook `notebooks/mid_evaluation_demo.ipynb` | Done |
| 8 | Mid-eval report + 15-slide deck | Done |

---

## 2. System Model

Received frequency-domain matrix after OFDM demodulation:

$$Y = H \odot X + W \in \mathbb{C}^{M \times N}$$

with $M=64$ antennas, $N=1200$ subcarriers (100 MHz, 15 kHz SCS), TDL-A delay profile, and exponential spatial correlation across antennas.

Raw fronthaul rate (32-bit I/Q, numerology 0):

$$R_{\mathrm{raw}} = 2\,M\,N_{\mathrm{sc}}\,N_{\mathrm{sym}}\,b\,R_{\mathrm{slot}} \approx 15.36~\mathrm{Gbps/cell}$$

---

## 3. Methods & Theorems

| Method | Role | Complexity | Theory |
|---|---|---|---|
| BFP | O-RAN baseline | $\mathcal{O}(MN)$ | Empirical quantization |
| Truncated SVD | Strong baseline | $\mathcal{O}(MN\min(M,N))$ | Eckart–Young |
| **CSEE** | Proposed 1 | $\mathcal{O}(MN\log N)$ | **Theorem 1** |
| **RAS-BFP** | Proposed 2 | $\mathcal{O}(rMN)$ | **Theorems 2–4** |
| **ACAFS** | System wrapper | $\mathcal{O}(M)$ / UE | **Theorem 5** |

### 3.1 CSEE — Theorem 1

TDL-A channels are sparse in **delay domain**. CSEE applies an IFFT along subcarriers, keeps the top-$K$ taps, quantizes with per-antenna BFP, and recovers via FFT.

$$\mathrm{NMSE}_{\mathrm{CSEE}} \le \frac{\sigma_{\mathrm{tail}}^2}{\sigma_Y^2} + \frac{\Delta^2}{12}\frac{K}{MN\sigma_Y^2}$$

### 3.2 RAS-BFP — Theorems 2–4

Spatial correlation ⇒ low numerical rank $r\ll\min(M,N)$.

1. SRHT sketch $Z=\Omega Y\in\mathbb{C}^{r\times N}$
2. Thin QR: $Z^H=QR$
3. $L=YQ$; transmit BFP$(L,Q)$

**Thm 2:** $\|Y-LQ^H\|_F^2 \le (1+\varepsilon_r)\|Y-Y_r\|_F^2$ w.p. $\ge 1-\delta$  
**Thm 4:** $r^\star=\left\lfloor\sqrt{B_{\mathrm{total}}/(b(M+N))}\right\rceil$

### 3.3 ACAFS — Theorem 5

Per-UE rank fraction $r_k/M$ selects Split **7.2x / 7.1 / 6**. Relative BW cut vs fixed Split 6:

$$\frac{\Delta\mathrm{BW}}{\mathrm{BW}_6}=1-\big(\mathrm{BW}_{7.2x}\tau_{\mathrm{low}}+\mathrm{BW}_{7.1}(\tau_{\mathrm{high}}-\tau_{\mathrm{low}})+\mathrm{BW}_6(1-\tau_{\mathrm{high}})\big)$$

Uniform-rank closed form ≈ **33.3%** ($\tau_{\mathrm{low}}=0.15$, $\tau_{\mathrm{high}}=0.55$).

---

## 4. Experimental Results (Measured)

### 4.1 Single-slot benchmark ($M=64$, $N=1200$, SNR $=20$ dB)

| Method | NMSE (dB) | Compression Ratio | Encode time | vs SVD |
|---|---|---|---|---|
| O-RAN BFP ($b=8$) | ≈ −46 dB | ≈ 3.9× | ≈ 3.1 ms | faster |
| Truncated SVD ($r=12$, $b=10$) | ≈ −21 dB | ≈ 16.2× | ≈ 18–30 ms | 1.0× (ref) |
| **CSEE** ($K=300$, $b=10$) | ≈ −21 dB | ≈ **12.7×** | ≈ **5.2 ms** | **~4–6× faster** |
| **RAS-BFP** ($r=12$, $b=10$) | ≈ −18 dB | ≈ 16.2× | ≈ **7.2 ms** | **~3–4× faster** |

CSEE at smaller $K$ (e.g. $K=60$) reaches **~63×** CR at NMSE ≈ −19 dB — the Pareto knee for delay-domain sparsification.

### 4.2 Figure suite

| Fig | File | Finding |
|---|---|---|
| 1 | `results/figures/exp1_nmse_vs_cr.png` | CSEE / RAS-BFP trade CR vs NMSE under Thm 1–2 bounds |
| 2 | `results/figures/exp2_complexity.png` | Sub-linear / near-linear scaling; SVD grows fastest in $M$ |
| 3 | `results/figures/exp3_acafs.png` | ACAFS BW cut vs Split 6 rises with SNR (rank collapse); mean ~30%+ |
| 4 | `results/figures/exp4_snr_sweep.png` | Stable NMSE across SNR $\in[-5,30]$ dB |

---

## 5. Roadmap — Remaining 50%

```
Phase 1 (Done · 50%)              Phase 2 (Planned · 50%)
[ TDL-A + Theory 1–5 ]  ──────►  [ C++ / AVX-512 / CUDA kernels ]
[ CSEE + RAS-BFP + ACAFS ] ───►  [ O-RAN near-RT RIC E2 xApp ]
[ Python Exp1–4 + Notebook ] ►  [ USRP / OpenAirInterface OTA ]
[ Mid-eval report + slides ] ►  [ IEEE TWC / JSAC submission ]
```

| Month | Milestone |
|---|---|
| +1–2 | SIMD / GPU real-time path (<100 µs encode) |
| +3 | ACAFS as near-RT RIC xApp (E2SM) |
| +4 | Over-the-air validation (USRP N310) |
| +5 | Camera-ready paper |

---

## 6. Deliverable Index

| Asset | Path |
|---|---|
| Demo notebook | `notebooks/mid_evaluation_demo.ipynb` |
| Slide deck (Markdown) | `docs/mid_evaluation_slides.md` |
| HTML presentation | `docs/mid_evaluation_slides.html` |
| This report | `docs/mid_evaluation_report.md` |
| Source | `src/{channel,encoder,split,metrics}/` |
| Experiments | `experiments/exp1_*.py` … `exp4_*.py` |
| Figures | `results/figures/exp{1..4}_*.{png,pdf}` |

---

## 7. Committee Sign-Off

**Project status:** On schedule — **50% milestone complete**  
**Artifacts:** Theory (Thm 1–5) · Working simulator · 4 figure suites · Live notebook · Report · Slides
