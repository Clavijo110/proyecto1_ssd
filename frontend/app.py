"""
Dashboard de Gestión Clínica - Streamlit
Vistas diferenciadas por rol: Admin, Médico, Paciente.
"""
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
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
SIGNOS_VITALES = [
    "heart-rate", "temperature", "blood-pressure",
    "blood-pressure-systolic", "blood-pressure-diastolic", "respiratory-rate",
]
UNIDADES = {
    "heart-rate": "beats/min", "temperature": "°C",
    "blood-pressure": "mmHg", "blood-pressure-systolic": "mmHg",
    "blood-pressure-diastolic": "mmHg", "respiratory-rate": "resp/min",
}
ROLE_LABELS = {"admin": "Administrador", "medico": "Médico", "paciente": "Paciente"}
ROLE_ICONS = {"admin": "🛡️", "medico": "🩺", "paciente": "👤"}


# ─────────────────────────────────────────
# Utilidades de API
# ─────────────────────────────────────────

def get_headers():
    return {
        "X-Access-Key": st.session_state["access_key"],
        "X-Permission-Key": st.session_state["permission_key"],
    }


def api_request(method: str, url: str, silent_403: bool = False, **kwargs):
    """Llamada API con manejo de errores 401, 403, 429."""
    kwargs.setdefault("headers", get_headers())
    kwargs.setdefault("timeout", 15)
    try:
        r = requests.request(method, url, **kwargs)
    except requests.exceptions.ConnectionError:
        st.error("No se pudo conectar al servidor. Verifica que el backend esté en ejecución.")
        return None
    except Exception as e:
        st.error(f"Error de red: {e}")
        return None

    if r.status_code == 401:
        st.error("Sesión expirada o claves inválidas. Por favor inicia sesión de nuevo.")
        st.session_state.clear()
        st.rerun()
    elif r.status_code == 403 and not silent_403:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        st.error(f"**Sin permiso (403):** {detail}")
        return None
    elif r.status_code == 429:
        st.error("**Límite de peticiones alcanzado (429).** Espera un minuto e intenta de nuevo.")
        return None
    return r


def is_outlier(code: str, value: float) -> bool:
    limits = OUTLIER_LIMITS.get(code.lower())
    if not limits:
        return False
    lo, hi = limits
    return value < lo or value > hi


# ─────────────────────────────────────────
# Componentes reutilizables
# ─────────────────────────────────────────

def render_charts(observations: list):
    """Gráficas de tendencias Plotly con marcadores de outliers."""
    if not observations:
        st.info("Este paciente no tiene observaciones registradas.")
        return

    df = pd.DataFrame([{
        "fecha": o["effective_datetime"],
        "code": o["code"],
        "valor": o["value_quantity"],
        "unidad": o.get("unit", ""),
    } for o in observations])
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values("fecha")
    codes = df["code"].unique().tolist()

    cols = st.columns(min(2, len(codes)) or 1)
    for i, code in enumerate(codes):
        subset = df[df["code"] == code]
        with cols[i % 2]:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=subset["fecha"], y=subset["valor"],
                mode="lines+markers", name=code,
                line=dict(color="#1f77b4", width=2),
                marker=dict(size=6),
            ))
            outliers = subset[subset.apply(lambda row: is_outlier(code, row["valor"]), axis=1)]
            if not outliers.empty:
                fig.add_trace(go.Scatter(
                    x=outliers["fecha"], y=outliers["valor"],
                    mode="markers", name="⚠️ Fuera de rango",
                    marker=dict(size=14, color="red", symbol="x"),
                ))
            fig.update_layout(
                title=f"{code}",
                xaxis_title="Fecha",
                yaxis_title=f"Valor",
                hovermode="x unified",
                margin=dict(t=40, b=30),
            )
            st.plotly_chart(fig, use_container_width=True)
            if not outliers.empty:
                st.error(f"⚠️ **Valores fuera de rango clínico** detectados en **{code}**")


def render_observation_table(observations: list):
    """Tabla de observaciones con filas rojas si hay outlier."""
    df = pd.DataFrame(observations)
    df["outlier"] = df.apply(lambda r: is_outlier(r["code"], r["value_quantity"]), axis=1)
    display_df = df[["id", "code", "value_quantity", "unit", "effective_datetime"]].copy()
    display_df.columns = ["ID", "Signo Vital", "Valor", "Unidad", "Fecha y Hora"]
    outlier_flags = df["outlier"]

    def highlight(row):
        return ["background-color: #ffcccc"] * len(row) if outlier_flags.iloc[row.name] else [""] * len(row)

    st.dataframe(display_df.style.apply(highlight, axis=1), use_container_width=True, hide_index=True)


def form_nueva_observacion(patient_id: int):
    """Formulario para registrar un signo vital."""
    with st.form("crear_obs"):
        c1, c2, c3 = st.columns(3)
        with c1:
            code = st.selectbox("Signo vital", SIGNOS_VITALES)
        with c2:
            value = st.number_input("Valor", min_value=0.0, step=0.1, format="%.1f")
        with c3:
            unit = st.text_input("Unidad", value=UNIDADES.get(code, ""))
        display = st.text_input("Descripción (opcional)")
        if st.form_submit_button("Registrar observación", type="primary"):
            body = {"patient_id": patient_id, "code": code, "value_quantity": value}
            if unit:
                body["unit"] = unit
            if display:
                body["display"] = display
            r = api_request("POST", f"{API_BASE}/fhir/Observation", json=body)
            if r and r.status_code in (200, 201):
                st.success("Observación registrada.")
                st.rerun()


def paginacion_controls(total: int, page_size: int, page_offset: int):
    """Muestra controles de paginación y retorna si hubo cambio."""
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = (page_offset // page_size) + 1
    col_prev, col_info, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("◀ Anterior", disabled=(page_offset == 0), key="btn_prev"):
            st.session_state["page_offset"] = max(0, page_offset - page_size)
            st.rerun()
    with col_info:
        st.caption(f"Página **{current_page}** de **{total_pages}** · Total: **{total}** pacientes")
    with col_next:
        if st.button("Siguiente ▶", disabled=(page_offset + page_size >= total), key="btn_next"):
            st.session_state["page_offset"] = page_offset + page_size
            st.rerun()


# ─────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────

def login_form():
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.title("🏥 Dashboard Clínico FHIR-Lite")
        st.markdown("---")
        st.subheader("🔐 Iniciar sesión")
        with st.form("login"):
            access_key = st.text_input("X-Access-Key", type="password", placeholder="Token de acceso")
            permission_key = st.text_input("X-Permission-Key", type="password", placeholder="Llave de permisos")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

            if submitted:
                if not access_key or not permission_key:
                    st.error("Debes ingresar ambas API Keys.")
                    return
                try:
                    # Validar keys y obtener rol desde /me
                    r = requests.get(
                        f"{API_BASE}/me",
                        headers={"X-Access-Key": access_key, "X-Permission-Key": permission_key},
                        timeout=10,
                    )
                    if r.status_code == 200:
                        info = r.json()
                        st.session_state["access_key"] = access_key
                        st.session_state["permission_key"] = permission_key
                        st.session_state["role"] = info["role"]
                        st.session_state["user_id"] = info["user_id"]
                        st.session_state["logged_in"] = True
                        st.rerun()
                    elif r.status_code == 401:
                        st.error("Claves inválidas. Verifica tus API Keys.")
                    elif r.status_code == 404:
                        st.error("El backend no está actualizado. Realiza un nuevo deploy en Render para activar el endpoint /me.")
                    else:
                        st.error(f"Error del servidor: {r.status_code}")
                except requests.exceptions.ConnectionError:
                    st.error("No se pudo conectar al servidor.")
                except Exception as e:
                    st.error(str(e))


# ─────────────────────────────────────────
# VISTA ADMINISTRADOR
# ─────────────────────────────────────────

def vista_admin():
    """
    Admin: gestión administrativa de pacientes (solo datos identificativos, sin info clínica).
    Puede consultar y corregir datos básicos. NO puede crear ni eliminar pacientes.
    """
    st.title("🛡️ Panel de Administración")
    st.caption("Consulta y corrección de datos de registro. Los datos clínicos son de uso exclusivo del personal médico.")

    page_size = st.sidebar.selectbox("Registros por página", [10, 25, 50, 100], index=1, key="page_size")
    page_offset = st.session_state.get("page_offset", 0)

    r = api_request("GET", f"{API_BASE}/fhir/Patient", params={"limit": page_size, "offset": page_offset})
    if not r or r.status_code != 200:
        return
    data = r.json()
    patients = data.get("items", [])
    total = data.get("total", 0)

    tab_lista, tab_editar = st.tabs(["📋 Registros de pacientes", "✏️ Corregir datos"])

    # ── TAB: Lista (solo datos identificativos, sin info clínica)
    with tab_lista:
        if not patients:
            st.info("No hay pacientes registrados.")
        else:
            paginacion_controls(total, page_size, page_offset)
            st.divider()
            df = pd.DataFrame([{
                "ID": p["id"],
                "Identifier": p["identifier"],
                "Nombre": p["name"],
                "Apellido": p["family_name"],
                "Fecha nacimiento": p.get("birth_date") or "—",
                "Género": p.get("gender") or "—",
            } for p in patients])
            st.dataframe(df, use_container_width=True, hide_index=True)

    # ── TAB: Editar datos básicos (sin campos clínicos)
    with tab_editar:
        if not patients:
            st.info("No hay pacientes para editar.")
        else:
            edit_options = {f"ID {p['id']} – {p['name']} {p['family_name']}": p["id"] for p in patients}
            edit_sel = st.selectbox("Seleccionar paciente", list(edit_options.keys()), key="edit_select")
            edit_id = edit_options[edit_sel]

            rp = api_request("GET", f"{API_BASE}/fhir/Patient/{edit_id}")
            if rp and rp.status_code == 200:
                p = rp.json()
                with st.form("editar_paciente"):
                    st.subheader(f"Corrigiendo datos de: {p['name']} {p['family_name']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        name = st.text_input("Nombre", value=p.get("name", ""))
                        family_name = st.text_input("Apellido", value=p.get("family_name", ""))
                    with c2:
                        birth_date = st.text_input("Fecha de nacimiento", value=p.get("birth_date") or "")
                        _opts = ["", "male", "female", "other"]
                        _g = p.get("gender") or ""
                        gender = st.selectbox("Género", _opts, index=_opts.index(_g) if _g in _opts else 0)
                    if st.form_submit_button("Guardar corrección", type="primary"):
                        body = {}
                        if name:
                            body["name"] = name
                        if family_name:
                            body["family_name"] = family_name
                        if birth_date:
                            body["birth_date"] = birth_date
                        if gender:
                            body["gender"] = gender
                        r2 = api_request("PUT", f"{API_BASE}/fhir/Patient/{edit_id}", json=body)
                        if r2 and r2.status_code == 200:
                            st.success("Datos corregidos correctamente.")
                            st.rerun()


# ─────────────────────────────────────────
# VISTA MÉDICO
# ─────────────────────────────────────────

def vista_medico():
    """
    Médico: historia clínica completa.
    Puede crear/editar pacientes y observaciones. No puede borrar pacientes.
    """
    st.title("🩺 Estación de Trabajo Médica")

    page_size = st.sidebar.selectbox("Pacientes por página", [10, 25, 50, 100], index=1, key="page_size")
    page_offset = st.session_state.get("page_offset", 0)

    r = api_request("GET", f"{API_BASE}/fhir/Patient", params={"limit": page_size, "offset": page_offset})
    if not r or r.status_code != 200:
        return
    data = r.json()
    patients = data.get("items", [])
    total = data.get("total", 0)

    tab_hc, tab_nuevo, tab_editar = st.tabs(["📋 Historia clínica", "➕ Nuevo paciente", "✏️ Editar paciente"])

    # ── TAB: Historia clínica
    with tab_hc:
        if not patients:
            st.info("No hay pacientes registrados. Crea uno en la pestaña 'Nuevo paciente'.")
        else:
            paginacion_controls(total, page_size, page_offset)
            st.divider()

            # Selector de paciente
            options = {f"{p['name']} {p['family_name']} (ID: {p['id']})": p for p in patients}
            selected_label = st.selectbox("Seleccionar paciente", list(options.keys()), key="patient_select")
            selected = options[selected_label]
            patient_id = selected["id"]

            # Ficha del paciente con datos clínicos
            with st.expander("📄 Ficha del paciente", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Nombre", f"{selected['name']} {selected['family_name']}")
                c2.metric("Identifier", selected["identifier"])
                c3.metric("Fecha de nacimiento", selected.get("birth_date") or "—")
                c4, c5 = st.columns(2)
                c4.metric("Género", selected.get("gender") or "—")
                c5.metric("ID en sistema", selected["id"])
                if selected.get("identification_doc"):
                    st.info(f"📋 **Documento:** {selected['identification_doc']}")
                if selected.get("medical_summary"):
                    st.warning(f"📝 **Resumen médico:** {selected['medical_summary']}")

            st.divider()

            # Gráficas
            obs_r = api_request("GET", f"{API_BASE}/fhir/Observation",
                                 params={"patient_id": patient_id, "limit": 500, "offset": 0})
            observations = obs_r.json().get("items", []) if obs_r and obs_r.status_code == 200 else []

            st.subheader("📈 Tendencias de signos vitales")
            render_charts(observations)

            # Registrar nueva observación
            st.divider()
            st.subheader("➕ Registrar signo vital")
            form_nueva_observacion(patient_id)

            # Tabla de observaciones
            if observations:
                st.divider()
                st.subheader("📊 Historial de observaciones")
                render_observation_table(observations)

    # ── TAB: Nuevo paciente
    with tab_nuevo:
        st.subheader("Registrar nuevo paciente")
        with st.form("crear_paciente"):
            c1, c2 = st.columns(2)
            with c1:
                identifier = st.text_input("Identifier *", placeholder="PAC001")
                name = st.text_input("Nombre *", placeholder="Juan")
                family_name = st.text_input("Apellido *", placeholder="Pérez")
                birth_date = st.text_input("Fecha de nacimiento", placeholder="1990-01-15")
                gender = st.selectbox("Género", ["", "male", "female", "other"])
            with c2:
                identification_doc = st.text_input("Documento de identidad", placeholder="12345678A")
                medical_summary = st.text_area("Resumen médico", placeholder="Alergias, antecedentes, condiciones...")
            if st.form_submit_button("Crear paciente", type="primary"):
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
                    r2 = api_request("POST", f"{API_BASE}/fhir/Patient", json=body)
                    if r2 and r2.status_code in (200, 201):
                        st.success(f"Paciente **{name} {family_name}** creado.")
                        st.rerun()

    # ── TAB: Editar
    with tab_editar:
        if not patients:
            st.info("No hay pacientes para editar.")
        else:
            edit_options = {f"{p['name']} {p['family_name']} (ID:{p['id']})": p["id"] for p in patients}
            edit_sel = st.selectbox("Seleccionar paciente", list(edit_options.keys()), key="edit_select")
            edit_id = edit_options[edit_sel]

            rp = api_request("GET", f"{API_BASE}/fhir/Patient/{edit_id}")
            if rp and rp.status_code == 200:
                p = rp.json()
                with st.form("editar_paciente"):
                    st.subheader(f"Editando: {p['name']} {p['family_name']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        name = st.text_input("Nombre", value=p.get("name", ""))
                        family_name = st.text_input("Apellido", value=p.get("family_name", ""))
                        birth_date = st.text_input("Fecha de nacimiento", value=p.get("birth_date") or "")
                        _opts = ["", "male", "female", "other"]
                        _g = p.get("gender") or ""
                        gender = st.selectbox("Género", _opts, index=_opts.index(_g) if _g in _opts else 0)
                    with c2:
                        identification_doc = st.text_input("Documento", value=p.get("identification_doc") or "")
                        medical_summary = st.text_area("Resumen médico", value=p.get("medical_summary") or "")
                    if st.form_submit_button("Guardar cambios", type="primary"):
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
                        r2 = api_request("PUT", f"{API_BASE}/fhir/Patient/{edit_id}", json=body)
                        if r2 and r2.status_code == 200:
                            st.success("Paciente actualizado.")
                            st.rerun()


# ─────────────────────────────────────────
# VISTA PACIENTE
# ─────────────────────────────────────────

def vista_paciente():
    """
    Paciente: solo lectura de sus propios datos clínicos y signos vitales.
    No puede ver datos de otros pacientes ni realizar ninguna modificación.
    """
    user_id = st.session_state.get("user_id")
    if not user_id:
        st.error("No se encontró tu ID de paciente. Contacta al administrador.")
        return

    st.title("👤 Mi Historia Clínica")
    st.caption("Vista de solo lectura. Aquí puedes consultar tus datos y el seguimiento de tus signos vitales.")

    # Cargar datos propios
    rp = api_request("GET", f"{API_BASE}/fhir/Patient/{user_id}")
    if not rp or rp.status_code != 200:
        st.error("No se pudieron cargar tus datos.")
        return

    p = rp.json()

    # Ficha personal
    with st.container():
        st.subheader("📄 Mis datos")
        c1, c2, c3 = st.columns(3)
        c1.metric("Nombre", f"{p['name']} {p['family_name']}")
        c2.metric("Fecha de nacimiento", p.get("birth_date") or "—")
        c3.metric("Género", p.get("gender") or "—")

        if p.get("medical_summary"):
            st.info(f"📝 **Resumen médico:** {p['medical_summary']}")

    st.divider()

    # Observaciones
    obs_r = api_request("GET", f"{API_BASE}/fhir/Observation",
                         params={"patient_id": user_id, "limit": 500, "offset": 0})
    observations = obs_r.json().get("items", []) if obs_r and obs_r.status_code == 200 else []

    st.subheader("📈 Mis signos vitales")
    render_charts(observations)

    if observations:
        st.divider()
        st.subheader("📊 Historial de observaciones")
        render_observation_table(observations)
    else:
        st.info("No hay observaciones registradas aún.")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    if not st.session_state.get("logged_in"):
        login_form()
        return

    role = st.session_state.get("role", "")
    role_label = ROLE_LABELS.get(role, role)
    role_icon = ROLE_ICONS.get(role, "")

    with st.sidebar:
        st.markdown(f"### {role_icon} {role_label}")
        st.caption("Sesión activa")
        st.divider()
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    if role == "admin":
        vista_admin()
    elif role == "medico":
        vista_medico()
    elif role == "paciente":
        vista_paciente()
    else:
        st.error(f"Rol desconocido: '{role}'. Contacta al administrador.")


if __name__ == "__main__":
    main()
