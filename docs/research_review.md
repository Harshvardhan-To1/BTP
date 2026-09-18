# Research review — fronthaul load management (compression, split selection, capacity-constrained allocation)

**Search cutoff: 17 September 2026.** Searches were run live (web search + fetching publisher / arXiv / standards pages). This is a relevance-driven selection of 29 sources (two independent search passes were merged; entries 22–29 came from the second pass and were verified against Crossref / arXiv / 3GPP records), not an exhaustive survey. Where a claim about a paper appears below, the *access level* column states whether the full text was inspected (`full`), only the abstract / publisher landing page (`abstract`), or a table of contents / annex listing of a standard (`toc`). Nothing is attributed to a paper beyond what was actually read.

The review is organised around the three levers the repository actually implements (see `docs/problem_formulation.md`): (A) per-RU I/Q compression, (B) rank-adaptive stream count / functional split, (C) sharing one fronthaul link between several RUs. A fourth group (D) covers the numerical-linear-algebra and rate-allocation foundations the code relies on, and (E) the learning-based work that motivates what is and is not implemented as ML.

---

## 1. Source table

| # | Reference (verified title, authors, year, venue) | Type | Access | Link / DOI |
|---|---|---|---|---|
| 1 | S.-H. Park, O. Simeone, O. Sahin, S. Shamai (Shitz), "Fronthaul Compression for Cloud Radio Access Networks: Signal processing advances inspired by network information theory," *IEEE Signal Processing Magazine*, 31(6), 2014 | journal (peer-reviewed) | abstract | https://doi.org/10.1109/MSP.2014.2330031 |
| 2 | M. Peng, C. Wang, V. Lau, H. V. Poor, "Fronthaul-Constrained Cloud Radio Access Networks: Insights and Challenges," *IEEE Wireless Communications*, 22(2), 2015 | journal | full (author OA copy) | https://oar.princeton.edu/jspui/bitstream/88435/pr1nr2f/1/OA_FronthaulConstrainedCloudRadioAccessNetworksInsightsChallenges.pdf |
| 3 | L. M. P. Larsen, A. Checko, H. L. Christiansen, "A Survey of the Functional Splits Proposed for 5G Mobile Crosshaul Networks," *IEEE Communications Surveys & Tutorials*, 21(1), 2019 (accepted 2018) | journal | full (DTU OA copy) | https://ieeexplore.ieee.org/document/8479363 ; OA: https://backend.orbit.dtu.dk/ws/files/158484230/hkkr_08479363.pdf |
| 4 | 3GPP TR 38.801 (Rel-14), "Study on new radio access technology: Radio access architecture and interfaces," §11.1.2 and Annex A (Table A-1/A-2) | standard | sections via iTecSpec mirror | https://itecspec.com/3gpp/38.801/s/annex-a |
| 5 | O-RAN Alliance WG4, "Control, User and Synchronization Plane Specification," O-RAN.WG4.TS.CUS.0-R004-v19.00 (Annex A: BFP, block scaling, μ-law, beamspace type I/II, modulation compression, selective RE sending) | standard | toc + annex titles; BFP details cross-checked with [6] and ETSI TS 103 859 v7.0.2 | https://specifications.o-ran.org/download?id=952 ; https://www.etsi.org/deliver/etsi_ts/103800_103899/103859/07.00.02_60/ts_103859v070002p.pdf |
| 6 | M. D. L. Silva, L. Ramalho, I. Almeida, E. Medeiros, M. Berg, A. Klautau, "A New O-RAN Compression Approach for Improved Performance on Uplink Signals," *Journal of Communication and Information Systems* (SBrT), 37(1), 30–41, 2022 | journal (peer-reviewed, open access) | full | https://doi.org/10.14209/jcis.2022.3 |
| 7 | S. Lagén, L. Giupponi, A. Hansson, X. Gelabert, "Modulation Compression in Next Generation RAN: Air Interface and Fronthaul Trade-offs," *IEEE Communications Magazine*, 59(1), 2021 | magazine (peer-reviewed) | full | https://doi.org/10.1109/MCOM.001.2000453 |
| 8 | S. Lagén, X. Gelabert, L. Giupponi, A. Hansson, "Fronthaul-Aware Scheduling Strategies for Dynamic Modulation Compression in Next Generation RANs," *IEEE Transactions on Mobile Computing*, 22(5), 2725–2740, 2023 (early access Nov. 2021) | journal | abstract | https://ui.adsabs.harvard.edu/abs/2023ITMC...22.2725L (IEEE Xplore full text) |
| 9 | S. Lagén, X. Gelabert, A. Hansson, M. Requena, L. Giupponi, "Fronthaul Compression Control for Shared Fronthaul Access Networks," *IEEE Communications Magazine*, 60(6), 2022 | magazine | full | https://doi.org/10.1109/MCOM.001.2100959 |
| 10 | M. Rahmani, J. Zhao, V. Ranjbar, A. Al-Tahmeesschi, H. Ahmadi, S. Pollin, A. G. Burr, "Exploring O-RAN Compression Techniques in Decentralized Distributed MIMO Systems: Reducing Fronthaul Load," arXiv:2507.04997, July 2025 | **preprint** | full | https://arxiv.org/abs/2507.04997 |
| 11 | "Hardware Implementation for O-RAN Block Floating Point Compression and Decompression Methods in 5G Base Station," *2024 Int. Conf. on Advanced Technologies for Communications (ATC)*, 2024 | conference | abstract | https://doi.org/10.1109/ATC63255.2024.10908174 |
| 12 | S. Yagi, M. Nakahara, K. Suzuoki, T. Kozuno, D. Hisano, "Deep Learning-based Nonlinear Quantizer for Fronthaul Compression," *OECC/PSC 2022* | conference | abstract | https://doi.org/10.23919/OECC/PSC53152.2022.9849918 |
| 13 | R. Qiao, T. Jiang, W. Yu, "Learning-Based Fronthaul Compression for Uplink Cloud Radio Access Networks," *IEEE ICC 2023*, pp. 5928–5933 | conference | abstract | https://doi.org/10.1109/ICC45041.2023.10279070 |
| 14 | R. Qiao, T. Jiang, W. Yu, "Meta-Learning-Based Fronthaul Compression for Cloud Radio Access Networks," arXiv:2403.09004 (Mar. 2024); journal version *IEEE Trans. Wireless Commun.*, 23(9), 11015–11029, 2024 | preprint + journal | abstract | https://arxiv.org/abs/2403.09004 |
| 15 | C.-K. Wen, W.-T. Shih, S. Jin, "Deep Learning for Massive MIMO CSI Feedback," *IEEE Wireless Communications Letters*, 7(5), 748–751, 2018 | journal | full (arXiv 1712.08919) | https://ieeexplore.ieee.org/document/8322184 ; https://arxiv.org/abs/1712.08919 |
| 16 | F. W. Murti, S. Ali, G. Iosifidis, M. Latva-aho, "Learning-Based Orchestration for Dynamic Functional Split and Resource Allocation in vRANs," *EuCNC/6G Summit 2022* | conference | full (arXiv 2205.07518) | https://doi.org/10.1109/EuCNC/6GSummit54941.2022.9815815 |
| 17 | F. W. Murti, S. Ali, G. Iosifidis, M. Latva-aho, "Deep Reinforcement Learning for Orchestrating Cost-Aware Reconfigurations of vRANs," *IEEE Trans. Network and Service Management*, 21(1), 200–216, 2024 (accepted 2023) | journal | full (arXiv 2208.05282) | https://doi.org/10.1109/TNSM.2023.3292713 |
| 18 | F. W. Murti, S. Ali, M. Latva-aho, "Constrained Deep Reinforcement Based Functional Split Optimization in Virtualized RANs," arXiv:2106.00011 (2021); a journal version in *IEEE Trans. Wireless Commun.* is indexed but was not checked | preprint | abstract | https://arxiv.org/abs/2106.00011 |
| 19 | N. Halko, P.-G. Martinsson, J. A. Tropp, "Finding Structure with Randomness: Probabilistic Algorithms for Constructing Approximate Matrix Decompositions," *SIAM Review*, 53(2), 217–288, 2011 | journal | full (arXiv 0909.4061) | https://doi.org/10.1137/090771806 |
| 20 | J. A. Tropp, "Improved Analysis of the Subsampled Randomized Hadamard Transform," *Advances in Adaptive Data Analysis*, 3(1–2), 115–126, 2011 | journal | full (author preprint) | https://doi.org/10.1142/S1793536911000787 |
| 21 | Y. Shoham, A. Gersho, "Efficient bit allocation for an arbitrary set of quantizers," *IEEE Trans. Acoustics, Speech, and Signal Processing*, 36(9), 1445–1453, 1988 | journal | abstract | https://doi.org/10.1109/29.90373 |
| 22 | Aswathylakshmi P, R. K. Ganti, "Fronthaul Compression for Uplink Massive MIMO using Matrix Decomposition," *IEEE WCNC 2022*, pp. 2524–2529 | conference | full (arXiv 2110.12532) | https://doi.org/10.1109/WCNC51071.2022.9771783 |
| 23 | F. Wiffen, W. H. Chin, A. Doufexi, "Distributed Dimension Reduction for Distributed Massive MIMO C-RAN with Finite Fronthaul Capacity," *Asilomar 2021*, pp. 1228–1236 | conference | full (arXiv 2201.12470) | https://doi.org/10.1109/IEEECONF53345.2021.9723180 |
| 24 | L. Li, M. Bi, H. Xin, Y. Zhang, Y. Fu, X. Miao, A. M. Mikaeil, W. Hu, "Enabling Flexible Link Capacity for eCPRI-Based Fronthaul With Load-Adaptive Quantization Resolution," *IEEE Access*, vol. 7, pp. 102174–102185, 2019 | journal | full | https://doi.org/10.1109/ACCESS.2019.2930214 |
| 25 | I. Kanno, M. Ito, Y. Amano, Y. Kishi, T. Choi, W.-Y. Chen, A. F. Molisch, "Adaptive Bit Allocation for SVD based Hybrid Processing of Uplink Cell-Free Massive MIMO under Limited Fronthaul Capacity," *IEEE VTC2023-Spring* | conference | abstract | https://doi.org/10.1109/VTC2023-Spring57618.2023.10201009 |
| 26 | L. Liu, R. Zhang, "Optimized Uplink Transmission in Multi-Antenna C-RAN With Spatial Compression and Forward," *IEEE Trans. Signal Process.*, vol. 63, no. 19, pp. 5083–5095, 2015 | journal | abstract | https://doi.org/10.1109/TSP.2015.2450199 |
| 27 | A. Martínez Alba, W. Kellerer, "Dynamic Functional Split Adaptation in Next-Generation Radio Access Networks," *IEEE Trans. Netw. Service Manag.*, vol. 19, no. 3, pp. 3239–3263, 2022 | journal | abstract | https://doi.org/10.1109/TNSM.2022.3178040 |
| 28 | L. Wang, S. Zhou, "On the Fronthaul Statistical Multiplexing Gain," *IEEE Commun. Lett.*, vol. 21, no. 5, pp. 1099–1102, 2017 | journal | abstract | https://doi.org/10.1109/LCOMM.2017.2653120 |
| 29 | 3GPP TR 38.901 V19.4.0, "Study on channel model for frequencies from 0.5 to 100 GHz," cl. 7.7.2–7.7.5 (TDL-A, delay scaling, correlation extension) | standard | full (clauses) | https://www.3gpp.org/ftp/Specs/archive/38_series/38.901/ |

Also seen (metadata only, cited only as the baselines used by [22]): Choi–Evans–Gatherer, ICC 2016 (frequency-domain PCA compression); Aswathylakshmi & Ganti, GC Wkshps 2019 (QR approximation). Entry 29 is cited for the TDL-A definition only; the repository's TDL-A taps, RMS-delay-spread scaling (`delay_spread_ns=100`) and exponential antenna-correlation extension (`rho=0.7`) are the constructs those clauses define.

Grey literature seen but **not** relied on: a 2025 Politecnico di Milano MSc thesis on BFP9 over-the-air measurements with OpenAirInterface / NVIDIA Aerial (abstract only; it reports that BFP9's penalty is negligible at low MCS and significant at high MCS, and demonstrates run-time bit-width switching). It is mentioned because it is the only source found that measures adaptive compression on hardware; it is not peer-reviewed.

---

## 2. Deeper analysis of the eight most useful sources

### [6] Silva et al. 2022 — O-RAN BFP / block scaling / μ-law evaluation (full text)
- **Problem / setting.** Uplink split 7.2x; each PRB (12 complex REs, 16-bit I and Q) is compressed independently with one of the three O-RAN WG4 methods; `iqWidth` is the mantissa width; BFP carries a 4-bit shared exponent per PRB in an 8-bit `udCompParam` field.
- **Method / inputs.** Direct implementation of the Annex A algorithms; metric is SQNR vs `iqWidth` and vs signal power; computational cost counted in operations. Proposes selecting the method per PRB (MMSE brute force, decision tree, or a dynamic-range heuristic) and shows how to signal it within the spec.
- **Findings supported by the paper.** BFP gives the best SQNR at low signal power; block scaling at high power; a per-PRB selector gains ≈3 dB effective SNR over BFP alone in some regimes.
- **Limitations.** No channel model or MIMO structure — it treats each PRB as an independent block. No multi-cell / capacity constraint.
- **Relevance.** This is exactly the baseline the repository implements in `src/encoder/bfp.py` (12-RE blocks, 4-bit exponent, `b`-bit mantissa) and confirms that our BFP bit accounting is the standard one. Its per-PRB adaptive selection is the closest published analogue to our per-RU menu selection, but at a finer granularity and with a single-RU objective.

### [7] Lagén et al. 2021 — modulation compression (full text) and [9] Lagén et al. 2022 — shared-fronthaul compression control (full text); [8] Lagén et al. 2023 TMC (abstract)
- **Problem / setting.** 5G NR, split 7.2x, downlink modulation compression: I/Q words are replaced by constellation indices, so the fronthaul rate scales with modulation order. [9] and [8] consider *several cells multiplexed on one fixed-capacity fronthaul link* through a layer-2 switch, and control compression + MAC scheduling centrally.
- **Method.** [7]: ns-3 5G-LENA system-level simulation; measures air-interface throughput vs. fronthaul capacity for different modulation caps. [8] (abstract): convex formulation for joint RB allocation and per-user modulation compression under a shared FH constraint; evaluated on ns-3.
- **Findings.** [7]: capping at 64-QAM yields ≈82 % fronthaul reduction with negligible air-interface loss; up to 94 % at low/medium load. [8] (abstract): 16 %–567 % gains in throughput percentiles under tight FH capacity vs. holistic baselines.
- **Limitations w.r.t. this repo.** Downlink and modulation compression (the DU knows the constellation) — not applicable to uplink received I/Q, which is the repository's case. End-to-end metrics (throughput) need a full MAC/PHY simulator we do not have.
- **Relevance.** These are the primary evidence that *shared fronthaul across cells with a centralised compression controller* is a recognised problem in the O-RAN literature, and they set the template our Exp5 follows in miniature: per-cell compression operating point, a common capacity constraint, a centralised solver, and static/uniform baselines. Our contribution differs by being uplink, I/Q-fidelity based (NMSE) and using analytical rate-distortion predictions rather than a system-level simulator.

### [10] Rahmani et al. 2025 — O-RAN compression in decentralised distributed MIMO (preprint, full text)
- **Setting.** Uplink, multiple RUs each with `N_r` antennas connected to a DU; TDL multipath channel; NR PUSCH chain; BFP / block scaling / μ-law at the RU; metric is BLER vs. SNR under different `iqWidth`.
- **Findings.** Aggressive O-RAN compression keeps BLER close to the uncompressed benchmark for the tested modulations; fronthaul load reduction is quantified per method.
- **Limitations.** Preprint (not peer-reviewed at the time of search); per-PRB scalar methods only — no low-rank or delay-domain structure; no capacity constraint or allocation.
- **Relevance.** Confirms that uplink RU→DU I/Q compression of `M × N` received matrices under a TDL channel is the right setting and that BFP is the accepted baseline. Its use of BLER is the metric we *cannot* yet report (no PUSCH chain in the simulator) — listed as future work.

### [3] Larsen, Checko, Christiansen 2019 — functional-split survey (full text) with [4] 3GPP TR 38.801
- **Content.** Maps split options 1–8 to fronthaul bit-rate, latency and centralisation. TR 38.801 Annex A (100 MHz, 256-QAM, 8 layers, 32 antenna ports) gives UL requirements: Option 6 ≈ 5.6 Gb/s; Option 7a 16.6–21.6 Gb/s; Option 7b 53.8–86.1 Gb/s; Option 8 157.3 Gb/s. Its summary table states that peak transport bandwidth is *lowest* for the higher-layer splits and *highest* for Option 8, and that split-7 traffic scales with antenna ports while split-6 traffic scales with MIMO layers.
- **Relevance.** This is the basis for the **correction** made to the repository's ACAFS model: the original figure treated split 6 as the most expensive option; per TR 38.801 it is the cheapest on the fronthaul (at the cost of hosting the full UL PHY in the RU). Our `SplitBandwidthModel` now orders `R_6 ≪ R_7.2x-beam ≤ R_7.x-antenna` and reports savings relative to the fixed antenna-space split.

### [15] Wen, Shih, Jin 2018 — CsiNet (full text)
- **Setting.** FDD downlink CSI feedback; channel matrix (subcarriers × antennas) transformed with a 2-D DFT into the angular-delay domain, where only the first `N_c` delay rows are non-negligible; an autoencoder compresses the truncated matrix.
- **Relevance.** This is the literature justification for *why* the repository's CSEE encoder works: delay-domain sparsity of the **channel**. It also explains the negative result found this iteration — CsiNet compresses `H`, not `H·diag(x)+W`; once random data symbols multiply each subcarrier, the delay-domain sparsity is destroyed. Hence CSEE is a CSI / reference-symbol compressor. CsiNet also shows learned transforms can beat fixed ones for CSI — relevant future work only if a data-driven basis is needed.

### [19] Halko, Martinsson, Tropp 2011 (full text) with [20] Tropp 2011 (full text)
- **Content.** Randomised range finder: `Z = ΩY`, QR, project, small SVD. Theorem 10.5 (arXiv numbering Thm. 18): for a Gaussian test matrix with target rank `k ≥ 2` and oversampling `p ≥ 2`, `E‖(I−P_Y)A‖_F ≤ (1 + k/(p−1))^{1/2} (Σ_{j>k} σ_j²)^{1/2}` (the proof first bounds the expected *squared* error by `(1+k/(p−1))Σσ_j²`). Complexity `O(mn log k)` with structured (SRFT/SRHT) sketches. Tropp 2011 proves that the SRHT preserves the geometry of a subspace with near-optimal constants, which is what makes SRHT a legitimate sketch.
- **Relevance.** The repository's RAS-BFP encoder is a direct instance of HMT Algorithms 4.1/5.1 applied to the received matrix, followed by BFP quantisation. Our "Theorem 2" is the HMT bound plus an Eckart–Young triangle-inequality step; it is stated for Gaussian sketches and only checked empirically for SRHT — the review makes that limitation explicit.

### [21] Shoham & Gersho 1988 (abstract)
- **Content.** Optimal / near-optimal allocation of a bit budget across an arbitrary set of quantizers with irregular rate-distortion points by minimising `D_i + λ R_i` per quantizer and searching λ — equivalent to operating on the lower convex hull of each quantizer's R-D points.
- **Relevance.** The multi-cell allocator in `src/control/allocator.py` is this algorithm (greedy marginal-gain on the convex hull ≡ λ-sweep), with RUs as the "quantizers" and fronthaul bits as the budget. We claim no algorithmic novelty; the engineering content is the analytical rate-distortion menu that makes the algorithm cheap to run per symbol.

### [22] Aswathylakshmi & Ganti 2022 — matrix-decomposition fronthaul compression (full text)
- **Setting.** Uplink massive MIMO RRH, `N_r = 64` antennas, `N`-point OFDM (1024 / 4096), `L = 12`-tap "TDLA30" channel with exponential antenna correlation 0.7, 64-QAM. Received matrix `Y ∈ ℂ^{N×N_r}`; the Fourier transform of the `L × N_r` tap matrix has rank ≤ `L`.
- **Method.** Alternating-minimisation blind deconvolution at the RRH factors `Y_f` into a diagonal data matrix and a low-rank channel matrix; only `N` data samples plus `L·N_r` channel-tap samples are forwarded. Baselines: frequency-domain PCA (Choi–Evans–Gatherer, ICC 2016) and the authors' earlier QR approximation (GC Wkshps 2019).
- **Findings (as read).** Sample-count compression ratios 36.6 (N=1024) / 53.9 (N=4096) single-user vs ≈5 for PCA; 9.2 / 13.5 for 4 users vs ≈1.3 for PCA. Uncoded SER with MRC matches the uncompressed system at CR 53.9; the multi-user ZF case loses diversity at high SNR after 10 iterations.
- **Limitations.** Iterative encoder (10 iterations); `L` assumed known/bounded; CR counts *samples*, not bits (no quantiser); SER only; single cell.
- **Relevance.** The **closest precedent for CSEE**: same 64-antenna TDL-A setting, same structural fact (few delay taps ⇒ low-rank / sparse delay domain). Two differences matter for our findings: (i) they *separate* the data symbols from the channel by blind deconvolution, which is exactly the step that CSEE lacks — this is the literature explanation for why CSEE only works on reference symbols; (ii) they count samples while we count bits after BFP quantisation, so their CRs are not comparable with ours. Also confirms PCA/SVD as the standard baseline family.

### [24] Li et al. 2019 — load-adaptive quantisation resolution for eCPRI (full text)
- **Setting.** eCPRI uplink, low-layer split; only loaded RBs are transported so fronthaul load is bursty and provisioning for peak wastes capacity.
- **Method.** LAFQB: the RU's per-RE quantisation bit-width is adjusted per subframe from link load (loaded/total RBs) and the predicted short-term SINR; block scaling normalises before a uniform quantiser; a QR manager at the CU/DU feeds the bit-width back to the RU.
- **Findings (as read).** MATLAB LTE uplink, one UE, EPA-5, HARQ+AMC, plus a 25 Gb/s optical link experiment: average bit-width 8 → 4.8 bits for a 2.0 % end-user throughput penalty; fixed 4.8-bit quantisation visibly hurts high-SINR users while the adaptive scheme does not; provisioned capacity 32.3 → ≈19.4 Gb/s at full load.
- **Limitations.** Single UE / single cell; LTE; uniform (non-BFP) quantiser; SINR-threshold heuristic rather than a distortion-optimal allocation.
- **Relevance.** The **closest prior art for the allocator**: bits per RE as a function of link load on a capacity-limited link. Ours differs by being multi-cell on a shared link, choosing among heterogeneous operating points from an analytical distortion predictor rather than SINR thresholds, and optimising sum / worst-cell NMSE. Their observation that fixed low resolution hurts high-SINR users is the effect our min-max ablation targets.

### [23][25][26] Wiffen et al. 2021 (full), Kanno et al. 2023 (abstract), Liu & Zhang 2015 (abstract) — stream reduction and per-stream bit allocation
- Wiffen et al.: per-RRH linear dimension reduction (conditional KLT) maximising joint mutual information; the information-bearing part of the received vector lies in an `r = min(M, K)`-dimensional subspace, so at least `r` coefficients per RRH suffice; with `N ≥ 3` of `M = 8` dimensions the information loss is small (i.i.d. fading, `L=4, K=8`). Theoretical backing for ACAFS sending *streams* instead of antennas.
- Kanno et al. (abstract only): SVD at each AP reduces streams, each stream gets an adaptive number of bits under a fronthaul budget, optimising average SNR or sum capacity — the nearest published statement of "rank selection + per-stream bit allocation", single-link.
- Liu & Zhang (abstract only): spatial compress-and-forward with fronthaul bit allocation in multi-antenna C-RAN — the information-theoretic ancestor of the same idea.
- None of the three allocates across *cells sharing one link* or mixes non-SVD operating points.

### [16][17] Murti et al. 2022 / 2024 — RL for functional-split orchestration (full text)
- **Setting.** vRAN with O-RAN-style split options; joint selection of splits, vCU/vDU placement, compute resources and routing to minimise long-term cost; testbed measurements show non-linear, high-variance demand→compute relationships; D3QN with action branching; real traces.
- **Findings.** Up to 59 % (TNSM) / 69 % (EuCNC) cost saving vs. static benchmarks; transfer learning speeds convergence.
- **Limitations w.r.t. this repo.** Their decision epoch is minutes–hours and the state is traffic demand and resource availability; ours is per OFDM symbol and the state is the received matrix's rank/energy profile. Their reward is monetary cost; ours is a physical distortion.
- **Relevance.** They justify *adaptive* split selection as a real research direction and show why model-free RL was chosen there: the compute-cost model was not available in closed form. In our case the rate model **is** closed-form (bits per symbol per split), so an RL agent is not justified for the mid-evaluation — a rule on the estimated rank suffices and is explainable. RL would become relevant only if we added slot-level dynamics with unknown RU compute costs.

---

## 3. Synthesis

### 3.1 Which approaches fit this project
- **Per-RU I/Q compression:** The standardised baseline is O-RAN BFP [5][6][10]; any proposed encoder must be compared against it at equal bit budget, as the repository now does. Structure-exploiting encoders (low-rank spatial [19][23], delay-domain sparse [15][22]) are established for CSI, for single-RRH uplink [22] and for cell-free uplink [13][14][25]; using them on *received I/Q* is legitimate but must respect what modulation does to each structure (§3.2).
- **Rank-adaptive stream count / split:** Beam-space compression (send `r` streams instead of `M` antennas) is a standardised option (O-RAN Annex A.4) and the split-6 alternative is quantified by 3GPP [4]. A rule-based controller on the estimated rank is the appropriate first step; learned orchestration [16][17] belongs to a later stage.
- **Shared capacity across RUs:** Lagén et al. [8][9] establish the problem; classic bit allocation [21] gives the solver. This is the layer the repository lacked and now implements (Exp5).

### 3.2 Assumptions in the literature vs. this implementation
| Literature assumption | Repository | Match? |
|---|---|---|
| BFP per 12-RE PRB with 4-bit exponent [5][6] | same | yes |
| Modulation compression needs DU-side knowledge of the constellation (downlink) [7] | uplink received I/Q only | not applicable — we do not use it |
| Delay-domain sparsity holds for the channel matrix [15][22]; [22] recovers it on data symbols only by blind deconvolution | holds for reference symbols (`H + W'`), destroyed on data symbols (`H·diag(x)`) — verified in Exp1/Exp4 | partially; now stated explicitly |
| Low-rank spatial structure from few dominant paths [13][14][19] | TDL-A with 23 taps and spatial correlation ⇒ rank ≤ 23 | yes |
| Split-6 traffic ≪ split-7 traffic [3][4] | corrected this iteration | yes (after fix) |
| Evaluation by BLER / throughput on a full PHY-MAC simulator [7][8][10] | NMSE vs transported and vs noiseless matrix only | no — stated as a limitation |
| Real traffic / traces [16][17] | i.i.d. channel realisations, one OFDM symbol | no — stated |

### 3.3 Gap the project addresses
The O-RAN compression literature is per-PRB and per-RU [6][10]; the shared-fronthaul control literature is downlink and modulation-compression based [7][8][9]; the structured-compression literature targets CSI [15] or cell-free beamforming design [13][14]. The closest prior art is single-link: Li et al. [24] adapt bit-width to load and SINR on one eCPRI link, Kanno et al. [25] allocate bits per SVD stream at one AP, Aswathylakshmi & Ganti [22] exploit the same delay-domain structure as CSEE for one RRH. None of the sources found combines (i) uplink I/Q encoders with a *closed-form rate-distortion predictor* usable per OFDM symbol, (ii) a shared-capacity allocation across RUs driven by those predictions, and (iii) a fidelity metric that separates signal loss from removed noise. That combination is an engineering contribution and a validation study — not a new algorithm.

### 3.4 What was implemented and evaluated credibly for the mid-evaluation
- Standard BFP and economy-SVD baselines at exact bit accounting [5][6][19].
- CSEE with Proposition 1 (analytical rate-distortion, exact tail term) and RAS-BFP with an HMT-type bound [19][20].
- Rank-adaptive split controller with the 3GPP-consistent bandwidth ordering [3][4].
- Shoham–Gersho-style allocation across 8 RUs [21] with uniform baselines, an encode-everything oracle, sum/max/noise-aware objectives, 5 seeds.

### 3.5 What should remain future work
- BLER / throughput evaluation with a PUSCH chain (as in [10]) — the metric the community expects.
- Slot-level simulation with mixed data and reference symbols, so the allocator can choose between CSEE and spatial encoders per symbol.
- Joint split + allocation under one capacity with an RU compute constraint (bridge to the matrix-inversion benchmark).
- Learned components only where no analytical predictor exists (e.g. a rate-distortion predictor for RAS-BFP under SRHT, or a learned CSI basis as in [15]); RL orchestration [16][17] only if slot-level dynamics and unknown costs are introduced.

### 3.6 Comparability caveat
Numbers in [6], [7], [8], [10], [22], [24] (SQNR, % fronthaul reduction, throughput percentiles, BLER) were obtained with different workloads, channel models and metrics from ours and are **not** directly comparable with the NMSE / CR figures in `results/`. They are cited for problem framing and baseline definitions only.
