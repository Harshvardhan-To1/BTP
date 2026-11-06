#!/bin/sh
cd "$(dirname "$0")" && gcc -O3 -march=native -fopenmp -ffast-math -shared -fPIC cmat_kernels.c -o libcmat.so -lm
