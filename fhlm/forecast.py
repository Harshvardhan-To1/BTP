"""Per-cell probabilistic forecasting of the deadline-feasible fronthaul rate.

Target: y_i = r*(a_i[t - tau : t + T], D_i) / peak_i, the minimum constant
budget rate (bits/slot, normalised by the cell's peak fronthaul rate) that
would carry the arrivals the controller has not yet seen within the cell's
deadline (see demand.py). It depends only on exogenous traffic, never on the
controller, so the training data are policy independent.

Two forecasters expose the same interface (predict_quantiles(obs) -> [N, K]
in bits/slot):

  * QuantileGBMForecaster    - gradient-boosted quantile regression (one model
                               per quantile level) trained on traffic traces
                               from TRAINING seeds only.
  * WindowQuantileForecaster - non-ML reference: empirical quantiles of the
                               realised r* over the last W horizons of the cell.

Features use only information available at the decision time (history up to
t - tau and the current spectral efficiency) and are normalised by
configuration constants (cell peak rate), never by data statistics, so there
is no preprocessing leakage.
"""
from __future__ import annotations

from typing import List, Optional, Dict, Any
import pickle
import time

import numpy as np

from .config import NetworkConfig, ControlConfig
from .simulator import Observation
from .traffic import TrafficTrace
from .demand import required_rates

DEFAULT_QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.9, 0.95)
NUM_LAG_INTERVALS = 6
NUM_LAST_SLOTS = 4
NUM_RSTAR_LAGS = 3


def feature_names(num_cells: int) -> List[str]:
    names = [f"lag_mean_{k}" for k in range(1, NUM_LAG_INTERVALS + 1)]
    names += ["lag_mean", "lag_std", "lag_max", "ewma_fast", "ewma_slow"]
    names += [f"last_slot_{k}" for k in range(1, NUM_LAST_SLOTS + 1)]
    names += [f"rstar_lag_{k}" for k in range(1, NUM_RSTAR_LAGS + 1)]
    names += ["se_rel", "deadline_rel"]
    names += [f"cell_{i}" for i in range(num_cells)]
    return names


def _scale(net: NetworkConfig) -> np.ndarray:
    """Normalisation constant per cell: peak fronthaul bits per slot."""
    return np.array(net.peak_bits_per_slot)


def build_features(history_fh: np.ndarray, se: np.ndarray, net: NetworkConfig, ctrl: ControlConfig) -> np.ndarray:
    """Feature matrix [N, F] from observed history (columns are past slots only)."""
    n = history_fh.shape[0]
    T = ctrl.interval_slots
    H = T + ctrl.telemetry_delay_slots
    scale = _scale(net)
    deadlines = np.array([c.deadline_slots for c in net.cells])
    L = history_fh.shape[1]
    feats = np.zeros((n, len(feature_names(n))))
    lag_means = np.zeros((n, NUM_LAG_INTERVALS))
    for k in range(NUM_LAG_INTERVALS):
        hi = L - k * H
        lo = max(hi - H, 0)
        if hi <= 0:
            break
        lag_means[:, k] = history_fh[:, lo:hi].mean(1)
    col = 0
    feats[:, col:col + NUM_LAG_INTERVALS] = lag_means / scale[:, None]
    col += NUM_LAG_INTERVALS
    feats[:, col] = lag_means.mean(1) / scale
    feats[:, col + 1] = lag_means.std(1) / scale
    feats[:, col + 2] = lag_means.max(1) / scale
    col += 3
    for j, win in enumerate((T, 10 * T)):
        if L > 0:
            alpha = 2.0 / (win + 1.0)
            h = history_fh[:, -min(L, 6 * win):]
            w = (1 - alpha) ** np.arange(h.shape[1])[::-1]
            feats[:, col + j] = (h * w).sum(1) / w.sum() / scale
    col += 2
    for k in range(NUM_LAST_SLOTS):
        if L - 1 - k >= 0:
            feats[:, col + k] = history_fh[:, L - 1 - k] / scale
    col += NUM_LAST_SLOTS
    for k in range(NUM_RSTAR_LAGS):
        hi = L - k * H
        lo = max(hi - H, 0)
        if hi <= 0:
            break
        feats[:, col + k] = required_rates(history_fh[:, lo:hi], deadlines) / scale
    col += NUM_RSTAR_LAGS
    nominal_se = np.array([c.se_bits_per_prb_layer for c in net.cells])
    feats[:, col] = se / nominal_se
    feats[:, col + 1] = deadlines / H
    col += 2
    feats[:, col:col + n] = np.eye(n)
    return feats


def features_from_obs(obs: Observation) -> np.ndarray:
    return build_features(obs.history_fh_demand, obs.se, obs.net, obs.ctrl)


# ---------------------------------------------------------------------------
# dataset construction from exogenous traces (controller independent)
# ---------------------------------------------------------------------------
def build_dataset(traces: List[TrafficTrace], net: NetworkConfig, ctrl: ControlConfig,
                  min_history_slots: Optional[int] = None):
    """Rows = (trace, decision epoch, cell). Returns X [M, F], y [M] (normalised r*)."""
    T = ctrl.interval_slots
    tau = ctrl.telemetry_delay_slots
    H = T + tau
    min_hist = min_history_slots or (NUM_LAG_INTERVALS + 1) * H
    scale = _scale(net)
    deadlines = np.array([c.deadline_slots for c in net.cells])
    X, Y = [], []
    for tr in traces:
        S = tr.num_slots
        for t in range(0, S - T, T):
            obs_slot = t - tau
            if obs_slot < min_hist:
                continue
            f = build_features(tr.fh_demand_bits[:, :obs_slot], tr.se[:, obs_slot], net, ctrl)
            y = required_rates(tr.fh_demand_bits[:, obs_slot:t + T], deadlines) / scale
            X.append(f)
            Y.append(y)
    return np.vstack(X), np.concatenate(Y)


# ---------------------------------------------------------------------------
# fast inference for fitted HistGradientBoosting models
# ---------------------------------------------------------------------------
class CompiledGBM:
    """Vectorised evaluation of one or several fitted HistGradientBoostingRegressors.

    scikit-learn's predict() loops over the trees in Python (~20 us each), which
    costs several milliseconds per call for 300 trees. Here the trees of all
    models are packed into padded arrays and traversed level by level with
    numpy, so one call for a handful of rows costs well under a millisecond.
    Produces the same raw prediction as the estimators (identity link for the
    quantile loss).
    """

    def __init__(self, models):
        if not isinstance(models, (list, tuple)):
            models = [models]
        self.n_models = len(models)
        preds, owner = [], []
        self.baseline = np.zeros(self.n_models)
        for j, model in enumerate(models):
            ps = [p[0] for p in model._predictors]   # models may have different tree counts (early stopping)
            preds.extend(ps)
            owner.extend([j] * len(ps))
            self.baseline[j] = float(np.ravel(model._baseline_prediction)[0])
        self.tree_owner = np.asarray(owner, dtype=np.int64)
        counts = np.bincount(self.tree_owner, minlength=self.n_models)
        if (counts == 0).any():
            raise ValueError("every model must have at least one tree")
        self._model_starts = np.concatenate([[0], np.cumsum(counts)[:-1]]).astype(np.int64)
        self.n_trees = len(preds)
        max_nodes = max(len(p.nodes) for p in preds)
        self.max_depth = int(max(p.nodes["depth"].max() for p in preds)) + 1
        shape = (self.n_trees, max_nodes)
        self.value = np.zeros(shape)
        self.feature = np.zeros(shape, dtype=np.int64)
        self.threshold = np.zeros(shape)
        self.left = np.zeros(shape, dtype=np.int64)
        self.right = np.zeros(shape, dtype=np.int64)
        self.is_leaf = np.ones(shape, dtype=bool)
        self.missing_left = np.ones(shape, dtype=bool)
        for k, p in enumerate(preds):
            nd = p.nodes
            m = len(nd)
            self.value[k, :m] = nd["value"]
            self.feature[k, :m] = nd["feature_idx"]
            self.threshold[k, :m] = nd["num_threshold"]
            self.left[k, :m] = nd["left"]
            self.right[k, :m] = nd["right"]
            self.is_leaf[k, :m] = nd["is_leaf"]
            self.missing_left[k, :m] = nd["missing_go_to_left"]
        self.tree_idx = np.arange(self.n_trees)[:, None]

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Returns [n_rows, n_models]."""
        X = np.asarray(X, dtype=float)
        n, F = X.shape
        if not hasattr(self, "_flat"):
            self._flat = True
            self._max_nodes = self.value.shape[1]
            self._offset = (np.arange(self.n_trees) * self._max_nodes)[:, None]
            self._value_f = self.value.ravel()
            self._feature_f = self.feature.ravel()
            self._threshold_f = self.threshold.ravel()
            self._left_f = self.left.ravel()
            self._right_f = self.right.ravel()
            self._is_leaf_f = self.is_leaf.ravel()
            self._missing_f = self.missing_left.ravel()
        xt = np.ascontiguousarray(X.T).ravel()            # xt[f * n + row]
        rows = np.arange(n)[None, :]
        idx = np.broadcast_to(self._offset, (self.n_trees, n)).copy()
        for _ in range(self.max_depth):
            leaf = np.take(self._is_leaf_f, idx)
            if leaf.all():
                break
            f = np.take(self._feature_f, idx)
            x = np.take(xt, f * n + rows)
            go_left = np.where(np.isnan(x), np.take(self._missing_f, idx), x <= np.take(self._threshold_f, idx))
            nxt = np.where(go_left, np.take(self._left_f, idx), np.take(self._right_f, idx)) + self._offset
            idx = np.where(leaf, idx, nxt)
        leaf_values = np.take(self._value_f, idx)                                  # [n_trees, n]
        per_model = np.add.reduceat(leaf_values, self._model_starts, axis=0)      # [n_models, n]
        return (per_model + self.baseline[:, None]).T


class QuantileGBMForecaster:
    """One HistGradientBoostingRegressor per quantile level (CPU friendly)."""

    def __init__(self, quantiles=DEFAULT_QUANTILES, max_iter: int = 300, learning_rate: float = 0.05,
                 max_leaf_nodes: int = 15, min_samples_leaf: int = 40, l2: float = 1.0):
        self.quantiles = tuple(quantiles)
        self.params = dict(max_iter=max_iter, learning_rate=learning_rate, max_leaf_nodes=max_leaf_nodes,
                           min_samples_leaf=min_samples_leaf, l2_regularization=l2)
        self.models = []
        self._compiled = None
        self.meta: Dict[str, Any] = {}

    @property
    def median_index(self) -> int:
        return int(np.argmin(np.abs(np.array(self.quantiles) - 0.5)))

    def fit(self, X: np.ndarray, y: np.ndarray, X_val: Optional[np.ndarray] = None,
            y_val: Optional[np.ndarray] = None) -> Dict[str, Any]:
        from sklearn.ensemble import HistGradientBoostingRegressor
        self.models = []
        self._compiled = None
        t0 = time.perf_counter()
        for q in self.quantiles:
            m = HistGradientBoostingRegressor(loss="quantile", quantile=q, random_state=0, **self.params)
            m.fit(X, y)
            self.models.append(m)
        info = {"train_rows": int(len(y)), "train_time_s": time.perf_counter() - t0}
        if X_val is not None:
            info["val"] = self.evaluate(X_val, y_val)
        self.meta.update(info)
        return info

    # The compiled traversal allocates n_trees x n_rows work arrays, so it is only
    # used for the small online batches (one row per cell); big offline batches go
    # through scikit-learn's predict, which is memory-bounded.
    FAST_MAX_ROWS = 256

    def predict_normalised(self, X: np.ndarray, fast: bool = True) -> np.ndarray:
        if fast and X.shape[0] <= self.FAST_MAX_ROWS:
            if self._compiled is None:
                self._compiled = CompiledGBM(self.models)
            q = self._compiled.predict(X)
        else:
            q = np.column_stack([m.predict(X) for m in self.models])
        q = np.clip(q, 0.0, None)
        return np.sort(q, axis=1)  # enforce monotone quantiles

    def predict_quantiles(self, obs: Observation) -> np.ndarray:
        """[N, K] forecast quantiles of the deadline-feasible rate in bits/slot."""
        return self.predict_normalised(features_from_obs(obs)) * _scale(obs.net)[:, None]

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
        return forecast_metrics(self.predict_normalised(X), y, self.quantiles)

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump({"quantiles": self.quantiles, "params": self.params, "models": self.models,
                         "meta": self.meta}, f)

    @classmethod
    def load(cls, path: str) -> "QuantileGBMForecaster":
        with open(path, "rb") as f:
            d = pickle.load(f)
        params = dict(d["params"])
        params["l2"] = params.pop("l2_regularization", 1.0)
        obj = cls(quantiles=d["quantiles"], **params)
        obj.models = d["models"]
        obj.meta = d.get("meta", {})
        obj._compiled = CompiledGBM(obj.models)
        return obj


class WindowQuantileForecaster:
    """Non-ML reference: empirical quantiles of realised r* over the last `window` horizons."""

    def __init__(self, quantiles=DEFAULT_QUANTILES, window: int = 30):
        self.quantiles = tuple(quantiles)
        self.window = window

    @property
    def median_index(self) -> int:
        return int(np.argmin(np.abs(np.array(self.quantiles) - 0.5)))

    def predict_quantiles(self, obs: Observation) -> np.ndarray:
        H = obs.ctrl.interval_slots + obs.ctrl.telemetry_delay_slots
        hist = obs.history_fh_demand
        L = hist.shape[1]
        n = hist.shape[0]
        k = min(self.window, L // H)
        if k == 0:
            base = required_rates(hist, obs.deadlines) if L > 0 else np.zeros(n)
            return np.repeat(base[:, None], len(self.quantiles), axis=1)
        chunks = hist[:, L - k * H:].reshape(n, k, H)
        rs = np.stack([required_rates(chunks[:, j, :], obs.deadlines) for j in range(k)], axis=1)  # [N, k]
        return np.quantile(rs, self.quantiles, axis=1).T

    def evaluate_on_traces(self, traces, net, ctrl) -> Dict[str, float]:
        """Forecast-quality metrics of the window method on decision epochs of the traces."""
        from .simulator import Observation as _Obs
        T, tau = ctrl.interval_slots, ctrl.telemetry_delay_slots
        deadlines = np.array([c.deadline_slots for c in net.cells])
        scale = _scale(net)
        Q, Y = [], []
        for tr in traces:
            for t in range((NUM_LAG_INTERVALS + 1) * (T + tau) + tau, tr.num_slots - T, T):
                obs_slot = t - tau
                obs = _Obs(slot=t, obs_slot=obs_slot, queue_bits=np.zeros(net.num_cells),
                           hol_age=np.zeros(net.num_cells), se=tr.se[:, obs_slot],
                           history_fh_demand=tr.fh_demand_bits[:, :obs_slot],
                           history_arrivals=tr.arrivals_bits[:, :obs_slot],
                           prev_budgets=np.zeros(net.num_cells), net=net, ctrl=ctrl)
                Q.append(self.predict_quantiles(obs) / scale[:, None])
                Y.append(required_rates(tr.fh_demand_bits[:, obs_slot:t + T], deadlines) / scale)
        return forecast_metrics(np.vstack(Q), np.concatenate(Y), self.quantiles)


def forecast_metrics(q: np.ndarray, y: np.ndarray, quantiles) -> Dict[str, float]:
    """Pinball loss, coverage and median error for normalised targets."""
    quantiles = np.array(quantiles)
    out = {}
    pin = 0.0
    for k, a in enumerate(quantiles):
        d = y - q[:, k]
        pin += np.mean(np.maximum(a * d, (a - 1) * d))
        out[f"coverage_q{int(round(a * 100)):02d}"] = float(np.mean(y <= q[:, k]))
    out["pinball_mean"] = float(pin / len(quantiles))
    mi = int(np.argmin(np.abs(quantiles - 0.5)))
    out["median_mae"] = float(np.mean(np.abs(y - q[:, mi])))
    out["median_mae_rel"] = float(np.mean(np.abs(y - q[:, mi])) / max(np.mean(y), 1e-9))
    lo = int(np.argmin(np.abs(quantiles - 0.05)))
    hi = int(np.argmin(np.abs(quantiles - 0.95)))
    out["interval90_coverage"] = float(np.mean((y >= q[:, lo]) & (y <= q[:, hi])))
    out["interval90_width_rel"] = float(np.mean(q[:, hi] - q[:, lo]) / max(np.mean(y), 1e-9))
    return out
