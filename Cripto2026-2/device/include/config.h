// Configuracion de red y del servidor de firmware.
// EDITA estos tres valores con los datos de TU montaje antes de compilar.
#pragma once

// --- WiFi al que se conectan los ESP32 ---
// Puede ser tu router de casa o el hotspot del PC. PC y ESP32 en la MISMA red.
#define WIFI_SSID "JARVIS"
#define WIFI_PASS "nohaycontrasena"

// --- Servidor de firmware (el PC con serve.py) ---
// Usa la IP que imprime serve.py (ej. http://192.168.1.50:8000).
// Deja la barra final; el codigo concatena el nombre del paquete.
#define SERVER_BASE_URL "http://192.168.12.1:8000/"

// --- Que paquete pedir ---
// En la Opcion A (actualizacion OTA realista) el ESP32 pide SIEMPRE el mismo
// nombre "latest", y en el PC decides que version publicas copiando encima:
//   cp firmwares/camera_v1.fwpkg firmwares/camera_latest.fwpkg   (publicar v1)
//   cp firmwares/camera_v2.fwpkg firmwares/camera_latest.fwpkg   (actualizar a v2)
// El ESP32 descarga en su proximo chequeo y actualiza solo si la version es mayor.
//
// Para los ESP32: camera -> "camera_latest.fwpkg", sensor -> "sensor_latest.fwpkg".
// Para probar rechazos, apunta a un paquete concreto:
//   camera_v1_tampered.fwpkg (integridad), camera_v1_fakekey.fwpkg (autenticidad),
//   camera_v1.fwpkg en un sensor (compatibilidad).
#define FIRMWARE_PACKAGE "camera_latest.fwpkg"

// Segundos entre intentos de actualizacion.
#define CHECK_INTERVAL_S 15
