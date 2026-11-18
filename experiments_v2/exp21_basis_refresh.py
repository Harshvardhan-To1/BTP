"""Exp21: basis refresh policies for the pilot-sketch encoder under channel aging.

Round-robin: each slot refreshes every Tb-th PRB (offset by the slot index), the others reuse their basis.
Certificate: a reused basis is kept only while the energy of validation REs (a data symbol not used to build
the basis) outside it stays below thr x its value in the slot where the basis was built, so the refresh rate
follows the user speed.
"""
from common import *
from iqcomp.uplink import UplinkConfig, slot_sequence, post_detection_quality
from iqcomp.codecs import raw_bits, bfp, dmrs_columns
from iqcomp import fastcodec as fc
import warnings; warnings.filterwarnings("ignore")


def main(n_drops=3, T=16, b=8):
    pil = dmrs_columns()
    res = {}
    policies = [(Tb, 0.0) for Tb in (1, 2, 4, 8)] + [(16, c) for c in (1.1, 1.25, 1.5)]
    for v in (3, 30, 120):
        for Tb, cert in policies:
            loss, cr, evm, frac = [], [], [], []
            for d in range(n_drops):
                cfg = UplinkConfig(K=8, snr_db=20, n_prb=24, seed=300 + d)
                state = None
                for t, s in enumerate(slot_sequence(cfg, T, v)):
                    P, M, _ = s["Y"].shape
                    mask = ((np.arange(P) + t) % Tb) == 0 if state is not None else None
                    Qq, Lq, r, bits, did, state = fc.pilot_encode(s["Y"], pil, b, 8, refresh=mask, state=state,
                                                                  cert_thr=cert if state is not None else 0.0)
                    if t < min(Tb, 4):
                        continue
                    frac.append(did.mean())
                    ref = post_detection_quality(s["Y"], s)
                    q = post_detection_quality((Qq @ Lq).astype(complex), s)
                    loss.append(ref["sinr_db"] - q["sinr_db"]); evm.append(q["evm"]); cr.append(raw_bits(P, M) / bits)
            name = f"round-robin Tb={Tb}" if cert == 0 else f"certificate thr={cert}"
            res[f"{v} km/h | {name}"] = dict(loss_db=float(np.mean(loss)), evm=float(np.mean(evm)), cr=float(np.mean(cr)),
                                             refresh_fraction=float(np.mean(frac)))
            print(f"{v:4d} km/h  {name:22s}: CR {np.mean(cr):5.2f}x  EVM {100 * np.mean(evm):.2f} %  "
                  f"loss {np.mean(loss):.2f} dB  refreshed {100 * np.mean(frac):.0f} % of PRBs")
    dump(res, "exp21_basis_refresh")


if __name__ == "__main__":
    main()
