"""Cifrado/descifrado de datos sensibles con Fernet (AES-128-CBC + HMAC-SHA256).

La clave Fernet se deriva UNA SOLA VEZ al importar el módulo usando PBKDF2-HMAC-SHA256.
Esto garantiza que:
  - Cualquier string de ENCRYPTION_KEY produce una clave Fernet válida de 32 bytes.
  - La clave es siempre la misma para la misma ENCRYPTION_KEY (determinista).
  - Si ENCRYPTION_KEY no está configurada en producción, el servidor arranca
    pero lanza una advertencia clara en los logs.
"""
import base64
import logging
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Salt fijo y público — la seguridad recae en ENCRYPTION_KEY, no en el salt
_SALT = b"fhir_lite_salt_2024"
_ITERATIONS = 260_000  # OWASP 2023 recommendation para PBKDF2-SHA256


def _derive_fernet(raw_key: str) -> Fernet:
    """Deriva una clave Fernet de 32 bytes a partir de cualquier string."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(raw_key.encode("utf-8")))
    return Fernet(key)


# ── Inicialización única al arrancar el servidor ──────────────────────────────
_raw = os.getenv("ENCRYPTION_KEY", "")

if not _raw:
    logger.critical(
        "ENCRYPTION_KEY no está configurada. "
        "Los datos sensibles NO podrán cifrarse ni descifrarse correctamente. "
        "Configura esta variable de entorno en Render antes de continuar."
    )
    # Usamos un fallback de desarrollo para no crashear, pero los datos
    # cifrados con esta clave no serán recuperables en otro arranque.
    _raw = "dev-fallback-key-NOT-for-production"

_fernet: Fernet = _derive_fernet(_raw)
# ─────────────────────────────────────────────────────────────────────────────


def encrypt_value(plain: str | None) -> str | None:
    """Cifra un valor sensible antes de guardarlo en la BD."""
    if not plain:
        return None
    try:
        return _fernet.encrypt(plain.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        logger.error("Error cifrando valor: %s", exc)
        raise


def decrypt_value(encrypted: str | None) -> str | None:
    """Descifra un valor sensible leído de la BD."""
    if not encrypted:
        return None
    try:
        return _fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        logger.warning("No se pudo descifrar valor (clave incorrecta o dato corrupto): %s", exc)
        return "[cifrado inválido]"
