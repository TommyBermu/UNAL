# Simulación IoT: verificación de integridad y autenticidad de firmware

Simula la actualización de firmware "por aire" (WiFi) de dos dispositivos IoT
(una **cámara** y un **sensor**) hechos con ESP32, verificando tres propiedades
antes de aceptar cualquier firmware:

| Propiedad | Pregunta que responde | Mecanismo |
|---|---|---|
| **Integridad** | ¿Llegó sin alterarse? | SHA-256 |
| **Autenticidad** | ¿Lo firmó quien dice? | Firma ECDSA P-256 |
| **Compatibilidad** | ¿Es para *este* aparato? | `device_type` **dentro** de lo firmado |

El PC actúa como servidor que firma y publica el firmware. Cada ESP32 descarga,
verifica y solo "aplica" (efecto visible en su LED) si las tres propiedades pasan.

> Es una simulación de la **verificación**: el ESP32 no se re-flashea de verdad,
> trata el firmware como un blob de datos. Eso aísla el concepto criptográfico,
> que es lo que se quiere demostrar.

## Por qué ECDSA P-256 y no Ed25519

El mbedTLS que incluye el framework Arduino-ESP32 soporta **ECDSA P-256** de
forma nativa y estable, pero **no** trae Ed25519 habilitado. Para no depender de
librerías externas frágiles, la firma es ECDSA P-256 sobre SHA-256. Es un
estándar perfectamente válido para autenticidad.

## Estructura

```
server/                   # corre en el PC (Python 3 + cryptography)
  gen_keys.py             # genera par ECDSA P-256; exporta la pública al firmware
  sign_firmware.py        # empaqueta metadata + firma + firmware -> .fwpkg
  build_firmwares.py      # genera y firma todos los paquetes (.fwpkg) de un golpe
  publish.py              # publica una version como "latest" (actualizacion OTA)
  serve.py                # servidor HTTP que publica los .fwpkg
  verify_local.py         # verificador espejo en el PC (mismo flujo que el ESP32)
  keys/                   # private.pem (NO compartir), public.pem
  firmwares/              # .bin de prueba y .fwpkg firmados
device/                   # proyecto PlatformIO (ESP32)
  platformio.ini          # entornos env:camera y env:sensor
  include/config.h        # WiFi, IP del servidor y qué paquete pedir  <-- EDITAR
  include/public_key.h    # clave pública embebida (la genera gen_keys.py)
  src/main.cpp            # descarga + verificación de 3 pasos
```

## Formato del paquete `.fwpkg`

```
[ "FWP1" 4B ][ meta_len 2B BE ][ metadata JSON ][ firma r||s 64B ][ firmware N ]
metadata = {"device_type","sha256","size","version"}   (claves ordenadas)
firmware = {"device_type","version","led":{"on","off"},"melody":[[freq_Hz,dur_ms],...]}
```
La firma cubre `metadata`, que contiene el `sha256` del firmware. El
**comportamiento** (ritmo del LED y melodía del buzzer) vive **dentro del
firmware** (`.bin`), no en una etiqueta aparte. Queda protegido por la cadena
`firma → hash → firmware`: si alguien altera el patrón, cambia el hash del
firmware, que ya no coincide con el `sha256` firmado, y el dispositivo lo
rechaza por integridad. El `device_type` y `version` van en ambos (metadata y
firmware) y el ESP32 comprueba que coincidan.

---

## Parte A — PC (servidor)

Requiere Python 3 y el paquete `cryptography` (ya instalado en esta máquina).

```bash
cd server
python3 gen_keys.py      # genera claves + include/public_key.h del ESP32
python3 build_firmwares.py   # genera y firma todos los .fwpkg en firmwares/
python3 serve.py         # publica por HTTP; anota la IP que imprime
```

`serve.py` imprime algo como `http://192.168.1.50:8000/`. Esa IP va en `config.h`.

> Si regeneras las claves con `gen_keys.py`, **recompila y reflashea** los ESP32,
> porque cambia la clave pública embebida.

## Parte B — ESP32 (dispositivos), con PlatformIO en VSCode

1. Abre la carpeta `device/` en VSCode (extensión PlatformIO).
2. Edita `include/config.h`:
   - `WIFI_SSID` / `WIFI_PASS`: tu red (router de casa o hotspot del PC; PC y
     ESP32 en la **misma** red).
   - `SERVER_BASE_URL`: la IP que mostró `serve.py`, con `:8000/` y barra final.
   El dispositivo ya no pide un archivo por nombre: consulta `/check` con su
   tipo y versión, y el servidor decide (ver abajo).
3. Si tu placa no es `esp32dev`, ajusta `board` en `platformio.ini`. Si el LED
   integrado no es GPIO2, ajusta `LED_BUILTIN`. El **buzzer pasivo** va en
   `BUZZER_PIN` (pata +) y **GND** (pata −).
4. Elige el entorno en la barra de PlatformIO:
   - **`env:camera`** para el ESP32 que será la cámara.
   - **`env:sensor`** para el ESP32 que será el sensor.
5. Upload a cada placa (flashea cada ESP32 con su entorno) y abre el **Monitor
   Serie** (115200 baudios) para ver el resultado de la verificación.

Por terminal sería: `pio run -e camera -t upload` y `pio run -e sensor -t upload`.

### Quién decide la actualización

El dispositivo **no** elige del catálogo. Consulta al servidor:
```
GET /check?type=camera&version=1
```
y el **servidor decide**: si hay una versión publicada mayor, responde con el
`.fwpkg`; si no, responde `204` ("estás al día"). Qué versión está publicada se
controla en el PC con `publish.py`.

Esto separa dos responsabilidades: el servidor decide **qué ofrecer**
(comodidad), pero el dispositivo decide **si lo acepta**, verificando siempre
firma + hash + tipo. El ESP32 **nunca confía en el servidor**; aunque este le
ofrezca algo, si la firma no valida, lo rechaza.

### El firmware define el comportamiento (LED + buzzer)

El comportamiento (ritmo del LED + melodía del buzzer) viaja **dentro del
firmware** (`.bin`), protegido por la cadena firma→hash. Cuando el ESP32 acepta
un firmware, lee ese patrón y lo ejecuta. Así se ve y se oye la diferencia:

| Firmware | LED | Buzzer |
|---|---|---|
| `camera_v1` | parpadeo rápido (120/120 ms) | dos bips agudos + nota alta |
| `camera_v2` | medio (250/150 ms) | melodía ascendente de 4 notas |
| `sensor_v1` | lento (600/600 ms) | un tono grave largo |
| `sensor_v2` | medio-lento (400/400 ms) | dos tonos graves alternados |

Alterar el patrón cambia el hash del firmware, que ya no coincide con el firmado,
y el dispositivo lo rechaza por integridad.

---

## Guion de la demostración

Deja el servidor corriendo (`python3 serve.py`) y los ESP32 flasheados una vez
(`env:camera` y `env:sensor`). Todo lo demás se hace desde el PC con `publish.py`,
**sin tocar los ESP32**.

### Parte 1: actualización de firmware por WiFi (v1 → v2)

La narrativa principal: el dispositivo arranca con la v1 y se **actualiza** a la
v2 por aire. El cambio se **oye y se ve** (otro ritmo y otra melodía).

```bash
cd server
python3 publish.py camera 1     # estado inicial: v1 publicada
# (el ESP32 cámara, en su próximo chequeo, descarga v1 y suena el ritmo v1)
python3 publish.py camera 2     # ACTUALIZAR: ahora se publica la v2
# (a los ~15 s el ESP32 descarga v2, la verifica y cambia a sonar/parpadear v2)
```
Lo mismo con `sensor`. En el monitor serie verás `ACEPTADO (ACTUALIZADO): ... v2`.

### Parte 2: rechazos (las tres propiedades de seguridad)

Primero genera los paquetes de ataque (una vez):
```bash
python3 build_firmwares.py --with-attacks
```

Luego, con `publish.py`, vas publicando cada caso y miras el serial del ESP32:

| Comando en el PC | Placa | Resultado en el ESP32 | Qué demuestra |
|---|---|---|---|
| `publish.py camera 2` | cámara | **ACEPTA**, cambia a v2 | Actualización legítima |
| `publish.py sensor 2` | sensor | **ACEPTA**, cambia a v2 | Actualización legítima |
| `publish.py camera tampered` | cámara | **RECHAZA** (integridad) | 1 byte alterado se detecta |
| `publish.py camera fakekey` | cámara | **RECHAZA** (autenticidad) | Firma de clave falsa se detecta |

Para volver a la normalidad tras un ataque: `publish.py camera 1`.

**Caso de compatibilidad** (el corazón de la idea): flashea un ESP32 con el
entorno `env:sensor` y publica un firmware de cámara apuntando su `/check` al
tipo cámara. La forma simple de verlo es con el verificador del PC (abajo):
el paquete de cámara es legítimo y bien firmado, pero un sensor lo rechaza
porque el `device_type` firmado no es el suyo.

Cuando un firmware se rechaza, el dispositivo **mantiene el comportamiento que
ya tenía** (no se apaga); si nunca había aceptado ninguno, queda en silencio.

### Verificación sin hardware (en el PC)

Puedes mostrar los mismos resultados sin ESP32, con el verificador espejo:

```bash
cd server
python3 verify_local.py --pkg firmwares/camera_v1.fwpkg          --my-type camera   # ACEPTA
python3 verify_local.py --pkg firmwares/camera_v2.fwpkg          --my-type camera   # ACEPTA (v2)
python3 verify_local.py --pkg firmwares/sensor_v1.fwpkg          --my-type sensor   # ACEPTA
python3 verify_local.py --pkg firmwares/camera_v1.fwpkg          --my-type sensor   # RECHAZA (tipo)
python3 verify_local.py --pkg firmwares/camera_v1_tampered.fwpkg --my-type camera   # RECHAZA (integridad)
python3 verify_local.py --pkg firmwares/camera_v1_fakekey.fwpkg  --my-type camera   # RECHAZA (autenticidad)
```

---

## Notas prácticas

- **Red aislada sin router:** puedes usar el hotspot del PC (Linux:
  `nmcli device wifi hotspot ssid <ssid> password <clave>`; Windows: "Mobile
  hotspot"). El código del servidor es el mismo; solo cambia a qué red se
  conectan los ESP32. Algunos hotspots de PC aíslan clientes: si los ESP32 no
  alcanzan al PC, usa un router.
- **LED integrado:** la mayoría de DevKit ESP32 lo tienen en GPIO2. Si el tuyo
  no parpadea, prueba otro GPIO en `LED_BUILTIN` dentro de `src/main.cpp`.
- **La clave privada** (`server/keys/private.pem`) nunca sale del PC. El ESP32
  solo lleva la pública. Esa separación es lo que hace útil la firma.
- **Arduino UNO:** quedan fuera a propósito. El ESP32 ya es un dispositivo IoT
  completo (CPU + WiFi + GPIO) y hace de "periférico" con su propio LED. Un
  ATmega328P no tiene radio ni recursos para verificar firmas de forma realista.
- Las antenas / tarjeta WiFi del portátil no aplican: el ESP32 trae su propia
  radio y antena integradas.
```
