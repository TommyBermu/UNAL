/*
 * Dispositivo IoT (ESP32) que descarga un paquete de firmware por WiFi y
 * verifica, en este orden, antes de "aceptarlo":
 *
 *   1) AUTENTICIDAD  -> firma ECDSA P-256 sobre el bloque metadata (clave publica embebida).
 *   2) INTEGRIDAD    -> SHA-256 del firmware recibido == el hash dentro de metadata.
 *   3) COMPATIBILIDAD -> metadata.device_type == DEVICE_TYPE de ESTA placa.
 *
 * Si las tres pasan y la version es nueva: ACEPTA y ejecuta el COMPORTAMIENTO
 * que viene DENTRO del firmware (patron de LED + melodia del buzzer).
 * Si alguna falla: RECHAZA e imprime el motivo por serial, sin cambiar nada.
 *
 * Este firmware NO re-flashea el ESP32: es una simulacion de la VERIFICACION.
 * Pero el "firmware" recibido NO es relleno: es un JSON con el comportamiento
 * (tipo, version, led, melody). El ESP32 lo lee tras verificarlo y lo aplica.
 * El comportamiento queda protegido por la cadena hash->firma: alterar el .bin
 * cambia su hash y rompe la verificacion de integridad.
 *
 * Formato del paquete (ver server/sign_firmware.py):
 *   [MAGIC 4] [meta_len 2 BE] [metadata JSON] [firma 64] [firmware N]
 *   metadata = {device_type, version, size, sha256}
 *   firmware = {device_type, version, led:{on,off}, melody:[[freq,dur],...]}
 *
 * mbedTLS (SHA-256 y ECDSA P-256) viene con Arduino-ESP32.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>   // NVS: recuerda la version instalada entre reinicios

#include "mbedtls/sha256.h"
#include "mbedtls/ecdsa.h"
#include "mbedtls/ecp.h"
#include "mbedtls/bignum.h"

#include "config.h"
#include "public_key.h"   // generado por server/gen_keys.py

#ifndef DEVICE_TYPE
#define DEVICE_TYPE "camera"   // valor por defecto si no vino del build flag
#endif

static const uint8_t MAGIC[4] = {'F', 'W', 'P', '1'};

#ifndef LED_BUILTIN
#define LED_BUILTIN 2   // GPIO2 en la mayoria de DevKit ESP32
#endif

// Buzzer PASIVO conectado a este pin (+ a GPIO4, - a GND).
#ifndef BUZZER_PIN
#define BUZZER_PIN 4
#endif
// Canal LEDC (solo informativo; en core 3.x la API usa el PIN directamente).
#define BUZZER_LEDC_CHANNEL 0

// Estado del "firmware aceptado" -> controla el efecto fisico visible.
static bool accepted = false;
static int acceptedVersion = -1;

// Version actualmente INSTALADA (persistida en NVS). -1 = ninguna todavia.
static int installedVersion = -1;
static Preferences prefs;

// --- Patron de LED + melodia que trae el firmware aceptado ---
#define MAX_NOTES 32
static int   patLedOn = 150;     // ms LED encendido
static int   patLedOff = 150;    // ms LED apagado
static int   patFreq[MAX_NOTES]; // frecuencia de cada nota (0 = silencio)
static int   patDur[MAX_NOTES];  // duracion de cada nota en ms
static int   patNoteCount = 0;   // numero de notas de la melodia

// ---------- utilidades ----------

static void log_line(const String &s) {
    Serial.println(s);
}

// Extrae el valor de una clave simple de un JSON compacto {"k":"v",...} o {"k":N,...}.
// No es un parser general; basta para el metadata fijo que produce el servidor.
static bool json_get_string(const String &json, const String &key, String &out) {
    String needle = "\"" + key + "\":\"";
    int i = json.indexOf(needle);
    if (i < 0) return false;
    i += needle.length();
    int j = json.indexOf('"', i);
    if (j < 0) return false;
    out = json.substring(i, j);
    return true;
}

static bool json_get_int(const String &json, const String &key, long &out) {
    String needle = "\"" + key + "\":";
    int i = json.indexOf(needle);
    if (i < 0) return false;
    i += needle.length();
    // salta un posible espacio
    while (i < (int)json.length() && json[i] == ' ') i++;
    int j = i;
    while (j < (int)json.length() && (isdigit(json[j]) || json[j] == '-')) j++;
    if (j == i) return false;
    out = json.substring(i, j).toInt();
    return true;
}

static String to_hex(const uint8_t *buf, size_t len) {
    static const char *hexchars = "0123456789abcdef";
    String s;
    s.reserve(len * 2);
    for (size_t i = 0; i < len; i++) {
        s += hexchars[buf[i] >> 4];
        s += hexchars[buf[i] & 0x0F];
    }
    return s;
}

// Parsea el patron del CUERPO del firmware (.bin): led on/off y la lista de
// notas [[freq,dur],...]. Parser minimo adaptado al JSON que produce el servidor.
static void parse_pattern(const String &json) {
    // valores por defecto por si el firmware no trae patron
    patLedOn = 150; patLedOff = 150; patNoteCount = 0;

    long on = 150, off = 150;
    if (json_get_int(json, "on", on)) patLedOn = (int)on;
    if (json_get_int(json, "off", off)) patLedOff = (int)off;

    int m = json.indexOf("\"melody\":[");
    if (m < 0) return;
    // Recorre todos los pares [freq,dur] que aparezcan tras "melody":[
    patNoteCount = 0;
    int i = m + 9;                 // justo despues de "melody":
    int melodyEnd = json.indexOf("]]", i);   // cierre del array externo
    if (melodyEnd < 0) melodyEnd = json.length();
    while (patNoteCount < MAX_NOTES) {
        int open = json.indexOf('[', i + 1);
        if (open < 0 || open > melodyEnd) break;
        int comma = json.indexOf(',', open);
        int close = json.indexOf(']', open);
        if (comma < 0 || close < 0 || comma > close) break;
        patFreq[patNoteCount] = json.substring(open + 1, comma).toInt();
        patDur[patNoteCount]  = json.substring(comma + 1, close).toInt();
        patNoteCount++;
        i = close;
    }
}

// ---------- verificacion criptografica ----------

// Verifica una firma ECDSA P-256 (formato r||s, 64 bytes) sobre el SHA-256
// de `msg`, usando la clave publica PUBLIC_KEY_XY (64 bytes X||Y).
// Devuelve true si la firma es valida. Todo con mbedTLS nativo del ESP32.
static bool ecdsa_p256_verify(const uint8_t *msg, size_t msg_len,
                              const uint8_t *sig_rs) {
    bool ok = false;

    mbedtls_ecp_group grp;
    mbedtls_ecp_point Q;
    mbedtls_mpi r, s;
    mbedtls_ecp_group_init(&grp);
    mbedtls_ecp_point_init(&Q);
    mbedtls_mpi_init(&r);
    mbedtls_mpi_init(&s);

    do {
        if (mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1) != 0) break;

        // Reconstruye el punto publico: 0x04 || X || Y.
        uint8_t point[65];
        point[0] = 0x04;
        memcpy(point + 1, PUBLIC_KEY_XY, 64);
        if (mbedtls_ecp_point_read_binary(&grp, &Q, point, sizeof(point)) != 0) break;
        if (mbedtls_ecp_check_pubkey(&grp, &Q) != 0) break;

        // r y s desde los 64 bytes de la firma.
        if (mbedtls_mpi_read_binary(&r, sig_rs, 32) != 0) break;
        if (mbedtls_mpi_read_binary(&s, sig_rs + 32, 32) != 0) break;

        // Hash del mensaje (metadata).
        uint8_t digest[32];
        mbedtls_sha256_context sc;
        mbedtls_sha256_init(&sc);
        mbedtls_sha256_starts(&sc, 0);
        mbedtls_sha256_update(&sc, msg, msg_len);
        mbedtls_sha256_finish(&sc, digest);
        mbedtls_sha256_free(&sc);

        int rc = mbedtls_ecdsa_verify(&grp, digest, sizeof(digest), &Q, &r, &s);
        ok = (rc == 0);
    } while (false);

    mbedtls_mpi_free(&r);
    mbedtls_mpi_free(&s);
    mbedtls_ecp_point_free(&Q);
    mbedtls_ecp_group_free(&grp);
    return ok;
}

static void sha256(const uint8_t *data, size_t len, uint8_t out[32]) {
    mbedtls_sha256_context ctx;
    mbedtls_sha256_init(&ctx);
    mbedtls_sha256_starts(&ctx, 0);   // 0 = SHA-256 (no SHA-224)
    mbedtls_sha256_update(&ctx, data, len);
    mbedtls_sha256_finish(&ctx, out);
    mbedtls_sha256_free(&ctx);
}

// Resultado de la verificacion de un paquete.
enum VerifyResult {
    VR_UPDATED,    // paso las 3 propiedades y la version es nueva -> aplicado
    VR_REJECTED,   // fallo seguridad (firma/hash/tipo) o formato -> descartar
    VR_UPTODATE    // valido pero version no mayor que la instalada -> no cambiar nada
};

// Aplica los 3 pasos sobre el paquete completo en memoria.
static VerifyResult verify_package(const uint8_t *pkg, size_t pkg_len) {
    if (pkg_len < 4 + 2 + 64) {
        log_line("  RECHAZADO: paquete demasiado corto");
        return VR_REJECTED;
    }
    if (memcmp(pkg, MAGIC, 4) != 0) {
        log_line("  RECHAZADO: formato invalido (magic)");
        return VR_REJECTED;
    }
    size_t off = 4;
    uint16_t meta_len = (pkg[off] << 8) | pkg[off + 1];
    off += 2;
    if (off + meta_len + 64 > pkg_len) {
        log_line("  RECHAZADO: longitudes inconsistentes");
        return VR_REJECTED;
    }
    const uint8_t *meta = pkg + off;
    off += meta_len;
    const uint8_t *sig = pkg + off;
    off += 64;
    const uint8_t *firmware = pkg + off;
    size_t fw_len = pkg_len - off;

    // Paso 1: AUTENTICIDAD
    if (!ecdsa_p256_verify(meta, meta_len, sig)) {
        log_line("  RECHAZADO: firma invalida (AUTENTICIDAD)");
        return VR_REJECTED;
    }
    log_line("  [1/3] Firma ECDSA P-256 valida -> autenticidad OK");

    String metaStr;
    metaStr.reserve(meta_len + 1);
    for (size_t i = 0; i < meta_len; i++) metaStr += (char)meta[i];

    // Paso 2: INTEGRIDAD
    String wantHash;
    long wantSize = 0;
    if (!json_get_string(metaStr, "sha256", wantHash) ||
        !json_get_int(metaStr, "size", wantSize)) {
        log_line("  RECHAZADO: metadata ilegible");
        return VR_REJECTED;
    }
    if ((long)fw_len != wantSize) {
        log_line("  RECHAZADO: tamano no coincide (INTEGRIDAD)");
        return VR_REJECTED;
    }
    uint8_t digest[32];
    sha256(firmware, fw_len, digest);
    String gotHash = to_hex(digest, 32);
    if (gotHash != wantHash) {
        log_line("  RECHAZADO: hash no coincide (INTEGRIDAD)");
        log_line("    esperado: " + wantHash);
        log_line("    obtenido: " + gotHash);
        return VR_REJECTED;
    }
    log_line("  [2/3] SHA-256 coincide -> integridad OK");

    // Paso 3: COMPATIBILIDAD
    String fwType;
    long fwVersion = -1;
    if (!json_get_string(metaStr, "device_type", fwType) ||
        !json_get_int(metaStr, "version", fwVersion)) {
        log_line("  RECHAZADO: metadata sin device_type/version");
        return VR_REJECTED;
    }
    if (fwType != String(DEVICE_TYPE)) {
        log_line("  RECHAZADO: firmware para '" + fwType +
                 "' pero yo soy '" + String(DEVICE_TYPE) +
                 "' (COMPATIBILIDAD)");
        return VR_REJECTED;
    }
    log_line("  [3/3] device_type coincide -> compatibilidad OK");

    // El comportamiento vive DENTRO del firmware (.bin), ya protegido por el hash.
    // Lo pasamos a String para leer su patron.
    String body;
    body.reserve(fw_len + 1);
    for (size_t i = 0; i < fw_len; i++) body += (char)firmware[i];

    // Consistencia: el tipo/version del .bin deben coincidir con la metadata firmada.
    String bodyType;
    long bodyVersion = -1;
    if (!json_get_string(body, "device_type", bodyType) ||
        !json_get_int(body, "version", bodyVersion)) {
        log_line("  RECHAZADO: cuerpo del firmware ilegible");
        return VR_REJECTED;
    }
    if (bodyType != fwType || bodyVersion != fwVersion) {
        log_line("  RECHAZADO: el .bin no concuerda con la metadata (consistencia)");
        return VR_REJECTED;
    }

    // Politica OTA: actualizar solo si la version es MAYOR que la instalada
    // (anti-downgrade, y evita re-aplicar la misma version una y otra vez).
    if ((int)fwVersion <= installedVersion) {
        log_line("  AL DIA: version " + String(fwVersion) +
                 " no es mayor que la instalada (" + String(installedVersion) +
                 "). No se actualiza.");
        return VR_UPTODATE;
    }

    acceptedVersion = (int)fwVersion;
    installedVersion = (int)fwVersion;
    prefs.putInt("version", installedVersion);   // persiste version en NVS
    parse_pattern(body);                          // lee el patron del cuerpo del firmware
    prefs.putString("body", body);                // persiste el firmware para reanudar tras reiniciar
    log_line("  ACEPTADO (ACTUALIZADO): " + fwType + " v" + String(fwVersion) +
             "  (patron: LED " + String(patLedOn) + "/" + String(patLedOff) +
             "ms, " + String(patNoteCount) + " notas)");
    return VR_UPDATED;
}

// ---------- red ----------

static bool download(const String &url, uint8_t **buf, size_t *len) {
    HTTPClient http;
    if (!http.begin(url)) {
        log_line("  [!] no se pudo iniciar HTTP");
        return false;
    }
    int code = http.GET();
    if (code != HTTP_CODE_OK) {
        log_line("  [!] HTTP " + String(code) + " pidiendo " + url);
        http.end();
        return false;
    }
    int size = http.getSize();
    WiFiClient *stream = http.getStreamPtr();
    // Si el servidor no da Content-Length, leemos incremental.
    const size_t CHUNK = 512;
    size_t cap = (size > 0) ? (size_t)size : CHUNK;
    uint8_t *data = (uint8_t *)malloc(cap);
    size_t got = 0;
    if (!data) { http.end(); return false; }

    uint32_t lastData = millis();
    while (http.connected() && (size < 0 || got < (size_t)size)) {
        size_t avail = stream->available();
        if (avail) {
            if (got + avail > cap) {
                cap = got + avail;
                uint8_t *n = (uint8_t *)realloc(data, cap);
                if (!n) { free(data); http.end(); return false; }
                data = n;
            }
            int r = stream->readBytes(data + got, avail);
            got += r;
            lastData = millis();
        } else {
            if (millis() - lastData > 3000) break;  // timeout sin datos
            delay(5);
        }
    }
    http.end();
    *buf = data;
    *len = got;
    return got > 0;
}

static void connectWiFi() {
    log_line("Conectando a WiFi '" + String(WIFI_SSID) + "' ...");
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    uint32_t t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
        delay(400);
        Serial.print(".");
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
        log_line("WiFi OK. IP: " + WiFi.localIP().toString());
    } else {
        log_line("WiFi FALLO. Revisa SSID/clave en include/config.h");
    }
}

// ---------- efecto fisico: ejecuta el patron del firmware aceptado ----------
// LED y melodia corren sin bloquear (basados en millis()), para que el loop
// siga pudiendo chequear actualizaciones. El buzzer es PASIVO: se usa LEDC
// para generar la frecuencia de cada nota.

static void buzzerTone(int freq) {
    // Arduino-ESP32 core 3.x: ledcWriteTone recibe el PIN y la frecuencia.
    // freq 0 = silencio.
    ledcWriteTone(BUZZER_PIN, freq > 0 ? freq : 0);
}

static void physicalEffect() {
    static bool wasAccepted = false;
    static uint32_t ledNext = 0;
    static bool ledState = false;
    static uint32_t noteNext = 0;
    static int noteIdx = 0;

    // Transicion a "rechazado / sin firmware": apaga todo.
    if (!accepted) {
        if (wasAccepted) {
            digitalWrite(LED_BUILTIN, LOW);
            buzzerTone(0);
            wasAccepted = false;
        }
        return;
    }

    // Al aceptar un firmware nuevo, reinicia el ciclo del patron.
    if (!wasAccepted) {
        wasAccepted = true;
        ledState = false; ledNext = 0;
        noteIdx = 0; noteNext = 0;
    }

    uint32_t now = millis();

    // --- LED no bloqueante ---
    if (now >= ledNext) {
        ledState = !ledState;
        digitalWrite(LED_BUILTIN, ledState ? HIGH : LOW);
        ledNext = now + (uint32_t)(ledState ? patLedOn : patLedOff);
    }

    // --- Melodia no bloqueante (en bucle) ---
    if (patNoteCount > 0 && now >= noteNext) {
        buzzerTone(patFreq[noteIdx]);
        noteNext = now + (uint32_t)patDur[noteIdx];
        noteIdx = (noteIdx + 1) % patNoteCount;  // repite la melodia
    }
}

// ---------- ciclo principal ----------

void setup() {
    Serial.begin(115200);
    delay(500);
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, LOW);

    // Buzzer PASIVO via LEDC (core 3.x). Frecuencia inicial dummy; resolucion 10 bits.
    ledcAttach(BUZZER_PIN, 2000, 10);
    ledcWriteTone(BUZZER_PIN, 0);  // silencio al arrancar

    // Recupera la version instalada de NVS (sobrevive a reinicios/corte de bateria).
    prefs.begin("otasim", false);
    installedVersion = prefs.getInt("version", -1);
    if (installedVersion >= 0) {
        // Reanuda el comportamiento del ultimo firmware aceptado sin re-descargar.
        String savedBody = prefs.getString("body", "");
        if (savedBody.length() > 0) {
            parse_pattern(savedBody);
            accepted = true;
        }
    }

    log_line("");
    log_line("====================================");
    log_line(" Dispositivo IoT: tipo = " + String(DEVICE_TYPE));
    log_line(" Version instalada: " + (installedVersion < 0 ? String("ninguna") : String(installedVersion)));
    log_line(" Clave publica X||Y (hex): " + to_hex(PUBLIC_KEY_XY, 64));
    log_line("====================================");
    connectWiFi();
}

void loop() {
    static uint32_t lastCheck = 0;
    physicalEffect();

    if (WiFi.status() == WL_CONNECTED &&
        (lastCheck == 0 || millis() - lastCheck > (uint32_t)CHECK_INTERVAL_S * 1000)) {
        lastCheck = millis();

        String url = String(SERVER_BASE_URL) + FIRMWARE_PACKAGE;
        log_line("");
        log_line("Pidiendo firmware: " + url);

        uint8_t *buf = nullptr;
        size_t len = 0;
        if (download(url, &buf, &len)) {
            log_line("Descargados " + String(len) + " bytes. Verificando...");
            VerifyResult r = verify_package(buf, len);
            if (r == VR_UPDATED) {
                accepted = true;   // nuevo patron activo (parse_pattern ya corrio)
                log_line(">> Firmware APLICADO. Nuevo comportamiento (LED + buzzer) activo.");
            } else if (r == VR_UPTODATE) {
                // Ya estaba al dia: mantiene el patron actual, no toca nada.
                log_line(">> Sin cambios: ya tiene la ultima version.");
            } else {
                // VR_REJECTED: fallo de seguridad. No cambia el estado actual.
                // (Si nunca hubo firmware valido, accepted sigue false = apagado.)
                log_line(">> Firmware DESCARTADO. El dispositivo sigue como estaba.");
            }
            free(buf);
        } else {
            log_line("No se pudo descargar el paquete.");
            if (buf) free(buf);
        }
    }

    delay(10);
}
