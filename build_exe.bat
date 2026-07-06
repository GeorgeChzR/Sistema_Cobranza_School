@echo off
chcp 65001 >nul
echo ============================================
echo  Empaquetado Sistema de Cobranza - Meraki
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado en esta maquina.
    echo Instala Python 3.10+ para generar el ejecutable.
    pause
    exit /b 1
)

echo [1/3] Instalando dependencias...
pip install -r requirements.txt -r requirements-build.txt -q
if errorlevel 1 goto error

echo [2/3] Generando ejecutable (puede tardar varios minutos)...
python -m PyInstaller SistemaCobranza.spec --noconfirm --clean
if errorlevel 1 goto error

echo [3/3] Copiando archivos de configuracion...
set DIST=dist\SistemaCobranzaMeraki
if not exist "%DIST%\.env.example" copy ".env.example" "%DIST%\" >nul
if not exist "%DIST%\config.yaml" copy "config.yaml" "%DIST%\" >nul

echo.
echo ============================================
echo  LISTO
echo ============================================
echo.
echo Carpeta del programa:
echo   %CD%\%DIST%
echo.
echo Ejecutable:
echo   %DIST%\SistemaCobranzaMeraki.exe
echo.
echo Para distribuir:
echo   1. Copia toda la carpeta %DIST% a cada computadora
echo   2. Crea o edita el archivo .env con MONGODB_URI
echo   3. Ejecuta SistemaCobranzaMeraki.exe
echo.
pause
exit /b 0

:error
echo.
echo ERROR durante el empaquetado.
pause
exit /b 1
