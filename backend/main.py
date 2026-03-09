"""API REST FHIR-Lite con PostgreSQL, doble API-Key, paginación, cifrado y rate-limiting."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from fastapi import Depends
from database import init_db
from limiter import limiter
from routers import patient, observation
from auth import get_api_keys
from models import ApiKey

# Importar modelos para que Base.metadata los registre antes de init_db
import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializar BD al arrancar."""
    init_db()
    yield


app = FastAPI(
    title="FHIR-Lite API",
    description="API REST FHIR-Lite para gestión clínica con PostgreSQL, doble API-Key y paginación",
    version="1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Rutas FHIR
app.include_router(patient.router)
app.include_router(observation.router)


@app.get("/")
def root():
    return {"message": "FHIR-Lite API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/me")
def me(api_key: ApiKey = Depends(get_api_keys)):
    """Devuelve el rol y user_id del API Key autenticado."""
    return {
        "role": api_key.role,
        "user_id": api_key.user_id,
    }
