#!/usr/bin/env python3
"""
Genera un par de claves ECDSA P-256 (secp256r1) para firmar firmware.

Se usa ECDSA P-256 (y no Ed25519) porque el mbedTLS que trae el ESP32
lo soporta de forma nativa y estable, sin librerias externas.

- La clave PRIVADA (keys/private.pem) se queda SOLO en el PC servidor.
- La clave PUBLICA se exporta:
    * keys/public.pem      -> para herramientas/depuracion en el PC
    * device/include/public_key.h -> las coordenadas X||Y del punto publico
      (64 bytes: 32 de X + 32 de Y) listas para el firmware del ESP32.

La seguridad depende de que la privada no se filtre.
"""

from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

KEYS_DIR = Path(__file__).parent / "keys"


def format_c_array(raw: bytes) -> str:
    lines = []
    for i in range(0, len(raw), 12):
        chunk = raw[i:i + 12]
        lines.append("    " + ", ".join(f"0x{b:02x}" for b in chunk) + ",")
    body = "\n".join(lines)
    return (
        "// Clave publica ECDSA P-256 en formato punto sin comprimir, SIN el\n"
        "// byte 0x04 inicial: son 64 bytes = X (32) || Y (32).\n"
        "// Se puede publicar sin riesgo: solo sirve para VERIFICAR firmas.\n"
        "#pragma once\n"
        "#include <stdint.h>\n\n"
        "static const uint8_t PUBLIC_KEY_XY[64] = {\n"
        f"{body}\n"
        "};\n"
    )


def main() -> None:
    KEYS_DIR.mkdir(parents=True, exist_ok=True)

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    (KEYS_DIR / "private.pem").write_bytes(priv_pem)

    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    (KEYS_DIR / "public.pem").write_bytes(pub_pem)

    # Punto publico sin comprimir: 0x04 || X(32) || Y(32). Quitamos el 0x04.
    uncompressed = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    assert len(uncompressed) == 65 and uncompressed[0] == 0x04
    xy = uncompressed[1:]

    header_path = Path(__file__).parent.parent / "device" / "include" / "public_key.h"
    header_path.parent.mkdir(parents=True, exist_ok=True)
    header_path.write_text(format_c_array(xy))

    print("Claves generadas (ECDSA P-256):")
    print(f"  Privada  : {KEYS_DIR / 'private.pem'}   (NO COMPARTIR)")
    print(f"  Publica  : {KEYS_DIR / 'public.pem'}")
    print(f"  Cabecera : {header_path}   (incluida por el firmware ESP32)")
    print(f"  Publica X||Y (hex): {xy.hex()}")


if __name__ == "__main__":
    main()
