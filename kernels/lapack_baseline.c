/* Baseline RZF precoder in C on OpenBLAS + LAPACK (no fusion, standard library calls per subcarrier).
 *
 * Per subcarrier s, with B = H_s^H stored column-major (M x K), which is the [K][M] row-major layout of W^T:
 *   G = B^H B + alpha I            cblas_cherk
 *   G = L L^H                      LAPACKE_cpotrf_work
 *   W = B G^-1 = B L^-H L^-1       two cblas_ctrsm (right side)
 *   W *= sqrt(P / ||W||_F^2)
 * Subcarriers are split across OpenMP threads; OpenBLAS runs single-threaded inside each call.
 */
#include <cblas.h>
#include <lapacke.h>
#include <math.h>
#include <complex.h>
#include <stdlib.h>
#include <omp.h>

void openblas_set_num_threads(int);

void set_blas_single(void) { openblas_set_num_threads(1); }

void rzf_lapack(const float complex *H, float complex *W, int S, int K, int M, float alpha, float power, int nthreads) {
    const float complex one = 1.0f;
#pragma omp parallel num_threads(nthreads)
    {
        float complex *G = malloc(sizeof(float complex) * K * K);
#pragma omp for schedule(static)
        for (int s = 0; s < S; s++) {
            const float complex *h = H + (size_t)s * K * M;
            float complex *b = W + (size_t)s * K * M;
            for (int i = 0; i < K * M; i++) b[i] = conjf(h[i]);
            cblas_cherk(CblasColMajor, CblasLower, CblasConjTrans, K, M, 1.0f, b, M, 0.0f, G, K);
            for (int k = 0; k < K; k++) G[k * K + k] += alpha;
            LAPACKE_cpotrf_work(LAPACK_COL_MAJOR, 'L', K, G, K);
            cblas_ctrsm(CblasColMajor, CblasRight, CblasLower, CblasConjTrans, CblasNonUnit, M, K, &one, G, K, b, M);
            cblas_ctrsm(CblasColMajor, CblasRight, CblasLower, CblasNoTrans, CblasNonUnit, M, K, &one, G, K, b, M);
            float nrm = cblas_scnrm2(K * M, b, 1);
            cblas_csscal(K * M, sqrtf(power) / nrm, b, 1);
        }
        free(G);
    }
}
