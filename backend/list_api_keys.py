"""Listar API Keys existentes en la base de datos."""
import sys
sys.path.insert(0, ".")

from database import SessionLocal
from models import ApiKey

def main():
    db = SessionLocal()
    try:
        keys = db.query(ApiKey).all()
        if not keys:
            print("No hay API Keys. Ejecutar: python init_api_keys.py")
            return
        for k in keys:
            print(f"=== {k.role.upper()} (user_id={k.user_id}) ===")
            print(f"X-Access-Key: {k.access_key}")
            print(f"X-Permission-Key: {k.permission_key}")
            print()
    finally:
        db.close()

if __name__ == "__main__":
    main()
