#!/usr/bin/env python3
"""
Servidor HTTP simple que publica los paquetes de firmware (.fwpkg).

Los ESP32 piden, por ejemplo:
    GET http://<IP_DEL_PC>:8000/camera_v3.fwpkg

Sirve el contenido de la carpeta firmwares/. No tiene logica de seguridad:
TODA la verificacion (firma, hash, device_type) la hace el ESP32 al recibir.
Eso es a proposito: el dispositivo nunca confia en el servidor.

Uso:
    python3 serve.py              # escucha en 0.0.0.0:8000
    python3 serve.py --port 9000
"""

import argparse
import http.server
import socket
from functools import partial
from pathlib import Path

FIRMWARES_DIR = Path(__file__).parent / "firmwares"


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
    # Metodo del socket saliente (ruta por defecto, normalmente internet).
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
    # Lectura directa de interfaces via /proc o ip (Linux), para no perder
    # la interfaz del hotspot (ap0), que no tiene ruta a internet.
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
    handler = partial(
        http.server.SimpleHTTPRequestHandler, directory=str(FIRMWARES_DIR)
    )
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), handler)

    print(f"Sirviendo {FIRMWARES_DIR}")
    print("El servidor escucha en TODAS las interfaces (0.0.0.0).")
    print("Usa en los ESP32 la IP del PC EN LA MISMA RED que ellos:")
    print("  - Si usas el hotspot del PC: la IP del rango del hotspot")
    print("    (p.ej. 192.168.12.1, interfaz ap0).")
    print("  - Si usas tu router: la IP del PC en el WiFi de casa.")
    print("Direcciones detectadas en este PC:")
    for ip in local_ips():
        print(f"    http://{ip}:{args.port}/")
    print(f"    http://127.0.0.1:{args.port}/   (solo local)")
    print("Archivos disponibles:")
    for f in sorted(FIRMWARES_DIR.glob("*")):
        print(f"  - {f.name}")
    print("Ctrl+C para detener.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")


if __name__ == "__main__":
    main()
