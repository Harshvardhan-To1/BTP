#!/bin/sh
cd "$(dirname "$0")" && gcc -O3 -march=native -fopenmp -shared -fPIC cmat_kernels.c -o libcmat.so -lm
