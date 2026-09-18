import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from matinv_bench.generate_dataset import generate_pairs
from matinv_bench.inversenet import FastBLASInferenceEngine, build_model
from matinv_bench.methods import CLASSICAL_METHODS


@pytest.fixture(scope="module")
def sample():
    m, inv = generate_pairs(n=24, num_samples=3, seed=0)
    return m, inv


@pytest.mark.parametrize("name", list(CLASSICAL_METHODS))
def test_classical_methods_invert(sample, name):
    m, inv = sample
    fn = CLASSICAL_METHODS[name]
    for a, true in zip(m, inv):
        x = fn(a)
        assert np.linalg.norm(x @ a - np.eye(24)) / np.sqrt(24) < 1e-4
        assert np.linalg.norm(x - true) / np.linalg.norm(true) < 1e-4


def test_dataset_is_well_conditioned(sample):
    m, _ = sample
    assert m.dtype == np.float32
    assert all(np.linalg.cond(a.astype(np.float64)) < 20 for a in m)


def test_ultra_engine_matches_torch_model():
    dim = 10
    model = build_model("ultra", dim)
    ckpt = os.path.join(os.path.dirname(__file__), "..", "models", f"inversenet_ultra_dim{dim}.pt")
    if os.path.exists(ckpt):
        model.load_state_dict(torch.load(ckpt, weights_only=True))
    else:
        torch.manual_seed(0)
        with torch.no_grad():                     # make the hyper-network non-trivial
            model.hyper[-1].weight.uniform_(-0.1, 0.1)
    engine = FastBLASInferenceEngine(model)
    a = generate_pairs(dim, 1, seed=1)[0][0]
    with torch.no_grad():
        ref = model(torch.from_numpy(a)[None])[0].numpy()
    out = engine(a)
    assert np.allclose(out, ref, rtol=1e-4, atol=1e-5)


def test_ns_model_dimension_independent():
    model = build_model("ns", 500)
    assert sum(p.numel() for p in model.parameters()) == 17          # alpha + 8 beta + 8 gamma
    with pytest.raises(ValueError):
        build_model("mlp", 500)
