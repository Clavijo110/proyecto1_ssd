"""Esquemas Pydantic FHIR-Lite: Patient y Observation."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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

# Rangos clínicamente imposibles por código de parámetro.
# Valores fuera de estos límites son fisiológicamente inviables
# y se rechazan con HTTP 422 antes de llegar a la base de datos.
CLINICAL_LIMITS: dict[str, tuple[float, float]] = {
    "heart-rate":               (0.0,   350.0),   # beats/min
    "temperature":              (10.0,  50.0),     # °C
    "blood-pressure-systolic":  (10.0,  350.0),   # mmHg
    "blood-pressure-diastolic": (5.0,   250.0),   # mmHg
    "respiratory-rate":         (0.0,   100.0),   # resp/min
    "oxygen-saturation":        (0.0,   100.0),   # %
    "body-weight":              (0.1,   700.0),   # kg
    "body-height":              (10.0,  300.0),   # cm
    "bmi":                      (2.0,   200.0),   # kg/m²
    "blood-glucose":            (0.0,   2000.0),  # mg/dL
}

VALID_CODES = set(CLINICAL_LIMITS.keys())


class ObservationCreate(BaseModel):
    """Crear observación (parámetro clínico).
    Valida que el código sea conocido y que el valor sea fisiológicamente posible.
    """
    patient_id: int
    code: str
    display: Optional[str] = None
    value_quantity: float
    unit: Optional[str] = None
    effective_datetime: Optional[datetime] = None

    @field_validator("code")
    @classmethod
    def code_must_be_valid(cls, v: str) -> str:
        normalized = v.lower().strip()
        if normalized not in VALID_CODES:
            raise ValueError(
                f"Código '{v}' no reconocido. "
                f"Valores aceptados: {', '.join(sorted(VALID_CODES))}"
            )
        return normalized

    @field_validator("value_quantity")
    @classmethod
    def value_must_be_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("El valor no puede ser negativo.")
        return v

    def validate_clinical_range(self) -> None:
        """Llamar desde el endpoint tras construir el objeto.
        Separado para poder acceder a self.code ya normalizado.
        """
        limits = CLINICAL_LIMITS.get(self.code)
        if limits is None:
            return
        lo, hi = limits
        if not (lo <= self.value_quantity <= hi):
            raise ValueError(
                f"Valor {self.value_quantity} fuera del rango fisiológicamente posible "
                f"para '{self.code}' ({lo} – {hi}). Registro rechazado."
            )


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
