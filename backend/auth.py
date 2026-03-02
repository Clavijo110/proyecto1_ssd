"""Autenticación doble API-Key: X-Access-Key (entrada) y X-Permission-Key (rol)."""
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import ApiKey

# Roles y permisos
ROLES = {"admin", "medico", "paciente"}

# Acciones permitidas por rol: admin todo, medico sin delete, paciente solo read propio
ROLE_PERMISSIONS = {
    "admin": {"create", "read", "update", "delete"},
    "medico": {"create", "read", "update"},  # No delete
    "paciente": {"read"},  # Solo lectura de sus datos
}


async def get_api_keys(
    x_access_key: str = Header(..., alias="X-Access-Key", description="Token de entrada"),
    x_permission_key: str = Header(..., alias="X-Permission-Key", description="Llave de permisos/rol"),
    db: Session = Depends(get_db),
) -> ApiKey:
    """
    Valida X-Access-Key y X-Permission-Key. Si no son válidas -> 401.
    Retorna el registro ApiKey asociado.
    """
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.access_key == x_access_key, ApiKey.permission_key == x_permission_key)
        .first()
    )
    if not api_key:
        raise HTTPException(status_code=401, detail="Claves de acceso inválidas")
    return api_key


def require_permission(action: str):
    """Dependency factory: verifica que el rol tenga permiso para la acción."""

    async def _check(api_key: ApiKey = Depends(get_api_keys)) -> ApiKey:
        allowed = ROLE_PERMISSIONS.get(api_key.role, set())
        if action not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Tu rol '{api_key.role}' no tiene permiso para ejecutar esta acción",
            )
        return api_key

    return _check


def require_admin(api_key: ApiKey = Depends(get_api_keys)) -> ApiKey:
    """Solo Admin."""
    if api_key.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden ejecutar esta acción")
    return api_key


def require_patient_access(patient_id: int, api_key: ApiKey = Depends(get_api_keys)) -> ApiKey:
    """Paciente solo puede acceder a sus propios datos."""
    if api_key.role == "paciente" and api_key.user_id != patient_id:
        raise HTTPException(status_code=403, detail="No puedes acceder a datos de otros pacientes")
    return api_key
