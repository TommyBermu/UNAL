#!/usr/bin/env python3
"""
Servidor HTTP de actualizacion de firmware.

Dos formas de pedir:

1) /check  (recomendada): el DISPOSITIVO dice quien es y que version tiene, y el
   SERVIDOR decide si hay actualizacion. El dispositivo no ve el catalogo.
       GET /check?type=camera&version=1
   Respuestas:
       200 + el .fwpkg   -> hay una version mas nueva publicada para ese tipo
       204 (sin cuerpo)  -> ya esta al dia (no hay version mayor)
       400 / 404         -> peticion mal formada o sin firmware publicado

   Que version es "la publicada" lo decide el PC con publish.py (copia una
   version sobre <type>_latest.fwpkg). El servidor lee la version REAL del
   paquete publicado y la compara con la del dispositivo.

2) Descarga directa por nombre (compatibilidad / depuracion):
       GET /camera_v1.fwpkg

IMPORTANTE: el servidor decide QUE ofrecer, pero NO es de confianza. El ESP32
SIEMPRE verifica la firma, el hash y el device_type de lo que reciba. Que el
servidor elija no sustituye esa verificacion.

Uso:
    python3 serve.py              # escucha en 0.0.0.0:8000
    python3 serve.py --port 9000
"""

import argparse
import http.server
import json
import socket
import struct
from pathlib import Path
from urllib.parse import urlparse, parse_qs

FIRMWARES_DIR = Path(__file__).parent / "firmwares"
MAGIC = b"FWP1"


def read_package_version(path: Path) -> int | None:
    """Lee la 'version' de la metadata firmada de un .fwpkg, sin verificar firma."""
    try:
        data = path.read_bytes()
        if data[:4] != MAGIC:
            return None
        meta_len = struct.unpack(">H", data[4:6])[0]
        meta = json.loads(data[6:6 + meta_len])
        return int(meta["version"])
    except (OSError, ValueError, KeyError, struct.error):
        return None


class UpdateHandler(http.server.SimpleHTTPRequestHandler):
    """Sirve firmwares/ y ademas resuelve el endpoint /check."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FIRMWARES_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/check":
            self.handle_check(parse_qs(parsed.query))
            return
        # Cualquier otra ruta: descarga de archivo normal.
        super().do_GET()

    def handle_check(self, params: dict):
        dev_type = (params.get("type") or [""])[0]
        dev_version_raw = (params.get("version") or [""])[0]

        if dev_type not in ("camera", "sensor") or not dev_version_raw.lstrip("-").isdigit():
            self.send_error(400, "params invalidos (type=camera|sensor, version=entero)")
            return
        dev_version = int(dev_version_raw)

        published = FIRMWARES_DIR / f"{dev_type}_latest.fwpkg"
        latest_version = read_package_version(published)
        if latest_version is None:
            self.send_error(404, f"no hay firmware publicado para '{dev_type}'")
            return

        # Si existe un flag "force" junto al latest, el servidor ofrece el paquete
        # SIEMPRE (sin comparar version). Lo usa publish.py al publicar los casos
        # de ataque (tampered/fakekey): simula a un atacante que intenta empujar
        # un firmware malicioso, ignorando la regla de versiones. El ESP32 lo
        # recibira y lo RECHAZARA por firma/hash (ahi se demuestra la seguridad).
        force = (FIRMWARES_DIR / f"{dev_type}_latest.force").exists()

        # DECISION DEL SERVIDOR: ofrece si hay version mayor, o si esta forzado.
        if force or latest_version > dev_version:
            payload = published.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Firmware-Version", str(latest_version))
            self.end_headers()
            self.wfile.write(payload)
            self.log_message("check type=%s v%d -> ofrece v%d%s (%d bytes)",
                             dev_type, dev_version, latest_version,
                             " [forzado]" if force else "", len(payload))
        else:
            # Al dia: 204 No Content, sin cuerpo.
            self.send_response(204)
            self.send_header("X-Firmware-Version", str(latest_version))
            self.end_headers()
            self.log_message("check type=%s v%d -> al dia (publicada v%d)",
                             dev_type, dev_version, latest_version)


def local_ips() -> list[str]:
    """Devuelve todas las IPv4 de todas las interfaces (menos loopback)."""
    ips = []
    try:
        import socket as _s

        infos = _s.getaddrinfo(_s.gethostname(), None, _s.AF_INET)
        for info in infos:
            ip = info[4][0]
            if not str(ip).startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        if ip not in ips:
            ips.append(ip)
    except OSError:
        pass
    finally:
        s.close()
    try:
        import subprocess

        out = subprocess.run(
            ["ip", "-4", "-o", "addr", "show"],
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[2] == "inet":
                ip = parts[3].split("/")[0]
                if not ip.startswith("127.") and ip not in ips:
                    ips.append(ip)
    except Exception:
        pass
    return ips


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    FIRMWARES_DIR.mkdir(parents=True, exist_ok=True)
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), UpdateHandler)

    print(f"Sirviendo {FIRMWARES_DIR}")
    print("Endpoint de actualizacion: GET /check?type=<camera|sensor>&version=<n>")
    print("El servidor escucha en TODAS las interfaces (0.0.0.0).")
    print("Usa en los ESP32 la IP del PC EN LA MISMA RED que ellos:")
    print("  - Si usas el hotspot del PC: la IP del rango del hotspot")
    print("    (p.ej. 192.168.12.1, interfaz ap0).")
    print("  - Si usas tu router: la IP del PC en el WiFi de casa.")
    print("Direcciones detectadas en este PC:")
    for ip in local_ips():
        print(f"    http://{ip}:{args.port}/")
    print(f"    http://127.0.0.1:{args.port}/   (solo local)")
    print("Firmwares publicados (lo que /check puede ofrecer):")
    for f in sorted(FIRMWARES_DIR.glob("*_latest.fwpkg")):
        v = read_package_version(f)
        print(f"  - {f.name}  (version {v})")
    print("Ctrl+C para detener.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")


if __name__ == "__main__":
    main()
