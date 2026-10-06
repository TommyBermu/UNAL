#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Punto 9 del Taller Practico Hilos.

- Construye la tabla comparativa (consumidores, tiempo de ejecucion, rapidez).
- Calcula la rapidez (speedup) de cada ejecucion:
      speedup(N) = T(1 consumidor) / T(N consumidores)
- Genera dos graficas:
      * tiempo de ejecucion vs. numero de consumidores
      * rapidez (speedup) vs. numero de consumidores

Los datos se leen de resultados/resumen.txt. Si no existe, usa los valores
embebidos abajo (actualizalos si repites pruebas).
"""

import os
import csv
import re

import matplotlib
matplotlib.use("Agg")  # backend sin ventana (guarda a archivo)
import matplotlib.pyplot as plt

RAIZ = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(RAIZ, "resultados")
RESUMEN = os.path.join(OUT, "resumen.txt")

# Nombre corto para las leyendas de las graficas
NOMBRE_CORTO = {
    "WordCountProducerConsumer": "ProducerConsumer",
    "WordCountSynchronizedHashMap": "SynchronizedHashMap",
    "WordCountConcurrentHashMap": "ConcurrentHashMap",
    "WordCountBatchConcurrentHashMap": "BatchConcurrentHashMap",
}

# Datos de respaldo (se usan solo si no se puede leer resumen.txt)
DATOS_RESPALDO = {
    "WordCountProducerConsumer": {1: 17625.20},
    "WordCountSynchronizedHashMap": {
        1: 16553.00, 2: 20574.90, 3: 22196.00, 4: 20449.20,
        5: 22351.50, 6: 23202.20, 7: 22501.40,
    },
    "WordCountConcurrentHashMap": {
        1: 19970.80, 2: 10099.40, 3: 8206.80, 4: 6585.30,
        5: 6341.90, 6: 6184.50, 7: 6291.30,
    },
    "WordCountBatchConcurrentHashMap": {
        1: 19464.70, 2: 10309.10, 3: 7855.90, 4: 6832.80,
        5: 6686.20, 6: 6377.00, 7: 6554.80,
    },
}


def leer_resumen(path):
    """Lee resumen.txt y devuelve {programa: {consumidores: tiempo_ms}}."""
    datos = {}
    linea_re = re.compile(r"^(WordCount\S+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)")
    with open(path, encoding="utf-8") as f:
        for linea in f:
            m = linea_re.match(linea.strip())
            if m:
                prog, cons, ms = m.group(1), int(m.group(2)), float(m.group(3))
                datos.setdefault(prog, {})[cons] = ms
    return datos


def cargar_datos():
    if os.path.isfile(RESUMEN):
        try:
            d = leer_resumen(RESUMEN)
            if d:
                print(f"Datos leidos de {RESUMEN}")
                return d
        except Exception as e:
            print(f"No se pudo leer resumen.txt ({e}); usando datos de respaldo.")
    print("Usando datos de respaldo embebidos.")
    return DATOS_RESPALDO


def main():
    os.makedirs(OUT, exist_ok=True)
    datos = cargar_datos()

    # ---- Tabla comparativa + rapidez -------------------------------------
    filas = []  # (programa, consumidores, tiempo_ms, speedup)
    for prog, serie in datos.items():
        base = serie.get(1)  # tiempo con 1 consumidor = referencia del speedup
        for cons in sorted(serie):
            t = serie[cons]
            speedup = (base / t) if base else float("nan")
            filas.append((prog, cons, t, speedup))

    # CSV
    csv_path = os.path.join(OUT, "punto9_tabla.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Programa", "Consumidores", "Tiempo_promedio_ms", "Rapidez_speedup"])
        for prog, cons, t, s in filas:
            w.writerow([prog, cons, f"{t:.2f}", f"{s:.3f}"])
    print(f"Tabla CSV -> {csv_path}")

    # TXT legible
    txt_path = os.path.join(OUT, "punto9_tabla.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("PUNTO 9 - Tabla comparativa (tiempo y rapidez)\n")
        f.write("Rapidez(N) = Tiempo(1 consumidor) / Tiempo(N consumidores)\n\n")
        f.write(f"{'Programa':<32} | {'Cons.':>5} | {'Tiempo(ms)':>12} | {'Rapidez':>8}\n")
        f.write("-" * 32 + "-+-" + "-" * 5 + "-+-" + "-" * 12 + "-+-" + "-" * 8 + "\n")
        prog_prev = None
        for prog, cons, t, s in filas:
            if prog_prev is not None and prog != prog_prev:
                f.write("\n")
            f.write(f"{prog:<32} | {cons:>5} | {t:>12.2f} | {s:>8.3f}\n")
            prog_prev = prog
    print(f"Tabla TXT -> {txt_path}")

    # ---- Grafica 1: tiempo vs consumidores -------------------------------
    plt.figure(figsize=(9, 6))
    for prog, serie in datos.items():
        xs = sorted(serie)
        ys = [serie[x] for x in xs]
        plt.plot(xs, ys, marker="o", label=NOMBRE_CORTO.get(prog, prog))
    plt.title("Tiempo de ejecucion vs. numero de consumidores")
    plt.xlabel("Numero de consumidores")
    plt.ylabel("Tiempo promedio (ms)")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    g1 = os.path.join(OUT, "punto9_tiempo.png")
    plt.savefig(g1, dpi=150)
    plt.close()
    print(f"Grafica tiempo -> {g1}")

    # ---- Grafica 2: rapidez (speedup) vs consumidores --------------------
    plt.figure(figsize=(9, 6))
    for prog, serie in datos.items():
        base = serie.get(1)
        if not base:
            continue
        xs = sorted(serie)
        ys = [base / serie[x] for x in xs]
        plt.plot(xs, ys, marker="s", label=NOMBRE_CORTO.get(prog, prog))
    # Linea de speedup ideal (lineal) como referencia
    max_cons = max((max(s) for s in datos.values()), default=7)
    ideal = list(range(1, max_cons + 1))
    plt.plot(ideal, ideal, linestyle=":", color="gray", label="Ideal (lineal)")
    plt.title("Rapidez (speedup) vs. numero de consumidores")
    plt.xlabel("Numero de consumidores")
    plt.ylabel("Rapidez = T(1) / T(N)")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    g2 = os.path.join(OUT, "punto9_rapidez.png")
    plt.savefig(g2, dpi=150)
    plt.close()
    print(f"Grafica rapidez -> {g2}")

    # ---- Resumen en consola ----------------------------------------------
    print("\n" + "=" * 60)
    print("PUNTO 9 - RESUMEN")
    print("=" * 60)
    with open(txt_path, encoding="utf-8") as f:
        print(f.read())


if __name__ == "__main__":
    main()
