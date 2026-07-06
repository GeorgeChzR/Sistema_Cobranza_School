"""Gestión de usuarios del sistema de cobranza (MongoDB)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import pandas as pd

try:
    import bcrypt
except ImportError:  # pragma: no cover
    bcrypt = None  # type: ignore

from pymongo import ASCENDING

from .bitacora import ROLES
from .env_config import obtener_env
from .mongodb import coleccion, esta_configurada, verificar_conexion

ROL_ADMIN = "Administración General"
COLECCION_USUARIOS = "usuarios"


def es_admin(usuario: dict | None) -> bool:
    return bool(usuario and usuario.get("rol") == ROL_ADMIN)


def _col_usuarios():
    return coleccion(COLECCION_USUARIOS)


def _asegurar_indices() -> None:
    col = _col_usuarios()
    col.create_index([("username", ASCENDING)], unique=True)
    col.create_index([("activo", ASCENDING)])


def _hash_password(password: str) -> bytes:
    if bcrypt is None:
        raise RuntimeError("Instala bcrypt: pip install bcrypt")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def _verificar_password(password: str, password_hash: bytes) -> bool:
    if bcrypt is None or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash)
    except ValueError:
        return False


def _normalizar_username(username: str) -> str:
    return re.sub(r"\s+", "", username.strip().lower())


def _doc_publico(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "username": doc["username"],
        "nombre": doc["nombre"],
        "rol": doc["rol"],
        "activo": doc.get("activo", True),
        "creado_en": doc.get("creado_en"),
        "actualizado_en": doc.get("actualizado_en"),
    }


def inicializar_usuarios() -> None:
    """Crea índices y, si no hay usuarios, el administrador desde variables de entorno."""

    if not esta_configurada():
        return

    _asegurar_indices()
    if _col_usuarios().count_documents({}) > 0:
        return

    username = obtener_env("ADMIN_USUARIO")
    nombre = obtener_env("ADMIN_NOMBRE", "Administrador")
    password = obtener_env("ADMIN_PASSWORD")

    if not username or not password:
        return

    crear_usuario(
        username=username,
        nombre=nombre,
        rol=ROL_ADMIN,
        password=password,
        creado_por="sistema",
    )


def autenticar(username: str, password: str) -> dict | None:
    """Valida credenciales. Devuelve el usuario (sin contraseña) o None."""

    if not esta_configurada():
        return None

    inicializar_usuarios()
    user = _normalizar_username(username)
    doc = _col_usuarios().find_one({"username": user, "activo": True})
    if not doc:
        return None
    if not _verificar_password(password, doc.get("password_hash", b"")):
        return None
    return _doc_publico(doc)


def listar_usuarios() -> pd.DataFrame:
    if not esta_configurada():
        return pd.DataFrame()

    filas = []
    for doc in _col_usuarios().find().sort("nombre", ASCENDING):
        filas.append(
            {
                "Usuario": doc["username"],
                "Nombre": doc["nombre"],
                "Rol": doc["rol"],
                "Activo": "Sí" if doc.get("activo", True) else "No",
                "id": str(doc["_id"]),
            }
        )
    return pd.DataFrame(filas)


def crear_usuario(
    *,
    username: str,
    nombre: str,
    rol: str,
    password: str,
    creado_por: str,
) -> str:
    user = _normalizar_username(username)
    nombre = nombre.strip()
    if not user:
        raise ValueError("El usuario es obligatorio.")
    if len(password) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres.")
    if rol not in ROLES:
        raise ValueError(f"Rol inválido. Opciones: {', '.join(ROLES)}")

    if _col_usuarios().find_one({"username": user}):
        raise ValueError(f"El usuario '{user}' ya existe.")

    ahora = datetime.utcnow()
    doc = {
        "username": user,
        "nombre": nombre,
        "rol": rol,
        "password_hash": _hash_password(password),
        "activo": True,
        "creado_en": ahora,
        "actualizado_en": ahora,
        "creado_por": creado_por,
        "actualizado_por": creado_por,
    }
    res = _col_usuarios().insert_one(doc)
    return str(res.inserted_id)


def actualizar_usuario(
    *,
    user_id: str,
    nombre: str | None = None,
    rol: str | None = None,
    activo: bool | None = None,
    password: str | None = None,
    actualizado_por: str,
) -> None:
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        oid = ObjectId(user_id)
    except (InvalidId, TypeError) as exc:
        raise ValueError("Usuario no válido.") from exc

    doc = _col_usuarios().find_one({"_id": oid})
    if not doc:
        raise ValueError("Usuario no encontrado.")

    if doc.get("rol") == ROL_ADMIN and activo is False:
        otros_admin = _col_usuarios().count_documents(
            {"rol": ROL_ADMIN, "activo": True, "_id": {"$ne": oid}}
        )
        if otros_admin == 0:
            raise ValueError("Debe existir al menos un administrador activo.")

    actualizacion: dict[str, Any] = {
        "actualizado_en": datetime.utcnow(),
        "actualizado_por": actualizado_por,
    }
    if nombre is not None:
        actualizacion["nombre"] = nombre.strip()
    if rol is not None:
        if rol not in ROLES:
            raise ValueError(f"Rol inválido. Opciones: {', '.join(ROLES)}")
        if doc.get("rol") == ROL_ADMIN and rol != ROL_ADMIN:
            otros_admin = _col_usuarios().count_documents(
                {"rol": ROL_ADMIN, "activo": True, "_id": {"$ne": oid}}
            )
            if otros_admin == 0:
                raise ValueError("No puedes quitar el rol de administrador al único admin activo.")
        actualizacion["rol"] = rol
    if activo is not None:
        actualizacion["activo"] = activo
    if password:
        if len(password) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres.")
        actualizacion["password_hash"] = _hash_password(password)

    _col_usuarios().update_one({"_id": oid}, {"$set": actualizacion})


def obtener_usuario_por_id(user_id: str) -> dict | None:
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        doc = _col_usuarios().find_one({"_id": ObjectId(user_id)})
    except (InvalidId, TypeError):
        return None
    return _doc_publico(doc) if doc else None
