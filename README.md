# Transcriptor de video

App de escritorio: el usuario elige un video y obtiene la transcripción en **Word (.docx)** o **texto (.txt)**. Usa la API de OpenAI para transcribir y FFmpeg (incluido en el ejecutable) para extraer el audio.

**Formatos de entrada:** MP4, MOV, MKV, AVI, WEBM, WMV, FLV, M4V, MPEG, 3GP, TS/MTS y audio (MP3, WAV, M4A, AAC, OGG, FLAC, OPUS, WMA).

## Uso rápido (desarrollo)

Requiere Python 3.9 o superior.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

La primera vez, pulsa **Configuración** y pega tu API key de OpenAI (https://platform.openai.com/api-keys). La cuenta necesita saldo cargado.

También puedes usar un archivo `.env` (útil en desarrollo y con la CLI):

```bash
cp .env.template .env   # Windows: copy .env.template .env
# edita .env y completa OPENAI_API_KEY
```

La app busca `.env` en la carpeta actual y luego junto al ejecutable o en la raíz del proyecto. Prioridad: opción de la CLI > Configuración guardada > variables de entorno reales > `.env` > valores por defecto. El `.env` está en `.gitignore` y los scripts de compilación no lo incluyen en el ejecutable.

En Linux, tkinter puede no venir instalado: `sudo apt install python3-tk`.

Línea de comandos (útil para pruebas y automatización):

```bash
python -m app.cli mi_video.mov --formato txt --idioma es
python -m app.cli mi_video.mov --contexto "Reunión de producto; temas: Figma, KPI" --revisar
```

### Costo de cada transcripción

Al terminar, la ventana muestra el costo estimado desglosado (transcripción por minutos de audio; revisión y flashcards por tokens usados), el total y el acumulado en ese equipo (se puede reiniciar). La CLI lo imprime al final.

Los precios por defecto vienen de comparadores de terceros (nov. 2026), no de OpenAI: `gpt-transcribe` $0.0045/min y `gpt-5.4-mini` $0.75 / $4.50 por millón de tokens de entrada / salida. Ajústalos en **Configuración → Precios** según https://openai.com/api/pricing. El cobro real está en https://platform.openai.com/usage.

### Flashcards para Anki

Marca **Crear flashcards para estudiar en Anki** y, junto a la transcripción, se guarda `video_flashcards_anki.csv` con tarjetas de pregunta y respuesta cortas (una idea por tarjeta, solo con información del material).

Al marcarla aparece **Material para las flashcards**:

- **Usar también el contenido del video**: marcado por defecto. Desmárcalo para que las tarjetas salgan solo de los documentos (la transcripción se guarda igual).
- **Documentos**: PDF, Word (.docx), Markdown o texto. Se arrastran a su propio recuadro (o clic para elegirlos). Se convierten a Markdown (títulos, listas y tablas) antes de enviarlos a la IA. Los PDF escaneados (sin texto seleccionable) y los Word antiguos (.doc) no se admiten: se avisa y se omiten.
- **Resultados de aprendizaje**: uno por línea. Las flashcards se crean a partir de ellos: cada tarjeta ayuda a lograr alguno, con la información del material, y se omite lo que no se relaciona. Si se deja vacío, se cubren las ideas principales.
- **Sin video**: quita el video (botón ✕) y deja solo documentos. El botón cambia a «Crear flashcards» y se guarda `documento_flashcards_anki.csv`, sin costo de transcripción.

La cantidad crece con el material: cerca de una tarjeta cada 250 palabras (transcripción + documentos), entre 5 y 80, con un mínimo de 2 por resultado de aprendizaje. El modelo puede crear menos si el contenido no da para más.

El archivo es un CSV de dos columnas (pregunta, respuesta) en UTF-8, sin líneas de metadatos, así que también se abre bien en Excel. Para importarlas: en Anki, **Archivo → Importar…**, elige el archivo, el mazo de destino, separador «Coma» y tipo de nota «Básico». Desde la CLI: `--flashcards`, `--documento RUTA` (se puede repetir; el video pasa a ser opcional) y `--resultados "…"`.

### Contexto del tema

En el campo **Contexto** puedes escribir de qué trata la grabación: nombres, empresas, siglas o términos técnicos. Se usa de dos formas:

1. **Siempre (sin costo extra):** se envía al motor de transcripción como pista de vocabulario, para que escriba bien nombres y términos.
2. **Opcional, «Revisar el texto con IA»:** al terminar, un modelo de chat (`gpt-5.4-mini` por defecto; se cambia en **Configuración**) corrige palabras mal entendidas usando el contexto. No resume ni reescribe, conserva las marcas de tiempo y descarta cambios sospechosos. Si la revisión falla, se guarda la transcripción sin revisar y se avisa. El archivo final indica el contexto usado y si se revisó con IA.

## Compartir la app con otras personas

**Opción recomendada: el ejecutable.** La persona descarga un solo archivo y le hace doble clic. No necesita Python ni instalar nada.

1. Genera `dist\Transcriptor.exe` con `build_windows.bat` (y la versión de Mac con `build_mac_linux.sh` en una Mac).
2. Súbelo a un lugar desde donde se pueda descargar: GitHub Releases, Google Drive, SharePoint…
3. La persona lo descarga, le hace doble clic, pulsa **Configuración** y pega su API key de OpenAI.

**Opción con el código:** si la persona descarga la carpeta completa, solo tiene que hacer doble clic en `Iniciar Transcriptor.bat` (Windows) o `Iniciar Transcriptor.command` (macOS). La primera vez prepara todo en unos minutos; después abre directo. Esta opción sí requiere tener Python instalado.

El icono está en `assets/` y se genera con `python tools/make_icon.py`.

## Generar el ejecutable

PyInstaller no compila de forma cruzada: genera el `.exe` en Windows y la `.app` en macOS.

- **Windows:** doble clic en `build_windows.bat` → `dist\Transcriptor.exe`
- **macOS / Linux:** `./build_mac_linux.sh` → `dist/`

Los scripts crean el entorno virtual, instalan dependencias, corren las pruebas y compilan. El resultado es un único archivo que incluye Python, FFmpeg y las librerías, así que el usuario final no instala nada.

Notas:
- `--onefile` arranca unos segundos más lento porque se descomprime al abrir. Si prefieres arranque rápido, cambia a `--onedir` y distribuye la carpeta.
- Sin firma de código, Windows SmartScreen y macOS Gatekeeper mostrarán una advertencia. Para distribución amplia hace falta un certificado de firma (y notarización en macOS).

## Arquitectura

```
main.py                         Punto de entrada (ventana)
app/
├── config.py                   Configuración persistente (API key, modelo, preferencias)
├── cli.py                      Interfaz de línea de comandos
├── core/
│   ├── models.py               Segment, Transcript, ExportOptions
│   ├── errors.py               Errores con mensajes para el usuario
│   └── pipeline.py             Orquestador: video → audio → partes → texto → archivo
├── media/
│   └── ffmpeg.py               Lectura, extracción de audio y división en partes
├── transcription/
│   ├── base.py                 Contrato Transcriber (cualquier motor)
│   ├── openai_provider.py      Implementación con OpenAI
│   └── __init__.py             Fábrica: elige el motor según la configuración
├── exporters/
│   ├── base.py                 Contrato Exporter (cualquier formato)
│   ├── formatting.py           Encabezado, marcas de tiempo, párrafos
│   ├── txt_exporter.py
│   ├── docx_exporter.py
│   └── __init__.py             Registro de formatos
└── ui/
    ├── main_window.py          Ventana principal (tkinter, hilo de trabajo + cola)
    └── settings_dialog.py      Ventana de configuración
tests/                          Pruebas con videos sintéticos y un motor falso
```

**Flujo:**

1. La UI llama al pipeline en un hilo aparte.
2. El pipeline valida el archivo y extrae el audio a MP3 mono de 16 kHz y 32 kbps (unos 14 MB por hora).
3. Si el audio supera el límite del motor (24 MB para OpenAI, unos 100 minutos), lo divide en partes y pasa el final de cada parte como contexto a la siguiente.
4. Une los textos, corrige los tiempos de cada parte y exporta.

**Reglas de dependencia:** `ui` y `cli` dependen de `core`; `core` depende de los contratos de `media`, `transcription` y `exporters`; ningún módulo depende de `ui`. Así el mismo núcleo sirve para la ventana, la línea de comandos o, más adelante, una versión web.

### Cómo extender

- **Nuevo formato de salida (PDF, SRT, Markdown):** crea una clase que herede de `Exporter` en `app/exporters/` y añádela a `_ALL` en `app/exporters/__init__.py`. Aparece sola en la ventana y en la CLI.
- **Nuevo motor (AssemblyAI, Deepgram, Whisper local):** crea una clase que herede de `Transcriber` y regístrala en `create_transcriber`. Ajusta `max_file_bytes` al límite de ese motor.
- **Resumen con GPT:** añade un paso opcional en el pipeline después de unir los textos y un campo `summary` en `Transcript` que los exportadores muestren si existe.

## Costos

OpenAI cobra por minuto de audio. Como referencia, `gpt-transcribe` costaba unos $0,0045/min (≈ $0,27 por hora) en noviembre de 2026, según comparadores de terceros. Confírmalo en la página de precios de OpenAI. El modelo se cambia en **Configuración** sin tocar código.

## Seguridad de la API key

- La key se guarda en texto plano en la carpeta de configuración del usuario (en macOS y Linux, con permisos solo para ese usuario). La ruta exacta aparece en la ventana de Configuración.
- **No incluyas tu propia key dentro del ejecutable** si lo vas a distribuir: cualquiera podría extraerla y gastar tu saldo. Cada usuario debe poner la suya. Si quieres que los usuarios no necesiten key, hace falta un pequeño servidor propio que haga de intermediario.
- El video nunca sale del equipo; solo se envía a OpenAI el audio extraído.

## Limitaciones conocidas

- **Marcas de tiempo:** la app pide tiempos por segmento (`verbose_json`). Si el modelo no los ofrece, la app lo detecta y genera párrafos sin tiempos automáticamente. No pude confirmar en la documentación oficial si `gpt-transcribe` los devuelve; con `whisper-1` sí, pero ese modelo se retira el 26/02/2027.
- **Videos largos:** el corte entre partes es por tiempo y puede partir una palabra. El contexto que se pasa a la parte siguiente reduce, pero no elimina, este efecto.
- **Cancelar** detiene el proceso al terminar el paso en curso; no interrumpe una parte que ya se está enviando.
- **Revisión humana:** los modelos de transcripción pueden inventar frases en silencios o con mucho ruido. Para usos legales o médicos, revisa siempre el resultado.
- **Arrastrar y soltar:** puedes soltar un video o audio sobre la ventana (usa `tkinterdnd2`). Si sueltas varios, se toma el primero compatible. Si la librería no carga en tu sistema, la app funciona igual con el botón **Elegir…**.

## Pruebas

```bash
python -m unittest discover -s tests -t . -v
```

Las pruebas generan videos sintéticos con FFmpeg y usan un motor de transcripción falso, así que no consumen saldo de OpenAI.
