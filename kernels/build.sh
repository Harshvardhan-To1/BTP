#!/bin/sh
cd "$(dirname "$0")" && gcc -O3 -march=native -fopenmp -ffast-math -mprefer-vector-width=512 -shared -fPIC cmat_kernels.c -o libcmat.so -lm \
  && gcc -O3 -march=native -fopenmp -ffast-math -mprefer-vector-width=512 -shared -fPIC iq_kernels.c -o libiq.so -llapacke -lopenblas -lm \
  && g++ -O3 -march=native -fopenmp -ffast-math -shared -fPIC -I/usr/include/eigen3 -I/usr/include/x86_64-linux-gnu/openblas-pthread \
       rzf_baselines.cpp -o librzfbase.so -llapacke -lopenblas
