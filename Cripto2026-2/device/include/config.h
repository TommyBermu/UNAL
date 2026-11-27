// Configuracion de red y del servidor de firmware.
// EDITA estos tres valores con los datos de TU montaje antes de compilar.
#pragma once

// --- WiFi al que se conectan los ESP32 ---
// Puede ser tu router de casa o el hotspot del PC. PC y ESP32 en la MISMA red.
#define WIFI_SSID "JARVIS"
#define WIFI_PASS "nohaycontrasena"

// --- Servidor de firmware (el PC con serve.py) ---
// Usa la IP que imprime serve.py (ej. http://192.168.1.50:8000).
// Deja la barra final; el codigo arma la URL del endpoint /check.
#define SERVER_BASE_URL "http://192.168.12.1:8000/"

// El dispositivo NO pide un archivo por nombre. Consulta al servidor con su
// tipo (DEVICE_TYPE, fijado por el entorno camera/sensor) y su version actual:
//   GET /check?type=camera&version=1
// El SERVIDOR decide si hay algo mas nuevo y lo envia; si no, responde 204.
// Que version esta publicada se controla en el PC con publish.py.
// El ESP32 SIEMPRE verifica firma+hash+tipo de lo que reciba (no confia en el
// servidor). Ver README para el guion de la demo.

// Segundos entre consultas de actualizacion.
#define CHECK_INTERVAL_S 15
