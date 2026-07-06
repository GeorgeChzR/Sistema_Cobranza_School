"""Carga y representación de la configuración del sistema."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


from .paths import ruta_config

RUTA_CONFIG_DEFAULT = ruta_config()


@dataclass
class Config:
    """Parámetros de negocio para el análisis de cartera."""

    dia_vencimiento_default: int = 10
    amarillo_min: int = 1
    amarillo_max: int = 30
    naranja_min: int = 31
    naranja_max: int = 60
    rojo_min: int = 61
    responsables: Dict[str, str] = field(default_factory=dict)
    acciones: Dict[str, str] = field(default_factory=dict)
    escalamiento: Dict[str, int] = field(default_factory=dict)
    conceptos_incluidos: List[str] = field(default_factory=list)
    metodo_aplicacion_pagos: str = "fifo"

    def responsable(self, color: str) -> str:
        return self.responsables.get(color, "Sin asignar")

    def accion(self, color: str) -> str:
        return self.acciones.get(color, "")


def cargar_config(ruta: str | Path | None = None) -> Config:
    """Lee el archivo YAML de configuración; usa valores por defecto si falta."""

    ruta = Path(ruta) if ruta else RUTA_CONFIG_DEFAULT
    if yaml is None or not ruta.exists():
        return Config(
            responsables={
                "Verde": "Asistente Administrativa",
                "Amarillo": "Asistente Administrativa",
                "Naranja": "Directora del Plantel",
                "Rojo": "Administración General",
            }
        )

    with open(ruta, "r", encoding="utf-8") as fh:
        datos = yaml.safe_load(fh) or {}

    sem = datos.get("semaforo", {})
    return Config(
        dia_vencimiento_default=datos.get("dia_vencimiento_default", 10),
        amarillo_min=sem.get("amarillo_min", 1),
        amarillo_max=sem.get("amarillo_max", 30),
        naranja_min=sem.get("naranja_min", 31),
        naranja_max=sem.get("naranja_max", 60),
        rojo_min=sem.get("rojo_min", 61),
        responsables=datos.get("responsables", {}),
        acciones=datos.get("acciones", {}),
        escalamiento=datos.get("escalamiento", {}),
        conceptos_incluidos=datos.get("conceptos_incluidos", []) or [],
        metodo_aplicacion_pagos=datos.get("metodo_aplicacion_pagos", "fifo"),
    )
