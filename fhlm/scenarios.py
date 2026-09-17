"""Scenario definitions and seed splits (train / validation / test never overlap)."""
from __future__ import annotations

from dataclasses import replace
from typing import Dict, List

from .config import SimConfig, TrafficConfig, ControlConfig, NetworkConfig

# Seeds: disjoint ranges so that no test trace is ever seen in training or tuning.
TRAIN_SEEDS: List[int] = list(range(1000, 1016))
VAL_SEEDS: List[int] = list(range(2000, 2004))
TEST_SEEDS: List[int] = list(range(3000, 3005))

# Traffic families ------------------------------------------------------------
NOMINAL = dict(regime_mean_slots=2000.0, regime_log_sigma=0.25, burst_rate_scale=1.0,
               on_duration_scale=1.0, flash_crowd_prob=0.0, pareto_alpha_on=1.5, pareto_alpha_off=1.8)

SCENARIOS: Dict[str, TrafficConfig] = {
    # offered fronthaul load relative to usable link capacity
    "low": TrafficConfig(load=0.50, **NOMINAL),
    "moderate": TrafficConfig(load=0.65, **NOMINAL),
    "high": TrafficConfig(load=0.80, **NOMINAL),
    # flash crowds push the offered load above capacity for ~1 s at a time
    "overload_bursts": TrafficConfig(load=0.80, **{**NOMINAL, "flash_crowd_prob": 0.15, "flash_crowd_mult": 1.8}),
    # held-out distribution shift: burstier traffic than anything in training
    "shift": TrafficConfig(load=0.80, **{**NOMINAL, "burst_rate_scale": 1.5, "on_duration_scale": 1.5,
                                        "pareto_alpha_on": 1.2}),
}

# Loads used for training traces (nominal traffic family)
TRAIN_LOADS = [0.5, 0.65, 0.8, 0.95]
VAL_SCENARIOS = ["moderate", "high"]

DEFAULT_SLOTS = 20000
DEFAULT_WARMUP = 1000


def make_config(scenario: str, seed: int, num_slots: int = DEFAULT_SLOTS, warmup: int = DEFAULT_WARMUP,
                interval_slots: int = 20, telemetry_delay_slots: int = 2) -> SimConfig:
    return SimConfig(num_slots=num_slots, warmup_slots=warmup, seed=seed, network=NetworkConfig(),
                     traffic=replace(SCENARIOS[scenario]),
                     control=ControlConfig(interval_slots=interval_slots, telemetry_delay_slots=telemetry_delay_slots))


def train_config(load: float, seed: int, num_slots: int = DEFAULT_SLOTS, interval_slots: int = 20,
                 telemetry_delay_slots: int = 2) -> SimConfig:
    return SimConfig(num_slots=num_slots, warmup_slots=0, seed=seed, network=NetworkConfig(),
                     traffic=TrafficConfig(load=load, **NOMINAL),
                     control=ControlConfig(interval_slots=interval_slots, telemetry_delay_slots=telemetry_delay_slots))
