#!/usr/bin/env python3
"""
Genera y firma TODOS los paquetes de firmware del proyecto.

El "firmware" (.bin) YA NO es relleno: es el contenido real que define el
comportamiento del dispositivo. Es un JSON con el tipo, la version y el patron
(ritmo del LED + melodia del buzzer). El ESP32, tras verificar, LEE ese .bin y
ejecuta lo que dice.

Cadena de proteccion:
    firma  ->  cubre la metadata  ->  que contiene sha256(.bin)  ->  que contiene el patron
Si alguien altera el patron dentro del .bin, cambia su hash, que ya no coincide
con el sha256 firmado -> el dispositivo lo rechaza por integridad.

Contenido del .bin (JSON compacto):
  {
    "device_type": "camera"|"sensor",
    "version": <int>,
    "led":    {"on": <ms>, "off": <ms>},
    "melody": [[freq_Hz, dur_ms], ...]      # freq 0 = silencio
  }

La metadata firmada solo lleva: device_type, version, size y sha256 del .bin.
device_type y version van en AMBOS (metadata y .bin); el ESP32 comprueba que
coincidan, como consistencia extra.

Firmwares BUENOS (se generan siempre):
  camera_v1/v2.fwpkg, sensor_v1/v2.fwpkg  -> ACEPTAN en su dispositivo
  camera_latest.fwpkg, sensor_latest.fwpkg -> copia de la v1 (lo que piden los ESP32)
  (camera_v1.fwpkg en el sensor -> RECHAZA por compatibilidad, no requiere archivo extra)

Firmwares de ATAQUE (solo con  --with-attacks):
  camera_v1_tampered.fwpkg  -> RECHAZA (integridad; 1 byte alterado tras firmar)
  camera_v1_fakekey.fwpkg   -> RECHAZA (autenticidad; firmado con clave de atacante)

Uso:
  python3 build_firmwares.py                 # solo los firmwares buenos
  python3 build_firmwares.py --with-attacks  # ademas los de ataque

Requiere haber corrido antes: python3 gen_keys.py
"""

import json
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

BASE = Path(__file__).parent
FW_DIR = BASE / "firmwares"
KEYS_DIR = BASE / "keys"

# --- Comportamiento de cada version (ritmo del LED + melodia del buzzer) ---
# Notas aproximadas: A4=440, C5=523, E5=659, G5=784, C6=1047, C4=262, G3=196
PATTERNS = {
    "camera_v1": {
        "led": {"on": 120, "off": 120},
        "melody": [[659, 120], [0, 60], [659, 120], [0, 60], [784, 180], [0, 300]],
    },
    "camera_v2": {
        "led": {"on": 250, "off": 150},
        "melody": [[523, 150], [659, 150], [784, 150], [1047, 250], [0, 400]],
    },
    "sensor_v1": {
        "led": {"on": 600, "off": 600},
        "melody": [[196, 500], [0, 700]],
    },
    "sensor_v2": {
        "led": {"on": 400, "off": 400},
        "melody": [[262, 250], [196, 250], [0, 600]],
    },
}


def make_firmware(name: str, device_type: str, version: int, pattern: dict) -> Path:
    """Crea el .bin: el contenido REAL del firmware, con el comportamiento dentro."""
    FW_DIR.mkdir(parents=True, exist_ok=True)
    firmware = {
        "device_type": device_type,
        "version": version,
        "led": pattern["led"],
        "melody": pattern["melody"],
    }
    # JSON compacto y determinista (claves ordenadas) como cuerpo del firmware.
    payload = json.dumps(firmware, separators=(",", ":"), sort_keys=True).encode("utf-8")
    path = FW_DIR / name
    path.write_bytes(payload)
    return path


def sign(infile: Path, device_type: str, version: int, out: str,
         key: str | None = None) -> None:
    cmd = [
        sys.executable, str(BASE / "sign_firmware.py"),
        "--in", str(infile),
        "--device-type", device_type,
        "--version", str(version),
        "--out", str(FW_DIR / out),
    ]
    if key:
        cmd += ["--key", key]
    subprocess.run(cmd, check=True)


def build_attacks(cam_v1: Path) -> None:
    """Genera los paquetes de ATAQUE (solo bajo peticion, con --with-attacks)."""
    # --- Integridad: corrompe 1 byte del firmware DESPUES de firmar ---
    tampered = bytearray((FW_DIR / "camera_v1.fwpkg").read_bytes())
    tampered[-10] ^= 0xFF
    (FW_DIR / "camera_v1_tampered.fwpkg").write_bytes(bytes(tampered))
    print("Paquete alterado:   camera_v1_tampered.fwpkg  (1 byte volteado tras firmar)")

    # --- Autenticidad: firma con clave de atacante ---
    attacker_key = KEYS_DIR / "attacker_private.pem"
    ak = ec.generate_private_key(ec.SECP256R1())
    attacker_key.write_bytes(ak.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    sign(cam_v1, "camera", 1, "camera_v1_fakekey.fwpkg", key=str(attacker_key))
    print("Paquete clave falsa: camera_v1_fakekey.fwpkg  (firmado con clave de atacante)")


def main() -> None:
    with_attacks = "--with-attacks" in sys.argv

    if not (KEYS_DIR / "private.pem").exists():
        raise SystemExit("Falta keys/private.pem. Corre primero: python3 gen_keys.py")

    # --- Firmwares BUENOS: el .bin lleva el comportamiento dentro ---
    cam_v1 = make_firmware("camera_v1.bin", "camera", 1, PATTERNS["camera_v1"])
    cam_v2 = make_firmware("camera_v2.bin", "camera", 2, PATTERNS["camera_v2"])
    sen_v1 = make_firmware("sensor_v1.bin", "sensor", 1, PATTERNS["sensor_v1"])
    sen_v2 = make_firmware("sensor_v2.bin", "sensor", 2, PATTERNS["sensor_v2"])

    sign(cam_v1, "camera", 1, "camera_v1.fwpkg")
    sign(cam_v2, "camera", 2, "camera_v2.fwpkg")
    sign(sen_v1, "sensor", 1, "sensor_v1.fwpkg")
    sign(sen_v2, "sensor", 2, "sensor_v2.fwpkg")

    # --- "latest": lo que piden los ESP32 (Opcion A). Arranca publicando la v1. ---
    import shutil
    shutil.copy(FW_DIR / "camera_v1.fwpkg", FW_DIR / "camera_latest.fwpkg")
    shutil.copy(FW_DIR / "sensor_v1.fwpkg", FW_DIR / "sensor_latest.fwpkg")
    print("Publicado inicial: camera_latest.fwpkg = v1, sensor_latest.fwpkg = v1")

    # --- Paquetes de ataque: solo si se piden explicitamente ---
    if with_attacks:
        build_attacks(cam_v1)

    print("\nPaquetes en firmwares/:")
    for f in sorted(FW_DIR.glob("*.fwpkg")):
        print(f"  - {f.name}")

    print("\nFirmwares BUENOS listos. Mapa de casos:")
    print("  ACEPTA   camera_v1.fwpkg  en ESP32-camara  (ritmo v1)")
    print("  ACEPTA   camera_v2.fwpkg  en ESP32-camara  (ritmo v2, suena distinto)")
    print("  ACEPTA   sensor_v1.fwpkg  en ESP32-sensor  (ritmo v1)")
    print("  ACEPTA   sensor_v2.fwpkg  en ESP32-sensor  (ritmo v2, suena distinto)")
    print("  RECHAZA  camera_v1.fwpkg  en ESP32-sensor  (device_type/compatibilidad)")

    if with_attacks:
        print("\nFirmwares de ATAQUE generados:")
        print("  RECHAZA  camera_v1_tampered.fwpkg en camara  (integridad/hash)")
        print("  RECHAZA  camera_v1_fakekey.fwpkg  en camara  (autenticidad/firma)")
    else:
        print("\n(Para generar los paquetes de ataque:  python3 build_firmwares.py --with-attacks)")


if __name__ == "__main__":
    main()
