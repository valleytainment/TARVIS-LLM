# Jarvis-Core: Local AI Agent

This project aims to build a local AI assistant inspired by Jarvis, running primarily on Windows, with a graphical chat interface and configurable conversation history storage.

## Features

*   Conversational AI using a local LLM (Meta-Llama-3-8B default, configurable path and quantization).
*   Graphical chat window interface using CustomTkinter.
*   Skills: Opening applications, file operations, clipboard access (initial set).
*   Storage: Configurable between local file storage (default: `~/.jarvis-core/history/jarvis_chat_history.json`, custom path configurable) and Google Drive sync (`Jarvis-Core History/jarvis_chat_history.json` on Drive) via an in-app settings panel.
*   Configuration: Settings UI (⚙️) allows configuring storage mode/path, LLM model path, and system prompt path. Backend settings via `.env` file.
*   Performance Optimizations: Supports GPU offloading, selectable quantization levels, and memory locking (mlock) for the LLM via environment variables.
*   Platform: Windows (initial focus).

## Setup

1.  **Clone/Download:** Get the project files into a directory (e.g., `C:\Jarvis-Core`).
2.  **Environment:** Ensure Python 3.10+ is installed on Windows.
3.  **Dependencies:** Install required Python packages. Open Command Prompt or PowerShell, navigate to the project directory (`tarvis-audit`), and run:
    ```bash
    pip install -r requirements.txt
    # or python -m pip install -r requirements.txt
    ```
    *Note: This includes backend libraries (LangChain, GPT4All), GUI framework (CustomTkinter), and Google Drive API libraries.*

4.  **Configuration:**
    *   **`.env` file (Backend - Required for Optimizations):** Create this file in the `tarvis-audit` root directory to customize backend and performance settings:
        *   `USE_GPU=1`: Set to `1` to enable GPU usage. Requires compatible GPU and drivers (CUDA/ROCm). Default is `0` (CPU).
        *   `N_GPU_LAYERS=10`: (Requires `USE_GPU=1`) Number of LLM layers to offload to the GPU. Adjust based on your VRAM. `0` means no layers offloaded. Default is `0`.
        *   `LLM_QUANT_PREFERENCE=Q4_K_M`: Choose the default quantization level if no custom model path is set. Options: `Q4_0`, `Q4_K_M` (recommended balance), `Q5_K_M`, `Q8_0` (higher accuracy). Default is `Q4_K_M`.
        *   `USE_MLOCK=1`: Set to `1` to attempt locking the model in RAM (prevents swapping). Requires sufficient RAM and potentially specific system permissions. Default is `0`.
        *   `N_THREADS=8`: Number of CPU threads to use for inference. Default is `8`.
        *   `GOOGLE_DRIVE_CREDENTIALS_FILE=path/to/your/credentials.json`: (Optional) Specify a custom path for your Google Drive credentials file if it's not named `credentials.json` or not in the project root.
        *   `MODEL_DIR=path/to/your/models`: (Optional) Specify a custom directory where models are stored or downloaded. Defaults to `models/` within the project root.
    *   **`config/app_paths.yaml`:** Verify application paths match your Windows setup (e.g., for Notepad, Calculator).
    *   **`config/settings.json` (Storage, Model, Prompt):** This file is created automatically with defaults if it doesn't exist. You can edit it directly or use the in-app Settings panel (⚙️ button):
        *   `storage_mode`: Set to `local` (default) or `google_drive`.
        *   `local_storage_path`: (Optional) Absolute path to a custom directory for storing history when `storage_mode` is `local`. If empty or `null`, defaults to `~/.jarvis-core/history`.
        *   `llm_model_path`: (Optional) Absolute path to the `.gguf` model file. If empty or `null`, the application looks for a model in the `models/` directory (or `MODEL_DIR`) based on `LLM_QUANT_PREFERENCE`.
        *   `system_prompt_path`: (Optional) Absolute path to a custom system prompt `.txt` file. If empty or `null`, defaults to `config/prompts/system_prompt.txt`.
        *   `google_drive_credentials_file`: Path to your Google Drive API credentials file (relative to project root or absolute). Defaults to `credentials.json`.
        *   `google_drive_token_file`: Name for the token file storing authentication. Defaults to `token.json` (stored in `.jarvis-core` user directory).
        *   `google_drive_folder_name`: Name of the folder to create/use on Google Drive. Defaults to `Jarvis-Core History`.
        *   `history_filename`: Name for the chat history file (used in both local and Google Drive modes). Defaults to `jarvis_chat_history.json`.
    *   **Google Drive Setup (if using `google_drive` mode):**
        *   **Credentials:** Obtain OAuth 2.0 Client ID credentials (`credentials.json`) from Google Cloud Console for the Drive API (choose "Desktop App" type). Place this file in the location specified by `google_drive_credentials_file` in `settings.json` (defaults to the project root).
        *   **Authentication:** The *first time* you switch to `google_drive` mode (or click "Authenticate Google Drive" in Settings), the application will attempt to open your web browser to authorize access. Follow the prompts. A token file (`token.json` by default) will be created in your user's `.jarvis-core` directory to store authorization for future runs.
5.  **Model:**
    *   **Automatic Download (Default):** The application will automatically download the default LLM model (based on `LLM_QUANT_PREFERENCE`, e.g., `Meta-Llama-3-8B-Instruct.Q4_K_M.gguf`) from Hugging Face to the `models/` directory (or `MODEL_DIR`) the first time it runs if the file is not found and no custom model path is specified in the settings. This may take some time depending on your internet connection.
    *   **Manual/Custom Model:** You can still manually download a different compatible `.gguf` model and place it in the `models/` directory (or `MODEL_DIR`), or specify the full path to any `.gguf` model using the `llm_model_path` setting in the Settings UI or `config/settings.json`. If a valid custom path is provided, the automatic download will be skipped.

## Usage

Run the graphical chat interface from the `tarvis-audit` directory:

```bash
python -m src.gui.main_window
```

*   Type messages in the input box and press Enter or click Send.
*   Click the Settings button (⚙️) to change the conversation history storage mode (`local` or `google_drive`), model paths, etc.
    *   Changing the mode requires the application to re-initialize storage. History will be loaded from the new source.
    *   If switching to Google Drive, you may need to click "Authenticate Google Drive" if not previously authorized.

## Important Notes

*   **LLM Performance:** Achieving high performance depends heavily on your hardware (CPU, RAM, GPU/VRAM). Experiment with the `.env` settings (`N_GPU_LAYERS`, `LLM_QUANT_PREFERENCE`, `USE_MLOCK`) to find the best balance for your system.
*   **Google Drive Authentication:** The browser-based OAuth flow requires user interaction and cannot be fully tested in automated sandbox environments. Ensure you run the application in a standard Windows desktop environment for the initial Google Drive setup.
*   **GUI Testing:** Full visual and interactive testing of the GUI is best performed in a standard Windows desktop environment.
*   **Running Scripts:** Some internal scripts (like `llm_manager.py`) might use relative imports. If running them directly for testing, use `python -m <module.path>` from the project root (e.g., `python -m src.core.llm_manager`).

## Development Phases

*   **Phase 1:** Core backend setup (LLM, orchestrator, basic skills) - **Completed**
*   **Phase 2:** Graphical User Interface (Chat Window) - **Completed**
*   **Phase 3:** Storage options (Local file, Google Drive, Settings Panel) - **Completed**
*   **Phase 4:** Performance Optimizations & Refinements - **In Progress**
*   **Phase 5:** Packaging (Windows executable, icon) and Testing - *Pending*
*   **Phase 6:** Future Enhancements (More skills, STT/TTS, RAG, cross-platform, etc.).

## Based On

Initial structure and concepts adapted from the user-provided blueprint (`pasted_content.txt`).

