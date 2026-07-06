"""Bitácora de gestión de cobranza en MongoDB.

Registra avisos, medios de contacto, resultados y observaciones conforme a la
política MTI-PRO-ADM-2026-003 (sección 6: bitácora obligatoria).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
from pymongo import ASCENDING

from .env_config import obtener_env
from .mongodb import (
    coleccion,
    esta_configurada,
    mensaje_configuracion,
    verificar_conexion as _ping_mongodb,
)

ROLES = [
    "Asistente Administrativa",
    "Directora del Plantel",
    "Administración General",
]

MEDIOS = [
    "Llamada telefónica",
    "WhatsApp",
    "Correo electrónico",
    "Citatorio presencial",
    "Otro",
]

RESULTADOS = [
    "Contactó — acuerdo verbal",
    "Contactó — prometió pagar",
    "No contestó",
    "Buzón / número incorrecto",
    "Canalizar a Directora",
    "Canalizar a Administración",
    "Pago reportado (pendiente validar)",
    "Otro",
]

COLLECTION_DEFAULT = "bitacora_seguimientos"


def _coleccion_bitacora():
    col_name = obtener_env("MONGODB_COLLECTION", COLLECTION_DEFAULT)
    return coleccion(col_name)


def verificar_conexion() -> tuple[bool, str]:
    ok, msg = _ping_mongodb()
    if ok:
        _asegurar_indices()
    return ok, msg


def _asegurar_indices() -> None:
    col = _coleccion_bitacora()
    col.create_index(
        [("matricula", ASCENDING), ("ciclo_escolar", ASCENDING), ("fecha_aviso", ASCENDING)]
    )
    col.create_index([("fecha_registro", ASCENDING)])


def _clave_matricula(val) -> str:
    return str(val).strip()


def registrar_seguimiento(
    *,
    matricula: str,
    alumno: str,
    ciclo_escolar: str,
    fecha_aviso: date,
    registrado_por: str,
    rol: str,
    semaforo: str,
    aviso_realizado: bool,
    medio: str,
    resultado: str,
    compromiso_pago: date | None = None,
    observaciones: str = "",
    saldo: float | None = None,
    saldo_vencido: float | None = None,
) -> str:
    doc = {
        "matricula": _clave_matricula(matricula),
        "alumno": str(alumno).strip(),
        "ciclo_escolar": str(ciclo_escolar).strip(),
        "fecha_aviso": datetime.combine(fecha_aviso, datetime.min.time()),
        "fecha_registro": datetime.utcnow(),
        "registrado_por": registrado_por.strip(),
        "rol": rol,
        "semaforo": semaforo,
        "aviso_realizado": aviso_realizado,
        "medio": medio,
        "resultado": resultado,
        "compromiso_pago": (
            datetime.combine(compromiso_pago, datetime.min.time())
            if compromiso_pago
            else None
        ),
        "observaciones": observaciones.strip(),
        "saldo_al_momento": saldo,
        "saldo_vencido_al_momento": saldo_vencido,
    }
    res = _coleccion_bitacora().insert_one(doc)
    return str(res.inserted_id)


def historial_alumno(matricula: str, ciclo_escolar: str, limite: int = 50) -> pd.DataFrame:
    if not esta_configurada():
        return pd.DataFrame()

    cursor = (
        _coleccion_bitacora()
        .find(
            {
                "matricula": _clave_matricula(matricula),
                "ciclo_escolar": str(ciclo_escolar).strip(),
            }
        )
        .sort("fecha_aviso", -1)
        .limit(limite)
    )
    return pd.DataFrame([_doc_a_fila(d) for d in cursor])


def listar_seguimientos(
    *,
    ciclo_escolar: str | None = None,
    rol: str | None = None,
    limite: int = 200,
) -> pd.DataFrame:
    if not esta_configurada():
        return pd.DataFrame()

    filtro: dict[str, Any] = {}
    if ciclo_escolar:
        filtro["ciclo_escolar"] = ciclo_escolar
    if rol:
        filtro["rol"] = rol

    cursor = _coleccion_bitacora().find(filtro).sort("fecha_aviso", -1).limit(limite)
    return pd.DataFrame([_doc_a_fila(d) for d in cursor])


def resumen_por_alumnos(estado: pd.DataFrame) -> pd.DataFrame:
    cols_extra = [
        "Último Aviso",
        "Días Sin Contacto",
        "Último Medio",
        "Último Resultado",
        "Total Seguimientos",
    ]
    if estado.empty or not esta_configurada():
        for c in cols_extra:
            if c not in estado.columns:
                estado[c] = None if c != "Total Seguimientos" else 0
        return estado

    claves = [
        {
            "matricula": _clave_matricula(r["Matrícula"]),
            "ciclo_escolar": str(r["Ciclo Escolar"]).strip(),
        }
        for _, r in estado.iterrows()
    ]
    if not claves:
        return estado

    pipeline = [
        {
            "$match": {
                "$or": [
                    {"matricula": k["matricula"], "ciclo_escolar": k["ciclo_escolar"]}
                    for k in claves
                ]
            }
        },
        {"$sort": {"fecha_aviso": -1}},
        {
            "$group": {
                "_id": {"matricula": "$matricula", "ciclo": "$ciclo_escolar"},
                "ultimo_aviso": {"$first": "$fecha_aviso"},
                "ultimo_medio": {"$first": "$medio"},
                "ultimo_resultado": {"$first": "$resultado"},
                "total": {"$sum": 1},
            }
        },
    ]

    resumen: dict[tuple[str, str], dict] = {}
    for doc in _coleccion_bitacora().aggregate(pipeline):
        k = (doc["_id"]["matricula"], doc["_id"]["ciclo"])
        resumen[k] = doc

    hoy = pd.Timestamp.today().normalize()
    ultimos, dias_sin, medios, resultados, totales = [], [], [], [], []

    for _, r in estado.iterrows():
        k = (_clave_matricula(r["Matrícula"]), str(r["Ciclo Escolar"]).strip())
        info = resumen.get(k)
        if not info:
            ultimos.append(None)
            dias_sin.append(None)
            medios.append(None)
            resultados.append(None)
            totales.append(0)
            continue

        fa = pd.Timestamp(info["ultimo_aviso"]).normalize()
        ultimos.append(fa.date())
        dias_sin.append(int((hoy - fa).days))
        medios.append(info.get("ultimo_medio"))
        resultados.append(info.get("ultimo_resultado"))
        totales.append(info.get("total", 0))

    estado = estado.copy()
    estado["Último Aviso"] = ultimos
    estado["Días Sin Contacto"] = dias_sin
    estado["Último Medio"] = medios
    estado["Último Resultado"] = resultados
    estado["Total Seguimientos"] = totales
    return estado


def _doc_a_fila(doc: dict) -> dict:
    fa = doc.get("fecha_aviso")
    cp = doc.get("compromiso_pago")
    return {
        "Fecha aviso": fa.date() if isinstance(fa, datetime) else fa,
        "Matrícula": doc.get("matricula"),
        "Alumno": doc.get("alumno"),
        "Ciclo": doc.get("ciclo_escolar"),
        "Registrado por": doc.get("registrado_por"),
        "Rol": doc.get("rol"),
        "Semáforo": doc.get("semaforo"),
        "Aviso realizado": "Sí" if doc.get("aviso_realizado") else "No",
        "Medio": doc.get("medio"),
        "Resultado": doc.get("resultado"),
        "Compromiso pago": cp.date() if isinstance(cp, datetime) else cp,
        "Observaciones": doc.get("observaciones"),
        "Saldo al momento": doc.get("saldo_al_momento"),
    }
