"""Motor de análisis de cartera y semaforización por alumno.

Calcula, para cada alumno, el saldo pendiente, la antigüedad del adeudo más
antiguo y el color del semáforo conforme a la política MTI-PRO-ADM-2026-003.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd

from .config import Config, cargar_config

CLAVE_ALUMNO = ["Matrícula", "Alumno", "Ciclo Escolar"]
CAMPOS_INFO = ["Plantel", "Nivel", "Grado", "Grupo"]


def _fecha_normalizada(val) -> pd.Timestamp | None:
    """Convierte a fecha sin hora; devuelve None si el valor es inválido (NaT)."""

    if val is None:
        return None
    try:
        ts = pd.Timestamp(val)
    except (ValueError, TypeError):
        return None
    if pd.isna(ts):
        return None
    return ts.normalize()


def _vencimiento_cargo(fila) -> pd.Timestamp | None:
    """Fecha de vencimiento del cargo con respaldo en la fecha del movimiento."""

    return _fecha_normalizada(fila.get("fecha_vencimiento")) or _fecha_normalizada(
        fila.get("fecha_mov")
    )


def _color_por_atraso(dias: int, saldo: float, cfg: Config) -> str:
    if saldo <= 0.005:
        return "Verde"
    if dias <= 0:
        return "Verde"  # tiene saldo pero aún no vence (preventivo)
    if dias <= cfg.amarillo_max:
        return "Amarillo"
    if dias <= cfg.naranja_max:
        return "Naranja"
    return "Rojo"


def _clave_cuenta(val) -> str:
    """Normaliza el identificador de Cuenta por Cobrar para emparejar cargo/abono."""

    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip().replace(",", ".")
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _liquidacion_cargos(cargos: pd.DataFrame, abonos: pd.DataFrame) -> list[dict]:
    """Saldo pendiente por cargo.

    1. Abonos con la misma *Cuenta por Cobrar* (o Referencia Bancaria) se aplican
       al cargo correspondiente.
    2. Abonos sin vínculo se reparten FIFO entre cargos con saldo restante.
    """

    by_cuenta: dict[str, dict] = {}
    sin_cuenta: list[dict] = []

    for _, c in cargos.iterrows():
        cuenta = _clave_cuenta(c.get("Cuenta por Cobrar"))
        monto = float(c["importe_cargo"])
        venc = _vencimiento_cargo(c)
        ref = str(c.get("Referencia Bancaria") or "").strip()
        fila = {"cuenta": cuenta, "monto": monto, "pagado": 0.0, "venc": venc, "ref": ref}

        if cuenta:
            if cuenta not in by_cuenta:
                by_cuenta[cuenta] = {**fila, "monto": 0.0}
            by_cuenta[cuenta]["monto"] += monto
            prev = by_cuenta[cuenta]["venc"]
            if venc is not None and (prev is None or venc < prev):
                by_cuenta[cuenta]["venc"] = venc
        else:
            sin_cuenta.append(fila)

    registros = list(by_cuenta.values()) + sin_cuenta

    sin_vincular = 0.0
    for _, a in abonos.iterrows():
        monto = float(a["importe_abono"])
        cuenta = _clave_cuenta(a.get("Cuenta por Cobrar"))
        ref = str(a.get("Referencia Bancaria") or "").strip()

        destino = by_cuenta.get(cuenta) if cuenta else None
        if destino is None and ref:
            destino = next((r for r in registros if r.get("ref") == ref), None)

        if destino is not None:
            destino["pagado"] += monto
        else:
            sin_vincular += monto

    registros.sort(key=lambda r: (r["venc"] is None, r["venc"] or pd.Timestamp.max))
    restante = sin_vincular
    for r in registros:
        pend = r["monto"] - r["pagado"]
        if pend <= 0.005 or restante <= 0.005:
            continue
        aplicar = min(pend, restante)
        r["pagado"] += aplicar
        restante -= aplicar

    for r in registros:
        r["pendiente"] = round(max(r["monto"] - r["pagado"], 0.0), 2)
    return registros


def _estado_cartera(
    cargos: pd.DataFrame, abonos: pd.DataFrame, fecha_corte: pd.Timestamp
) -> tuple[int, pd.Timestamp | None, int, float]:
    """Calcula atraso y saldo vencido a partir de cargos liquidados individualmente."""

    liq = _liquidacion_cargos(cargos, abonos)
    corte = _fecha_normalizada(fecha_corte) or pd.Timestamp.today().normalize()

    pendientes = [r for r in liq if r["pendiente"] > 0.005]
    pendientes.sort(key=lambda r: (r["venc"] is None, r["venc"] or pd.Timestamp.max))

    meses_pendientes = len(pendientes)
    saldo_vencido = 0.0
    for r in pendientes:
        venc = r["venc"]
        if venc is None or venc <= corte:
            saldo_vencido += r["pendiente"]

    if not pendientes:
        return 0, None, 0, 0.0

    fecha_pendiente = pendientes[0]["venc"]
    if fecha_pendiente is None:
        return 0, None, meses_pendientes, round(saldo_vencido, 2)

    dias = (corte - fecha_pendiente).days
    return dias, fecha_pendiente, meses_pendientes, round(saldo_vencido, 2)


def analizar_cartera(
    df: pd.DataFrame,
    fecha_corte: str | date | datetime | None = None,
    cfg: Config | None = None,
) -> pd.DataFrame:
    """Genera el estado de cuenta consolidado por alumno.

    Parámetros
    ----------
    df : DataFrame normalizado por `cargar_movimientos`.
    fecha_corte : fecha de referencia para calcular atrasos (por defecto hoy).
    cfg : configuración de negocio.
    """

    cfg = cfg or cargar_config()
    if fecha_corte is None:
        fecha_corte = pd.Timestamp.today()
    fecha_corte = pd.Timestamp(fecha_corte)

    datos = df[~df["cancelado"]].copy()

    if cfg.conceptos_incluidos:
        datos = datos[datos["Concepto"].isin(cfg.conceptos_incluidos)]

    filas = []
    for clave, grupo in datos.groupby(CLAVE_ALUMNO, dropna=False):
        cargos = grupo[grupo["es_cargo"]]
        abonos = grupo[grupo["es_abono"]]
        total_cargo = float(cargos["importe_cargo"].sum())
        total_abono = float(abonos["importe_abono"].sum())
        saldo = round(total_cargo - total_abono, 2)

        dias, fecha_pend, meses_pend, saldo_vencido = _estado_cartera(
            cargos, abonos, fecha_corte
        )
        # Si ya pagó todo, no hay atraso ni saldo vencido
        if saldo <= 0.005:
            dias, fecha_pend, meses_pend, saldo_vencido = 0, None, 0, 0.0

        color = _color_por_atraso(dias, saldo, cfg)
        info = grupo.iloc[0]

        filas.append(
            {
                "Matrícula": clave[0],
                "Alumno": clave[1],
                "Ciclo Escolar": clave[2],
                "Plantel": info.get("Plantel", ""),
                "Nivel": info.get("Nivel", ""),
                "Grado": info.get("Grado", ""),
                "Grupo": info.get("Grupo", ""),
                "Total Cargos": round(total_cargo, 2),
                "Total Pagado": round(total_abono, 2),
                "Saldo": saldo,
                "Saldo Vencido": saldo_vencido,
                "Meses Pendientes": meses_pend,
                "Vencimiento Más Antiguo": (
                    fecha_pend.date() if fecha_pend is not None and pd.notna(fecha_pend) else None
                ),
                "Días Atraso": max(dias, 0),
                "Semáforo": color,
                "Responsable": cfg.responsable(color),
                "Acción Sugerida": cfg.accion(color),
                "Referencia Bancaria": _ultima_referencia(cargos),
            }
        )

    resultado = pd.DataFrame(filas)
    if resultado.empty:
        return resultado

    orden_color = {"Rojo": 0, "Naranja": 1, "Amarillo": 2, "Verde": 3}
    resultado["_orden"] = resultado["Semáforo"].map(orden_color)
    resultado = resultado.sort_values(
        ["_orden", "Días Atraso", "Saldo"], ascending=[True, False, False]
    ).drop(columns="_orden")

    return resultado.reset_index(drop=True)


def _ultima_referencia(cargos: pd.DataFrame) -> str:
    if "Referencia Bancaria" not in cargos.columns or cargos.empty:
        return ""
    pendientes = cargos.sort_values("fecha_vencimiento")
    ref = pendientes["Referencia Bancaria"].dropna()
    return str(ref.iloc[-1]) if not ref.empty else ""


def resumen_indicadores(estado: pd.DataFrame, fecha_corte=None) -> dict:
    """Indicadores mensuales (sección 11 de la política)."""

    total = len(estado)
    if total == 0:
        return {"total_alumnos": 0}

    conteo = estado["Semáforo"].value_counts().to_dict()
    saldo_por_color = estado.groupby("Semáforo")["Saldo"].sum().to_dict()

    def pct(color):
        return round(100 * conteo.get(color, 0) / total, 1)

    con_adeudo = estado[estado["Saldo"] > 0.005]
    colores_vencido = ["Amarillo", "Naranja", "Rojo"]
    alumnos_adeudo_vencido = sum(conteo.get(c, 0) for c in colores_vencido)
    pct_adeudo_vencido = round(100 * alumnos_adeudo_vencido / total, 1)
    saldo_vencido = round(
        float(
            estado.loc[estado["Semáforo"].isin(colores_vencido), "Saldo"]
            .clip(lower=0)
            .sum()
        ),
        2,
    )

    return {
        "fecha_corte": pd.Timestamp(fecha_corte).date() if fecha_corte else pd.Timestamp.today().date(),
        "total_alumnos": total,
        "alumnos_con_adeudo": len(con_adeudo),
        "alumnos_con_adeudo_vencido": alumnos_adeudo_vencido,
        "porcentaje_adeudo_vencido": pct_adeudo_vencido,
        "saldo_total": round(float(estado["Saldo"].clip(lower=0).sum()), 2),
        "saldo_vencido": saldo_vencido,
        "conteo": {c: conteo.get(c, 0) for c in ["Verde", "Amarillo", "Naranja", "Rojo"]},
        "porcentaje": {c: pct(c) for c in ["Verde", "Amarillo", "Naranja", "Rojo"]},
        "saldo_por_color": {c: round(saldo_por_color.get(c, 0.0), 2) for c in ["Verde", "Amarillo", "Naranja", "Rojo"]},
    }
