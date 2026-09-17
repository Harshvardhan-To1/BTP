# Focused literature review: fronthaul load management under bursty traffic

Scope: (i) what determines split 7-2x fronthaul load and why a shared packet
fronthaul link is oversubscribed; (ii) how prior work allocates shared
transport/compute capacity from forecasts; (iii) uncertainty-aware and
conformal resource allocation. Search performed up to 2026-09-17. Entries are
marked **[peer-reviewed]**, **[standard/spec]** or **[preprint]**. DOIs/links were
resolved during the review.

## A. Primary sources on the fronthaul itself

1. **3GPP TR 38.801 V14.0.0**, "Study on new radio access technology: Radio access
   architecture and interfaces", 2017. **[standard]** Defines functional split
   options 1-8; option 7 (intra-PHY) variants motivate O-RAN's 7-2x.
   https://www.3gpp.org/ftp/Specs/archive/38_series/38.801/
2. **O-RAN WG4**, *Control, User and Synchronization Plane Specification*
   (O-RAN.WG4.CUS.0, e.g. R004-v19.00). **[standard]** Split 7-2x, section-based
   U-plane (startPrbu/numPrbu: IQ is sent per scheduled PRB), block-floating-point
   compression (Annex A.1), and delay management with O-RU receive windows
   (T2a): U-plane packets outside the window are useless. Example values in the
   spec: T2amin = 100 us, T2amax = 260 us. https://specifications.o-ran.org/
3. **IEEE 802.1CM-2018**, *Time-Sensitive Networking for Fronthaul*. **[standard]**
   Class 2 (eCPRI intra-PHY) high-priority fronthaul: 100 us one-way latency budget,
   frame-loss ratio 1e-7. (Values as summarised in Pérez et al. [5].)
4. **L. M. P. Larsen, A. Checko, H. L. Christiansen**, "A Survey of the Functional
   Splits Proposed for 5G Mobile Crosshaul Networks", *IEEE Commun. Surveys &
   Tutorials*, 21(1):146-172, 2019. **[peer-reviewed]**
   DOI 10.1109/COMST.2018.2868805. Key facts used: for splits 1 to 7-2 "the bitrate
   will vary with the user load" (only splits 7-1/8 are constant-rate); ~8% DL
   overhead for Ethernet transport of split 7-2. => Fronthaul demand is a
   function of scheduled PRB-layers, **not** of application bits.
5. **G. O. Pérez, J. A. Hernández, D. Larrabeiti**, "Fronthaul Network Modeling and
   Dimensioning Meeting Ultra-Low Latency Requirements for 5G", *J. Opt. Commun.
   Netw.*, 10(6):573-581, 2018. **[peer-reviewed]** DOI 10.1364/JOCN.10.000573; and
   **G. O. Pérez et al.**, "5G New Radio Fronthaul Network Design for eCPRI-IEEE
   802.1CM and Extreme Latency Percentiles", *IEEE Access*, 2019.
   DOI 10.1109/ACCESS.2019.2923020. **[peer-reviewed]** Packet-switched
   aggregation of eCPRI flows, dimensioning via high delay percentiles
   (G/G/1, N*D/D/1). Establishes the aggregation-switch/shared-link model and the
   statistical-multiplexing rationale used here.
6. **"On the Fronthaul Statistical Multiplexing Gain"**, *IEEE Communications
   Letters*, 2017 (arXiv:1701.08266, DOI 10.48550/arXiv.1701.08266). **[peer-reviewed;
   author list to be confirmed from the publisher page]**
   Analytical blocking probability when several RRUs share one fronthaul link;
   the gain grows with the cluster size. Motivates oversubscription (our default
   aggregate cell peak = 2.4x link capacity).
7. **S. Lagén, X. Gelabert, A. Hansson, M. Requena, L. Giupponi**, "Fronthaul
   Compression Control for Shared Fronthaul Access Networks", *IEEE Communications
   Magazine*, 2022. **[peer-reviewed]** DOI 10.1109/MCOM.001.2100959. Closest
   *fronthaul* work: several 7-2x cells share one fixed-capacity FH link via an
   L2 switch; FH-aware modulation compression and scheduling in ns-3. Control is
   **reactive** (current-slot state) and per-slot; no forecasting, no
   uncertainty treatment, no cross-cell deadline weighting. We keep their
   deployment scenario (shared link, co-located DUs) but study the budget
   coordination problem that arises when the coordination loop is slower than a
   slot.

## B. Predictive / anticipatory capacity allocation (closest methodological work)

8. **D. Bega, M. Gramaglia, M. Fiore, A. Banchs, X. Costa-Pérez**, "DeepCog:
   Cognitive Network Management in Sliced 5G Networks with Deep Learning", *IEEE
   INFOCOM 2019* (DOI 10.1109/INFOCOM.2019.8737488) and the *IEEE JSAC* 2020
   extension (DOI 10.1109/JSAC.2019.2959245). **[peer-reviewed]** Capacity
   forecasting per slice with a cost-aware loss (over-provisioning vs SLA
   violation). Differences: single-resource per slice (no coupling through a
   shared link inside the decision), no queue/deadline state, DNN trained for one
   fixed cost ratio (the trade-off point is baked into the model, not chosen at
   decision time).
9. **D. Bega et al.**, "AZTEC: Anticipatory Capacity Allocation for Zero-Touch
   Network Slicing", *IEEE INFOCOM 2020*. DOI 10.1109/INFOCOM41043.2020.9155299.
   **[peer-reviewed]** Two-timescale allocation of dedicated + shared capacity from
   DL forecasts. Closest in spirit (shared pool, advance decision). Differences:
   minute-scale slice orchestration, monetary cost objective, no deadline
   feasibility notion; our decision is a per-cell fronthaul budget at 10 ms with
   an explicit newsvendor/KKT rule driven by forecast quantiles.
10. **V. Sciancalepore et al.**, "Mobile traffic forecasting for maximizing 5G
    network slicing resource utilization", *IEEE INFOCOM 2017*.
    DOI 10.1109/INFOCOM.2017.8057230. **[peer-reviewed]** Forecast-driven slice
    admission; point forecasts.
11. **Predictive DBA for PON-based fronthaul**: A. M. Mikaeil, W. Hu, S. B. Hussain,
    "Traffic-Estimation-Based Low-Latency XGS-PON Mobile Front-Haul for Small-Cell
    C-RAN Based on an Adaptive Learning Neural Network", *Applied Sciences*
    8(7):1097, 2018, DOI 10.3390/app8071097 **[peer-reviewed]**; and the LSTM
    variant by M. Zhang, B. Xu et al., *Chinese Optics Letters* 17(7):070603, 2019,
    DOI 10.3788/COL201917.070603 **[peer-reviewed]**. Grants are pre-computed
    from **point** predictions of ONU buffer occupancy to remove the DBA
    round-trip. Same "decide before you observe" structure as ours, but no
    uncertainty representation and no deadline-differentiated cells. Cooperative
    DBA (CTI-based, e.g. *J. Opt. Commun. Netw.* 12(5), 2020) removes the need
    to forecast by exporting the DU schedule; it is the natural alternative when
    such an interface exists.
12. **F. Kavehmadavani, V.-D. Nguyen, T. X. Vu, S. Chatzinotas**, "Intelligent
    Traffic Steering in Beyond 5G Open RAN Based on LSTM Traffic Prediction",
    *IEEE Trans. Wireless Commun.*, 2023. DOI 10.1109/TWC.2023.3254903. **[peer-reviewed]** Long-timescale LSTM
    forecasts feed a short-timescale allocation with a fronthaul capacity
    constraint; point forecasts, no deadlines.

## C. Uncertainty-aware forecasting and conformal allocation

13. **K. M. Cohen, S. Park, O. Simeone, P. Popovski, S. Shamai**, "Guaranteed Dynamic Scheduling
    of Ultra-Reliable Low-Latency Traffic via Conformal Prediction", *IEEE
    Wireless Communications Letters*, 2023 (arXiv:2302.07675). **[peer-reviewed]**
    Online conformal prediction adjusts the amount of pre-allocated URLLC
    resources so that a reliability target holds irrespective of predictor
    quality. Single traffic stream, radio resources. Our adaptive-conformal
    ablation (per-cell level offset) follows this idea; in our coupled
    multi-cell setting it did **not** improve the weighted objective (see
    results), which is itself a useful finding.
14. **I. Gibbs, E. Candès**, "Adaptive Conformal Inference Under Distribution
    Shift", *NeurIPS 2021*. **[peer-reviewed]** The online level-update rule we
    use for calibration.
15. **V. Kasuluru, L. Blanco, C. J. Vaca-Rubio, E. Zeydan**, "On the Impact of PRB
    Load Uncertainty Forecasting for Sustainable Open RAN", arXiv:2407.14400,
    2024. **[preprint]** Probabilistic PRB-load
    forecasting (DeepAR/Transformer) and the over/under-provisioning effect of
    picking a percentile. Confirms that percentile selection is a knob, but the
    percentile is chosen globally rather than derived from a coupled allocation.
16. **CONTINA**, arXiv:2504.13961, 2025 **[preprint]**; **MetaSTNet**,
    arXiv:2505.21553, 2025 **[preprint]**: adaptive conformal intervals for
    (transport / cellular) traffic demand. Show current interest in calibrated
    traffic intervals; none closes the loop with a capacity-constrained allocation.

## D. Foundational methods reused

17. **W. Willinger, M. S. Taqqu, R. Sherman, D. V. Wilson**, "Self-similarity through
    high-variability: statistical analysis of Ethernet LAN traffic at the source
    level", *IEEE/ACM Trans. Netw.* 5(1):71-86, 1997. **[peer-reviewed]**
    Heavy-tailed ON/OFF sources -> self-similar aggregate traffic; basis of our
    synthetic burst model.
18. **Multi-item newsvendor with a budget constraint** (Hadley & Whitin, *Analysis
    of Inventory Systems*, 1963; textbook treatment in Porteus 2002). The
    KKT / "equal marginal tail probability" structure of our allocation rule is
    this classical result applied with learned quantiles and deadline weights.
19. **Le Boudec & Thiran**, *Network Calculus*, Springer 2001. Arrival/service
    curve argument behind the deadline-feasible rate r*.

## What the review implies for the contribution

* The fronthaul-specific literature (2, 4, 5, 7) establishes the model: load
  depends on scheduled PRB-layers; several RUs share an oversubscribed packet
  link; late U-plane packets are lost. It handles the sharing either by static
  dimensioning (5, 6) or by reactive per-slot compression/scheduling (7).
* The forecast-driven allocation literature (8-12) shows that anticipatory
  allocation of a shared resource pays off, but uses **point** forecasts (or a
  DNN with a fixed cost ratio), and none combines forecasts with **per-cell
  deadline feasibility** or **queue state**.
* The conformal literature (13-16) provides calibrated uncertainty for a single
  stream but does not couple cells through a shared capacity constraint.

**Gap targeted (candidate contribution):** a budget-coordination rule for a
shared 7-2x fronthaul link that (a) uses a *deadline-feasible rate* (not the
mean volume) as the per-cell demand, (b) represents forecast uncertainty with
learned quantiles, and (c) allocates the coupled capacity by equalising the
priority-weighted probability that the marginal budget unit is needed
(constrained newsvendor / KKT), evaluated against a competent deadline-aware
reactive baseline and a point-forecast ablation on identical traces. We
describe this as a *proposed method*; the individual ingredients are known,
the combination and the evaluation in the fronthaul budget setting are what
is new here.
