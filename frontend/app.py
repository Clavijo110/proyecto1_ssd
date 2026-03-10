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

# Catálogo de signos vitales según estándar FHIR-Lite / LOINC
# Campos: label, unit, step, fmt, outlier (lo, hi), normal (lo, hi)
SIGNOS_VITALES_INFO = {
    "heart-rate": {
        "label": "Frecuencia cardíaca",
        "unit": "beats/min", "step": 1.0, "fmt": "%.0f",
        "outlier": (40, 180), "normal": (60, 100),
    },
    "temperature": {
        "label": "Temperatura corporal",
        "unit": "°C", "step": 0.1, "fmt": "%.1f",
        "outlier": (35.0, 42.0), "normal": (36.1, 37.5),
    },
    "blood-pressure-systolic": {
        "label": "Presión arterial sistólica",
        "unit": "mmHg", "step": 1.0, "fmt": "%.0f",
        "outlier": (70, 200), "normal": (90, 120),
    },
    "blood-pressure-diastolic": {
        "label": "Presión arterial diastólica",
        "unit": "mmHg", "step": 1.0, "fmt": "%.0f",
        "outlier": (40, 130), "normal": (60, 80),
    },
    "respiratory-rate": {
        "label": "Frecuencia respiratoria",
        "unit": "resp/min", "step": 1.0, "fmt": "%.0f",
        "outlier": (8, 40), "normal": (12, 20),
    },
    "oxygen-saturation": {
        "label": "Saturación de oxígeno (SpO₂)",
        "unit": "%", "step": 0.5, "fmt": "%.1f",
        "outlier": (90.0, 100.0), "normal": (95.0, 100.0),
    },
    "body-weight": {
        "label": "Peso corporal",
        "unit": "kg", "step": 0.1, "fmt": "%.1f",
        "outlier": (2.0, 300.0), "normal": (3.0, 200.0),
    },
    "body-height": {
        "label": "Talla corporal",
        "unit": "cm", "step": 0.5, "fmt": "%.1f",
        "outlier": (30.0, 250.0), "normal": (45.0, 220.0),
    },
    "bmi": {
        "label": "Índice de masa corporal (IMC)",
        "unit": "kg/m²", "step": 0.1, "fmt": "%.1f",
        "outlier": (10.0, 70.0), "normal": (18.5, 24.9),
    },
    "blood-glucose": {
        "label": "Glucosa en sangre",
        "unit": "mg/dL", "step": 1.0, "fmt": "%.0f",
        "outlier": (40.0, 600.0), "normal": (70.0, 100.0),
    },
}

# Derivados para compatibilidad con el resto del código
OUTLIER_LIMITS = {code: info["outlier"] for code, info in SIGNOS_VITALES_INFO.items()}
SIGNOS_VITALES = list(SIGNOS_VITALES_INFO.keys())
UNIDADES = {code: info["unit"] for code, info in SIGNOS_VITALES_INFO.items()}
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
    """Formulario para registrar un signo vital.
    El selectbox está fuera del form para que la unidad y el rango se actualicen
    automáticamente al cambiar el signo vital.
    """
    # Selección fuera del form → provoca rerun inmediato al cambiar
    code = st.selectbox(
        "Signo vital",
        SIGNOS_VITALES,
        format_func=lambda k: f"{SIGNOS_VITALES_INFO[k]['label']} ({SIGNOS_VITALES_INFO[k]['unit']})",
        key=f"obs_code_{patient_id}",
    )
    info = SIGNOS_VITALES_INFO[code]
    n_lo, n_hi = info["normal"]
    o_lo, o_hi = info["outlier"]

    col_info1, col_info2 = st.columns(2)
    col_info1.info(f"**Unidad:** {info['unit']}  ·  **Rango normal:** {n_lo} – {n_hi} {info['unit']}")
    col_info2.warning(f"**Alerta outlier** si valor < {o_lo} o > {o_hi} {info['unit']}")

    with st.form(f"crear_obs_{patient_id}"):
        c1, c2 = st.columns(2)
        with c1:
            value = st.number_input(
                f"Valor ({info['unit']})",
                min_value=0.0,
                step=info["step"],
                format=info["fmt"],
            )
        with c2:
            display = st.text_input("Descripción (opcional)", placeholder="Ej: en reposo, ayunas...")

        if st.form_submit_button("Registrar observación", type="primary"):
            if value <= 0:
                st.error("El valor debe ser mayor a 0.")
            else:
                if value < o_lo or value > o_hi:
                    st.warning(f"⚠️ Valor fuera del rango clínico ({o_lo}–{o_hi} {info['unit']}). Se registrará de todas formas.")
                body = {
                    "patient_id": patient_id,
                    "code": code,
                    "value_quantity": value,
                    "unit": info["unit"],
                }
                if display:
                    body["display"] = display
                r = api_request("POST", f"{API_BASE}/fhir/Observation", json=body)
                if r and r.status_code in (200, 201):
                    st.success(f"✅ Observación registrada: {info['label']} = {value} {info['unit']}")
                    st.rerun()


def paginacion_controls(total: int, page_size: int, page_offset: int):
    """Paginación con botones primera/anterior/siguiente/última y salto directo a página."""
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = (page_offset // page_size) + 1

    c1, c2, c3, c4, c5 = st.columns([1, 1, 3, 1, 1])
    with c1:
        if st.button("⏮", help="Primera página", disabled=(current_page == 1), key="btn_first"):
            st.session_state["page_offset"] = 0
            st.rerun()
    with c2:
        if st.button("◀", help="Página anterior", disabled=(current_page == 1), key="btn_prev"):
            st.session_state["page_offset"] = max(0, page_offset - page_size)
            st.rerun()
    with c3:
        target = st.number_input(
            "Ir a página",
            min_value=1, max_value=total_pages,
            value=current_page, step=1,
            key="page_input",
            label_visibility="collapsed",
        )
        st.caption(f"Página **{current_page}** de **{total_pages}** · **{total}** registros en total")
        if int(target) != current_page:
            st.session_state["page_offset"] = (int(target) - 1) * page_size
            st.rerun()
    with c4:
        if st.button("▶", help="Página siguiente", disabled=(current_page >= total_pages), key="btn_next"):
            st.session_state["page_offset"] = page_offset + page_size
            st.rerun()
    with c5:
        if st.button("⏭", help="Última página", disabled=(current_page >= total_pages), key="btn_last"):
            st.session_state["page_offset"] = (total_pages - 1) * page_size
            st.rerun()


def filtrar_pacientes(patients: list, query: str) -> list:
    """Filtra la lista de pacientes por nombre, apellido o identifier (case-insensitive)."""
    if not query.strip():
        return patients
    q = query.strip().lower()
    return [
        p for p in patients
        if q in p.get("name", "").lower()
        or q in p.get("family_name", "").lower()
        or q in p.get("identifier", "").lower()
    ]


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
    Admin: gestión completa de pacientes (crear, consultar, editar, eliminar).
    Solo muestra datos identificativos; los datos clínicos son exclusivos del personal médico.
    """
    st.title("🛡️ Panel de Administración")
    st.caption("Gestión de registros de pacientes. Los datos clínicos son de uso exclusivo del personal médico.")

    # Controles en sidebar
    page_size = st.sidebar.selectbox("Registros por página", [10, 25, 50, 100], index=1, key="page_size")
    buscar = st.sidebar.text_input("🔍 Buscar paciente", placeholder="Nombre, apellido o identifier...", key="buscar_admin")
    page_offset = st.session_state.get("page_offset", 0)

    r = api_request("GET", f"{API_BASE}/fhir/Patient", params={"limit": page_size, "offset": page_offset})
    if not r or r.status_code != 200:
        return
    data = r.json()
    patients_page = data.get("items", [])
    total = data.get("total", 0)

    # Filtrado client-side sobre la página actual
    patients = filtrar_pacientes(patients_page, buscar)

    tab_lista, tab_nuevo, tab_editar = st.tabs(["📋 Registros", "➕ Nuevo paciente", "✏️ Editar / Eliminar"])

    # ── TAB: Lista
    with tab_lista:
        paginacion_controls(total, page_size, page_offset)
        st.divider()

        if buscar and not patients:
            st.warning(f"No se encontraron pacientes que coincidan con «{buscar}» en esta página. Prueba en otra página o limpia el filtro.")
        elif not patients_page:
            st.info("No hay pacientes registrados.")
        else:
            df = pd.DataFrame([{
                "ID": p["id"],
                "Identifier": p["identifier"],
                "Nombre": p["name"],
                "Apellido": p["family_name"],
                "Fecha nacimiento": p.get("birth_date") or "—",
                "Género": p.get("gender") or "—",
            } for p in patients])
            st.dataframe(df, use_container_width=True, hide_index=True)
            if buscar:
                st.caption(f"Mostrando {len(patients)} resultado(s) filtrados de {len(patients_page)} en esta página.")

    # ── TAB: Nuevo paciente
    with tab_nuevo:
        st.subheader("Registrar nuevo paciente")
        with st.form("crear_paciente"):
            c1, c2 = st.columns(2)
            with c1:
                identifier = st.text_input("Identifier *", placeholder="PAC001")
                name = st.text_input("Nombre *", placeholder="Juan")
                family_name = st.text_input("Apellido *", placeholder="Pérez")
            with c2:
                birth_date = st.text_input("Fecha de nacimiento", placeholder="1990-01-15")
                gender = st.selectbox("Género", ["", "male", "female", "other"])
            if st.form_submit_button("Crear paciente", type="primary"):
                if not identifier or not name or not family_name:
                    st.error("Identifier, Nombre y Apellido son obligatorios.")
                else:
                    body = {"identifier": identifier, "name": name, "family_name": family_name}
                    if birth_date:
                        body["birth_date"] = birth_date
                    if gender:
                        body["gender"] = gender
                    r2 = api_request("POST", f"{API_BASE}/fhir/Patient", json=body)
                    if r2 and r2.status_code in (200, 201):
                        st.success(f"Paciente **{name} {family_name}** creado correctamente.")
                        st.rerun()

    # ── TAB: Editar / Eliminar (usa el filtro de búsqueda del sidebar)
    with tab_editar:
        pool = patients if patients else patients_page
        if not pool:
            st.info("No hay pacientes registrados.")
        else:
            if buscar and not patients:
                st.warning(f"No hay coincidencias para «{buscar}» en esta página.")
            else:
                # ── Sección editar
                st.subheader("✏️ Editar datos")
                edit_options = {f"{p['name']} {p['family_name']}  —  ID {p['id']}  |  {p['identifier']}": p["id"] for p in pool}
                edit_sel = st.selectbox(
                    "Seleccionar paciente a editar",
                    list(edit_options.keys()),
                    key="edit_select",
                    help="Usa el buscador del panel izquierdo para filtrar la lista",
                )
                edit_id = edit_options[edit_sel]

                rp = api_request("GET", f"{API_BASE}/fhir/Patient/{edit_id}")
                if rp and rp.status_code == 200:
                    p = rp.json()
                    with st.form("editar_paciente"):
                        c1, c2 = st.columns(2)
                        with c1:
                            name = st.text_input("Nombre", value=p.get("name", ""))
                            family_name = st.text_input("Apellido", value=p.get("family_name", ""))
                        with c2:
                            birth_date = st.text_input("Fecha de nacimiento", value=p.get("birth_date") or "")
                            _opts = ["", "male", "female", "other"]
                            _g = p.get("gender") or ""
                            gender = st.selectbox("Género", _opts, index=_opts.index(_g) if _g in _opts else 0)
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
                            r2 = api_request("PUT", f"{API_BASE}/fhir/Patient/{edit_id}", json=body)
                            if r2 and r2.status_code == 200:
                                st.success("Paciente actualizado.")
                                st.rerun()

                st.divider()

                # ── Sección eliminar
                st.subheader("🗑️ Eliminar paciente")
                del_options = {f"{p['name']} {p['family_name']}  —  ID {p['id']}  |  {p['identifier']}": p["id"] for p in pool}
                del_sel = st.selectbox(
                    "Seleccionar paciente a eliminar",
                    list(del_options.keys()),
                    key="del_select",
                    help="Usa el buscador del panel izquierdo para filtrar la lista",
                )
                del_id = del_options[del_sel]

                col_btn, col_warn = st.columns([1, 3])
                with col_btn:
                    if st.button("🗑️ Eliminar", type="secondary"):
                        if st.session_state.get("confirm_delete") == del_id:
                            r2 = api_request("DELETE", f"{API_BASE}/fhir/Patient/{del_id}")
                            if r2 and r2.status_code == 200:
                                st.success("Paciente eliminado.")
                                st.session_state.pop("confirm_delete", None)
                                st.rerun()
                        else:
                            st.session_state["confirm_delete"] = del_id
                with col_warn:
                    if st.session_state.get("confirm_delete") == del_id:
                        st.warning("⚠️ Haz clic en **Eliminar** de nuevo para confirmar la eliminación.")


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
    buscar = st.sidebar.text_input("🔍 Buscar paciente", placeholder="Nombre, apellido o identifier...", key="buscar_medico")
    page_offset = st.session_state.get("page_offset", 0)

    r = api_request("GET", f"{API_BASE}/fhir/Patient", params={"limit": page_size, "offset": page_offset})
    if not r or r.status_code != 200:
        return
    data = r.json()
    patients_page = data.get("items", [])
    total = data.get("total", 0)

    patients = filtrar_pacientes(patients_page, buscar)

    tab_hc, tab_nuevo, tab_editar = st.tabs(["📋 Historia clínica", "➕ Nuevo paciente", "✏️ Editar paciente"])

    # ── TAB: Historia clínica
    with tab_hc:
        if not patients_page:
            st.info("No hay pacientes registrados. Crea uno en la pestaña 'Nuevo paciente'.")
        else:
            paginacion_controls(total, page_size, page_offset)
            st.divider()

            if buscar and not patients:
                st.warning(f"No hay coincidencias para «{buscar}» en esta página.")
                return

            # Selector de paciente filtrado
            options = {f"{p['name']} {p['family_name']}  —  ID {p['id']}  |  {p['identifier']}": p for p in patients}
            selected_label = st.selectbox(
                "Seleccionar paciente",
                list(options.keys()),
                key="patient_select",
                help="Usa el buscador del panel izquierdo para filtrar la lista",
            )
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

    # ── TAB: Editar (médico)
    with tab_editar:
        pool_m = patients if patients else patients_page
        if not pool_m:
            st.info("No hay pacientes para editar.")
        else:
            if buscar and not patients:
                st.warning(f"No hay coincidencias para «{buscar}» en esta página. Limpia el filtro o navega a otra página.")
            else:
                edit_options = {f"{p['name']} {p['family_name']}  —  ID {p['id']}  |  {p['identifier']}": p["id"] for p in pool_m}
                edit_sel = st.selectbox(
                    "Seleccionar paciente",
                    list(edit_options.keys()),
                    key="edit_select",
                    help="Usa el buscador del panel izquierdo para filtrar la lista",
                )
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
