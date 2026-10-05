#!/usr/bin/env bash
###############################################################################
# Taller Practico Hilos - Ejecucion automatica de todas las pruebas
#
# Puntos 5-8 del documento:
#   5. WordCountProducerConsumer         -> 1 productor, 1 consumidor
#   6. WordCountSynchronizedHashMap      -> 1,2,3,4,5,6,7 consumidores
#   7. WordCountConcurrentHashMap        -> 1,2,3,4,5,6,7 consumidores
#   8. WordCountBatchConcurrentHashMap   -> 1,2,3,4,5,6,7 consumidores
#
# Cada caso se ejecuta 10 veces y se calcula el promedio.
# Se genera un archivo .txt por cada tanda de 10 pruebas, con su promedio.
# Al final se escribe un resumen general (resumen.txt).
###############################################################################

set -u

# --- Configuracion ---------------------------------------------------------
RAIZ="$(cd "$(dirname "$0")" && pwd)"
OUT="${OUT:-$RAIZ/resultados}"
REPES="${REPES:-10}"                            # repeticiones por caso (minimo 10 segun el PDF)
CONSUMIDORES="${CONSUMIDORES:-1 2 3 4 5 6 7}"   # casos de consumidores para los puntos 6,7,8
MAIN="com.paulbutcher.WordCount"

# Flags para desactivar los limites del parser XML de Java moderno (Java 15+).
# Sin esto, el parser corta la lectura a ~2900 paginas y las pruebas quedan
# incompletas (terminan en segundos en vez de procesar las 100.000 paginas).
JVM_FLAGS="-Djdk.xml.maxGeneralEntitySizeLimit=0 -Djdk.xml.totalEntitySizeLimit=0 -Djdk.xml.entityExpansionLimit=0"

mkdir -p "$OUT"

# Programas con numero de consumidores configurable (args[0] = #consumidores)
PROG_MULTI="WordCountSynchronizedHashMap WordCountConcurrentHashMap WordCountBatchConcurrentHashMap"

# --- Utilidades ------------------------------------------------------------

# Compila un proyecto (si no esta compilado) y devuelve su classpath
compilar() {
  local proj="$1"
  echo "  compilando $proj ..."
  ( cd "$RAIZ/$proj" && mvn -q clean compile >/dev/null 2>&1 )
}

# Ejecuta una tanda de REPES corridas de un programa con N consumidores.
# $1 = proyecto, $2 = numero de consumidores (vacio para ProducerConsumer),
# $3 = etiqueta descriptiva, $4 = archivo de salida
tanda() {
  local proj="$1"; local n="$2"; local etiqueta="$3"; local archivo="$4"
  local cp="$RAIZ/$proj/target/classes"
  local suma=0
  local tiempos=()

  {
    echo "============================================================"
    echo " Programa : $proj"
    echo " Caso     : $etiqueta"
    echo " Repeticiones: $REPES"
    echo " Fecha    : $(date '+%Y-%m-%d %H:%M:%S')"
    echo "============================================================"
  } > "$archivo"

  for i in $(seq 1 "$REPES"); do
    # Captura la salida completa de la corrida
    local salida
    salida=$(cd "$RAIZ/$proj" && java $JVM_FLAGS -cp target/classes "$MAIN" $n 2>/dev/null)
    # Extrae el tiempo "Elapsed time: XXXms"
    local ms
    ms=$(echo "$salida" | grep -oE 'Elapsed time: [0-9]+' | grep -oE '[0-9]+')
    ms=${ms:-0}
    tiempos+=("$ms")
    suma=$((suma + ms))
    printf "  Corrida %2d: %6d ms\n" "$i" "$ms" >> "$archivo"
    printf "  [%s | %s] corrida %2d/%d -> %d ms\n" "$proj" "$etiqueta" "$i" "$REPES" "$ms"
  done

  # Promedio (una cifra decimal)
  local prom
  prom=$(awk "BEGIN { printf \"%.2f\", $suma/$REPES }")

  {
    echo "------------------------------------------------------------"
    echo " Suma total : ${suma} ms"
    echo " PROMEDIO   : ${prom} ms"
    echo "------------------------------------------------------------"
  } >> "$archivo"

  echo "  -> promedio: ${prom} ms  (guardado en ${archivo#$RAIZ/})"
  echo ""

  # Devuelve datos para el resumen via variable global
  ULTIMO_PROM="$prom"
}

# --- Inicio ----------------------------------------------------------------
echo "########################################################"
echo "# Ejecutando pruebas del Taller (REPES=$REPES por caso) #"
echo "########################################################"
echo ""

RESUMEN="$OUT/resumen.txt"
{
  echo "RESUMEN GENERAL DE PRUEBAS - Taller Practico Hilos"
  echo "Fecha: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "Repeticiones por caso: $REPES"
  echo ""
  printf "%-32s | %-12s | %-12s\n" "Programa" "Consumidores" "Promedio(ms)"
  printf "%-32s-+-%-12s-+-%-12s\n" "--------------------------------" "------------" "------------"
} > "$RESUMEN"

# --- Punto 5: WordCountProducerConsumer (1 productor, 1 consumidor) ---------
PROJ="WordCountProducerConsumer"
compilar "$PROJ"
tanda "$PROJ" "" "1 productor / 1 consumidor" "$OUT/${PROJ}_1cons.txt"
printf "%-32s | %-12s | %-12s\n" "$PROJ" "1" "$ULTIMO_PROM" >> "$RESUMEN"

# --- Puntos 6,7,8: programas con 1..7 consumidores --------------------------
for PROJ in $PROG_MULTI; do
  compilar "$PROJ"
  for N in $CONSUMIDORES; do
    tanda "$PROJ" "$N" "${N} consumidor(es)" "$OUT/${PROJ}_${N}cons.txt"
    printf "%-32s | %-12s | %-12s\n" "$PROJ" "$N" "$ULTIMO_PROM" >> "$RESUMEN"
  done
  echo "" >> "$RESUMEN"
done

# --- Punto 10: palabras con mas y menos repeticiones ------------------------
# Se hace UNA corrida adicional y se guarda la salida completa (incluye el
# top 5 / bottom 5 que imprime Results.printTopAndBottom).
PALABRAS="$OUT/palabras_top_bottom.txt"
PROJ_P10="WordCountConcurrentHashMap"
N_P10=4
echo ""
echo "=== Punto 10: generando top 5 / bottom 5 de palabras ($PROJ_P10, $N_P10 consumidores) ==="
{
  echo "============================================================"
  echo " PUNTO 10 - Palabras con mas y menos repeticiones"
  echo " Programa : $PROJ_P10 ($N_P10 consumidores)"
  echo " Fecha    : $(date '+%Y-%m-%d %H:%M:%S')"
  echo "============================================================"
  ( cd "$RAIZ/$PROJ_P10" && java $JVM_FLAGS -cp target/classes "$MAIN" "$N_P10" 2>/dev/null )
} > "$PALABRAS"
echo "  -> guardado en ${PALABRAS#$RAIZ/}"

echo "########################################################"
echo "# Listo. Resultados en: $OUT"
echo "# Resumen general       : $RESUMEN"
echo "# Punto 10 (palabras)   : $PALABRAS"
echo "########################################################"
cat "$RESUMEN"
