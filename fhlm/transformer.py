"""Link-aware cross-cell quantile Transformer (LCQT) for the deadline-feasible rate r*.

Drop-in replacement for QuantileGBMForecaster: same target (r* of the unseen
horizon, normalised by the cell peak), same six quantile levels, same
predict_quantiles(obs) -> [N, K] bits/slot interface, so the KKT allocation
rule in proposed.py is used unchanged.

Architecture (one forward pass per control epoch, all N cells jointly):

  1. Patch tokens. The observed per-slot fronthaul demand of each cell is cut
     into the last P horizons (patch length H = T + tau slots, PatchTST-style).
     Each patch is the H normalised slot demands plus three patch statistics
     (r* of the patch at the cell's deadline, mean, max). A summary token
     carries the 28 hand-made features of the GBM forecaster.
  2. Temporal encoder (shared by all cells): pre-norm Transformer encoder over
     [summary, patch_1..patch_P] with learned positional embeddings.
  3. Deadline/priority FiLM: the summary output is scaled and shifted by an
     affine map of (D_i / H, priority_i), so one network serves both classes.
  4. Link-aware cross-cell attention: one Transformer layer whose tokens are the
     N cells that share the link. Bursts that coincide across cells are what
     make the shortage, and a per-cell model cannot see them.
  5. Non-crossing quantile head: q_1 = softplus(a_1), q_k = q_{k-1} + softplus(a_k).

Training loss: pinball loss averaged over levels, each cell weighted by its
operator priority (the allocation pays w_i per missing bit, so errors of the
low-latency cells cost more). Trained on TRAINING seeds, early-stopped on
VALIDATION seeds, never sees TEST seeds.
"""
from __future__ import annotations

import time
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

from .config import NetworkConfig, ControlConfig
from .simulator import Observation
from .traffic import TrafficTrace
from .demand import required_rates
from .forecast import (DEFAULT_QUANTILES, NUM_LAG_INTERVALS, build_features, feature_names, forecast_metrics,
                       _scale)

NUM_PATCHES = 16
PATCH_STATS = 3


def build_patches(history_fh: np.ndarray, deadlines: np.ndarray, scale: np.ndarray, H: int,
                  P: int = NUM_PATCHES) -> np.ndarray:
    """[N, P, H + 3] patch tokens of the observed history (oldest first, zero-padded if short)."""
    n, L = history_fh.shape
    out = np.zeros((n, P, H + PATCH_STATS), dtype=np.float32)
    for k in range(P):
        hi = L - k * H
        lo = hi - H
        if lo < 0:
            break
        seg = history_fh[:, lo:hi] / scale[:, None]
        j = P - 1 - k
        out[:, j, :H] = seg
        out[:, j, H] = required_rates(history_fh[:, lo:hi], deadlines) / scale
        out[:, j, H + 1] = seg.mean(1)
        out[:, j, H + 2] = seg.max(1)
    return out


def cell_conditioning(net: NetworkConfig, ctrl: ControlConfig) -> np.ndarray:
    H = ctrl.interval_slots + ctrl.telemetry_delay_slots
    d = np.array([c.deadline_slots for c in net.cells], dtype=np.float32) / H
    p = np.array([c.priority for c in net.cells], dtype=np.float32)
    return np.stack([d, p / p.max()], axis=1)


def build_sequence_dataset(traces: List[TrafficTrace], net: NetworkConfig, ctrl: ControlConfig,
                           P: int = NUM_PATCHES):
    """Rows = (trace, decision epoch); every row holds all N cells (needed for cross-cell attention)."""
    T = ctrl.interval_slots
    tau = ctrl.telemetry_delay_slots
    H = T + tau
    min_hist = max((NUM_LAG_INTERVALS + 1) * H, P * H)
    scale = _scale(net)
    deadlines = np.array([c.deadline_slots for c in net.cells])
    Xp, Xf, Y = [], [], []
    for tr in traces:
        for t in range(0, tr.num_slots - T, T):
            obs_slot = t - tau
            if obs_slot < min_hist:
                continue
            hist = tr.fh_demand_bits[:, :obs_slot]
            Xp.append(build_patches(hist, deadlines, scale, H, P))
            Xf.append(build_features(hist, tr.se[:, obs_slot], net, ctrl).astype(np.float32))
            Y.append((required_rates(tr.fh_demand_bits[:, obs_slot:t + T], deadlines) / scale).astype(np.float32))
    return np.stack(Xp), np.stack(Xf), np.stack(Y)


def _make_net(H: int, F: int, K: int, d: int, heads: int, layers: int, P: int, cross: bool):
    import torch
    import torch.nn as nn

    class LCQTNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.patch = nn.Linear(H + PATCH_STATS, d)
            self.summary = nn.Linear(F, d)
            self.pos = nn.Parameter(torch.randn(P + 1, d) * 0.02)
            enc = nn.TransformerEncoderLayer(d, heads, 2 * d, dropout=0.1, batch_first=True, norm_first=True)
            self.temporal = nn.TransformerEncoder(enc, layers, enable_nested_tensor=False)
            self.film = nn.Linear(2, 2 * d)
            self.cross = None
            if cross:
                cenc = nn.TransformerEncoderLayer(d, heads, 2 * d, dropout=0.1, batch_first=True, norm_first=True)
                self.cross = nn.TransformerEncoder(cenc, 1, enable_nested_tensor=False)
            self.norm = nn.LayerNorm(d)
            self.head = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, K))

        def forward(self, xp, xf, cond):
            B, N, P_, _ = xp.shape
            tok = torch.cat([self.summary(xf).unsqueeze(2), self.patch(xp)], dim=2) + self.pos
            z = self.temporal(tok.reshape(B * N, P_ + 1, d))[:, 0].reshape(B, N, d)
            g, b = self.film(cond).chunk(2, dim=-1)
            z = z * (1.0 + g) + b
            if self.cross is not None:
                z = self.cross(z)
            a = self.head(self.norm(z))
            return torch.cumsum(nn.functional.softplus(a), dim=-1)

    return LCQTNet()


class TransformerQuantileForecaster:
    """Link-aware cross-cell quantile Transformer (see module docstring)."""

    def __init__(self, quantiles=DEFAULT_QUANTILES, d_model: int = 48, heads: int = 4, layers: int = 2,
                 patches: int = NUM_PATCHES, cross_cell: bool = True, priority_weighted: bool = True):
        self.quantiles = tuple(quantiles)
        self.hp = dict(d_model=d_model, heads=heads, layers=layers, patches=patches, cross_cell=cross_cell,
                       priority_weighted=priority_weighted)
        self.net = None
        self.dims: Dict[str, int] = {}
        self.meta: Dict[str, Any] = {}
        self._cond = None

    @property
    def median_index(self) -> int:
        return int(np.argmin(np.abs(np.array(self.quantiles) - 0.5)))

    def _build(self, H: int, F: int):
        hp = self.hp
        self.dims = {"H": H, "F": F}
        self.net = _make_net(H, F, len(self.quantiles), hp["d_model"], hp["heads"], hp["layers"],
                             hp["patches"], hp["cross_cell"])

    def fit(self, train: Tuple[np.ndarray, np.ndarray, np.ndarray], val: Tuple[np.ndarray, np.ndarray, np.ndarray],
            cond: np.ndarray, priorities: np.ndarray, epochs: int = 40, batch: int = 64, lr: float = 2e-3,
            patience: int = 8, seed: int = 0, threads: int = 4) -> Dict[str, Any]:
        import torch
        torch.manual_seed(seed)
        torch.set_num_threads(threads)
        Xp, Xf, Y = train
        Vp, Vf, VY = val
        self._build(Xp.shape[-1] - PATCH_STATS, Xf.shape[-1])
        self._cond = cond.astype(np.float32)
        levels = torch.tensor(self.quantiles, dtype=torch.float32)
        w = torch.tensor(priorities / priorities.mean() if self.hp["priority_weighted"] else np.ones_like(priorities),
                         dtype=torch.float32)
        c = torch.tensor(self._cond)
        tXp, tXf, tY = map(torch.from_numpy, (Xp, Xf, Y))
        opt = torch.optim.AdamW(self.net.parameters(), lr=lr, weight_decay=1e-4)
        steps = epochs * int(np.ceil(len(Y) / batch))
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps, pct_start=0.1)
        best, best_state, bad, hist = np.inf, None, 0, []
        t0 = time.perf_counter()
        for ep in range(epochs):
            self.net.train()
            perm = torch.randperm(len(Y))
            tot = 0.0
            for s in range(0, len(Y), batch):
                idx = perm[s:s + batch]
                q = self.net(tXp[idx], tXf[idx], c.expand(len(idx), -1, -1))
                d = tY[idx].unsqueeze(-1) - q
                pin = torch.maximum(levels * d, (levels - 1) * d).mean(-1)          # [B, N]
                loss = (pin * w).mean()
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
                opt.step()
                sched.step()
                tot += loss.item() * len(idx)
            vq = self._predict_batch(Vp, Vf)
            vm = forecast_metrics(vq.reshape(-1, len(self.quantiles)), VY.reshape(-1), self.quantiles)
            hist.append({"epoch": ep, "train_loss": tot / len(Y), "val_pinball": vm["pinball_mean"]})
            print(f"[lcqt] epoch {ep:2d} train {tot / len(Y):.5f} val pinball {vm['pinball_mean']:.5f}", flush=True)
            if vm["pinball_mean"] < best - 1e-6:
                best, bad = vm["pinball_mean"], 0
                best_state = {k: v.detach().clone() for k, v in self.net.state_dict().items()}
            else:
                bad += 1
                if bad >= patience:
                    break
        self.net.load_state_dict(best_state)
        self.net.eval()
        n_params = int(sum(p.numel() for p in self.net.parameters()))
        info = {"train_rows": int(len(Y)), "train_time_s": time.perf_counter() - t0, "epochs_run": len(hist),
                "n_params": n_params, "history": hist,
                "val": forecast_metrics(self._predict_batch(Vp, Vf).reshape(-1, len(self.quantiles)),
                                        VY.reshape(-1), self.quantiles)}
        self.meta.update({k: v for k, v in info.items() if k != "history"})
        return info

    def _predict_batch(self, Xp: np.ndarray, Xf: np.ndarray, batch: int = 512) -> np.ndarray:
        import torch
        self.net.eval()
        c = torch.tensor(self._cond)
        out = []
        with torch.no_grad():
            for s in range(0, len(Xp), batch):
                xp = torch.from_numpy(Xp[s:s + batch])
                out.append(self.net(xp, torch.from_numpy(Xf[s:s + batch]), c.expand(len(xp), -1, -1)).numpy())
        return np.concatenate(out)

    def predict_quantiles(self, obs: Observation) -> np.ndarray:
        """[N, K] forecast quantiles of the deadline-feasible rate in bits/slot."""
        import torch
        H = obs.ctrl.interval_slots + obs.ctrl.telemetry_delay_slots
        scale = _scale(obs.net)
        xp = build_patches(obs.history_fh_demand, obs.deadlines, scale, H, self.hp["patches"])
        xf = build_features(obs.history_fh_demand, obs.se, obs.net, obs.ctrl).astype(np.float32)
        with torch.no_grad():
            q = self.net(torch.from_numpy(xp)[None], torch.from_numpy(xf)[None],
                         torch.from_numpy(self._cond)[None])[0].numpy()
        return q.astype(float) * scale[:, None]

    def save(self, path: str) -> None:
        import torch
        torch.save({"quantiles": self.quantiles, "hp": self.hp, "dims": self.dims, "cond": self._cond,
                    "state": self.net.state_dict(), "meta": self.meta}, path)

    @classmethod
    def load(cls, path: str, threads: int = 1) -> "TransformerQuantileForecaster":
        import torch
        torch.set_num_threads(threads)
        d = torch.load(path, map_location="cpu", weights_only=False)
        hp = dict(d["hp"])
        obj = cls(quantiles=d["quantiles"], d_model=hp["d_model"], heads=hp["heads"], layers=hp["layers"],
                  patches=hp["patches"], cross_cell=hp["cross_cell"], priority_weighted=hp["priority_weighted"])
        obj._build(d["dims"]["H"], d["dims"]["F"])
        obj.net.load_state_dict(d["state"])
        obj.net.eval()
        obj._cond = d["cond"]
        obj.meta = d.get("meta", {})
        return obj
