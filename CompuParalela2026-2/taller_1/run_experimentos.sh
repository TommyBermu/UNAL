#!/usr/bin/env bash
#
# Taller Practico Hilos - Computacion Paralela y Distribuida (UNAL)
# Automatiza las ejecuciones de los 4 programas WordCount.
#
# Para cada configuracion ejecuta N repeticiones (por defecto 10), guarda
# un archivo .txt por variacion de consumidores con:
#   - el tiempo de cada corrida
#   - el promedio
#   - la rapidez (speedup) respecto al caso base (1 consumidor)
#   - el top-5 / bottom-5 de palabras (de la ultima corrida)
#
# Uso:
#   ./run_experimentos.sh /ruta/al/enwiki-latest-pages-articles13.xml [REPS] [XMX]
#
# Ejemplos:
#   ./run_experimentos.sh ~/datos/enwiki.xml
#   ./run_experimentos.sh ~/datos/enwiki.xml 10 4g
#
set -euo pipefail

# ----------------------------------------------------------------------------
# Parametros
# ----------------------------------------------------------------------------
DATA_FILE="${1:-}"
REPS="${2:-10}"
XMX="${3:-4g}"              # memoria maxima de la JVM (-Xmx)
MAX_CONSUMERS=7             # consumidores de 1 a 7 (pasos 6,7,8 del taller)

if [[ -z "$DATA_FILE" ]]; then
  echo "ERROR: debes indicar la ruta del archivo XML de entrada."
  echo "Uso: $0 /ruta/al/enwiki-latest-pages-articles13.xml [REPS] [XMX]"
  exit 1
fi
if [[ ! -f "$DATA_FILE" ]]; then
  echo "ERROR: no existe el archivo de datos: $DATA_FILE"
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$ROOT/resultados"
SUMMARY_CSV="$OUT_DIR/resumen.csv"
JVM_OPTS="-Xmx${XMX}"

mkdir -p "$OUT_DIR"

echo "============================================================"
echo " Taller Practico Hilos - ejecucion de experimentos"
echo "============================================================"
echo " Datos      : $DATA_FILE"
echo " Repeticiones: $REPS"
echo " JVM        : $JVM_OPTS"
echo " Salida     : $OUT_DIR"
echo "============================================================"

# ----------------------------------------------------------------------------
# 1. Compilar los 4 proyectos
# ----------------------------------------------------------------------------
PROJECTS=(
  WordCountProducerConsumer
  WordCountSynchronizedHashMap
  WordCountConcurrentHashMap
  WordCountBatchConcurrentHashMap
)

echo
echo ">> Compilando proyectos..."
for p in "${PROJECTS[@]}"; do
  echo "   - $p"
  ( cd "$ROOT/$p" && mvn -q compile )
done
echo ">> Compilacion completa."

# ----------------------------------------------------------------------------
# Encabezado del CSV resumen
# ----------------------------------------------------------------------------
echo "programa,consumidores,promedio_ms,speedup,corridas_ms" > "$SUMMARY_CSV"

# ----------------------------------------------------------------------------
# Funcion: corre un programa para un numero de consumidores dado.
#   $1 = nombre del proyecto
#   $2 = numero de consumidores (vacio -> no se pasa, usado en ProducerConsumer)
#   $3 = archivo de salida .txt
# Imprime (stdout) el promedio en ms para que el llamador lo capture.
# ----------------------------------------------------------------------------
run_config() {
  local project="$1"
  local consumers="$2"
  local outfile="$3"
  local cp="$ROOT/$project/target/classes"

  {
    echo "============================================================"
    echo " Programa     : $project"
    if [[ -n "$consumers" ]]; then
      echo " Consumidores : $consumers"
    else
      echo " Consumidores : 1 (productor-consumidor fijo)"
    fi
    echo " Archivo datos: $DATA_FILE"
    echo " Repeticiones : $REPS"
    echo " JVM          : $JVM_OPTS"
    echo " Fecha        : $(date '+%Y-%m-%d %H:%M:%S')"
    echo "============================================================"
  } > "$outfile"

  local total=0
  local last_output=""
  local -a times=()

  for ((r=1; r<=REPS; r++)); do
    local output
    if [[ -n "$consumers" ]]; then
      output="$(java $JVM_OPTS -cp "$cp" com.paulbutcher.WordCount "$DATA_FILE" "$consumers")"
    else
      output="$(java $JVM_OPTS -cp "$cp" com.paulbutcher.WordCount "$DATA_FILE")"
    fi
    last_output="$output"

    # Extraer el tiempo "Elapsed time: NNNms"
    local ms
    ms="$(echo "$output" | grep -oE 'Elapsed time: [0-9]+ms' | grep -oE '[0-9]+' | head -n1)"
    times+=("$ms")
    total=$((total + ms))
    printf "  Corrida %02d: %s ms\n" "$r" "$ms" | tee -a "$outfile"
  done

  # Promedio (con 2 decimales via awk)
  local avg
  avg="$(awk -v t="$total" -v n="$REPS" 'BEGIN{ printf "%.2f", t/n }')"

  {
    echo "------------------------------------------------------------"
    echo "Tiempos (ms): ${times[*]}"
    echo "PROMEDIO (ms): $avg"
    echo "------------------------------------------------------------"
    echo
    echo ">> Resultado de palabras (ultima corrida):"
    echo "$last_output" | sed -n '/Palabras distintas/,$p'
  } >> "$outfile"

  # Devolver avg y la lista de corridas por una variable global
  LAST_AVG="$avg"
  LAST_TIMES="${times[*]}"
}

# ----------------------------------------------------------------------------
# 2. WordCountProducerConsumer (1 productor, 1 consumidor) - paso 5
# ----------------------------------------------------------------------------
echo
echo ">> [1/4] WordCountProducerConsumer (1 consumidor)"
OUT="$OUT_DIR/WordCountProducerConsumer_consumidores_1.txt"
run_config "WordCountProducerConsumer" "" "$OUT"
PC_BASE="$LAST_AVG"
echo "WordCountProducerConsumer,1,$LAST_AVG,1.00,\"$LAST_TIMES\"" >> "$SUMMARY_CSV"
echo "   promedio: $LAST_AVG ms  ->  $OUT"

# ----------------------------------------------------------------------------
# Funcion para los 3 programas con 1..7 consumidores (pasos 6,7,8)
# El speedup se calcula respecto al caso de 1 consumidor del MISMO programa.
# ----------------------------------------------------------------------------
run_scaling_program() {
  local project="$1"
  local base_avg=""
  echo
  echo ">> $project (1..$MAX_CONSUMERS consumidores)"
  for ((c=1; c<=MAX_CONSUMERS; c++)); do
    local out="$OUT_DIR/${project}_consumidores_${c}.txt"
    run_config "$project" "$c" "$out"
    if [[ "$c" -eq 1 ]]; then
      base_avg="$LAST_AVG"
    fi
    local speedup
    speedup="$(awk -v b="$base_avg" -v a="$LAST_AVG" 'BEGIN{ if(a>0) printf "%.2f", b/a; else print "NA" }')"
    # anexar speedup al archivo
    echo "RAPIDEZ (speedup vs 1 consumidor): ${speedup}x" >> "$out"
    echo "${project},${c},${LAST_AVG},${speedup},\"${LAST_TIMES}\"" >> "$SUMMARY_CSV"
    echo "   c=$c  promedio: $LAST_AVG ms  speedup: ${speedup}x  ->  $out"
  done
}

# ----------------------------------------------------------------------------
# 3,4,5. Programas escalables
# ----------------------------------------------------------------------------
run_scaling_program "WordCountSynchronizedHashMap"
run_scaling_program "WordCountConcurrentHashMap"
run_scaling_program "WordCountBatchConcurrentHashMap"

echo
echo "============================================================"
echo " LISTO. Archivos .txt en: $OUT_DIR"
echo " Resumen CSV            : $SUMMARY_CSV"
echo "============================================================"
echo
echo "Resumen:"
column -t -s',' "$SUMMARY_CSV" 2>/dev/null || cat "$SUMMARY_CSV"
