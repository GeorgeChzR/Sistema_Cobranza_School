"""Dashboard interactivo del Sistema de Cobranza Escolar (Streamlit).

Ejecutar con:
    streamlit run app.py
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from cobranza import analizar_cartera, cargar_config, cargar_movimientos
from cobranza.analisis import resumen_indicadores
from cobranza.bitacora import (
    MEDIOS,
    RESULTADOS,
    ROLES,
    esta_configurada,
    historial_alumno,
    listar_seguimientos,
    mensaje_configuracion,
    registrar_seguimiento,
    resumen_por_alumnos,
    verificar_conexion,
)
from cobranza.mongodb import verificar_conexion as ping_mongo
from cobranza.reporte import exportar_reporte_bytes
from cobranza.usuarios import (
    actualizar_usuario,
    autenticar,
    crear_usuario,
    es_admin,
    inicializar_usuarios,
    listar_usuarios,
)

COLORES = {"Verde": "#2e7d32", "Amarillo": "#f9a825", "Naranja": "#ef6c00", "Rojo": "#c62828"}
COLORES_TEXTO = {"Verde": "#ffffff", "Amarillo": "#1a1a1a", "Naranja": "#ffffff", "Rojo": "#ffffff"}
OPCIONES_SEMAFORO = ["Rojo", "Naranja", "Amarillo", "Verde"]

st.set_page_config(page_title="Cobranza Escolar - Meraki", layout="wide")


def _inyectar_css_ui() -> None:
    """Estilos estáticos del panel de filtros."""
    if st.session_state.get("_css_ui"):
        return
    st.session_state["_css_ui"] = True

    panel = """
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.filtro-seguimiento-marker) {
        padding: 1.1rem 1.25rem 1.25rem;
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.03);
    }
    .filtro-seg-subtitulo {
        color: rgba(250, 250, 250, 0.55);
        font-size: 0.82rem;
        margin: -0.25rem 0 0.75rem 0;
    }
    .filtro-seg-contador {
        color: rgba(250, 250, 250, 0.45);
        font-size: 0.78rem;
        text-align: right;
        margin-top: 0.35rem;
    }
    """
    st.markdown(f"<style>{panel}</style>", unsafe_allow_html=True)


def _css_chips_semaforo(seleccionados: list[str]) -> None:
    """Colores por chip; se recalcula cada vez según la selección activa."""

    reglas = []
    for color in OPCIONES_SEMAFORO:
        bg = COLORES[color]
        fg = COLORES_TEXTO[color]
        activo = color in seleccionados
        opacidad = "1" if activo else "0.38"
        extra = (
            "box-shadow: 0 0 0 2px rgba(255,255,255,0.85) inset, 0 4px 12px rgba(0,0,0,0.22) !important;"
            "transform: translateY(-1px) !important;"
            if activo
            else ""
        )
        sel = f".st-key-chip_sem_{color}"
        reglas.append(
            f"{sel} button, {sel} button[kind='secondary'], {sel} button[kind='primary'], "
            f"{sel} [data-testid='stBaseButton-secondary'], {sel} [data-testid='stBaseButton-primary'] {{"
            f"background: {bg} !important;"
            f"background-color: {bg} !important;"
            f"border-color: {bg} !important;"
            f"color: {fg} !important;"
            f"opacity: {opacidad} !important;"
            f"min-height: 2.75rem !important;"
            f"border-radius: 12px !important;"
            f"font-weight: 700 !important;"
            f"{extra}"
            f"}}"
            f"{sel} button p, {sel} button span {{"
            f"color: {fg} !important;"
            f"font-weight: 700 !important;"
            f"white-space: nowrap !important;"
            f"font-size: 0.95rem !important;"
            f"}}"
            f"{sel} button:hover {{"
            f"background: {bg} !important;"
            f"background-color: {bg} !important;"
            f"border-color: {bg} !important;"
            f"opacity: {'1' if activo else '0.55'} !important;"
            f"}}"
        )
    st.markdown(f"<style>{''.join(reglas)}</style>", unsafe_allow_html=True)


def _filtro_semaforo_coloreado() -> list[str]:
    """Filtro de semáforo con etiquetas en su color correspondiente."""

    key = "colores_sel"
    if key not in st.session_state:
        st.session_state[key] = ["Rojo", "Naranja", "Amarillo"]

    seleccion = list(st.session_state[key])
    _inyectar_css_ui()
    _css_chips_semaforo(seleccion)
    st.markdown("##### Semáforo")
    st.markdown(
        '<p class="filtro-seg-subtitulo">Clic en cada color para incluir o quitar del listado</p>',
        unsafe_allow_html=True,
    )

    chip_cols = st.columns(len(OPCIONES_SEMAFORO), gap="small")
    for col, color in zip(chip_cols, OPCIONES_SEMAFORO):
        activo = color in st.session_state[key]
        etiqueta = f"✓ {color}" if activo else color
        with col:
            if st.button(
                etiqueta,
                key=f"chip_sem_{color}",
                use_container_width=True,
                type="secondary",
                help=f"{'Quitar' if activo else 'Agregar'} {color} al filtro",
            ):
                seleccion = list(st.session_state[key])
                if activo:
                    if len(seleccion) > 1:
                        seleccion.remove(color)
                else:
                    seleccion.append(color)
                st.session_state[key] = seleccion
                st.rerun()

    n = len(st.session_state[key])
    st.markdown(
        f'<p class="filtro-seg-contador">{n} de {len(OPCIONES_SEMAFORO)} colores activos</p>',
        unsafe_allow_html=True,
    )
    return list(st.session_state[key])


def _panel_filtros_seguimiento(estado: pd.DataFrame) -> tuple[list[str], str, bool, bool]:
    """Panel de filtros para la tabla de alumnos."""

    _inyectar_css_ui()
    niveles = ["(Todos)"] + sorted(estado["Nivel"].dropna().unique().tolist())

    with st.container(border=True):
        st.markdown('<span class="filtro-seguimiento-marker"></span>', unsafe_allow_html=True)
        colores_sel = _filtro_semaforo_coloreado()

        st.divider()

        c1, c2, c3 = st.columns([2.2, 1.4, 1.4], vertical_alignment="bottom")
        with c1:
            nivel_sel = st.selectbox("Nivel educativo", niveles, key="filtro_nivel")
        with c2:
            solo_adeudo = st.checkbox("Solo con saldo pendiente", value=True, key="filtro_adeudo")
        with c3:
            sin_aviso = st.checkbox("Sin aviso registrado", value=False, key="filtro_sin_aviso")

    return colores_sel, nivel_sel, solo_adeudo, sin_aviso


def _usuario_sesion() -> dict | None:
    return st.session_state.get("usuario")


def _cerrar_sesion() -> None:
    st.session_state.pop("usuario", None)
    st.session_state.pop("reporte_bytes", None)


def _pagina_login() -> None:
    st.title("Sistema de Cobranza Escolar")
    st.caption("Gestión Integral de Cartera · MTI-PRO-ADM-2026-003")

    if not esta_configurada():
        st.error("MongoDB no está configurado. Es necesario para usuarios y bitácora.")
        st.code(mensaje_configuracion(), language="text")
        return

    ok, msg = ping_mongo()
    if not ok:
        st.error(msg)
        return

    try:
        inicializar_usuarios()
    except Exception as exc:
        st.error(f"No se pudo inicializar usuarios: {exc}")
        return

    st.subheader("Iniciar sesión")

    with st.form("login"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    if entrar:
        usuario = autenticar(username, password)
        if usuario:
            st.session_state["usuario"] = usuario
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos, o cuenta inactiva.")

    #with st.expander("Primera vez: crear administrador"):
    #    st.markdown(
    #        "Si no hay usuarios, configura estas variables en **Streamlit Secrets** "
    #        "(Cloud) o en tu archivo **`.env`** (local):\n\n"
    #        "```\n"
    #        "ADMIN_USUARIO=admin\n"
    #        "ADMIN_NOMBRE=Nombre del administrador\n"
    #        "ADMIN_PASSWORD=tu_contraseña_segura\n"
    #        "```\n\n"
    #        "Al recargar la app, el administrador se crea automáticamente."
    #    )


def _sidebar(usuario: dict) -> tuple[object | None, date]:
    with st.sidebar:
        st.header("Sesión")
        st.markdown(f"**{usuario['nombre']}**")
        st.caption(usuario["rol"])
        if st.button("Cerrar sesión", use_container_width=True):
            _cerrar_sesion()
            st.rerun()

        st.divider()
        st.header("Datos de entrada")
        archivo = st.file_uploader(
            "Archivo de Cuentas por Cobrar (.csv o .xlsx)",
            type=["csv", "xlsx", "xls"],
        )
        fecha_corte = st.date_input("Fecha de corte", value=date.today())
        st.divider()
        st.markdown(
            "**Semaforización**\n\n"
            "- Verde: preventivo\n"
            "- Amarillo: 1 a 30 días\n"
            "- Naranja: 31 a 60 días\n"
            "- Rojo: más de 60 días"
        )
        st.divider()
        ok, msg = verificar_conexion()
        if ok:
            st.success("MongoDB conectado")
        else:
            st.error(msg)

    return archivo, fecha_corte


def _cargar(archivo) -> pd.DataFrame:
    suffix = ".xlsx" if archivo.name.lower().endswith(("xlsx", "xls")) else ".csv"
    tmp = f"_subida_temporal{suffix}"
    with open(tmp, "wb") as fh:
        fh.write(archivo.getbuffer())
    return cargar_movimientos(tmp)


def _etiqueta_alumno(row) -> str:
    return f"{row['Alumno']} · {row['Matrícula']} · {row['Grado']} {row['Grupo']} · {row['Semáforo']}"


def _tab_usuarios(usuario: dict) -> None:
    if not es_admin(usuario):
        st.warning("Solo **Administración General** puede gestionar usuarios.")
        return

    st.subheader("Gestión de usuarios")

    lista = listar_usuarios()
    if not lista.empty:
        st.dataframe(
            lista.drop(columns=["id"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No hay usuarios registrados.")

    col_nuevo, col_editar = st.columns(2)

    with col_nuevo:
        st.markdown("#### Crear usuario")
        with st.form("crear_usuario"):
            nu_user = st.text_input("Usuario (login)", key="nu_user")
            nu_nombre = st.text_input("Nombre completo", key="nu_nombre")
            nu_rol = st.selectbox("Rol", ROLES, key="nu_rol")
            nu_pass = st.text_input("Contraseña", type="password", key="nu_pass")
            nu_pass2 = st.text_input("Confirmar contraseña", type="password", key="nu_pass2")
            crear = st.form_submit_button("Crear usuario", type="primary")

        if crear:
            if nu_pass != nu_pass2:
                st.error("Las contraseñas no coinciden.")
            else:
                try:
                    crear_usuario(
                        username=nu_user,
                        nombre=nu_nombre,
                        rol=nu_rol,
                        password=nu_pass,
                        creado_por=usuario["nombre"],
                    )
                    st.success(f"Usuario '{nu_user}' creado.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with col_editar:
        st.markdown("#### Modificar usuario")
        if lista.empty:
            st.caption("Crea un usuario primero.")
        else:
            opciones = {
                f"{r['Nombre']} ({r['Usuario']})": r["id"]
                for _, r in lista.iterrows()
            }
            sel = st.selectbox("Seleccionar usuario", list(opciones.keys()))
            user_id = opciones[sel]
            fila = lista[lista["id"] == user_id].iloc[0]

            with st.form("editar_usuario"):
                ed_nombre = st.text_input("Nombre completo", value=fila["Nombre"])
                ed_rol = st.selectbox("Rol", ROLES, index=ROLES.index(fila["Rol"]))
                ed_activo = st.checkbox("Cuenta activa", value=fila["Activo"] == "Sí")
                ed_pass = st.text_input(
                    "Nueva contraseña (opcional)", type="password", placeholder="Dejar vacío para no cambiar"
                )
                guardar = st.form_submit_button("Guardar cambios", type="primary")

            if guardar:
                try:
                    actualizar_usuario(
                        user_id=user_id,
                        nombre=ed_nombre,
                        rol=ed_rol,
                        activo=ed_activo,
                        password=ed_pass or None,
                        actualizado_por=usuario["nombre"],
                    )
                    if user_id == usuario["id"]:
                        st.session_state["usuario"]["nombre"] = ed_nombre.strip()
                        st.session_state["usuario"]["rol"] = ed_rol
                    st.success("Usuario actualizado.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


# --- Inicio: login o app principal ---
if not _usuario_sesion():
    _pagina_login()
    st.stop()

usuario = _usuario_sesion()
cfg = cargar_config()

st.title("Sistema de Cobranza Escolar")
st.caption("Gestión Integral de Cartera · MTI-PRO-ADM-2026-003")

archivo, fecha_corte = _sidebar(usuario)

if archivo is None:
    st.info("Sube el archivo de Cuentas por Cobrar en la barra lateral para comenzar.")
    if es_admin(usuario):
        st.divider()
        _tab_usuarios(usuario)
    st.stop()

df = _cargar(archivo)
estado = analizar_cartera(df, fecha_corte=fecha_corte, cfg=cfg)
estado = resumen_por_alumnos(estado)
ind = resumen_indicadores(estado, fecha_corte)

if estado.empty:
    st.warning("No se encontraron movimientos válidos en el archivo.")
    st.stop()

tabs = ["Cartera", "Registrar aviso", "Historial bitácora"]
if es_admin(usuario):
    tabs.append("Usuarios")

widgets = st.tabs(tabs)
tab_cartera = widgets[0]
tab_bitacora = widgets[1]
tab_historial = widgets[2]
tab_usuarios = widgets[3] if es_admin(usuario) else None

with tab_cartera:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total alumnos", ind["total_alumnos"])
    c2.metric(
        "Con Adeudo Vencido",
        f"{ind['alumnos_con_adeudo_vencido']} ({ind['porcentaje_adeudo_vencido']}%)",
    )
    c3.metric("Saldo vencido", f"${ind['saldo_vencido']:,.0f}")
    c4.metric("En Rojo", ind["conteo"].get("Rojo", 0))

    st.subheader("Distribución de cartera")
    cols = st.columns(4)
    for col, color in zip(cols, ["Verde", "Amarillo", "Naranja", "Rojo"]):
        n = ind["conteo"].get(color, 0)
        pct = ind["porcentaje"].get(color, 0)
        saldo = ind["saldo_por_color"].get(color, 0)
        col.markdown(
            f"<div style='background:{COLORES[color]};padding:14px;border-radius:10px;color:white'>"
            f"<b>{color}</b><br>{n} alumnos ({pct}%)<br>${saldo:,.0f}</div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.subheader("Alumnos a dar seguimiento")
    colores_sel, nivel_sel, solo_adeudo, sin_aviso = _panel_filtros_seguimiento(estado)

    vista = estado.copy()
    if colores_sel:
        vista = vista[vista["Semáforo"].isin(colores_sel)]
    if nivel_sel != "(Todos)":
        vista = vista[vista["Nivel"] == nivel_sel]
    if solo_adeudo:
        vista = vista[vista["Saldo"] > 0.005]
    if sin_aviso and "Total Seguimientos" in vista.columns:
        vista = vista[vista["Total Seguimientos"].fillna(0) == 0]

    st.dataframe(vista, use_container_width=True, hide_index=True)
    st.caption(f"{len(vista)} alumnos en la vista actual.")

    _clave_reporte = f"{fecha_corte}|{archivo.name}"
    if st.session_state.get("_reporte_clave") != _clave_reporte:
        st.session_state.pop("reporte_bytes", None)
        st.session_state["_reporte_clave"] = _clave_reporte

    st.session_state["_estado_reporte"] = estado
    st.session_state["_fecha_reporte"] = fecha_corte

    def _generar_reporte_descarga() -> None:
        st.session_state["reporte_bytes"] = exportar_reporte_bytes(
            st.session_state["_estado_reporte"],
            st.session_state["_fecha_reporte"],
        )

    nombre_reporte = f"reporte_cobranza_{ind['fecha_corte']}.xlsx"
    st.download_button(
        "Descargar reporte Excel completo",
        data=st.session_state.get("reporte_bytes") or b"",
        file_name=nombre_reporte,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        on_click=_generar_reporte_descarga,
        key="btn_descarga_reporte",
        help="El reporte se genera al hacer clic; no se guarda en disco hasta que lo descargues.",
    )

with tab_bitacora:
    ok, msg = verificar_conexion()
    if not ok:
        st.error(msg)
        st.stop()

    candidatos = estado[estado["Saldo"] > 0.005].copy()
    if candidatos.empty:
        candidatos = estado.copy()

    opciones = candidatos.apply(_etiqueta_alumno, axis=1).tolist()
    if not opciones:
        st.warning("No hay alumnos en la cartera cargada.")
        st.stop()

    sel = st.selectbox("Alumno", opciones)
    idx = opciones.index(sel)
    alumno_row = candidatos.iloc[idx]

    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo", f"${alumno_row['Saldo']:,.2f}")
    c2.metric("Saldo vencido", f"${alumno_row['Saldo Vencido']:,.2f}")
    c3.metric("Semáforo", alumno_row["Semáforo"])

    st.caption(
        f"Registrando como: **{usuario['nombre']}** ({usuario['rol']}) · "
        f"Responsable sugerido: **{alumno_row['Responsable']}**"
    )

    with st.form("form_bitacora", clear_on_submit=True):
        st.subheader("Nuevo registro de aviso")
        fc1, fc2 = st.columns(2)
        fecha_aviso = fc1.date_input("Fecha del aviso", value=date.today())
        aviso_realizado = fc2.checkbox("¿Se realizó el aviso?", value=True)
        medio = st.selectbox("Medio utilizado", MEDIOS)
        resultado = st.selectbox("Resultado", RESULTADOS)
        tiene_compromiso = st.checkbox("Registrar compromiso de pago")
        compromiso = (
            st.date_input("Fecha de compromiso", value=date.today(), min_value=date.today())
            if tiene_compromiso
            else None
        )
        observaciones = st.text_area("Observaciones", placeholder="Respuesta de la familia, acuerdos, etc.")
        guardar = st.form_submit_button("Guardar en bitácora", type="primary")

    if guardar:
        try:
            doc_id = registrar_seguimiento(
                matricula=str(alumno_row["Matrícula"]),
                alumno=str(alumno_row["Alumno"]),
                ciclo_escolar=str(alumno_row["Ciclo Escolar"]),
                fecha_aviso=fecha_aviso,
                registrado_por=usuario["nombre"],
                rol=usuario["rol"],
                semaforo=str(alumno_row["Semáforo"]),
                aviso_realizado=aviso_realizado,
                medio=medio,
                resultado=resultado,
                compromiso_pago=compromiso,
                observaciones=observaciones,
                saldo=float(alumno_row["Saldo"]),
                saldo_vencido=float(alumno_row["Saldo Vencido"]),
            )
            st.success(f"Registro guardado (id: {doc_id[:8]}…)")
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo guardar: {exc}")

    st.subheader("Historial de este alumno")
    hist = historial_alumno(str(alumno_row["Matrícula"]), str(alumno_row["Ciclo Escolar"]))
    if hist.empty:
        st.caption("Sin registros previos.")
    else:
        st.dataframe(hist, use_container_width=True, hide_index=True)

with tab_historial:
    ok, msg = verificar_conexion()
    if not ok:
        st.error(msg)
        st.stop()

    ciclos = ["(Todos)"] + sorted(estado["Ciclo Escolar"].dropna().unique().tolist())
    hf1, hf2 = st.columns(2)
    filtro_ciclo = hf1.selectbox("Ciclo escolar", ciclos, key="hist_ciclo")
    filtro_rol = hf2.selectbox("Rol", ["(Todos)"] + ROLES, key="hist_rol")

    ciclo_param = None if filtro_ciclo == "(Todos)" else filtro_ciclo
    rol_param = None if filtro_rol == "(Todos)" else filtro_rol

    todos = listar_seguimientos(ciclo_escolar=ciclo_param, rol=rol_param)
    if todos.empty:
        st.info("Aún no hay registros en la bitácora.")
    else:
        st.dataframe(todos, use_container_width=True, hide_index=True)
        st.caption(f"{len(todos)} registros mostrados (máx. 200 más recientes).")

if tab_usuarios is not None:
    with tab_usuarios:
        _tab_usuarios(usuario)
