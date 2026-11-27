#!/usr/bin/env python3
"""
Verificador de referencia en el PC (espejo de lo que hace el ESP32).

Comprueba que los paquetes .fwpkg estan bien formados sin necesidad del
hardware, y documenta la misma logica de 3 pasos del firmware C++.

Firma: ECDSA P-256 sobre SHA-256, en formato r||s (64 bytes).

Uso:
    python3 verify_local.py --pkg firmwares/camera_v3.fwpkg --my-type camera
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

MAGIC = b"FWP1"
BASE = Path(__file__).parent


def load_public_key() -> ec.EllipticCurvePublicKey:
    pem = (BASE / "keys" / "public.pem").read_bytes()
    return serialization.load_pem_public_key(pem)


def verify(pkg: bytes, my_type: str, pub: ec.EllipticCurvePublicKey) -> tuple[bool, str]:
    if pkg[:4] != MAGIC:
        return False, "formato invalido (magic)"
    meta_len = struct.unpack(">H", pkg[4:6])[0]
    off = 6
    meta_bytes = pkg[off:off + meta_len]; off += meta_len
    sig_rs = pkg[off:off + 64]; off += 64
    firmware = pkg[off:]

    # Paso 1: AUTENTICIDAD. Reconstruye DER desde r||s y verifica.
    r = int.from_bytes(sig_rs[:32], "big")
    s = int.from_bytes(sig_rs[32:], "big")
    der = encode_dss_signature(r, s)
    try:
        pub.verify(der, meta_bytes, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        return False, "RECHAZADO: firma invalida (autenticidad)"

    meta = json.loads(meta_bytes)

    # Paso 2: INTEGRIDAD.
    if hashlib.sha256(firmware).hexdigest() != meta["sha256"]:
        return False, "RECHAZADO: hash no coincide (integridad)"
    if len(firmware) != meta["size"]:
        return False, "RECHAZADO: tamano no coincide (integridad)"

    # Paso 3: COMPATIBILIDAD.
    if meta["device_type"] != my_type:
        return False, (f"RECHAZADO: firmware para '{meta['device_type']}' "
                       f"pero yo soy '{my_type}' (compatibilidad)")

    # El comportamiento vive DENTRO del firmware (.bin), ya verificado por hash.
    try:
        body = json.loads(firmware)
    except (ValueError, UnicodeDecodeError):
        return False, "RECHAZADO: cuerpo del firmware ilegible"

    # Consistencia: el tipo/version del .bin deben coincidir con la metadata firmada.
    if body.get("device_type") != meta["device_type"] or body.get("version") != meta["version"]:
        return False, "RECHAZADO: el .bin no concuerda con la metadata (consistencia)"

    led = body["led"]
    melody = body["melody"]
    extra = f"  [patron: LED on/off={led['on']}/{led['off']}ms, {len(melody)} notas]"
    return True, f"ACEPTADO: {meta['device_type']} v{meta['version']}{extra}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--my-type", required=True, choices=["camera", "sensor"])
    args = ap.parse_args()

    pkg_path = Path(args.pkg)
    if not pkg_path.is_absolute():
        pkg_path = BASE / pkg_path

    ok, msg = verify(pkg_path.read_bytes(), args.my_type, load_public_key())
    print(f"[{args.my_type}] {pkg_path.name}: {msg}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
