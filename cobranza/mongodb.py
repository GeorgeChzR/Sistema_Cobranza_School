"""Conexión compartida a MongoDB Atlas."""

from __future__ import annotations

from functools import lru_cache

try:
    from pymongo import MongoClient
    from pymongo.collection import Collection
    from pymongo.database import Database
except ImportError:  # pragma: no cover
    MongoClient = None  # type: ignore
    Collection = None  # type: ignore
    Database = None  # type: ignore

from .env_config import obtener_env, origen_configuracion
from .paths import raiz_instalacion

ENV_PATH = raiz_instalacion() / ".env"
DB_NAME_DEFAULT = "meraki_cobranza"


def _cargar_env() -> None:
    """Compatibilidad: fuerza lectura de secrets / .env."""
    obtener_env("MONGODB_URI")


def uri_mongodb() -> str | None:
    uri = obtener_env("MONGODB_URI")
    return uri or None


def esta_configurada() -> bool:
    return uri_mongodb() is not None and MongoClient is not None


def mensaje_configuracion() -> str:
    if MongoClient is None:
        return "Instala la dependencia: `pip install pymongo python-dotenv bcrypt`"
    if not uri_mongodb():
        if origen_configuracion() == "streamlit_secrets":
            return "Falta `MONGODB_URI` en los Secrets de Streamlit Cloud."
        return (
            "Configura MongoDB de una de estas formas:\n\n"
            "• **Streamlit Cloud:** App settings → Secrets (ver `.streamlit/secrets.toml.example`)\n"
            "• **Local:** archivo `.env` en la raíz con:\n\n"
            "`MONGODB_URI=mongodb+srv://usuario:contraseña@cluster.mongodb.net/`"
        )
    return ""


@lru_cache(maxsize=1)
def cliente() -> MongoClient:
    if MongoClient is None:
        raise RuntimeError("pymongo no está instalado.")
    uri = uri_mongodb()
    if not uri:
        raise RuntimeError("MONGODB_URI no configurada.")
    return MongoClient(uri, serverSelectionTimeoutMS=8000)


def base_de_datos() -> Database:
    nombre = obtener_env("MONGODB_DB", DB_NAME_DEFAULT)
    return cliente()[nombre]


def coleccion(nombre: str) -> Collection:
    return base_de_datos()[nombre]


def verificar_conexion() -> tuple[bool, str]:
    if not esta_configurada():
        return False, mensaje_configuracion()
    try:
        cliente().admin.command("ping")
        return True, "Conectado a MongoDB."
    except Exception as exc:  # pragma: no cover
        return False, f"Error de conexión: {exc}"
