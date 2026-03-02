"""Modelos SQLAlchemy - Base de datos normalizada con Foreign Keys."""
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class ApiKey(Base):
    """API Keys con roles. Doble llave: access_key + permission_key -> rol."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    access_key = Column(String(64), unique=True, nullable=False, index=True)
    permission_key = Column(String(64), unique=True, nullable=False, index=True)
    role = Column(String(20), nullable=False)  # admin | medico | paciente
    user_id = Column(Integer, ForeignKey("patients.id"), nullable=True)  # Para rol paciente
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("Patient", backref="api_keys")


class Patient(Base):
    """Paciente FHIR-Lite. Campos sensibles encriptados."""
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    identifier = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    family_name = Column(String(255), nullable=False)
    birth_date = Column(String(10), nullable=True)
    gender = Column(String(10), nullable=True)

    # Campos sensibles: almacenados cifrados
    identification_doc_encrypted = Column(Text, nullable=True)
    medical_summary_encrypted = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    observations = relationship("Observation", back_populates="patient", cascade="all, delete-orphan")


class Observation(Base):
    """Observación FHIR-Lite (signos vitales). FK a Patient."""
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)

    code = Column(String(64), nullable=False)  # Ej: blood-pressure, heart-rate, temperature
    display = Column(String(255), nullable=True)
    value_quantity = Column(Float, nullable=False)
    unit = Column(String(32), nullable=True)
    effective_datetime = Column(DateTime, nullable=False, default=datetime.utcnow)

    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="observations")
