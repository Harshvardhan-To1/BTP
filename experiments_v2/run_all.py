"""Run every v2 experiment (about 1.5 minutes on a 4-core CPU). Outputs go to results/v2/."""
import exp5_spectrum_probability as e5, exp6_inversion_accuracy as e6, exp7_tracking as e7
import exp8_low_precision as e8, exp9_cost_latency as e9, exp10_fronthaul as e10
import warnings; warnings.filterwarnings("ignore")
for m in (e5, e6, e7, e8, e9, e10):
    print("=" * 20, m.__name__)
    m.main()
