"""Literature content shared by build_slides.py.

All entries were verified against a primary page on 17 Sep 2026; see
docs/research_review.md for access level (full text vs abstract) and links.
"""

REFERENCES = {
    # rows for the literature comparison table on slide 4
    "comparison_rows": [
        ["Standardised I/Q compression",
         "O-RAN WG4 CUS Annex A [5]; Silva et al., JCIS 2022 [6]",
         "per-PRB BFP / block scaling / μ-law, 4-bit exponent; SQNR vs iqWidth, single RU",
         "our BFP baseline reproduces this bit accounting; their per-PRB method selection ≈ our per-RU menu, but no capacity constraint"],
        ["Fronthaul survey / functional splits",
         "Park et al., IEEE SPM 2014 [1]; Larsen et al., COMST 2019 [3]; 3GPP TR 38.801 Annex A [4]",
         "quantize-and-forward theory; UL bit-rate per split: Opt.6 ≈ 5.6 Gb/s ≪ Opt.7b 54–86 ≪ Opt.8 157 Gb/s",
         "source of the split-ordering correction in ACAFS; motivates rank-adaptive stream count"],
        ["Shared fronthaul, centralised control",
         "Lagén et al., IEEE ComMag 2021/2022 [7][9]; IEEE TMC 2023 [8]",
         "several cells on one FH link; DL modulation compression + MAC scheduling; ns-3 throughput",
         "template for Exp5 (per-cell operating point, common capacity); ours is UL I/Q with NMSE, no MAC"],
        ["Structured compression of channel / received matrices",
         "Wen et al., WCL 2018 (CsiNet) [15]; Qiao–Jiang–Yu, ICC 2023 / TWC 2024 [13][14]; Rahmani et al., arXiv 2025 [10]",
         "delay-domain sparsity of H; learned dimension-reduction matrices from local CSI; O-RAN BFP under TDL, BLER",
         "explains why CSEE works only on reference symbols; low-rank sketch = our RAS-BFP; BLER is the metric we still lack"],
        ["Closest single-link prior art",
         "Aswathylakshmi–Ganti, WCNC 2022 [22]; Li et al., IEEE Access 2019 [24]; Kanno et al., VTC 2023 [25]",
         "64-ant. TDL-A delay-domain low rank via blind deconvolution; bit-width vs load/SINR on one eCPRI link; SVD streams + bits per stream at one AP",
         "CSEE's structure, but data symbols removed first — hence CSEE needs reference symbols; allocator extends [24][25] to many RUs"],
        ["Learning-based split orchestration",
         "Murti et al., EuCNC 2022 [16]; IEEE TNSM 2024 [17]",
         "DQN / D3QN over minutes-scale demand traces; cost model from testbed; up to 59–69 % cost saving vs static",
         "justifies adaptive split as a topic; RL not warranted here because our rate model is closed-form per symbol"],
        ["Numerical foundations",
         "Halko–Martinsson–Tropp, SIAM Rev. 2011 [19]; Tropp 2011 [20]; Shoham–Gersho 1988 [21]",
         "randomised range finder + Frobenius bound; SRHT subspace embedding; λ-sweep / convex-hull bit allocation",
         "RAS-BFP algorithm and Thm-2 bound; allocator = Shoham–Gersho on RU menus (no algorithmic novelty claimed)"],
    ],
    "gap_statement": "Gap addressed: prior art adapts bits or streams on one link [22][24][25]; here a closed-form per-symbol predictor drives allocation across RUs sharing one link, with a metric separating signal loss from removed noise.",
    "lit_notes": """
Research context, verified against primary sources with a cutoff of 17 September 2026; the full table with access levels is in docs/research_review.md.
Row one: the O-RAN specification and Silva et al. define the block floating point baseline I implement — twelve-RE blocks, a four-bit shared exponent. Silva et al. select the compression method per PRB; I select an operating point per RU under a shared budget.
Row two: the surveys and 3GPP TR 38.801 give the bit-rate ordering of the splits; this is the source of the correction to the ACAFS model.
Row three is the closest work: Lagén and co-authors control compression for several cells sharing one fronthaul link, but for downlink modulation compression with a full ns-3 simulator. My Exp5 is the uplink I/Q analogue with an analytical predictor instead of a system-level simulator.
Row four: CsiNet shows that channel matrices are sparse in the delay domain — that is why CSEE works on reference symbols and, as I will show, not on data symbols. Qiao, Jiang and Yu learn dimension-reduction matrices for cell-free uplink; RAS-BFP does the same reduction with a randomised sketch and no training.
Row five: Murti et al. use deep RL for split orchestration because their cost model is only measurable, not closed-form. Mine is closed-form per symbol, so a rule on the estimated rank is the right tool for now.
Row six is the closest prior art, found in a second search pass: Aswathylakshmi and Ganti compress a 64-antenna TDL-A uplink through the same delay-domain low rank as CSEE, but they first separate the data symbols by blind deconvolution — which is precisely why my CSEE without that step needs reference symbols. Li et al. adapt the bit-width to load and SINR on a single eCPRI link; Kanno et al. allocate bits per SVD stream at one access point. My allocator generalises that to several RUs sharing one link with heterogeneous operating points.
Row seven: the numerical foundations — HMT for the randomised range finder and its bound, Shoham–Gersho for the allocation algorithm. I claim no novelty in these algorithms.
""",
    "ieee_list": [
        "[1] S.-H. Park, O. Simeone, O. Sahin, S. Shamai, \"Fronthaul compression for cloud radio access networks,\" IEEE Signal Process. Mag., vol. 31, no. 6, 2014. doi:10.1109/MSP.2014.2330031 (abstract)",
        "[2] M. Peng, C. Wang, V. Lau, H. V. Poor, \"Fronthaul-constrained cloud radio access networks: Insights and challenges,\" IEEE Wireless Commun., vol. 22, no. 2, 2015. (full text, author copy)",
        "[3] L. M. P. Larsen, A. Checko, H. L. Christiansen, \"A survey of the functional splits proposed for 5G mobile crosshaul networks,\" IEEE Commun. Surveys Tuts., vol. 21, no. 1, 2019. (full text)",
        "[4] 3GPP TR 38.801 (Rel-14), \"Study on new radio access technology: Radio access architecture and interfaces,\" §11.1.2, Annex A Tables A-1/A-2.",
        "[5] O-RAN Alliance WG4, \"Control, User and Synchronization Plane Specification,\" O-RAN.WG4.TS.CUS.0-R004-v19.00, Annex A (compression methods). (annex listing; BFP details cross-checked with [6])",
        "[6] M. D. L. Silva, L. Ramalho, I. Almeida, E. Medeiros, M. Berg, A. Klautau, \"A new O-RAN compression approach for improved performance on uplink signals,\" J. Commun. Inf. Syst., vol. 37, no. 1, pp. 30–41, 2022. doi:10.14209/jcis.2022.3 (full text)",
        "[7] S. Lagén, L. Giupponi, A. Hansson, X. Gelabert, \"Modulation compression in next generation RAN: Air interface and fronthaul trade-offs,\" IEEE Commun. Mag., vol. 59, no. 1, 2021. doi:10.1109/MCOM.001.2000453 (full text)",
        "[8] S. Lagén, X. Gelabert, L. Giupponi, A. Hansson, \"Fronthaul-aware scheduling strategies for dynamic modulation compression in next generation RANs,\" IEEE Trans. Mobile Comput., vol. 22, no. 5, pp. 2725–2740, 2023. (abstract)",
        "[9] S. Lagén, X. Gelabert, A. Hansson, M. Requena, L. Giupponi, \"Fronthaul compression control for shared fronthaul access networks,\" IEEE Commun. Mag., vol. 60, no. 6, 2022. doi:10.1109/MCOM.001.2100959 (full text)",
        "[10] M. Rahmani et al., \"Exploring O-RAN compression techniques in decentralized distributed MIMO systems: Reducing fronthaul load,\" arXiv:2507.04997, 2025. (preprint, full text)",
        "[11] \"Hardware implementation for O-RAN block floating point compression and decompression methods in 5G base station,\" Proc. ATC 2024. doi:10.1109/ATC63255.2024.10908174 (abstract)",
        "[12] S. Yagi et al., \"Deep learning-based nonlinear quantizer for fronthaul compression,\" Proc. OECC/PSC 2022. (abstract)",
        "[13] R. Qiao, T. Jiang, W. Yu, \"Learning-based fronthaul compression for uplink cloud radio access networks,\" Proc. IEEE ICC 2023, pp. 5928–5933. (abstract)",
        "[14] R. Qiao, T. Jiang, W. Yu, \"Meta-learning-based fronthaul compression for cloud radio access networks,\" arXiv:2403.09004, 2024; IEEE Trans. Wireless Commun., vol. 23, no. 9, 2024. (abstract)",
        "[15] C.-K. Wen, W.-T. Shih, S. Jin, \"Deep learning for massive MIMO CSI feedback,\" IEEE Wireless Commun. Lett., vol. 7, no. 5, pp. 748–751, 2018. (full text)",
        "[16] F. W. Murti, S. Ali, G. Iosifidis, M. Latva-aho, \"Learning-based orchestration for dynamic functional split and resource allocation in vRANs,\" Proc. EuCNC/6G Summit 2022. (full text)",
        "[17] F. W. Murti, S. Ali, G. Iosifidis, M. Latva-aho, \"Deep reinforcement learning for orchestrating cost-aware reconfigurations of vRANs,\" IEEE Trans. Netw. Service Manag., vol. 21, no. 1, pp. 200–216, 2024. doi:10.1109/TNSM.2023.3292713 (full text)",
        "[18] F. W. Murti, S. Ali, M. Latva-aho, \"Constrained deep reinforcement based functional split optimization in virtualized RANs,\" arXiv:2106.00011, 2021. (abstract)",
        "[19] N. Halko, P.-G. Martinsson, J. A. Tropp, \"Finding structure with randomness,\" SIAM Rev., vol. 53, no. 2, pp. 217–288, 2011. doi:10.1137/090771806 (full text)",
        "[20] J. A. Tropp, \"Improved analysis of the subsampled randomized Hadamard transform,\" Adv. Adapt. Data Anal., vol. 3, no. 1–2, pp. 115–126, 2011. (full text, preprint)",
        "[22] Aswathylakshmi P, R. K. Ganti, \"Fronthaul compression for uplink massive MIMO using matrix decomposition,\" Proc. IEEE WCNC 2022, pp. 2524–2529. doi:10.1109/WCNC51071.2022.9771783 (full text)",
        "[23] F. Wiffen, W. H. Chin, A. Doufexi, \"Distributed dimension reduction for distributed massive MIMO C-RAN with finite fronthaul capacity,\" Proc. Asilomar 2021, pp. 1228–1236. doi:10.1109/IEEECONF53345.2021.9723180 (full text)",
        "[24] L. Li et al., \"Enabling flexible link capacity for eCPRI-based fronthaul with load-adaptive quantization resolution,\" IEEE Access, vol. 7, pp. 102174–102185, 2019. doi:10.1109/ACCESS.2019.2930214 (full text)",
        "[25] I. Kanno et al., \"Adaptive bit allocation for SVD based hybrid processing of uplink cell-free massive MIMO under limited fronthaul capacity,\" Proc. IEEE VTC2023-Spring. doi:10.1109/VTC2023-Spring57618.2023.10201009 (abstract)",
        "[26] L. Liu, R. Zhang, \"Optimized uplink transmission in multi-antenna C-RAN with spatial compression and forward,\" IEEE Trans. Signal Process., vol. 63, no. 19, pp. 5083–5095, 2015. (abstract)",
        "[27] A. Martínez Alba, W. Kellerer, \"Dynamic functional split adaptation in next-generation radio access networks,\" IEEE Trans. Netw. Service Manag., vol. 19, no. 3, pp. 3239–3263, 2022. (abstract)",
        "[28] L. Wang, S. Zhou, \"On the fronthaul statistical multiplexing gain,\" IEEE Commun. Lett., vol. 21, no. 5, pp. 1099–1102, 2017. (abstract)",
        "[29] 3GPP TR 38.901 V19.4.0, \"Study on channel model for frequencies from 0.5 to 100 GHz,\" cl. 7.7.2–7.7.5 (TDL-A, delay scaling, correlation extension).",
        "[21] Y. Shoham, A. Gersho, \"Efficient bit allocation for an arbitrary set of quantizers,\" IEEE Trans. Acoust., Speech, Signal Process., vol. 36, no. 9, pp. 1445–1453, 1988. doi:10.1109/29.90373 (abstract)",
    ],
}
