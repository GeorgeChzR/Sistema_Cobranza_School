"""Carga y normalización del archivo de Cuentas por Cobrar (csv o xlsx).

El archivo de origen usa convenciones locales (México):
- Separador de columnas: ";"
- Moneda: "$3.300,00"  (punto como separador de miles, coma como decimal)
- Fechas: DD/MM/YYYY
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNAS_MONETARIAS = [
    "Subtotal",
    "Recargos",
    "Descuentos",
    "Cargo",
    "Abono",
    "Donativo",
    "Comisiones",
    "Pago Total",
    "Saldo",
]

MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_RE_PERIODO = re.compile(r"([a-záéíóúñ]+)\s*-\s*(\d{4})", re.IGNORECASE)


def _parse_moneda(serie: pd.Series) -> pd.Series:
    """Convierte '$3.300,00' -> 3300.00 de forma vectorizada."""

    texto = (
        serie.astype(str)
        .str.replace(r"[$\s]", "", regex=True)
        .str.replace(".", "", regex=False)  # separador de miles
        .str.replace(",", ".", regex=False)  # separador decimal
    )
    texto = texto.replace({"": np.nan, "nan": np.nan, "None": np.nan})
    return pd.to_numeric(texto, errors="coerce").fillna(0.0)


def _leer_archivo(ruta: Path) -> pd.DataFrame:
    ext = ruta.suffix.lower()
    if ext in (".xlsx", ".xls", ".xlsm"):
        return pd.read_excel(ruta, dtype=str)
    # csv / txt
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(ruta, sep=";", dtype=str, encoding=encoding)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise ValueError(f"No fue posible leer el archivo: {ruta}")


def _periodo_desde_documento(documento: str) -> tuple[int | None, int | None]:
    """Extrae (mes, año) de textos como 'septiembre - 2025'."""

    if not isinstance(documento, str):
        return None, None
    m = _RE_PERIODO.search(documento.strip().lower())
    if not m:
        return None, None
    mes = MESES.get(m.group(1))
    anio = int(m.group(2))
    return mes, anio


def cargar_movimientos(ruta: str | Path) -> pd.DataFrame:
    """Devuelve un DataFrame normalizado con los movimientos de cartera.

    Columnas relevantes agregadas:
    - importe_cargo / importe_abono / importe_saldo (float)
    - fecha_mov (datetime)
    - periodo_mes / periodo_anio (del concepto/documento)
    - fecha_vencimiento (datetime, corregida con el periodo del documento)
    - es_cargo / es_abono / cancelado (bool)
    """

    ruta = Path(ruta)
    df = _leer_archivo(ruta)
    df.columns = [str(c).strip() for c in df.columns]

    # Montos
    for col in COLUMNAS_MONETARIAS:
        if col in df.columns:
            df[f"importe_{_slug(col)}"] = _parse_moneda(df[col])

    # Fechas de movimiento
    df["fecha_mov"] = pd.to_datetime(
        df.get("Fecha"), dayfirst=True, errors="coerce"
    )

    # Periodo (mes/año) a partir del Documento
    periodos = df.get("Documento", pd.Series([""] * len(df))).apply(
        _periodo_desde_documento
    )
    df["periodo_mes"] = periodos.apply(lambda t: t[0])
    df["periodo_anio"] = periodos.apply(lambda t: t[1])

    # Día de vencimiento tal cual viene en el archivo (puede traer año erróneo)
    venc_original = pd.to_datetime(
        df.get("Fecha Vencimiento"), dayfirst=True, errors="coerce"
    )
    df["fecha_vencimiento_original"] = venc_original

    # Banderas
    mov = df.get("Movimiento", pd.Series([""] * len(df))).astype(str).str.strip().str.lower()
    df["es_cargo"] = mov.eq("cargo")
    df["es_abono"] = mov.eq("abono")

    cancel = df.get("Cancelado", pd.Series([""] * len(df))).astype(str).str.strip().str.upper()
    df["cancelado"] = cancel.isin(["VERDADERO", "TRUE", "SI", "SÍ", "1"])

    df["fecha_vencimiento"] = df.apply(
        lambda r: _vencimiento_corregido(r, venc_original), axis=1
    )
    # Respaldo: algunos xlsx traen vencimiento vacío o ilegible
    sin_venc = df["fecha_vencimiento"].isna()
    df.loc[sin_venc, "fecha_vencimiento"] = df.loc[sin_venc, "fecha_mov"]

    return df


def _vencimiento_corregido(fila, venc_original: pd.Series) -> pd.Timestamp:
    """Reconstruye el vencimiento usando el periodo del documento.

    El archivo real trae años de vencimiento inconsistentes (ej. una
    colegiatura de septiembre-2025 con vencimiento en 2026). Cuando existe el
    periodo del documento, reconstruimos la fecha usando ese mes/año y el día
    original de vencimiento; así el cálculo de atraso es confiable.
    """

    dia = 10
    v = venc_original.get(fila.name) if hasattr(venc_original, "get") else None
    if pd.notna(v):
        dia = v.day

    mes = fila.get("periodo_mes")
    anio = fila.get("periodo_anio")
    if mes and anio:
        try:
            return pd.Timestamp(year=int(anio), month=int(mes), day=min(dia, 28))
        except (ValueError, TypeError):
            pass

    # Sin periodo: usar la fecha original o la del movimiento
    if pd.notna(v):
        return v
    return fila.get("fecha_mov")


def _slug(nombre: str) -> str:
    return (
        nombre.lower()
        .replace(" ", "_")
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )
