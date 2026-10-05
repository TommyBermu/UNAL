#!/usr/bin/env python3
"""
Taller Practico Hilos - Computacion Paralela y Distribuida (UNAL)

Genera la tabla comparativa y las graficas (paso 9) a partir del archivo
resultados/resumen.csv producido por run_experimentos.sh.

Produce:
  - resultados/grafica_tiempos.png   (consumidores vs tiempo promedio)
  - resultados/grafica_speedup.png   (consumidores vs rapidez/speedup)
  - imprime la tabla comparativa en consola

Uso:
  python3 graficar.py [ruta_resumen.csv]

Requiere matplotlib:  pip install matplotlib
"""
import csv
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "resultados", "resumen.csv")
OUT_DIR = os.path.dirname(CSV_PATH)


def load():
    data = defaultdict(list)  # programa -> [(consumidores, promedio, speedup)]
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            prog = row["programa"]
            c = int(row["consumidores"])
            avg = float(row["promedio_ms"])
            try:
                sp = float(row["speedup"])
            except ValueError:
                sp = None
            data[prog].append((c, avg, sp))
    for prog in data:
        data[prog].sort(key=lambda x: x[0])
    return data


def print_table(data):
    print("\n================ TABLA COMPARATIVA ================")
    print(f"{'Programa':<34}{'Consum.':>8}{'Prom(ms)':>12}{'Speedup':>10}")
    print("-" * 64)
    for prog, rows in data.items():
        for c, avg, sp in rows:
            sp_s = f"{sp:.2f}x" if sp is not None else "NA"
            print(f"{prog:<34}{c:>8}{avg:>12.2f}{sp_s:>10}")
        print("-" * 64)


def plot(data):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n[AVISO] matplotlib no esta instalado; se omiten las graficas.")
        print("        Instala con: pip install matplotlib")
        return

    # Grafica 1: tiempo promedio
    plt.figure(figsize=(9, 6))
    for prog, rows in data.items():
        xs = [r[0] for r in rows]
        ys = [r[1] for r in rows]
        plt.plot(xs, ys, marker="o", label=prog)
    plt.xlabel("Numero de consumidores")
    plt.ylabel("Tiempo promedio (ms)")
    plt.title("Tiempo de ejecucion vs numero de consumidores")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(fontsize=8)
    plt.tight_layout()
    p1 = os.path.join(OUT_DIR, "grafica_tiempos.png")
    plt.savefig(p1, dpi=120)
    print(f"\nGrafica de tiempos: {p1}")

    # Grafica 2: speedup
    plt.figure(figsize=(9, 6))
    for prog, rows in data.items():
        xs = [r[0] for r in rows if r[2] is not None]
        ys = [r[2] for r in rows if r[2] is not None]
        if xs:
            plt.plot(xs, ys, marker="s", label=prog)
    plt.xlabel("Numero de consumidores")
    plt.ylabel("Rapidez / speedup (x)")
    plt.title("Rapidez vs numero de consumidores")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(fontsize=8)
    plt.tight_layout()
    p2 = os.path.join(OUT_DIR, "grafica_speedup.png")
    plt.savefig(p2, dpi=120)
    print(f"Grafica de speedup: {p2}")


if __name__ == "__main__":
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: no existe {CSV_PATH}. Ejecuta primero run_experimentos.sh")
        sys.exit(1)
    data = load()
    print_table(data)
    plot(data)
