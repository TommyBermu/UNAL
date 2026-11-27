#!/usr/bin/env python3
"""
Publica un paquete como "latest" para la actualizacion OTA (Opcion A).

El ESP32 pide siempre <device>_latest.fwpkg. Este script copia el paquete
elegido sobre ese nombre. En el proximo chequeo (cada 15 s por defecto) el
ESP32 lo descarga y verifica.

Uso:
    python3 publish.py camera 2          # publica camera_v2  -> ACEPTA (actualiza)
    python3 publish.py sensor 1          # publica sensor_v1  -> ACEPTA
    python3 publish.py camera tampered   # publica el alterado -> RECHAZA (integridad)
    python3 publish.py camera fakekey    # publica el de clave falsa -> RECHAZA (autenticidad)

Nota: 'tampered' y 'fakekey' solo existen para la camara (son los casos de ataque
de la demo). Para el sensor usa versiones numericas.
"""

import shutil
import sys
from pathlib import Path

FW_DIR = Path(__file__).parent / "firmwares"


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("camera", "sensor"):
        raise SystemExit(
            "Uso: python3 publish.py <camera|sensor> <version|tampered|fakekey>")
    device, what = sys.argv[1], sys.argv[2]

    # Nombre del paquete fuente segun lo pedido.
    if what in ("tampered", "fakekey"):
        src = FW_DIR / f"{device}_v1_{what}.fwpkg"
        tipo = {"tampered": "integridad", "fakekey": "autenticidad"}[what]
        nota = f"-> el ESP32 lo RECHAZARA por {tipo}"
    else:
        src = FW_DIR / f"{device}_v{what}.fwpkg"
        nota = "-> el ESP32 lo ACEPTARA si la version es mayor que la instalada"

    dst = FW_DIR / f"{device}_latest.fwpkg"
    force_flag = FW_DIR / f"{device}_latest.force"
    if not src.exists():
        raise SystemExit(
            f"No existe {src.name}. Corre antes: python3 build_firmwares.py\n"
            f"(para tampered/fakekey:  python3 build_firmwares.py --with-attacks)")

    shutil.copy(src, dst)

    # Flag "force": para los ataques, el servidor debe ofrecerlos sin importar la
    # version (simula a un atacante). Para firmwares normales, se quita el flag
    # y el servidor vuelve a respetar la regla de "solo version mayor".
    if what in ("tampered", "fakekey"):
        force_flag.write_text("force\n")
    elif force_flag.exists():
        force_flag.unlink()

    print(f"Publicado: {dst.name} = {src.name}")
    print(f"El ESP32 '{device}' lo tomara en su proximo chequeo (unos segundos). {nota}")


if __name__ == "__main__":
    main()
