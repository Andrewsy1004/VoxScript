@echo off
REM Abre Transcriptor desde el código fuente (Windows).
REM La primera vez prepara el entorno (unos minutos); después abre directo.
cd /d "%~dp0"

if exist .venv\Scripts\pythonw.exe if exist .venv\.instalado goto :abrir

where python >nul 2>nul
if errorlevel 1 (
  echo No se encontro Python.
  echo Instalalo desde https://www.python.org/downloads/ marcando "Add python.exe to PATH"
  echo y vuelve a abrir este archivo.
  pause
  exit /b 1
)

echo Preparando Transcriptor por primera vez. Esto tarda unos minutos...
if not exist .venv python -m venv .venv || goto :error
.venv\Scripts\python.exe -m pip install --upgrade pip >nul
.venv\Scripts\python.exe -m pip install -r requirements.txt || goto :error
echo ok> .venv\.instalado

:abrir
start "" .venv\Scripts\pythonw.exe main.py
exit /b 0

:error
echo.
echo No se pudo preparar Transcriptor. Revisa tu conexion a internet y vuelve a intentarlo.
pause
exit /b 1
