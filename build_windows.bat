@echo off
REM Genera dist\Transcriptor.exe (ejecutar en Windows, con Python 3.9+ instalado)
cd /d "%~dp0"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
python -m unittest discover -s tests -t . || goto :error
if not exist assets\icon.ico python tools\make_icon.py || goto :error
pyinstaller --noconfirm --clean --onefile --windowed --name Transcriptor ^
  --icon assets\icon.ico --add-data "assets;assets" ^
  --collect-all imageio_ffmpeg --collect-all tkinterdnd2 --collect-data docx ^
  --collect-all pymupdf4llm --collect-binaries pymupdf ^
  --exclude-module onnxruntime --exclude-module pymupdf.layout --exclude-module pymupdf_layout ^
  main.py || goto :error
echo.
echo Listo: dist\Transcriptor.exe
goto :eof
:error
echo La compilacion fallo.
exit /b 1
