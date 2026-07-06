"""Punto de entrada para el ejecutable de Windows.

Inicia Streamlit y abre el navegador en http://localhost:8501
"""

from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _es_ejecutable() -> bool:
    return getattr(sys, "frozen", False)


def _carpeta_instalacion() -> Path:
    if _es_ejecutable():
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def _carpeta_recurso() -> Path:
    if _es_ejecutable():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _puerto_libre(preferido: int = 8501) -> int:
    for puerto in range(preferido, preferido + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", puerto))
                return puerto
            except OSError:
                continue
    return preferido


def _preparar_entorno() -> Path:
    instalacion = _carpeta_instalacion()
    recurso = _carpeta_recurso()
    os.chdir(instalacion)

    env_local = instalacion / ".env"
    env_ejemplo = recurso / ".env.example"
    if not env_local.exists() and env_ejemplo.exists():
        shutil.copy(env_ejemplo, env_local)

    config_local = instalacion / "config.yaml"
    config_recurso = recurso / "config.yaml"
    if not config_local.exists() and config_recurso.exists():
        shutil.copy(config_recurso, config_local)

    app = recurso / "app.py"
    if not app.exists():
        app = instalacion / "app.py"
    if not app.exists():
        raise FileNotFoundError("No se encontró app.py en el paquete.")
    return app


def _abrir_navegador(puerto: int) -> None:
    time.sleep(2.0)
    webbrowser.open(f"http://localhost:{puerto}")


def main() -> None:
    app = _preparar_entorno()
    puerto = _puerto_libre()

    threading.Thread(target=_abrir_navegador, args=(puerto,), daemon=True).start()

    sys.argv = [
        "streamlit",
        "run",
        str(app),
        f"--server.port={puerto}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]

    from streamlit.web import cli as stcli

    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
