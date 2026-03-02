"""Cifrado/descifrado de datos sensibles (identification_doc, medical_summary)."""
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from config import ENCRYPTION_KEY


def _get_fernet() -> Fernet:
    """Obtener instancia Fernet a partir de la clave de entorno."""
    key_bytes = ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY
    if len(key_bytes) == 44 and base64.urlsafe_b64decode(key_bytes):
        return Fernet(key_bytes)
    # Derivar clave si no es Fernet válida
    salt = b"fhir_salt_16b"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(key_bytes))
    return Fernet(key)


def encrypt_value(plain: str | None) -> str | None:
    """Serializa y cifra un valor sensible."""
    if plain is None or plain == "":
        return None
    f = _get_fernet()
    return f.encrypt(plain.encode()).decode()


def decrypt_value(encrypted: str | None) -> str | None:
    """Descifra un valor sensible."""
    if encrypted is None or encrypted == "":
        return None
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()
