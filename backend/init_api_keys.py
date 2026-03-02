"""
Script para crear API Keys iniciales (Admin, Médico, Paciente).
Ejecutar una vez después de crear las tablas: python init_api_keys.py
"""
import secrets
import sys
sys.path.insert(0, ".")

from database import SessionLocal, init_db
from models import ApiKey, Patient

def main():
    init_db()
    db = SessionLocal()
    try:
        if db.query(ApiKey).count() > 0:
            print("Ya existen API Keys. Usar las existentes o borrar la tabla api_keys.")
            return

        # Admin
        admin_access = secrets.token_hex(32)
        admin_permission = secrets.token_hex(32)
        db.add(ApiKey(access_key=admin_access, permission_key=admin_permission, role="admin"))
        print("=== ADMIN ===")
        print(f"X-Access-Key: {admin_access}")
        print(f"X-Permission-Key: {admin_permission}")
        print()

        # Médico
        med_access = secrets.token_hex(32)
        med_permission = secrets.token_hex(32)
        db.add(ApiKey(access_key=med_access, permission_key=med_permission, role="medico"))
        print("=== MÉDICO ===")
        print(f"X-Access-Key: {med_access}")
        print(f"X-Permission-Key: {med_permission}")
        print()

        # Paciente (necesita patient_id - crear paciente de ejemplo primero)
        patient = Patient(
            identifier="PAC001",
            name="Juan",
            family_name="Pérez",
            birth_date="1990-01-15",
            gender="male",
        )
        db.add(patient)
        db.flush()

        pac_access = secrets.token_hex(32)
        pac_permission = secrets.token_hex(32)
        db.add(ApiKey(access_key=pac_access, permission_key=pac_permission, role="paciente", user_id=patient.id))
        print("=== PACIENTE (Juan Pérez, id=1) ===")
        print(f"X-Access-Key: {pac_access}")
        print(f"X-Permission-Key: {pac_permission}")
        print()

        db.commit()
        print("API Keys creadas. Guardar en .env o Postman para pruebas.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
