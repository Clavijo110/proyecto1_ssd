"""Esquemas Pydantic FHIR-Lite: Patient y Observation."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# --- Patient FHIR-Lite ---

class PatientCreate(BaseModel):
    """Crear paciente (campos FHIR-Lite)."""
    identifier: str
    name: str
    family_name: str
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    identification_doc: Optional[str] = None  # Se encripta al guardar
    medical_summary: Optional[str] = None    # Se encripta al guardar


class PatientUpdate(BaseModel):
    """Actualizar paciente parcialmente."""
    name: Optional[str] = None
    family_name: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    identification_doc: Optional[str] = None
    medical_summary: Optional[str] = None


class PatientResponse(BaseModel):
    """Respuesta FHIR-Lite Patient."""
    id: int
    identifier: str
    name: str
    family_name: str
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    identification_doc: Optional[str] = None  # Desencriptado en respuesta si hay permiso
    medical_summary: Optional[str] = None

    class Config:
        from_attributes = True


# --- Observation FHIR-Lite ---

class ObservationCreate(BaseModel):
    """Crear observación (signo vital)."""
    patient_id: int
    code: str  # blood-pressure, heart-rate, temperature, etc.
    display: Optional[str] = None
    value_quantity: float
    unit: Optional[str] = None
    effective_datetime: Optional[datetime] = None


class ObservationResponse(BaseModel):
    """Respuesta FHIR-Lite Observation."""
    id: int
    patient_id: int
    code: str
    display: Optional[str] = None
    value_quantity: float
    unit: Optional[str] = None
    effective_datetime: datetime

    class Config:
        from_attributes = True


# --- Paginación ---

class PaginatedResponse(BaseModel):
    """Respuesta paginada estándar."""
    total: int
    limit: int
    offset: int
    items: list
