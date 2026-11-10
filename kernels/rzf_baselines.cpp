// Library baselines for the fused RZF kernel: same contract as rzf_fused_chol in cmat_kernels.c
// (H [S][K][M] complex64 -> Wt [S][K][M] = (H^H G^-1)^T scaled to ||W||_F^2 = power, G = H H^H + alpha I),
// OpenMP over subcarriers, one single-threaded library call chain per subcarrier.
//   rzf_lapack: OpenBLAS cgemm for G, LAPACK cposv (Cholesky solve G Z = H, no explicit inverse).
//   rzf_eigen : Eigen, fixed-size matrices for the benchmarked (K, M), LLT solve; dynamic size otherwise.
#include <complex>
#include <cmath>
#include <vector>
#include <omp.h>
#include <Eigen/Dense>
#include <cblas.h>
#include <lapacke.h>

extern "C" void openblas_set_num_threads(int);

typedef std::complex<float> cf;

static inline void finish(int K, int M, const cf *Z, float power, cf *wt) {
    double e = 0.0;
    for (int n = 0; n < K * M; n++) e += std::norm(Z[n]);
    float sc = std::sqrt(power / (float)e);
    for (int n = 0; n < K * M; n++) wt[n] = std::conj(Z[n]) * sc;
}

extern "C" void rzf_lapack(const cf *H, cf *Wt, int S, int K, int M, float alpha, float power, int nthreads) {
    openblas_set_num_threads(1);
#pragma omp parallel num_threads(nthreads)
    {
        std::vector<cf> G(K * K), Z(K * M);
        const cf one(1.f, 0.f), zero(0.f, 0.f);
#pragma omp for schedule(static)
        for (int s = 0; s < S; s++) {
            const cf *h = H + (size_t)s * K * M;
            cblas_cgemm(CblasRowMajor, CblasNoTrans, CblasConjTrans, K, K, M, &one, h, M, h, M, &zero, G.data(), K);
            for (int k = 0; k < K; k++) G[k * K + k] += alpha;
            std::copy(h, h + K * M, Z.begin());
            LAPACKE_cposv(LAPACK_ROW_MAJOR, 'L', K, M, (lapack_complex_float *)G.data(), K,
                          (lapack_complex_float *)Z.data(), M);
            finish(K, M, Z.data(), power, Wt + (size_t)s * K * M);
        }
    }
}

template <int K, int M>
static void eigen_batch(const cf *H, cf *Wt, int S, int Kd, int Md, float alpha, float power, int nthreads) {
    typedef Eigen::Matrix<cf, K, M, (M == 1 ? Eigen::ColMajor : Eigen::RowMajor)> HM;
    typedef Eigen::Matrix<cf, K, K> GM;
#pragma omp parallel num_threads(nthreads)
    {
        HM Z(Kd, Md);
        GM G(Kd, Kd);
#pragma omp for schedule(static)
        for (int s = 0; s < S; s++) {
            Eigen::Map<const HM> h(H + (size_t)s * Kd * Md, Kd, Md);
            G.noalias() = h * h.adjoint();
            G.diagonal().array() += alpha;
            Z.noalias() = G.template selfadjointView<Eigen::Lower>().llt().solve(h);
            finish(Kd, Md, Z.data(), power, Wt + (size_t)s * Kd * Md);
        }
    }
}

extern "C" void rzf_eigen(const cf *H, cf *Wt, int S, int K, int M, float alpha, float power, int nthreads) {
    Eigen::setNbThreads(1);
    if (K == 8 && M == 64) eigen_batch<8, 64>(H, Wt, S, K, M, alpha, power, nthreads);
    else if (K == 16 && M == 64) eigen_batch<16, 64>(H, Wt, S, K, M, alpha, power, nthreads);
    else if (K == 32 && M == 64) eigen_batch<32, 64>(H, Wt, S, K, M, alpha, power, nthreads);
    else if (K == 16 && M == 128) eigen_batch<16, 128>(H, Wt, S, K, M, alpha, power, nthreads);
    else eigen_batch<Eigen::Dynamic, Eigen::Dynamic>(H, Wt, S, K, M, alpha, power, nthreads);
}
