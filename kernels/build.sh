#!/bin/sh
cd "$(dirname "$0")" && gcc -O3 -march=native -fopenmp -ffast-math -mprefer-vector-width=512 -shared -fPIC cmat_kernels.c -o libcmat.so -lm \
  && gcc -O3 -march=native -fopenmp -ffast-math -mprefer-vector-width=512 -shared -fPIC iq_kernels.c -o libiq.so -llapacke -lopenblas -lm
