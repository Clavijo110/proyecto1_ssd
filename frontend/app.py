"""
Dashboard de Gestión Clínica - Streamlit
Login con API Keys, CRUD pacientes/observaciones, gráficas Plotly, alertas outliers.
"""
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os

st.set_page_config(page_title="FHIR-Lite Dashboard Clínico", page_icon="🏥", layout="wide")

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

OUTLIER_LIMITS = {
    "temperature": (35.0, 42.0),
    "heart-rate": (40, 180),
    "blood-pressure-systolic": (70, 200),
    "blood-pressure-diastolic": (40, 130),
    "blood-pressure": (40, 200),
    "respiratory-rate": (8, 40),
}

SIGNOS_VITALES = ["heart-rate", "temperature", "blood-pressure", "blood-pressure-systolic", "blood-pressure-diastolic", "respiratory-rate"]
UNIDADES = {"heart-rate": "beats/min", "temperature": "°C", "blood-pressure": "mmHg", "blood-pressure-systolic": "mmHg", "blood-pressure-diastolic": "mmHg", "respiratory-rate": "resp/min"}


def get_headers():
    return {
        "X-Access-Key": st.session_state["access_key"],
        "X-Permission-Key": st.session_state["permission_key"],
    }


def api_request(method: str, url: str, **kwargs):
    """Llamada API con manejo de errores 401, 403, 429."""
    kwargs.setdefault("headers", get_headers())
    kwargs.setdefault("timeout", 15)
    r = requests.request(method, url, **kwargs)
    if r.status_code == 401:
        st.error("Sesión expirada. Claves inválidas.")
        st.session_state.clear()
        st.rerun()
    elif r.status_code == 403:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        st.error(f"**Sin permiso (403)**: {detail}")
        return None
    elif r.status_code == 429:
        st.error("**Demasiadas peticiones (429)**. Espera un minuto antes de reintentar.")
        return None
    return r


def login_form():
    st.title("🔐 Login - Dashboard Clínico")
    st.markdown("Ingresa tus API Keys para acceder al sistema.")

    with st.form("login"):
        access_key = st.text_input("X-Access-Key", type="password", placeholder="Token de acceso")
        permission_key = st.text_input("X-Permission-Key", type="password", placeholder="Llave de permisos")
        submitted = st.form_submit_button("Iniciar sesión")

        if submitted:
            if not access_key or not permission_key:
                st.error("Debes ingresar ambas API Keys.")
                return

            try:
                r = requests.get(
                    f"{API_BASE}/fhir/Patient",
                    params={"limit": 1, "offset": 0},
                    headers={"X-Access-Key": access_key, "X-Permission-Key": permission_key},
                    timeout=10,
                )
                if r.status_code == 200:
                    st.session_state["access_key"] = access_key
                    st.session_state["permission_key"] = permission_key
                    st.session_state["logged_in"] = True
                    st.rerun()
                elif r.status_code == 401:
                    st.error("Claves inválidas.")
                else:
                    st.error(f"Error: {r.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("No se pudo conectar al servidor.")
            except Exception as e:
                st.error(str(e))


def fetch_patients(limit: int = 50, offset: int = 0):
    r = api_request("GET", f"{API_BASE}/fhir/Patient", params={"limit": limit, "offset": offset})
    if r and r.status_code == 200:
        return r.json()
    return None


def fetch_patient(patient_id: int):
    r = api_request("GET", f"{API_BASE}/fhir/Patient/{patient_id}")
    if r and r.status_code == 200:
        return r.json()
    return None


def create_patient(data: dict):
    r = api_request("POST", f"{API_BASE}/fhir/Patient", json=data)
    return r


def update_patient(patient_id: int, data: dict):
    r = api_request("PUT", f"{API_BASE}/fhir/Patient/{patient_id}", json=data)
    return r


def delete_patient(patient_id: int):
    r = api_request("DELETE", f"{API_BASE}/fhir/Patient/{patient_id}")
    return r


def fetch_observations(patient_id: int, limit: int = 500, offset: int = 0):
    r = api_request("GET", f"{API_BASE}/fhir/Observation", params={"patient_id": patient_id, "limit": limit, "offset": offset})
    if r and r.status_code == 200:
        return r.json()
    return None


def create_observation(data: dict):
    r = api_request("POST", f"{API_BASE}/fhir/Observation", json=data)
    return r


def delete_observation(observation_id: int):
    r = api_request("DELETE", f"{API_BASE}/fhir/Observation/{observation_id}")
    return r


def is_outlier(code: str, value: float) -> bool:
    limits = OUTLIER_LIMITS.get(code.lower())
    if not limits:
        return False
    lo, hi = limits
    return value < lo or value > hi


def render_charts(observations: list):
    if not observations:
        st.info("No hay observaciones.")
        return

    df = pd.DataFrame([{"fecha": o["effective_datetime"], "code": o["code"], "valor": o["value_quantity"], "unidad": o.get("unit", "")} for o in observations])
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values("fecha")
    codes = df["code"].unique().tolist()

    cols = st.columns(min(2, len(codes)) or 1)
    for i, code in enumerate(codes):
        subset = df[df["code"] == code]
        with cols[i % 2]:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=subset["fecha"], y=subset["valor"], mode="lines+markers", name=code, line=dict(color="#1f77b4")))
            outliers = subset[subset.apply(lambda row: is_outlier(code, row["valor"]), axis=1)]
            if not outliers.empty:
                fig.add_trace(go.Scatter(x=outliers["fecha"], y=outliers["valor"], mode="markers", name="⚠️ Outlier", marker=dict(size=14, color="red", symbol="x")))
            fig.update_layout(title=f"Tendencia: {code}", xaxis_title="Fecha", yaxis_title="Valor", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
            if not outliers.empty:
                st.error(f"⚠️ **Outliers** en {code}")
                st.dataframe(outliers[["fecha", "valor", "unidad"]], use_container_width=True, hide_index=True)


def main():
    if "logged_in" not in st.session_state or not st.session_state.get("logged_in"):
        login_form()
        return

    with st.sidebar:
        st.title("🏥 Dashboard Clínico")
        if st.button("Cerrar sesión"):
            st.session_state.clear()
            st.rerun()

    st.title("Gestión Clínica - Signos Vitales")

    # Paginación
    page_size = st.sidebar.selectbox("Pacientes por página", [10, 25, 50, 100], index=2, key="page_size")
    page_offset = st.session_state.get("page_offset", 0)

    data = fetch_patients(limit=page_size, offset=page_offset)
    if not data:
        return

    patients = data.get("items", [])
    total = data.get("total", 0)

    # --- Tabs: Lista | Nuevo paciente | Editar
    tab_lista, tab_nuevo, tab_editar = st.tabs(["📋 Lista de pacientes", "➕ Nuevo paciente", "✏️ Editar paciente"])

    with tab_nuevo:
        with st.form("crear_paciente"):
            st.subheader("Crear paciente (Admin/Médico)")
            c1, c2 = st.columns(2)
            with c1:
                identifier = st.text_input("Identifier*", placeholder="PAC001")
                name = st.text_input("Nombre*", placeholder="Juan")
                family_name = st.text_input("Apellido*", placeholder="Pérez")
                birth_date = st.text_input("Fecha nacimiento", placeholder="1990-01-15")
                gender = st.selectbox("Género", ["", "male", "female", "other"])
            with c2:
                identification_doc = st.text_input("Documento identidad", placeholder="12345678A")
                medical_summary = st.text_area("Resumen médico", placeholder="Alergias, condiciones...")
            if st.form_submit_button("Crear"):
                if not identifier or not name or not family_name:
                    st.error("Identifier, Nombre y Apellido son obligatorios.")
                else:
                    body = {"identifier": identifier, "name": name, "family_name": family_name}
                    if birth_date:
                        body["birth_date"] = birth_date
                    if gender:
                        body["gender"] = gender
                    if identification_doc:
                        body["identification_doc"] = identification_doc
                    if medical_summary:
                        body["medical_summary"] = medical_summary
                    r = create_patient(body)
                    if r and r.status_code in (200, 201):
                        st.success("Paciente creado correctamente.")
                        st.rerun()

    with tab_editar:
        if patients:
            edit_options = {f"{p['name']} {p['family_name']} (ID:{p['id']})": p for p in patients}
            edit_sel = st.selectbox("Seleccionar paciente a editar", list(edit_options.keys()), key="edit_select")
            if edit_sel:
                edit_patient_id = edit_options[edit_sel]
                p = fetch_patient(edit_patient_id["id"])
                if p is None:
                    st.error("No se pudo cargar el paciente.")
                else:
                    with st.form("editar_paciente"):
                        st.subheader(f"Editar: {p['name']} {p['family_name']}")
                        name = st.text_input("Nombre", value=p.get("name", ""))
                        family_name = st.text_input("Apellido", value=p.get("family_name", ""))
                        birth_date = st.text_input("Fecha nacimiento", value=p.get("birth_date") or "")
                        gender = st.selectbox("Género", ["", "male", "female", "other"], index=["", "male", "female", "other"].index((p.get("gender") or "")))
                        identification_doc = st.text_input("Documento", value=p.get("identification_doc") or "")
                        medical_summary = st.text_area("Resumen médico", value=p.get("medical_summary") or "")
                        if st.form_submit_button("Guardar"):
                            body = {}
                            if name:
                                body["name"] = name
                            if family_name:
                                body["family_name"] = family_name
                            if birth_date:
                                body["birth_date"] = birth_date
                            if gender:
                                body["gender"] = gender
                            body["identification_doc"] = identification_doc or None
                            body["medical_summary"] = medical_summary or None
                            r = update_patient(p["id"], body)
                            if r and r.status_code == 200:
                                st.success("Paciente actualizado.")
                                st.rerun()
        else:
            st.info("No hay pacientes para editar.")

    with tab_lista:
        if not patients:
            st.info("No hay pacientes. Crea uno en la pestaña 'Nuevo paciente'.")
            return

        # Controles de paginación
        total_pages = max(1, (total + page_size - 1) // page_size)
        current_page = (page_offset // page_size) + 1
        col_prev, col_info, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("◀ Anterior", disabled=(page_offset == 0)):
                st.session_state["page_offset"] = max(0, page_offset - page_size)
                st.rerun()
        with col_info:
            st.caption(f"Página {current_page} de {total_pages} · Total: {total} pacientes")
        with col_next:
            if st.button("Siguiente ▶", disabled=(page_offset + page_size >= total)):
                st.session_state["page_offset"] = page_offset + page_size
                st.rerun()

        options = {f"{p['name']} {p['family_name']} (ID: {p['id']})": p for p in patients}
        selected_label = st.selectbox("Seleccionar paciente", list(options.keys()), key="patient_select")
        selected_patient = options[selected_label]
        patient_id = selected_patient["id"]

        # Botón eliminar paciente (Admin solo - backend devolverá 403 si no)
        col_v, col_del = st.columns([4, 1])
        with col_del:
            if st.button("🗑️ Eliminar paciente", type="secondary"):
                if st.session_state.get("confirm_delete") == patient_id:
                    r = delete_patient(patient_id)
                    if r and r.status_code == 200:
                        st.success("Paciente eliminado.")
                        if "confirm_delete" in st.session_state:
                            del st.session_state["confirm_delete"]
                        st.rerun()
                else:
                    st.session_state["confirm_delete"] = patient_id
                    st.warning("Pulsa de nuevo para confirmar.")
        if st.session_state.get("confirm_delete") == patient_id:
            st.warning("Confirma eliminación con el botón 'Eliminar paciente'.")

        st.divider()
        st.subheader("Gráficas de tendencias")

        observations = []
        obs_data = fetch_observations(patient_id)
        if obs_data:
            observations = obs_data.get("items", [])

        render_charts(observations)

        # Crear observación
        st.subheader("Registrar signo vital")
        with st.expander("➕ Nueva observación (Admin/Médico)"):
            with st.form("crear_obs"):
                code = st.selectbox("Signo vital", SIGNOS_VITALES)
                value = st.number_input("Valor", min_value=0.0, step=0.1, format="%.1f")
                unit = st.text_input("Unidad", value=UNIDADES.get(code, ""))
                display = st.text_input("Descripción", placeholder="Opcional")
                if st.form_submit_button("Registrar"):
                    body = {"patient_id": patient_id, "code": code, "value_quantity": value}
                    if unit:
                        body["unit"] = unit
                    if display:
                        body["display"] = display
                    r = create_observation(body)
                    if r and r.status_code in (200, 201):
                        st.success("Observación registrada.")
                        st.rerun()

        # Tabla observaciones con outliers
        if observations:
            st.subheader("Tabla de observaciones")
            df = pd.DataFrame(observations)
            df["outlier"] = df.apply(lambda r: is_outlier(r["code"], r["value_quantity"]), axis=1)
            display_df = df[["id", "code", "value_quantity", "unit", "effective_datetime"]].copy()
            outlier_flags = df["outlier"]

            def highlight(row):
                is_out = outlier_flags.iloc[row.name]
                return ["background-color: #ffcccc"] * len(row) if is_out else [""] * len(row)

            styled = display_df.style.apply(highlight, axis=1)
            st.dataframe(styled, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
