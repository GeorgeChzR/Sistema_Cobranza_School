"""Variables de entorno: Streamlit Secrets (Cloud) o archivo .env (local)."""

from __future__ import annotations

import os
from functools import lru_cache

from .paths import raiz_instalacion

_dotenv_cargado = False


def _cargar_dotenv() -> None:
    global _dotenv_cargado
    if _dotenv_cargado:
        return
    _dotenv_cargado = True
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = raiz_instalacion() / ".env"
    if env_path.exists():
        load_dotenv(env_path)


@lru_cache(maxsize=1)
def _secrets_streamlit() -> dict[str, str]:
    try:
        import streamlit as st

        return {str(k): str(v) for k, v in st.secrets.items()}
    except Exception:
        return {}


def obtener_env(nombre: str, default: str = "") -> str:
    """Lee una variable: primero Streamlit Secrets, luego .env / entorno."""

    valor = _secrets_streamlit().get(nombre, "").strip()
    if valor:
        return valor
    _cargar_dotenv()
    return os.getenv(nombre, default).strip()


def origen_configuracion() -> str:
    if _secrets_streamlit():
        return "streamlit_secrets"
    env_path = raiz_instalacion() / ".env"
    if env_path.exists():
        return "env_file"
    return "ninguno"
