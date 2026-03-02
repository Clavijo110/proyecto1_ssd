"""Endpoints FHIR Observation con paginación."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Observation, Patient, ApiKey
from schemas import ObservationCreate, ObservationResponse, PaginatedResponse
from auth import require_permission

router = APIRouter(prefix="/fhir/Observation", tags=["FHIR Observation"])


@router.get("", response_model=PaginatedResponse)
def list_observations(
    patient_id: int | None = None,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_permission("read")),
):
    """
    GET /fhir/Observation?patient_id=1&limit=10&offset=0
    Paginación. Paciente solo ve las suyas (patient_id = user_id).
    """
    q = db.query(Observation)
    if patient_id:
        q = q.filter(Observation.patient_id == patient_id)
    if api_key.role == "paciente" and api_key.user_id:
        q = q.filter(Observation.patient_id == api_key.user_id)

    total = q.count()
    observations = q.order_by(Observation.effective_datetime.desc()).offset(offset).limit(limit).all()

    items = [ObservationResponse.model_validate(o) for o in observations]
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{observation_id}", response_model=ObservationResponse)
def get_observation(
    observation_id: int,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_permission("read")),
):
    """GET /fhir/Observation/{id}."""
    obs = db.query(Observation).filter(Observation.id == observation_id).first()
    if not obs:
        raise HTTPException(404, "Observación no encontrada")

    if api_key.role == "paciente" and api_key.user_id != obs.patient_id:
        raise HTTPException(403, "No puedes acceder a datos de otros pacientes")

    return ObservationResponse.model_validate(obs)


@router.post("", response_model=ObservationResponse)
def create_observation(
    body: ObservationCreate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_permission("create")),
):
    """POST /fhir/Observation. Solo Admin y Médico."""
    patient = db.query(Patient).filter(Patient.id == body.patient_id).first()
    if not patient:
        raise HTTPException(404, "Paciente no encontrado")

    obs = Observation(
        patient_id=body.patient_id,
        code=body.code,
        display=body.display,
        value_quantity=body.value_quantity,
        unit=body.unit,
        effective_datetime=body.effective_datetime or datetime.utcnow(),
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)
    return ObservationResponse.model_validate(obs)


@router.delete("/{observation_id}")
def delete_observation(
    observation_id: int,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_permission("delete")),
):
    """DELETE /fhir/Observation/{id}. Solo Admin."""
    obs = db.query(Observation).filter(Observation.id == observation_id).first()
    if not obs:
        raise HTTPException(404, "Observación no encontrada")

    db.delete(obs)
    db.commit()
    return {"message": "Observación eliminada"}
