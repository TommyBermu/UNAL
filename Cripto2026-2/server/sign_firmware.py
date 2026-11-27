#!/usr/bin/env python3
"""
Empaqueta y firma un archivo de firmware con ECDSA P-256 sobre SHA-256.

Formato del paquete (.fwpkg):

    [ MAGIC   4 bytes  ] = b"FWP1"
    [ meta_len 2 bytes ] = longitud del JSON de metadata (big-endian, uint16)
    [ metadata meta_len bytes ] = JSON UTF-8
    [ firma   64 bytes ] = ECDSA_P256( privada, metadata_bytes ) en formato r||s
                           (r y s, 32 bytes cada uno, big-endian)
    [ firmware N bytes ] = el binario tal cual

metadata (JSON, claves ordenadas, sin espacios) = {
    "device_type": "camera" | "sensor",   # compatibilidad
    "sha256":      hex del SHA-256 del firmware,   # integridad
    "size":        tamano del firmware en bytes,
    "version":     entero
}

La firma cubre los bytes de metadata. Como sha256(firmware) y device_type
viven dentro, una sola verificacion de firma protege autenticidad + integridad
+ compatibilidad.

La firma se guarda como r||s (64 bytes) en lugar de DER para que el ESP32
la reconstruya trivialmente sin parsear ASN.1.
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

MAGIC = b"FWP1"


def load_private_key(path: Path) -> ec.EllipticCurvePrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise SystemExit(f"{path} no es una clave privada EC")
    return key


def sign_raw_rs(private_key: ec.EllipticCurvePrivateKey, data: bytes) -> bytes:
    der = private_key.sign(data, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def build_package(firmware: bytes, device_type: str, version: int,
                  private_key: ec.EllipticCurvePrivateKey) -> bytes:
    metadata = {
        "device_type": device_type,
        "sha256": hashlib.sha256(firmware).hexdigest(),
        "size": len(firmware),
        "version": version,
    }
    meta_bytes = json.dumps(metadata, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = sign_raw_rs(private_key, meta_bytes)  # 64 bytes r||s

    if len(meta_bytes) > 0xFFFF:
        raise SystemExit("metadata demasiado grande")

    return b"".join([
        MAGIC,
        struct.pack(">H", len(meta_bytes)),
        meta_bytes,
        signature,
        firmware,
    ])


def main() -> None:
    ap = argparse.ArgumentParser(description="Firma y empaqueta un firmware (ECDSA P-256)")
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--device-type", required=True, choices=["camera", "sensor"])
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--out", dest="outfile", required=True)
    ap.add_argument("--key", default="keys/private.pem")
    args = ap.parse_args()

    base = Path(__file__).parent

    def resolve(p: str) -> Path:
        pp = Path(p)
        return pp if pp.is_absolute() else base / pp

    in_path = resolve(args.infile)
    key_path = resolve(args.key)
    out_path = resolve(args.outfile)

    firmware = in_path.read_bytes()
    private_key = load_private_key(key_path)
    package = build_package(firmware, args.device_type, args.version, private_key)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(package)

    print(f"Paquete firmado: {out_path}")
    print(f"  device_type : {args.device_type}")
    print(f"  version     : {args.version}")
    print(f"  firmware    : {len(firmware)} bytes  ({in_path.name})")
    print(f"  sha256      : {hashlib.sha256(firmware).hexdigest()}")
    print(f"  firmado con : {key_path.name}")
    print(f"  paquete     : {len(package)} bytes")


if __name__ == "__main__":
    main()
