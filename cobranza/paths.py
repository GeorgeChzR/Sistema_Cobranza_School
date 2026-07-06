"""Rutas del proyecto compatibles con ejecución normal y .exe (PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def raiz_instalacion() -> Path:
    """Carpeta donde vive el .exe o la raíz del proyecto (datos editables: .env)."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def raiz_recurso() -> Path:
    """Carpeta de solo lectura con archivos empaquetados dentro del ejecutable."""

    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def ruta_recurso(nombre: str) -> Path:
    return raiz_recurso() / nombre


def ruta_config() -> Path:
    """config.yaml junto al .exe (editable) o el empaquetado por defecto."""

    local = raiz_instalacion() / "config.yaml"
    if local.exists():
        return local
    return ruta_recurso("config.yaml")
