"""ACAFS -- Adaptive Channel-Aware Functional Split (rank-driven stream selection).

Bandwidth model (per cell, per OFDM symbol, bits)
--------------------------------------------------
Following 3GPP TR 38.801 (split options 1-8) and O-RAN WG4 (split 7.2x), the
uplink fronthaul payload of the candidate splits scales as

    7.1 / 7.2x antenna-space  (all M antenna streams):   R_ant  = 2 M N b
    7.2x beam-space           (r combined streams):      R_beam = 2 r N b + weights overhead
    6   (MAC-PHY)             (decoded transport blocks): R_6    = r N eta

with ``b`` I/Q bits per component and ``eta`` the spectral efficiency of the
decoded layers (bits per resource element, <= 7.4 for 256-QAM at rate 0.93).
Ordering is therefore  R_6 << R_beam <= R_ant  -- the *reference* against
which savings are reported is the fixed antenna-space split, not split 6.
(The repository's earlier documentation reported "reduction vs fixed Split 6"
with split 6 as the most expensive option; that ordering is inverted and is
corrected here.)

Decision rule
-------------
Given the estimated numerical rank ``r`` of the received matrix:

    rho = r / M
    rho <  tau_high  ->  7.2x beam-space with  r_tx = max(r, ceil(tau_low * M))  streams
    rho >= tau_high  ->  split 6 if the RU is allowed/able to run the full UL PHY,
                         otherwise stay antenna-space (no saving).

``tau_low`` is a stream floor guarding against rank under-estimation from a
single symbol; ``tau_high`` marks the point where beam-space saves too little
to justify RU-side combining.  Split 6 is gated by ``allow_split6`` because it
requires RU compute for equalisation (see the matrix-inversion benchmark in
``matinv_bench`` for what that costs).

Proposition 5 (expected saving under a rank distribution)
---------------------------------------------------------
For r uniform on {1, ..., M} the expected saving vs antenna-space is the
average of the per-rank saving under the rule above; ``theorem5_bound``
evaluates that closed form numerically.  It is a *model prediction*, not an
upper bound; the simulated saving can exceed it when ranks are concentrated
at low values (high SNR).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class FunctionalSplit(Enum):
    SPLIT_72x = "7.2x"   # beam-space, r streams
    SPLIT_71 = "7.1"     # antenna-space, M streams (also 7.2x category A)
    SPLIT_6 = "6"        # MAC-PHY, transport blocks


@dataclass
class SplitBandwidthModel:
    M: int
    N: int = 1200
    bits_iq: int = 16
    spectral_eff: float = 6.0      # bits per RE for decoded layers (64-QAM-ish average)
    coherence_symbols: int = 14    # beam weights refreshed once per slot

    def antenna_space_bits(self) -> float:
        return 2.0 * self.M * self.N * self.bits_iq

    def beam_space_bits(self, r_tx: int) -> float:
        weights = 2.0 * self.M * r_tx * self.bits_iq / self.coherence_symbols
        return 2.0 * r_tx * self.N * self.bits_iq + weights

    def split6_bits(self, r: int) -> float:
        return float(r) * self.N * self.spectral_eff

    def bits(self, split: FunctionalSplit, r: int, r_tx: int) -> float:
        if split is FunctionalSplit.SPLIT_71:
            return self.antenna_space_bits()
        if split is FunctionalSplit.SPLIT_72x:
            return self.beam_space_bits(r_tx)
        return self.split6_bits(max(r, 1))


class ACAFSController:
    def __init__(self, tau_low: float = 0.15, tau_high: float = 0.55, M: int = 64,
                 allow_split6: bool = True, bw_model: SplitBandwidthModel | None = None):
        if not 0.0 <= tau_low < tau_high <= 1.0:
            raise ValueError("need 0 <= tau_low < tau_high <= 1")
        if M < 1:
            raise ValueError("M must be positive")
        self.tau_low, self.tau_high, self.M = float(tau_low), float(tau_high), int(M)
        self.allow_split6 = allow_split6
        self.bw = bw_model or SplitBandwidthModel(M=M)
        self.stream_floor = max(1, int(np.ceil(self.tau_low * self.M)))

    # -- decisions ------------------------------------------------------------
    def select_split(self, rank: int) -> tuple[FunctionalSplit, int]:
        """Returns (split, streams transmitted)."""
        r = int(np.clip(rank, 0, self.M))
        if r == 0:                       # no signal energy: send the floor in beam-space
            return FunctionalSplit.SPLIT_72x, self.stream_floor
        if r / self.M < self.tau_high:
            return FunctionalSplit.SPLIT_72x, max(r, self.stream_floor)
        if self.allow_split6:
            return FunctionalSplit.SPLIT_6, r
        return FunctionalSplit.SPLIT_71, self.M

    def select_splits_batch(self, ranks) -> list[FunctionalSplit]:
        return [self.select_split(int(r))[0] for r in np.atleast_1d(ranks)]

    # -- bandwidth ------------------------------------------------------------
    def bits_for_rank(self, rank: int) -> float:
        split, r_tx = self.select_split(rank)
        return self.bw.bits(split, int(np.clip(rank, 1, self.M)), r_tx)

    def bw_reduction_for_rank(self, rank: int) -> float:
        ref = self.bw.antenna_space_bits()
        return float(1.0 - self.bits_for_rank(rank) / ref)

    def expected_bw_reduction(self, ranks) -> float:
        ranks = np.atleast_1d(ranks)
        if ranks.size == 0:
            return 0.0
        return float(np.mean([self.bw_reduction_for_rank(int(r)) for r in ranks]))

    def split_distribution(self, ranks) -> dict[str, float]:
        splits = self.select_splits_batch(ranks)
        n = max(len(splits), 1)
        return {s.value: sum(1 for x in splits if x is s) / n for s in FunctionalSplit}

    # -- analysis -------------------------------------------------------------
    @staticmethod
    def theorem5_bound(M: int, tau_low: float, tau_high: float, allow_split6: bool = True,
                       bw_model: SplitBandwidthModel | None = None) -> float:
        """Proposition 5: expected saving for r ~ Uniform{1..M} under the decision rule."""
        ctrl = ACAFSController(tau_low, tau_high, M, allow_split6, bw_model)
        return ctrl.expected_bw_reduction(np.arange(1, M + 1))
