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

// Exact inverse of Hermitian positive-definite G via Cholesky (G = L L^H), then X = L^-H L^-1. float32 complex.
void chol_inverse_batch(const float *G, float *Xout, int S, int K, int nthreads) {
#pragma omp parallel for num_threads(nthreads) schedule(static)
    for (int s = 0; s < S; s++) {
        float lr[KMAX * KMAX], li[KMAX * KMAX], yr[KMAX * KMAX], yi[KMAX * KMAX];
        float xr[KMAX * KMAX], xi[KMAX * KMAX];
        size_t off = (size_t)s * K * K * 2;
        const float *g = G + off;
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
        // Y = L^-1 (forward substitution on identity), row-oriented so inner loops are contiguous
        for (int i = 0; i < K; i++) {
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
        // X = Y^H Y  (Y lower triangular): X[i][j] = sum_k conj(Y[k][i]) Y[k][j], k >= max(i, j)
        for (int i = 0; i < K; i++)
            for (int j = 0; j < K; j++) { xr[i * K + j] = 0.f; xi[i * K + j] = 0.f; }
        for (int k = 0; k < K; k++)
            for (int i = 0; i <= k; i++) {
                float ar = yr[k * K + i], ai = -yi[k * K + i];
                for (int j = 0; j <= k; j++) {
                    xr[i * K + j] += ar * yr[k * K + j] - ai * yi[k * K + j];
                    xi[i * K + j] += ar * yi[k * K + j] + ai * yr[k * K + j];
                }
            }
        store_soa(K, xr, xi, Xout + off);
    }
}
