// Uplink IQ compression kernels (complex64, interleaved re/im), OpenMP over PRBs.
//   bfp_batch     : O-RAN block floating point, one exponent per 12 subcarriers of one stream and symbol.
//   pilot_encode  : RAS-BFP with a DMRS column-sampling sketch: eigen-decomposition of the p x p pilot Gram
//                   (LAPACK cheevd), Marchenko-Pastur rank, BFP basis, projection L = Q^H Y, BFP coefficients.
//                   PRBs with refresh[p] == 0 reuse the basis and rank already in Qq / rank (round-robin refresh),
//                   unless cert_thr > 0 and the energy of the validation columns vcol (REs not used to build the
//                   basis) outside that basis exceeds cert_thr x its value in the slot of the last refresh
//                   (cert_ref); refresh[] returns which PRBs were refreshed.
// Layout: Y [P, M, n] with n = 12 * 14 and column index sc * 14 + sym.
#include <complex.h>
#include <lapacke.h>
#include <math.h>
#include <omp.h>
#include <stdlib.h>
#include <string.h>

#define SC 12
#define SYM 14

extern void openblas_set_num_threads(int);

static inline float quant(float v, float scale, float lv) {
    float q = rintf(v / scale);
    if (q > lv) q = lv;
    if (q < -lv - 1) q = -lv - 1;
    return q * scale;
}

static inline float block_scale(float peak, float lv) {
    return exp2f(ceilf(log2f(fmaxf(peak, 1e-30f) / lv)));
}

// Quantise R streams of one PRB in place (z: R x n interleaved, n = SC * SYM, column = sc * SYM + sym).
static void bfp_prb(float *z, int R, int n, int b) {
    const float lv = (float)((1 << (b - 1)) - 1);
    for (int r = 0; r < R; r++) {
        float *row = z + 2 * (size_t)r * n;
        float peak[2 * SYM], scl[2 * SYM], inv[2 * SYM];
        for (int t = 0; t < 2 * SYM; t++) peak[t] = 0.f;
        for (int s = 0; s < SC; s++) {
            const float *v = row + 2 * s * SYM;
#pragma omp simd
            for (int t = 0; t < 2 * SYM; t++) peak[t] = fmaxf(peak[t], fabsf(v[t]));
        }
        for (int t = 0; t < SYM; t++) {
            float pk = fmaxf(peak[2 * t], peak[2 * t + 1]);
            float sc = block_scale(pk, lv);
            scl[2 * t] = scl[2 * t + 1] = sc;
            inv[2 * t] = inv[2 * t + 1] = 1.f / sc;
        }
        for (int s = 0; s < SC; s++) {
            float *v = row + 2 * s * SYM;
#pragma omp simd
            for (int t = 0; t < 2 * SYM; t++) {
                float q = rintf(v[t] * inv[t]);
                q = fminf(fmaxf(q, -lv - 1), lv);
                v[t] = q * scl[t];
            }
        }
    }
}

void bfp_batch(const float *Z, float *Zq, int P, int R, int n, int b, int threads) {
    memcpy(Zq, Z, sizeof(float) * 2 * (size_t)P * R * n);
#pragma omp parallel for num_threads(threads) schedule(static)
    for (int p = 0; p < P; p++) bfp_prb(Zq + 2 * (size_t)p * R * n, R, n, b);
}

// Energy of the columns Z outside the basis qq (first r columns), relative to the noise-only level p (M - r).
// The residual z - Q (Q^H z) is formed explicitly: total-minus-captured energy cancels catastrophically
// in float when the signal is far above the noise.
static float out_energy(const float *Zr, const float *Zi, const float *qq, int M, int np_, int rmax, int r) {
    double e = 0.0;
    float cr[64], ci[64];
    for (int j = 0; j < np_; j++) {
        for (int k = 0; k < r; k++) {
            float ar = 0.f, ai = 0.f;
            for (int m = 0; m < M; m++) {
                float qr = qq[2 * (m * rmax + k)], qi = qq[2 * (m * rmax + k) + 1];
                ar += qr * Zr[m * np_ + j] + qi * Zi[m * np_ + j];
                ai += qr * Zi[m * np_ + j] - qi * Zr[m * np_ + j];
            }
            cr[k] = ar; ci[k] = ai;
        }
        for (int m = 0; m < M; m++) {
            float vr = Zr[m * np_ + j], vi = Zi[m * np_ + j];
            for (int k = 0; k < r; k++) {
                float qr = qq[2 * (m * rmax + k)], qi = qq[2 * (m * rmax + k) + 1];
                vr -= qr * cr[k] - qi * ci[k];
                vi -= qr * ci[k] + qi * cr[k];
            }
            e += (double)vr * vr + (double)vi * vi;
        }
    }
    return (float)(e / ((double)np_ * (M - r)));
}

void pilot_encode(const float *Y, int P, int M, int n, const int *pil, int np_, const int *vcol, int nv,
                  float noise_var, float margin,
                  int b, int bq, int rmax, float cert_thr, unsigned char *refresh, float *cert_ref, float *Qq, float *Lq,
                  int *rank, int threads) {
    openblas_set_num_threads(1);
    const float edge = noise_var * powf(1.f + sqrtf((float)M / np_), 2.f) * margin;
    const float lvq = (float)((1 << (bq - 1)) - 1);
#pragma omp parallel num_threads(threads)
    {
        float *Zr = malloc(sizeof(float) * M * np_), *Zi = malloc(sizeof(float) * M * np_);
        float *Vr = malloc(sizeof(float) * M * nv), *Vi = malloc(sizeof(float) * M * nv);
        lapack_complex_float *A = malloc(sizeof(lapack_complex_float) * np_ * np_);
        float *w = malloc(sizeof(float) * np_);
        float *Yr = malloc(sizeof(float) * M * n), *Yi = malloc(sizeof(float) * M * n);
        float *Ur = malloc(sizeof(float) * M * rmax), *Ui = malloc(sizeof(float) * M * rmax);
#pragma omp for schedule(static)
        for (int p = 0; p < P; p++) {
            const float *y = Y + 2 * (size_t)p * M * n;
            for (int m = 0; m < M; m++) {
                const float *ym = y + 2 * (size_t)m * n;
                float *yr = Yr + (size_t)m * n, *yi = Yi + (size_t)m * n;
#pragma omp simd
                for (int c = 0; c < n; c++) { yr[c] = ym[2 * c]; yi[c] = ym[2 * c + 1]; }
                for (int j = 0; j < np_; j++) { Zr[m * np_ + j] = yr[pil[j]]; Zi[m * np_ + j] = yi[pil[j]]; }
                for (int j = 0; j < nv; j++) { Vr[m * nv + j] = yr[vcol[j]]; Vi[m * nv + j] = yi[vcol[j]]; }
            }
            float *qq = Qq + 2 * (size_t)p * M * rmax;
            int r;
            if (!refresh[p] && cert_thr > 0.f &&
                out_energy(Vr, Vi, qq, M, nv, rmax, rank[p]) > cert_thr * cert_ref[p]) refresh[p] = 1;
            if (refresh[p]) {
                // A = Z^H Z (row-major, upper triangle used by cheevd with 'U')
                for (int i = 0; i < np_; i++)
                    for (int j = i; j < np_; j++) {
                        float ar = 0.f, ai = 0.f;
                        for (int m = 0; m < M; m++) {
                            float xr = Zr[m * np_ + i], xi = Zi[m * np_ + i], vr = Zr[m * np_ + j], vi = Zi[m * np_ + j];
                            ar += xr * vr + xi * vi;
                            ai += xr * vi - xi * vr;
                        }
                        A[i * np_ + j] = ar + ai * I;
                    }
                LAPACKE_cheevd(LAPACK_ROW_MAJOR, 'V', 'U', np_, A, np_, w);
                r = 0;
                for (int k = np_ - 1; k >= 0 && r < rmax; k--) if (w[k] / np_ > edge) r++;
                if (r < 1) r = 1;
                rank[p] = r;
                // U_k = Z v_k / sqrt(w_k), BFP per column
                memset(qq, 0, sizeof(float) * 2 * M * rmax);
                for (int k = 0; k < r; k++) {
                    int e = np_ - 1 - k;
                    float inv = 1.f / sqrtf(fmaxf(w[e], 1e-30f)), peak = 0.f;
                    for (int m = 0; m < M; m++) {
                        float ur = 0.f, ui = 0.f;
                        for (int j = 0; j < np_; j++) {
                            float vr = crealf(A[j * np_ + e]), vi = cimagf(A[j * np_ + e]);
                            ur += Zr[m * np_ + j] * vr - Zi[m * np_ + j] * vi;
                            ui += Zr[m * np_ + j] * vi + Zi[m * np_ + j] * vr;
                        }
                        Ur[k * M + m] = ur * inv; Ui[k * M + m] = ui * inv;
                        peak = fmaxf(peak, fmaxf(fabsf(ur * inv), fabsf(ui * inv)));
                    }
                    float sc = block_scale(peak, lvq);
                    for (int m = 0; m < M; m++) {
                        Ur[k * M + m] = quant(Ur[k * M + m], sc, lvq);
                        Ui[k * M + m] = quant(Ui[k * M + m], sc, lvq);
                        qq[2 * (m * rmax + k)] = Ur[k * M + m];
                        qq[2 * (m * rmax + k) + 1] = Ui[k * M + m];
                    }
                }
                cert_ref[p] = out_energy(Vr, Vi, qq, M, nv, rmax, r);
            } else {
                r = rank[p];
                for (int k = 0; k < r; k++)
                    for (int m = 0; m < M; m++) {
                        Ur[k * M + m] = qq[2 * (m * rmax + k)];
                        Ui[k * M + m] = qq[2 * (m * rmax + k) + 1];
                    }
            }
            // L = Qq^H Y, then BFP (rows beyond r are zero)
            float *l = Lq + 2 * (size_t)p * rmax * n;
            memset(l, 0, sizeof(float) * 2 * rmax * n);
            for (int k0 = 0; k0 < r; k0 += 4) {
                const int kb = (r - k0) < 4 ? (r - k0) : 4;
                float lr[4][SC * SYM], li[4][SC * SYM];
                memset(lr, 0, sizeof lr); memset(li, 0, sizeof li);
                for (int m = 0; m < M; m++) {
                    const float *yr = Yr + (size_t)m * n, *yi = Yi + (size_t)m * n;
                    for (int kk = 0; kk < kb; kk++) {
                        const float qr = Ur[(k0 + kk) * M + m], qi = Ui[(k0 + kk) * M + m];
                        float *ar = lr[kk], *ai = li[kk];
#pragma omp simd
                        for (int c = 0; c < SC * SYM; c++) {
                            ar[c] += qr * yr[c] + qi * yi[c];
                            ai[c] += qr * yi[c] - qi * yr[c];
                        }
                    }
                }
                for (int kk = 0; kk < kb; kk++) {
                    float *dst = l + 2 * (size_t)(k0 + kk) * n;
#pragma omp simd
                    for (int c = 0; c < SC * SYM; c++) { dst[2 * c] = lr[kk][c]; dst[2 * c + 1] = li[kk][c]; }
                }
            }
            bfp_prb(l, r, n, b);
        }
        free(Vr); free(Vi); free(Zr); free(Zi); free(A); free(w); free(Yr); free(Yi); free(Ur); free(Ui);
    }
}
