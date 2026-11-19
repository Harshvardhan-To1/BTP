"""Exp20: saving on the total uplink fronthaul when only reference-symbol IQ is compressed.

Data symbols stay on BFP-9; reference symbols (DMRS/SRS) are sent with CSEE or RAS-BFP at their
link-level operating points. Rates use the same model as Exp10 (100 MHz, M=64, 273 PRBs).
"""
from common import *
from cmatinv.fronthaul import iq_bits_per_prb_sym, stream_rate_gbps

SYM_PER_SLOT = 14
REF_CONFIGS = {"1 DMRS": 1, "2 DMRS": 2, "2 DMRS + 1 SRS": 3}
ENCODERS = {"RAS-BFP r=24": 4.0, "CSEE K=300": 6.4, "CSEE K=60": 31.0}


def main(M=64):
    bfp_ratio = 12 * 2 * 16 / iq_bits_per_prb_sym(9)
    total = stream_rate_gbps(M)
    res = {"bfp9_ratio": bfp_ratio, "uplink_bfp9_gbps": total, "saving": {}}
    for name, n_ref in REF_CONFIGS.items():
        f = n_ref / SYM_PER_SLOT
        res["saving"][name] = {}
        for enc, cr in ENCODERS.items():
            saving = f * (1 - bfp_ratio / cr)
            res["saving"][name][enc] = dict(fraction=saving, gbps=saving * total)
            print(f"{name:16s} {enc:14s} saving {100 * saving:5.1f}%  ({saving * total:5.1f} Gbit/s)")
    dump(res, "exp20_fronthaul_share")


if __name__ == "__main__":
    main()
