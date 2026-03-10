"""Configuración y variables de entorno."""
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# Base de datos PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/fhir_db"
)

# Si Render usa postgres://, convertirlo a postgresql+psycopg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Render: la URL "Internal" (host dpg-xxx-a sin dominio) solo funciona dentro de Render.
# Para desarrollo local, usar la URL "External". Si el host no tiene punto, añadir dominio.
_host = urlparse(DATABASE_URL).hostname or ""
if _host.startswith("dpg-") and "-a" in _host and "." not in _host:
    region = os.getenv("RENDER_DB_REGION", "oregon")
    external_host = f"{_host}.{region}-postgres.render.com"
    DATABASE_URL = DATABASE_URL.replace(_host, external_host)

# ENCRYPTION_KEY la lee directamente encryption.py desde os.getenv.
# No se genera una clave aleatoria aquí para evitar que cada reinicio
# del servidor use una clave diferente e inutilice datos cifrados anteriormente.

# Rate limiting
RATE_LIMIT = os.getenv("RATE_LIMIT", "60/minute")
