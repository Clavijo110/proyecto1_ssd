"""Rate limiting Anti-DoS: límite de peticiones por minuto.

key_func lee X-Forwarded-For para obtener la IP real del cliente
cuando el servidor corre detrás de un proxy (Render, Cloudflare, etc.).
Sin esto, todas las peticiones comparten el mismo límite porque el proxy
presenta siempre su propia IP interna.
"""
from fastapi import Request
from slowapi import Limiter


def get_real_ip(request: Request) -> str:
    """Extrae la IP real aunque haya uno o varios proxies en el camino."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


# Límite global: 60 req/min por IP real
limiter = Limiter(key_func=get_real_ip, default_limits=["60/minute"])
