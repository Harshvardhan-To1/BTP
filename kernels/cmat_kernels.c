// Batched complex64 K x K kernels for RZF precoding on a CPU DU (K <= 64, row-major, interleaved re/im).
// Build: gcc -O3 -march=native -fopenmp -shared -fPIC cmat_kernels.c -o libcmat.so
#include <math.h>
#include <string.h>
#include <stdint.h>

#define KMAX 64

// C[K][K] = A[K][K] * B[K][K] on split-plane (SoA) buffers; inner loop over contiguous j vectorises with FMA.
static inline void cmm_soa(int K, const float *ar, const float *ai, const float *br, const float *bi,
                           float *cr, float *ci) {
    for (int i = 0; i < K; i++) {
        float *cri = cr + i * K, *cii = ci + i * K;
        for (int j = 0; j < K; j++) { cri[j] = 0.f; cii[j] = 0.f; }
        for (int k = 0; k < K; k++) {
            float xr = ar[i * K + k], xi = ai[i * K + k];
            const float *brk = br + k * K, *bik = bi + k * K;
            for (int j = 0; j < K; j++) {
                cri[j] += xr * brk[j] - xi * bik[j];
                cii[j] += xr * bik[j] + xi * brk[j];
            }
        }
    }
}

static inline void load_soa(int K, const float *src, float *re, float *im) {
    for (int n = 0; n < K * K; n++) { re[n] = src[2 * n]; im[n] = src[2 * n + 1]; }
}
static inline void store_soa(int K, const float *re, const float *im, float *dst) {
    for (int n = 0; n < K * K; n++) { dst[2 * n] = re[n]; dst[2 * n + 1] = im[n]; }
}

// Fused Newton-Schulz step per matrix:  T = G X ;  resid[s] = ||I - T||_F / sqrt(K)  (exact, free) ;  Xout = X (2I - T).
// Doing it in place (Xout may alias X). The residual is that of the INPUT X, so ||R_out||_F <= ||R||_F^2 (deterministic).
void ns_step_batch(const float *G, const float *X, float *Xout, float *resid, int S, int K, int nthreads) {
#pragma omp parallel for num_threads(nthreads) schedule(static)
    for (int s = 0; s < S; s++) {
        float gr[KMAX * KMAX], gi[KMAX * KMAX], xr[KMAX * KMAX], xi[KMAX * KMAX];
        float tr[KMAX * KMAX], ti[KMAX * KMAX], ur[KMAX * KMAX], ui[KMAX * KMAX];
        size_t off = (size_t)s * K * K * 2;
        load_soa(K, G + off, gr, gi);
        load_soa(K, X + off, xr, xi);
        cmm_soa(K, gr, gi, xr, xi, tr, ti);
        double acc = 0.0;
        for (int i = 0; i < K; i++)
            for (int j = 0; j < K; j++) {
                float er = (i == j ? 1.f : 0.f) - tr[i * K + j], ei = -ti[i * K + j];
                acc += (double)er * er + (double)ei * ei;
            }
        resid[s] = (float)sqrt(acc / K);
        for (int n = 0; n < K * K; n++) { tr[n] = -tr[n]; ti[n] = -ti[n]; }
        for (int i = 0; i < K; i++) tr[i * K + i] += 2.f;
        cmm_soa(K, xr, xi, tr, ti, ur, ui);
        store_soa(K, ur, ui, Xout + off);
    }
}

// ---- single-matrix building blocks (stack-resident, split re/im planes) --------------------------------------
// X = G^-1 for Hermitian positive-definite G (interleaved, only the lower triangle is read), via G = L L^H.
static void chol_inv_one(int K, const float *g, float *xr, float *xi) {
    float lr[KMAX * KMAX], li[KMAX * KMAX], yr[KMAX * KMAX], yi[KMAX * KMAX];
    memset(lr, 0, sizeof lr); memset(li, 0, sizeof li);
    for (int j = 0; j < K; j++) {
        float d = g[2 * (j * K + j)];
        for (int k = 0; k < j; k++) d -= lr[j * K + k] * lr[j * K + k] + li[j * K + k] * li[j * K + k];
        float ljj = sqrtf(d), inv = 1.f / ljj;
        lr[j * K + j] = ljj;
        for (int i = j + 1; i < K; i++) {
            float sr = g[2 * (i * K + j)], si = g[2 * (i * K + j) + 1];
            for (int k = 0; k < j; k++) {
                float ar = lr[i * K + k], ai = li[i * K + k], br = lr[j * K + k], bi = -li[j * K + k];
                sr -= ar * br - ai * bi; si -= ar * bi + ai * br;
            }
            lr[i * K + j] = sr * inv; li[i * K + j] = si * inv;
        }
    }
    for (int i = 0; i < K; i++) {                       // Y = L^-1
        for (int j = 0; j < K; j++) { yr[i * K + j] = (i == j); yi[i * K + j] = 0.f; }
        for (int k = 0; k < i; k++) {
            float ar = lr[i * K + k], ai = li[i * K + k];
            for (int j = 0; j <= k; j++) {
                yr[i * K + j] -= ar * yr[k * K + j] - ai * yi[k * K + j];
                yi[i * K + j] -= ar * yi[k * K + j] + ai * yr[k * K + j];
            }
        }
        float inv = 1.f / lr[i * K + i];
        for (int j = 0; j <= i; j++) { yr[i * K + j] *= inv; yi[i * K + j] *= inv; }
    }
    for (int i = 0; i < K * K; i++) { xr[i] = 0.f; xi[i] = 0.f; }
    for (int k = 0; k < K; k++)                         // X = Y^H Y
        for (int i = 0; i <= k; i++) {
            float ar = yr[k * K + i], ai = -yi[k * K + i];
            for (int j = 0; j <= k; j++) {
                xr[i * K + j] += ar * yr[k * K + j] - ai * yi[k * K + j];
                xi[i * K + j] += ar * yi[k * K + j] + ai * yr[k * K + j];
            }
        }
}

// In-place Gauss-Jordan "sweep" inverse of a Hermitian positive-definite matrix (no pivoting needed for HPD).
// K rank-1 updates whose inner loops run over contiguous rows -> fully vectorised, no sqrt / divide chains.
// g: interleaved lower triangle of G; output: full inverse in split planes xr/xi.
static void gj_inv_one(int K, const float *g, float *xr, float *xi) {
    for (int i = 0; i < K; i++)
        for (int j = 0; j <= i; j++) {
            float r = g[2 * (i * K + j)], q = g[2 * (i * K + j) + 1];
            xr[i * K + j] = r; xi[i * K + j] = q; xr[j * K + i] = r; xi[j * K + i] = -q;
        }
    float rkr[KMAX], rki[KMAX], ckr[KMAX], cki[KMAX];
    for (int k = 0; k < K; k++) {
        float piv = 1.f / xr[k * K + k];
        for (int j = 0; j < K; j++) { rkr[j] = xr[k * K + j]; rki[j] = xi[k * K + j]; ckr[j] = xr[j * K + k]; cki[j] = xi[j * K + k]; }
        for (int i = 0; i < K; i++) {
            if (i == k) continue;
            float fr = ckr[i] * piv, fi = cki[i] * piv;   // A[i][:] -= f * rowk
            float *ar = xr + i * K, *ai = xi + i * K;
#pragma omp simd
            for (int j = 0; j < K; j++) {
                ar[j] -= fr * rkr[j] - fi * rki[j];
                ai[j] -= fr * rki[j] + fi * rkr[j];
            }
            ar[k] = -fr; ai[k] = -fi;                      // column k becomes -A[i][k] * piv
        }
        float *kr = xr + k * K, *ki = xi + k * K;
#pragma omp simd
        for (int j = 0; j < K; j++) { kr[j] = rkr[j] * piv; ki[j] = rki[j] * piv; }
        kr[k] = piv; ki[k] = 0.f;
    }
}

void chol_inverse_batch(const float *G, float *Xout, int S, int K, int nthreads) {
#pragma omp parallel for num_threads(nthreads) schedule(static)
    for (int s = 0; s < S; s++) {
        float xr[KMAX * KMAX], xi[KMAX * KMAX];
        size_t off = (size_t)s * K * K * 2;
#ifdef USE_CHOL
        chol_inv_one(K, G + off, xr, xi);
#else
        gj_inv_one(K, G + off, xr, xi);
#endif
        store_soa(K, xr, xi, Xout + off);
    }
}

// ---- fused RZF pipeline -------------------------------------------------------------------------------------
#define MMAX 128

// G = H H^H + alpha I (lower triangle, interleaved) from SoA H [K][M]. Contiguous dot products -> SIMD reductions.
static void gram_lower(int K, int M, const float *hr, const float *hi, float alpha, float *g) {
    for (int i = 0; i < K; i++)
        for (int j = 0; j <= i; j++) {
            float sr = 0.f, si = 0.f;
            const float *ar = hr + i * M, *ai = hi + i * M, *br = hr + j * M, *bi = hi + j * M;
#pragma omp simd reduction(+ : sr, si)
            for (int m = 0; m < M; m++) {                // a * conj(b)
                sr += ar[m] * br[m] + ai[m] * bi[m];
                si += ai[m] * br[m] - ar[m] * bi[m];
            }
            if (i == j) sr += alpha, si = 0.f;
            g[2 * (i * K + j)] = sr; g[2 * (i * K + j) + 1] = si;
        }
}

// Wt[K][M] = (H^H X)^T :  Wt[k][m] = sum_j X[j][k] * conj(H[j][m]), then scale so ||W||_F^2 = power.
// Register-blocked axpy form: for each output row k and 32-wide m block the accumulators stay in registers while j loops.
#define MB 32
static void form_w(int K, int M, const float *hr, const float *hi, const float *xr, const float *xi, float power, float *wt) {
    double energy = 0.0;
    for (int k = 0; k < K; k++) {
        for (int m0 = 0; m0 < M; m0 += MB) {
            int nb = (M - m0 < MB) ? (M - m0) : MB;
            float ar[MB], ai[MB];
            for (int m = 0; m < MB; m++) { ar[m] = 0.f; ai[m] = 0.f; }
            for (int j = 0; j < K; j++) {
                float cr = xr[j * K + k], ci = xi[j * K + k];
                const float *hrj = hr + j * M + m0, *hij = hi + j * M + m0;
                if (nb == MB) {
#pragma omp simd
                    for (int m = 0; m < MB; m++) {           // (cr + i ci) * (hr - i hi)
                        ar[m] += cr * hrj[m] + ci * hij[m];
                        ai[m] += ci * hrj[m] - cr * hij[m];
                    }
                } else {
                    for (int m = 0; m < nb; m++) {
                        ar[m] += cr * hrj[m] + ci * hij[m];
                        ai[m] += ci * hrj[m] - cr * hij[m];
                    }
                }
            }
            float *o = wt + 2 * ((size_t)k * M + m0);
            for (int m = 0; m < nb; m++) { o[2 * m] = ar[m]; o[2 * m + 1] = ai[m]; energy += (double)ar[m] * ar[m] + (double)ai[m] * ai[m]; }
        }
    }
    float sc = (float)sqrt(power / energy);
    for (int n = 0; n < 2 * K * M; n++) wt[n] *= sc;
}

static void load_h(int K, int M, const float *src, float *hr, float *hi) {
    for (int n = 0; n < K * M; n++) { hr[n] = src[2 * n]; hi[n] = src[2 * n + 1]; }
}

// Exact path: Gram -> Cholesky inverse -> W, one pass per PRB, everything L1-resident.
#ifdef PROFILE
#include <x86intrin.h>
double prof_cycles[4];
#define TICK(i) do { unsigned long long t_ = __rdtsc(); if (s == 0) { prof_cycles[i] += (double)(t_ - last); } last = t_; } while (0)
#else
#define TICK(i)
#endif

void rzf_fused_chol(const float *H, float *W, int S, int K, int M, float alpha, float power, int nthreads) {
#pragma omp parallel for num_threads(nthreads) schedule(static)
    for (int s = 0; s < S; s++) {
        float hr[KMAX * MMAX], hi[KMAX * MMAX], g[KMAX * KMAX * 2], xr[KMAX * KMAX], xi[KMAX * KMAX];
#ifdef PROFILE
        unsigned long long last = __rdtsc();
#endif
        load_h(K, M, H + (size_t)s * K * M * 2, hr, hi);
        TICK(0);
        gram_lower(K, M, hr, hi, alpha, g);
        TICK(1);
#ifdef USE_CHOL
        chol_inv_one(K, g, xr, xi);
        for (int i = 0; i < K; i++)
            for (int j = i + 1; j < K; j++) { xr[i * K + j] = xr[j * K + i]; xi[i * K + j] = -xi[j * K + i]; }
#else
        gj_inv_one(K, g, xr, xi);
#endif
        TICK(2);
        form_w(K, M, hr, hi, xr, xi, power, W + (size_t)s * M * K * 2);
        TICK(3);
    }
}

// Tracking path: Gram -> ONE fused Newton-Schulz step from the previous inverse Xinout (updated in place) -> W.
// resid[s] = exact ||I - G X_prev||_F / sqrt(K) (the certificate), computed for free inside the step.
void rzf_fused_ns(const float *H, float *Xinout, float *W, float *resid, int S, int K, int M, float alpha, float power, int nthreads) {
#pragma omp parallel for num_threads(nthreads) schedule(static)
    for (int s = 0; s < S; s++) {
        float hr[KMAX * MMAX], hi[KMAX * MMAX], g[KMAX * KMAX * 2];
        float gr[KMAX * KMAX], gi[KMAX * KMAX], xr[KMAX * KMAX], xi[KMAX * KMAX];
        float tr[KMAX * KMAX], ti[KMAX * KMAX], ur[KMAX * KMAX], ui[KMAX * KMAX];
        load_h(K, M, H + (size_t)s * K * M * 2, hr, hi);
        gram_lower(K, M, hr, hi, alpha, g);
        for (int i = 0; i < K; i++)
            for (int j = 0; j <= i; j++) {
                gr[i * K + j] = g[2 * (i * K + j)]; gi[i * K + j] = g[2 * (i * K + j) + 1];
                gr[j * K + i] = gr[i * K + j];      gi[j * K + i] = -gi[i * K + j];
            }
        float *xp = Xinout + (size_t)s * K * K * 2;
        load_soa(K, xp, xr, xi);
        cmm_soa(K, gr, gi, xr, xi, tr, ti);
        double acc = 0.0;
        for (int i = 0; i < K; i++)
            for (int j = 0; j < K; j++) {
                float er = (i == j ? 1.f : 0.f) - tr[i * K + j], ei = -ti[i * K + j];
                acc += (double)er * er + (double)ei * ei;
            }
        resid[s] = (float)sqrt(acc / K);
        for (int n = 0; n < K * K; n++) { tr[n] = -tr[n]; ti[n] = -ti[n]; }
        for (int i = 0; i < K; i++) tr[i * K + i] += 2.f;
        cmm_soa(K, xr, xi, tr, ti, ur, ui);
        store_soa(K, ur, ui, xp);
        form_w(K, M, hr, hi, ur, ui, power, W + (size_t)s * M * K * 2);
    }
}

// ---- FP16 weight-formation path (AVX512-FP16 complex FMA) -------------------------------------------------------
// Gram and inverse stay in float32 (inversion amplifies rounding); only the final W^T = X conj(H) product, the largest stage,
// runs in half precision. H and X are block-scaled per PRB so the fp16 range is never an issue, and the global scale cancels
// in the power normalisation.
#ifdef __AVX512FP16__
#include <immintrin.h>

static void form_w_fp16(int K, int M, const float *Hint, const float *xr, const float *xi, float power, float *wt) {
    _Float16 hh[KMAX * MMAX * 2] __attribute__((aligned(64)));
    _Float16 xh[KMAX * KMAX * 2];
    float hmax = 1e-30f, xmax = 1e-30f;
    for (int n = 0; n < 2 * K * M; n++) { float a = fabsf(Hint[n]); if (a > hmax) hmax = a; }
    for (int n = 0; n < K * K; n++) { float a = fabsf(xr[n]), b = fabsf(xi[n]); if (a > xmax) xmax = a; if (b > xmax) xmax = b; }
    float sh = 1.f / hmax, sx = 1.f / xmax;
    for (int n = 0; n < 2 * K * M; n++) hh[n] = (_Float16)(Hint[n] * sh);
    for (int n = 0; n < K * K; n++) { xh[2 * n] = (_Float16)(xr[n] * sx); xh[2 * n + 1] = (_Float16)(xi[n] * sx); }
    double energy = 0.0;
    int nb = M / 16;                                   // 16 complex numbers per zmm; remainder handled in float
    for (int k = 0; k < K; k += 2) {                   // two output rows per pass -> 2*nb independent FMA chains
        int two = (k + 1 < K);
        __m512h acc0[MMAX / 16], acc1[MMAX / 16];
        for (int b = 0; b < nb; b++) { acc0[b] = _mm512_setzero_ph(); acc1[b] = _mm512_setzero_ph(); }
        for (int j = 0; j < K; j++) {
            __m512h x0 = (__m512h)_mm512_set1_epi32(((int *)xh)[j * K + k]);
            __m512h x1 = two ? (__m512h)_mm512_set1_epi32(((int *)xh)[j * K + k + 1]) : x0;
            const _Float16 *hrow = hh + 2 * (size_t)j * M;
            for (int b = 0; b < nb; b++) {
                __m512h h = _mm512_load_ph(hrow + 32 * b);
                acc0[b] = _mm512_fcmadd_pch(x0, h, acc0[b]);
                acc1[b] = _mm512_fcmadd_pch(x1, h, acc1[b]);
            }
        }
        for (int r = 0; r < 1 + two; r++) {
            float *o = wt + 2 * (size_t)(k + r) * M;
            for (int b = 0; b < nb; b++) {
                __m512h v = r ? acc1[b] : acc0[b];
                _mm512_storeu_ps(o + 32 * b, _mm512_cvtph_ps(_mm512_castsi512_si256((__m512i)v)));
                _mm512_storeu_ps(o + 32 * b + 16, _mm512_cvtph_ps(_mm512_extracti64x4_epi64((__m512i)v, 1)));
            }
            for (int n = 0; n < 32 * nb; n++) energy += (double)o[n] * o[n];
        }
    }
    float sc = (float)sqrt(power / energy);
    for (int k = 0; k < K; k++) { float *o = wt + 2 * (size_t)k * M; for (int n = 0; n < 32 * nb; n++) o[n] *= sc; }
}

void rzf_fused_fp16(const float *H, float *W, int S, int K, int M, float alpha, float power, int nthreads) {
#pragma omp parallel for num_threads(nthreads) schedule(static)
    for (int s = 0; s < S; s++) {
        float hr[KMAX * MMAX], hi[KMAX * MMAX], g[KMAX * KMAX * 2], xr[KMAX * KMAX], xi[KMAX * KMAX];
        const float *Hs = H + (size_t)s * K * M * 2;
        load_h(K, M, Hs, hr, hi);
        gram_lower(K, M, hr, hi, alpha, g);
        gj_inv_one(K, g, xr, xi);
        form_w_fp16(K, M, Hs, xr, xi, power, W + (size_t)s * M * K * 2);
    }
}
int has_fp16(void) { return 1; }
#else
void rzf_fused_fp16(const float *H, float *W, int S, int K, int M, float alpha, float power, int nthreads) {}
int has_fp16(void) { return 0; }
#endif
