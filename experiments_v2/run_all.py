"""Run every v2 experiment (about 3 minutes on a 4-core CPU). Outputs go to results/v2/."""
import exp5_spectrum_probability as e5, exp6_inversion_accuracy as e6, exp7_tracking as e7
import exp8_low_precision as e8, exp9_cost_latency as e9, exp10_fronthaul as e10
import exp11_doppler_law_and_certificate as e11, exp12_doppler_law as e12, exp13_confidence as e13, exp14_stronger_baselines as e14, exp15_kernel_bench as e15, exp16_warm_baselines as e16, exp17_pipeline_kernel as e17, exp18_fp16_kernel as e18
import warnings; warnings.filterwarnings("ignore")
for m in (e5, e6, e7, e8, e9, e10, e11, e12, e13, e14, e15, e16, e17, e18):
    print("=" * 20, m.__name__)
    m.main()
