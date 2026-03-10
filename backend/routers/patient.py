"""Endpoints FHIR Patient con paginación."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from database import get_db
from limiter import limiter
from models import Patient, ApiKey
from schemas import PatientCreate, PatientUpdate, PatientResponse, PaginatedResponse
from auth import get_api_keys, require_permission
from encryption import encrypt_value, decrypt_value

router = APIRouter(prefix="/fhir/Patient", tags=["FHIR Patient"])


@router.get("", response_model=PaginatedResponse)
@limiter.limit("60/minute")
def list_patients(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_permission("read")),
):
    """
    GET /fhir/Patient?limit=25&offset=0
    Paginación: limit (máx 100) y offset.
    Paciente solo ve los suyos (filtrado por user_id).
    """
    q = db.query(Patient)
    if api_key.role == "paciente" and api_key.user_id:
        q = q.filter(Patient.id == api_key.user_id)

    total = q.count()
    patients = q.offset(offset).limit(limit).all()

    items = []
    for p in patients:
        d = PatientResponse.model_validate(p)
        d.identification_doc = decrypt_value(p.identification_doc_encrypted) if p.identification_doc_encrypted else None
        d.medical_summary = decrypt_value(p.medical_summary_encrypted) if p.medical_summary_encrypted else None
        items.append(d)

    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


def _check_patient_access(patient_id: int, api_key: ApiKey):
    """Paciente solo puede ver sus propios datos."""
    if api_key.role == "paciente" and api_key.user_id != patient_id:
        raise HTTPException(403, "No puedes acceder a datos de otros pacientes")


@router.get("/{patient_id}", response_model=PatientResponse)
@limiter.limit("60/minute")
def get_patient(
    request: Request,
    patient_id: int,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_keys),
):
    """GET /fhir/Patient/{id}. Paciente solo puede ver sus datos."""
    _check_patient_access(patient_id, api_key)

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Paciente no encontrado")

    resp = PatientResponse.model_validate(patient)
    resp.identification_doc = decrypt_value(patient.identification_doc_encrypted) if patient.identification_doc_encrypted else None
    resp.medical_summary = decrypt_value(patient.medical_summary_encrypted) if patient.medical_summary_encrypted else None
    return resp


@router.post("", response_model=PatientResponse)
@limiter.limit("10/minute")
def create_patient(
    request: Request,
    body: PatientCreate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_permission("create")),
):
    """POST /fhir/Patient - Crear paciente. Solo Admin y Médico."""
    existing = db.query(Patient).filter(Patient.identifier == body.identifier).first()
    if existing:
        raise HTTPException(400, "Ya existe un paciente con ese identifier")

    patient = Patient(
        identifier=body.identifier,
        name=body.name,
        family_name=body.family_name,
        birth_date=body.birth_date,
        gender=body.gender,
        identification_doc_encrypted=encrypt_value(body.identification_doc) if body.identification_doc else None,
        medical_summary_encrypted=encrypt_value(body.medical_summary) if body.medical_summary else None,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    resp = PatientResponse.model_validate(patient)
    resp.identification_doc = body.identification_doc
    resp.medical_summary = body.medical_summary
    return resp


@router.put("/{patient_id}", response_model=PatientResponse)
@limiter.limit("10/minute")
def update_patient(
    request: Request,
    patient_id: int,
    body: PatientUpdate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_permission("update")),
):
    """PUT /fhir/Patient/{id}. Solo Admin y Médico."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Paciente no encontrado")

    data = body.model_dump(exclude_unset=True)
    if "identification_doc" in data:
        patient.identification_doc_encrypted = encrypt_value(data["identification_doc"]) if data["identification_doc"] else None
    if "medical_summary" in data:
        patient.medical_summary_encrypted = encrypt_value(data["medical_summary"]) if data["medical_summary"] else None
    for k in ("name", "family_name", "birth_date", "gender"):
        if k in data:
            setattr(patient, k, data[k])

    db.commit()
    db.refresh(patient)

    resp = PatientResponse.model_validate(patient)
    resp.identification_doc = decrypt_value(patient.identification_doc_encrypted)
    resp.medical_summary = decrypt_value(patient.medical_summary_encrypted)
    return resp


@router.delete("/{patient_id}")
@limiter.limit("5/minute")
def delete_patient(
    request: Request,
    patient_id: int,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_permission("delete")),
):
    """DELETE /fhir/Patient/{id}. Solo Admin. Médico -> 403."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Paciente no encontrado")

    db.delete(patient)
    db.commit()
    return {"message": "Paciente eliminado"}
