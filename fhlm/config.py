"""Configuration dataclasses and derived fronthaul constants.

Units are stated explicitly everywhere:
  * time      -> slots (one NR slot at 30 kHz SCS = 0.5 ms)
  * data      -> bits (user-plane payload bits or fronthaul IQ bits)
  * capacity  -> bits per slot
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
import json


# --------------------------------------------------------------------------
# Fronthaul traffic abstraction for split 7-2x (frequency-domain IQ per PRB
# per spatial layer). Bits per PRB per OFDM symbol per layer with block
# floating point (BFP) compression: 12 subcarriers x 2 (I,Q) x mantissa bits
# + one shared exponent byte (udCompParam) per PRB (O-RAN WG4 CUS, Annex A.1).
# --------------------------------------------------------------------------
SUBCARRIERS_PER_PRB = 12
SYMBOLS_PER_SLOT = 14
RES_PER_PRB_PER_SLOT = SUBCARRIERS_PER_PRB * SYMBOLS_PER_SLOT  # 168


def fronthaul_bits_per_prb_layer_slot(mantissa_bits: int = 9, overhead_factor: float = 1.08) -> float:
    """IQ bits carried on the fronthaul for one PRB, one layer, one slot.

    overhead_factor accounts for eCPRI/Ethernet/section headers (~8% DL
    overhead is the figure quoted by Larsen et al. 2019 for split 7-2).
    """
    per_symbol = SUBCARRIERS_PER_PRB * 2 * mantissa_bits + 8
    return per_symbol * SYMBOLS_PER_SLOT * overhead_factor


@dataclass
class CellClass:
    """Service class hosted by a cell (single dominant class per cell)."""

    name: str
    deadline_slots: int          # max DU queueing delay before a bit is discarded (slots)
    priority: float = 1.0        # operator priority weight (dimensionless)
    # spectral efficiency: user bits per PRB-layer per slot (data REs x bits/RE)
    se_bits_per_prb_layer: float = 168 * 0.8 * 3.0
    layers: int = 4
    # traffic-shape parameters (relative; absolute scale set by load target)
    burst_fraction: float = 0.5  # share of mean load carried by the ON/OFF component
    on_mean_slots: float = 20.0  # mean ON duration of the bursty component
    off_mean_slots: float = 80.0 # mean OFF duration
    smooth_cv: float = 0.3       # coefficient of variation of the smooth component per slot


@dataclass
class NetworkConfig:
    slot_duration_s: float = 0.5e-3
    prbs_per_cell: int = 273                # 100 MHz @ 30 kHz SCS
    mantissa_bits: int = 9                  # BFP-9
    overhead_factor: float = 1.08
    link_capacity_gbps: float = 25.0        # shared aggregation link (25GE)
    control_plane_reserve: float = 0.03     # fraction of link reserved for C/M/S-plane
    cells: List[CellClass] = field(default_factory=list)

    def __post_init__(self):
        if not self.cells:
            self.cells = default_cells()

    # --- derived quantities -------------------------------------------------
    @property
    def num_cells(self) -> int:
        return len(self.cells)

    @property
    def fh_bits_per_prb_layer(self) -> float:
        return fronthaul_bits_per_prb_layer_slot(self.mantissa_bits, self.overhead_factor)

    @property
    def link_bits_per_slot(self) -> float:
        return self.link_capacity_gbps * 1e9 * self.slot_duration_s

    @property
    def usable_bits_per_slot(self) -> float:
        """U-plane capacity available to the cells per slot (bits/slot)."""
        return self.link_bits_per_slot * (1.0 - self.control_plane_reserve)

    def cell_peak_bits_per_slot(self, i: int) -> float:
        """Maximum fronthaul demand of cell i in one slot (all PRBs, all layers)."""
        return self.prbs_per_cell * self.cells[i].layers * self.fh_bits_per_prb_layer

    @property
    def peak_bits_per_slot(self) -> List[float]:
        return [self.cell_peak_bits_per_slot(i) for i in range(self.num_cells)]

    @property
    def oversubscription(self) -> float:
        return sum(self.peak_bits_per_slot) / self.usable_bits_per_slot

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["derived"] = {
            "fh_bits_per_prb_layer_slot": self.fh_bits_per_prb_layer,
            "link_bits_per_slot": self.link_bits_per_slot,
            "usable_bits_per_slot": self.usable_bits_per_slot,
            "cell_peak_bits_per_slot": self.peak_bits_per_slot,
            "oversubscription": self.oversubscription,
        }
        return d


def default_cells() -> List[CellClass]:
    """Eight heterogeneous cells: 3 low-latency (LL) + 5 eMBB.

    Low-latency cells host XR/industrial style traffic: tight DU queueing
    deadline (4 slots = 2 ms), burstier, smaller volume (see
    TrafficConfig.load_share). eMBB cells tolerate 20 slots = 10 ms of DU
    queueing. Spectral efficiencies differ so that the fronthaul cost per
    user bit differs across cells. With a 25GE link the aggregate cell peak
    is ~2.4x the usable link capacity (statistical-multiplexing design).
    The ON-state arrival rate of every cell stays below its own air-interface
    peak at the design loads, so violations are caused by the shared
    fronthaul, not by the radio.
    """
    ll = dict(deadline_slots=4, priority=3.0, burst_fraction=0.5,
              on_mean_slots=10.0, off_mean_slots=30.0, smooth_cv=0.4)
    embb = dict(deadline_slots=20, priority=1.0, burst_fraction=0.5,
                on_mean_slots=30.0, off_mean_slots=90.0, smooth_cv=0.3)
    return [
        CellClass("LL-0", se_bits_per_prb_layer=168 * 0.8 * 2.5, **ll),
        CellClass("LL-1", se_bits_per_prb_layer=168 * 0.8 * 4.0, **ll),
        CellClass("LL-2", se_bits_per_prb_layer=168 * 0.8 * 3.0, **ll),
        CellClass("eMBB-0", se_bits_per_prb_layer=168 * 0.8 * 2.0, **embb),
        CellClass("eMBB-1", se_bits_per_prb_layer=168 * 0.8 * 3.5, **embb),
        CellClass("eMBB-2", se_bits_per_prb_layer=168 * 0.8 * 4.5, **embb),
        CellClass("eMBB-3", se_bits_per_prb_layer=168 * 0.8 * 5.5, **embb),
        CellClass("eMBB-4", se_bits_per_prb_layer=168 * 0.8 * 3.0, **embb),
    ]


@dataclass
class TrafficConfig:
    """Scenario-level traffic parameters (synthetic traffic model)."""

    load: float = 0.8                 # mean offered fronthaul load / usable link capacity
    # slow regime process: piecewise-constant multiplier per cell
    regime_mean_slots: float = 2000.0 # mean duration of a regime (1 s)
    regime_log_sigma: float = 0.25    # log-normal spread of regime multipliers
    # scale multipliers applied on top of the CellClass burst parameters
    burst_rate_scale: float = 1.0     # scales the ON-state intensity (peak/mean ratio)
    on_duration_scale: float = 1.0    # scales mean ON duration
    pareto_alpha_on: float = 1.5      # tail index of ON durations (smaller = heavier tail)
    pareto_alpha_off: float = 1.8     # tail index of OFF durations
    flash_crowd_prob: float = 0.0     # per-regime probability of a flash-crowd regime
    flash_crowd_mult: float = 1.8     # load multiplier during a flash crowd
    se_drift_sigma: float = 0.02      # per-regime relative drift of spectral efficiency
    load_share: List[float] | None = None  # per-cell share of total load (default: LL 0.6 x eMBB)


@dataclass
class ControlConfig:
    interval_slots: int = 20      # T: budgets are fixed for this many slots (10 ms)
    telemetry_delay_slots: int = 2  # tau: controller sees state that is tau slots old (1 ms)


@dataclass
class SimConfig:
    num_slots: int = 20000
    warmup_slots: int = 1000
    seed: int = 0
    network: NetworkConfig = field(default_factory=NetworkConfig)
    traffic: TrafficConfig = field(default_factory=TrafficConfig)
    control: ControlConfig = field(default_factory=ControlConfig)

    def to_json(self) -> str:
        d = asdict(self)
        d["network"] = self.network.to_dict()
        return json.dumps(d, indent=2, default=float)
