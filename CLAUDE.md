# Reglas internas del proyecto

## Actualizar el ejecutable después de cada cambio (obligatorio)

Siempre que se modifique cualquier archivo del código (`app/`, `main.py`, `assets/`, dependencias), al terminar:

1. Correr los tests: `.\.venv\Scripts\python.exe -m unittest discover -s tests -t .`
2. Si pasan, recompilar el ejecutable con el mismo comando de `build_windows.bat`:
   ```
   .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --windowed --name Transcriptor --icon assets\icon.ico --add-data "assets;assets" --collect-all imageio_ffmpeg --collect-all tkinterdnd2 --collect-data docx --collect-all pymupdf4llm --collect-binaries pymupdf --exclude-module onnxruntime --exclude-module pymupdf.layout --exclude-module pymupdf_layout main.py
   ```
3. Confirmar la fecha y hora nuevas de `dist\Transcriptor.exe` e informarlas al usuario.

Si la compilación falla con "Access is denied", la app está abierta. Pedir al usuario que la cierre; no cerrar el proceso a la fuerza.
Si los tests fallan, no compilar: corregir primero.
