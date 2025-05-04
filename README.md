# Jarvis-Core: Local AI Agent

This project aims to build a local AI assistant inspired by Jarvis, running primarily on Windows but with considerations for cross-platform compatibility, featuring a graphical chat interface, offline capabilities, and configurable conversation history storage.

## Features

*   **Conversational AI:** Uses a local LLM (default: `Meta-Llama-3-8B-Instruct.Q4_K_M.gguf`, path configurable via settings or `MODEL_DIR` environment variable). Includes performance optimizations like memory-mapped loading and optional CPU thread pinning.
*   **Offline Capabilities:** Integrated offline Speech-to-Text (STT) using Vosk and Text-to-Speech (TTS) using Piper TTS.
*   **Graphical Interface:** Chat window built with CustomTkinter, including microphone button for STT input and speaker icon for TTS output toggle.
*   **Modular Skills:** Dynamically loaded skills allow easy extension. Current skills include:
    *   `open_application`: Launches applications (cross-platform aware, input validated).
    *   `file_ops`: Copies and deletes files within a secure base directory (`~/.jarvis-core-files` by default, configurable via `JARVIS_SAFE_DIR` env var).
    *   `clipboard`: Reads from and writes to the system clipboard.
    *   `web_search`: Performs web searches using the agent's environment tools.
    *   `calculator`: Safely evaluates mathematical expressions.
    *   `system_info`: Gets the current date/time and basic system load (CPU/Memory).
*   **Storage:** Configurable between local file storage (default: `~/.jarvis-core/history/jarvis_chat_history.json`, custom path configurable) and Google Drive sync (`Jarvis-Core History/jarvis_chat_history.json` on Drive) via an in-app settings panel.
*   **Configuration:** Settings UI (⚙️) allows configuring storage mode/path, LLM model path, and system prompt path. Settings and resource files are located reliably whether running from source or a packaged executable using a resource path utility.
*   **Security:** Uses JSON for storing Google Drive authentication tokens, includes credential and model path validation, input validation for relevant skills, and dependency security checks (`pip-audit` performed during development).
*   **Platform:** Windows (primary focus), macOS & Linux (basic compatibility for core features).
*   **Deployment:** Includes a PyInstaller spec file (`jarvis-core.spec`) for creating a standalone executable (Note: Large models need separate handling).

## Setup

1.  **Clone/Download:** Get the project files into a directory (e.g., `C:\Jarvis-Core` or `~/jarvis-core`).
2.  **Environment:** Ensure Python 3.10+ is installed.
3.  **Dependencies:** Install required Python packages. Open a terminal or command prompt, navigate to the project directory (`jarvis-core`), and run:
    ```bash
    # Recommended: Create and activate a virtual environment first
    # python -m venv venv
    # source venv/bin/activate  (Linux/macOS)
    # venv\Scripts\activate  (Windows)

    pip install -r requirements.txt
    ```
    *Note: This includes backend libraries (LangChain `0.3.1`, etc.), GUI framework (CustomTkinter), STT/TTS libraries (Vosk, Piper-TTS, SoundDevice), Google Drive API libraries, and more.*

4.  **Configuration:**
    *   **`.env` file (Backend - Optional):** Create this file in the `jarvis-core` root directory if you need to customize backend settings:
        *   `USE_GPU=1`: Set this if you have a compatible GPU and installed necessary drivers/CUDA. Otherwise, leave as `0` (default) for CPU.
        *   `GOOGLE_DRIVE_CREDENTIALS_FILE=path/to/your/credentials.json`: (Optional) Specify a custom path for your Google Drive credentials file. Paths are resolved relative to the project root if not absolute. Ensure the path is secure.
        *   `MODEL_DIR=path/to/your/models/directory`: (Optional) Specify a directory containing your LLM, STT, and TTS model files. If set, the application will look here instead of the default `models/` directory within the project.
        *   `JARVIS_SAFE_DIR=path/to/your/safe/files/directory`: (Optional) Specify a base directory for the `file_ops` skill. Defaults to `~/.jarvis-core-files`.
    *   **`config/app_paths.yaml`:** Verify or add application paths for your operating system (Windows, macOS, Linux). The `open_app` skill uses this file and platform detection to find executables.
    *   **`config/settings.json` (Storage, Model, Prompt):** This file is created automatically with defaults if it doesn't exist. You can edit it directly or use the in-app Settings panel (⚙️ button). Paths specified here are resolved relative to the project root if not absolute.
        *   `storage_mode`: `local` (default) or `google_drive`.
        *   `local_storage_path`: (Optional) Custom directory for local history. Defaults to `~/.jarvis-core/history`.
        *   `llm_model_path`: (Optional) Path to the `.gguf` LLM file. If empty, uses `MODEL_DIR` or default `models/`.
        *   `system_prompt_path`: (Optional) Path to a custom system prompt `.txt` file. Defaults to `prompts/system_prompt.txt`.
        *   `google_drive_credentials_file`: Path to Google Drive API credentials. Defaults to `credentials.json`.
        *   `google_drive_token_file`: Name for the JSON token file. Defaults to `token.json` (stored in `~/.jarvis-core`).
        *   `google_drive_folder_name`: Folder name on Google Drive. Defaults to `Jarvis-Core History`.
        *   `history_filename`: Chat history filename. Defaults to `jarvis_chat_history.json`.
    *   **Google Drive Setup (if using `google_drive` mode):**
        *   **Credentials:** Obtain OAuth 2.0 Client ID credentials (`credentials.json`) from Google Cloud Console (Desktop App type). Place it in the location specified by `google_drive_credentials_file`.
        *   **Authentication:** The first time you use Google Drive mode, authorize access via the browser flow. A token (`token.json`) will be stored in `~/.jarvis-core`.
5.  **Models:**
    *   **LLM:** The application attempts to download the default LLM (`Meta-Llama-3-8B-Instruct.Q4_K_M.gguf`, ~4.7GB) to `models/` (or `MODEL_DIR`) if not found and no custom path is set.
    *   **STT (Vosk):** You need to manually download a Vosk model (e.g., `vosk-model-small-en-us-0.15`) and place it in `models/vosk-model-small-en-us-0.15` (or configure `MODEL_DIR`). See [Vosk Models](https://alphacephei.com/vosk/models).
    *   **TTS (Piper):** You need to manually download a Piper TTS voice model (e.g., `en_US-lessac-medium.onnx` and its `.json` config file) and place them in `models/piper-tts/` (or configure `MODEL_DIR`). See [Piper Samples](https://rhasspy.github.io/piper-samples/).
    *   *(Model download logic might be added/refined in future updates for STT/TTS)*.

## Usage

Run the graphical chat interface from the `jarvis-core` directory:

```bash
python -m src.gui.main_window
```

*   Type messages or click the microphone icon (🎙️) to use STT.
*   Press Enter or click Send.
*   Toggle TTS output using the speaker icon (🔊/🔇).
*   Click the Settings button (⚙️) to configure storage, paths, and Google Drive authentication.

## Packaging (PyInstaller)

A `jarvis-core.spec` file is provided to build a standalone executable using PyInstaller:

```bash
# Navigate to the jarvis-core directory
cd /path/to/jarvis-core

# Build the executable (output in dist/Jarvis-Core)
pyinstaller jarvis-core.spec
```

**Important:** The large model files (LLM, STT, TTS) are **not** included in the bundle. You must place the required models in a `models` subdirectory next to the executable (or configure paths via `MODEL_DIR` or settings) for the packaged application to find them.

## Version Control (Git & GitHub)

This repository uses Git. Large files (`*.gguf`, `*.onnx`, Vosk models, build artifacts, `venv/`, `.env`, `credentials.json`, `token.json`, etc.) are excluded via `.gitignore`.

## Important Notes

*   **Model Downloads:** Ensure required LLM, STT, and TTS models are downloaded and placed correctly (see Setup section).
*   **Google Drive Authentication:** Requires user interaction via browser on first setup.
*   **Resource Paths:** The application uses a utility (`src/utils/resource_path.py`) to locate configuration and prompt files correctly whether run from source or bundled.

## Development Phases

*   **Phase 1-6:** Core features, GUI, Storage, Packaging, Git, Critical Fixes - **Completed**
*   **Phase 7:** STT/TTS Integration, New Skills, Security Hardening, Deployment Enhancements - **Completed**
*   **Phase 8:** Further testing, documentation refinement, potential future enhancements.

## Based On

Initial structure and concepts adapted from the user-provided blueprint (`pasted_content.txt`).

