# Proyecto 1: Interoperabilidad – API REST FHIR-Lite

Sistema de gestión clínica con API REST basada en estándar FHIR-Lite, PostgreSQL, doble API-Key, cifrado de datos sensibles, rate limiting y dashboard Streamlit.

## Requerimientos

- Python 3.10+
- PostgreSQL (local o Render)
- Cuenta en Render (para despliegue)

## Instalación

### 1. Clonar y preparar entorno

```bash
git clone <url-del-repositorio>
cd Proyecto1-SSD
```

### 2. Backend

```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Crear archivo `.env` en `backend/` (o usar variables de Render):

```
DATABASE_URL=postgresql://usuario:password@host:5432/fhir_db
ENCRYPTION_KEY=<generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
```

### 4. Crear base de datos y API Keys

```bash
cd backend
python init_api_keys.py
```

Guarda las API Keys mostradas para usarlas en Postman y en el frontend.

### 5. Ejecutar backend

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Documentación interactiva: http://localhost:8000/docs

### 6. Frontend Streamlit

```bash
cd frontend
pip install -r requirements.txt

# Opcional: si el backend está en otra URL
set API_BASE_URL=http://localhost:8000  # Windows
export API_BASE_URL=http://localhost:8000  # Linux/Mac

streamlit run app.py
```

Acceder a http://localhost:8501

## Despliegue

### Backend en Render

1. Crear Web Service y conectarlo al repositorio.
2. Runtime: Python 3.
3. **Root Directory**: `backend` (importante: Render ejecuta el build dentro de esta carpeta).
4. Build: `pip install -r requirements.txt`
5. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Variables de entorno: `DATABASE_URL`, `ENCRYPTION_KEY`

### Base de datos PostgreSQL en Render

1. Crear PostgreSQL Database.
2. Copiar Internal Database URL y configurarla como `DATABASE_URL`.
3. Si Render usa `postgres://`, el código lo convierte a `postgresql://`.

### Frontend en Streamlit Cloud

1. Subir el proyecto a GitHub.
2. En Streamlit Cloud: New app → repositorio.
3. Main file: `frontend/app.py`
4. Root directory: `frontend`
5. Secrets: `API_BASE_URL = https://tu-backend.onrender.com`

### Ejecutar init_api_keys en Render

Después del primer despliegue, usar el Shell de Render o una migración para ejecutar `init_api_keys.py` y generar las API Keys.

## API Endpoints FHIR-Lite

| Método | Endpoint | Descripción | Roles |
|--------|----------|-------------|-------|
| GET | /fhir/Patient?limit=10&offset=0 | Listar pacientes (paginado) | admin, medico, paciente* |
| GET | /fhir/Patient/{id} | Obtener paciente | admin, medico, paciente* |
| POST | /fhir/Patient | Crear paciente | admin, medico |
| PUT | /fhir/Patient/{id} | Actualizar paciente | admin, medico |
| DELETE | /fhir/Patient/{id} | Borrar paciente | **solo admin** |
| GET | /fhir/Observation?patient_id=1&limit=10&offset=0 | Listar observaciones | admin, medico, paciente* |
| POST | /fhir/Observation | Crear observación | admin, medico |

\* Paciente solo ve sus propios datos.

### Headers requeridos

- `X-Access-Key`: Token de acceso (obligatorio)
- `X-Permission-Key`: Llave de permisos (rol)

## Entregables

1. **Código fuente**: Este repositorio en GitHub
2. **URL Backend**: https://tu-servidor.onrender.com
3. **URL Frontend**: https://tu-app.streamlit.app
4. **Postman**: Ver `postman_collection.json` (importar en Postman)

## Estructura del proyecto

```
Proyecto1-SSD/
├── backend/
│   ├── main.py          # FastAPI app
│   ├── config.py        # Variables de entorno
│   ├── database.py      # SQLAlchemy, PostgreSQL
│   ├── models.py        # Patient, Observation, ApiKey
│   ├── schemas.py       # Pydantic FHIR-Lite
│   ├── auth.py          # Doble API-Key, roles
│   ├── encryption.py    # Cifrado de datos sensibles
│   ├── limiter.py       # Rate limiting (Anti-DoS)
│   ├── init_api_keys.py # Crear API Keys iniciales
│   ├── routers/
│   │   ├── patient.py
│   │   └── observation.py
│   └── requirements.txt
├── frontend/
│   ├── app.py           # Streamlit dashboard
│   └── requirements.txt
├── .env.example
├── postman_collection.json
└── README.md
```
