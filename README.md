<div align="center">

<img src="assets/icon.png" alt="Transcriptor icon" width="96">

# 🎙️ Transcriptor

**Turn any video or audio into a clean transcript (Word or TXT) with OpenAI.**

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![OpenAI](https://img.shields.io/badge/OpenAI-API-412991?logo=openai&logoColor=white)
![FFmpeg](https://img.shields.io/badge/FFmpeg-bundled-007808?logo=ffmpeg&logoColor=white)

</div>

---

## ✨ Features

- 📝 **Transcripts** to Word (`.docx`) or plain text (`.txt`), with timestamps.
- 🖱️ **Drag & drop** a video or audio file onto the window.
- 🧩 **Context hints** (names, acronyms, jargon) plus optional **AI review** that fixes misheard words.
- 🧠 **Anki flashcards** from the video and/or PDF, Word and Markdown documents.
- 💰 **Cost estimate** after every run, with a running total.
- 📦 **Single-file executable**: Python and FFmpeg included, nothing to install.

## 📂 Supported formats

| Type | Formats |
|------|---------|
| 🎬 Video | MP4, MOV, MKV, AVI, WEBM, WMV, FLV, M4V, MPEG, 3GP, TS/MTS |
| 🎧 Audio | MP3, WAV, M4A, AAC, OGG, FLAC, OPUS, WMA |
| 📄 Documents (flashcards) | PDF, DOCX, Markdown, TXT |

---

## 🚀 Getting Started

### 1. Create a virtual environment

Requires Python 3.9 or newer:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your OpenAI API key

Get one at [platform.openai.com/api-keys](https://platform.openai.com/api-keys) (the account needs credit). Paste it in **Configuración** (Settings) inside the app, or use a `.env` file:

```bash
cp .env.template .env   # Windows: copy .env.template .env
# then fill in OPENAI_API_KEY
```

### 4. Run the app

```bash
python main.py
```

> [!TIP]
> On Linux, tkinter may be missing: `sudo apt install python3-tk`.

<details>
<summary>⚙️ Configuration priority</summary>

CLI option > saved Settings > real environment variables > `.env` > defaults. The app looks for `.env` in the current folder, then next to the executable or in the project root. `.env` is git-ignored and never bundled into the executable.

</details>

---

## 💻 Command line

```bash
python -m app.cli my_video.mov --formato txt --idioma es
python -m app.cli my_video.mov --contexto "Product meeting; topics: Figma, KPI" --revisar
python -m app.cli --flashcards --documento notes.pdf --resultados "Explain X"
```

Key flags: `--formato`, `--idioma`, `--salida`, `--sin-tiempos`, `--contexto`, `--revisar`, `--flashcards`, `--documento` (repeatable), `--resultados`.

## 🧩 Topic context

Describe the recording in the **Contexto** field (names, companies, acronyms, technical terms):

1. **Always, free:** sent to the transcription engine as a vocabulary hint.
2. **Optional "Revisar el texto con IA":** a chat model (`gpt-5.4-mini` by default) fixes misheard words. It doesn't summarize or rewrite, keeps timestamps and discards suspicious changes. If review fails, the unreviewed transcript is saved.

## 🧠 Flashcards for Anki

Check **Crear flashcards para estudiar en Anki** to also save `video_flashcards_anki.csv` (short Q&A, one idea per card).

- **Video content:** on by default; uncheck to build cards only from documents.
- **Documents:** PDF, DOCX, Markdown or text, converted to Markdown first. Scanned PDFs and legacy `.doc` are skipped with a warning.
- **Learning outcomes:** one per line; every card supports one. Empty = main ideas.
- **No video:** remove it (✕) to work from documents only, with no transcription cost.

About 1 card per 250 words, between 5 and 80 (min. 2 per learning outcome).
**Import:** Anki → *File → Import…* → separator *Comma*, note type *Basic*. The CSV is UTF-8 and opens fine in Excel.

## 💰 Costs

| Model | Default price |
|-------|---------------|
| `gpt-transcribe` | $0.0045 / audio minute (≈ $0.27 / hour) |
| `gpt-5.4-mini` (review, flashcards) | $0.75 input / $4.50 output per 1M tokens |

> [!NOTE]
> Defaults come from third-party comparison sites (Nov 2026), not from OpenAI. Adjust them in **Configuración → Precios** using [openai.com/api/pricing](https://openai.com/api/pricing). Actual billing: [platform.openai.com/usage](https://platform.openai.com/usage).

---

## 📦 Build the executable

PyInstaller doesn't cross-compile: build the `.exe` on Windows and the `.app` on macOS.

| Platform | Command | Output |
|----------|---------|--------|
| 🪟 Windows | `build_windows.bat` | `dist\Transcriptor.exe` |
| 🍎 macOS / 🐧 Linux | `./build_mac_linux.sh` | `dist/` |

The scripts create the venv, install dependencies, run tests and build a single file. Share it via GitHub Releases, Drive or SharePoint; users double-click it and add their own API key.

No Python on the target machine? Use the executable. With the source folder, double-click `Iniciar Transcriptor.bat` (Windows) or `Iniciar Transcriptor.command` (macOS) instead; this requires Python.

> [!WARNING]
> Unsigned builds trigger Windows SmartScreen and macOS Gatekeeper warnings. Wide distribution needs a code-signing certificate (plus notarization on macOS). `--onefile` also starts a few seconds slower; switch to `--onedir` for faster startup.

## 🔐 API key security

> [!CAUTION]
> **Never embed your own key in an executable you distribute.** Anyone could extract it and spend your credit. Each user must add theirs.

- The key is stored in plain text in the user's config folder (user-only permissions on macOS/Linux). The exact path is shown in Settings.
- The video never leaves the machine; only the extracted audio is sent to OpenAI.

---

## 🏗️ Architecture

```
main.py                         Entry point (window)
app/
├── config.py                   Persistent settings (API key, model, preferences)
├── cli.py                      Command-line interface
├── core/
│   ├── models.py               Segment, Transcript, ExportOptions
│   ├── errors.py               User-facing errors
│   └── pipeline.py             Orchestrator: video → audio → chunks → text → file
├── media/ffmpeg.py             Probing, audio extraction, splitting
├── transcription/              Transcriber contract + OpenAI provider + factory
├── correction/                 AI review of the transcript
├── flashcards/                 Anki flashcard generation
├── documents/                  PDF/DOCX/Markdown to Markdown
├── exporters/                  Exporter contract, TXT, DOCX, formatting
└── ui/                         tkinter window, settings, drag & drop
tests/                          Synthetic videos + fake engine
```

**Flow**

1. The UI runs the pipeline in a background thread.
2. Audio is extracted to mono MP3, 16 kHz, 32 kbps (~14 MB/hour).
3. Above the engine limit (24 MB for OpenAI, ~100 min), audio is split; each chunk's tail is passed as context to the next.
4. Texts are merged, timestamps realigned, and the file exported.

`ui` and `cli` depend on `core`; `core` depends on the `media`, `transcription` and `exporters` contracts; nothing depends on `ui`.

<details>
<summary>🔧 How to extend</summary>

- **New output format (PDF, SRT, Markdown):** subclass `Exporter` in `app/exporters/` and add it to `_ALL` in `app/exporters/__init__.py`. It shows up in the window and CLI automatically.
- **New engine (AssemblyAI, Deepgram, local Whisper):** subclass `Transcriber`, register it in `create_transcriber` and set `max_file_bytes` to that engine's limit.
- **GPT summary:** add an optional pipeline step after merging and a `summary` field in `Transcript` for exporters to render.

</details>

## ⚠️ Known limitations

- **Timestamps:** requested via `verbose_json`; if the model doesn't return them, paragraphs are generated without times. Not confirmed in official docs for `gpt-transcribe` (`whisper-1` does, but retires 2027-02-26).
- **Long videos:** chunks are cut by time and may split a word; passed context reduces but doesn't remove this.
- **Cancel** stops after the current step, not mid-upload.
- **Human review:** models can hallucinate in silence or noise. Always review for legal or medical use.

