# -*- mode: python ; coding: utf-8 -*-
"""Genera el ejecutable con: pyinstaller SistemaCobranza.spec"""

from PyInstaller.utils.hooks import collect_all

block_cipher = None

streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all("streamlit")
pandas_datas, pandas_binaries, pandas_hiddenimports = collect_all("pandas")

extra_hidden = [
    "streamlit.web.cli",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "pymongo",
    "bcrypt",
    "openpyxl",
    "yaml",
    "dotenv",
    "altair",
    "tornado",
    "watchdog",
    "PIL",
    "pyarrow",
    "cobranza",
    "cobranza.paths",
    "cobranza.mongodb",
    "cobranza.usuarios",
    "cobranza.bitacora",
    "cobranza.analisis",
    "cobranza.cargador",
    "cobranza.config",
    "cobranza.reporte",
]

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=streamlit_binaries + pandas_binaries,
    datas=[
        ("app.py", "."),
        ("config.yaml", "."),
        (".env.example", "."),
        ("cobranza", "cobranza"),
    ]
    + streamlit_datas
    + pandas_datas,
    hiddenimports=extra_hidden + streamlit_hiddenimports + pandas_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SistemaCobranzaMeraki",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SistemaCobranzaMeraki",
)
