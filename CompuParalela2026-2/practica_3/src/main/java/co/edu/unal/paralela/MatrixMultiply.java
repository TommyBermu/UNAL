package co.edu.unal.paralela;

import static edu.rice.pcdp.PCDP.forseq2d;
import static edu.rice.pcdp.PCDP.forallChunked;

/**
 * Clase envolvente pata implementar de forma eficiente la multiplicación dde
 * matrices en paralelo.
 */
public final class MatrixMultiply {
    /**
     * Constructor por omisión.
     */
    private MatrixMultiply() {
    }

    /**
     * Realiza una multiplicación de matrices bidimensionales (A x B = C) de forma
     * secuencial.
     *
     * @param A Una matriz de entrada con dimensiones NxN
     * @param B Una matriz de entrada con dimensiones NxN
     * @param C Matriz de salida
     * @param N Tamaño de las matrices de entrada
     */
    public static void seqMatrixMultiply(final double[][] A, final double[][] B,
            final double[][] C, final int N) {
        forseq2d(0, N - 1, 0, N - 1, (i, j) -> {
            C[i][j] = 0.0;
            for (int k = 0; k < N; k++) {
                C[i][j] += A[i][k] * B[k][j];
            }
        });
    }

    /**
     * Realiza una multiplicación de matrices bidimensionales (A x B = C) de forma
     * paralela.
     *
     * @param A Una matriz de entrada con dimensiones NxN
     * @param B Una matriz de entrada con dimensiones NxN
     * @param C Matriz de salida
     * @param N amaño de las matrices de entrada
     */
    public static void parMatrixMultiply(final double[][] A, final double[][] B,
            final double[][] C, final int N) {
        forallChunked(0, N - 1, (i) -> {
            final double[] rowA = A[i];
            final double[] rowC = C[i];
            for (int j = 0; j < N; j++) {
                rowC[j] = 0.0;
            }
            for (int k = 0; k < N; k++) {
                final double a = rowA[k];
                final double[] rowB = B[k];
                for (int j = 0; j < N; j++) {
                    rowC[j] += a * rowB[j];
                }
            }
        });
    }
}
