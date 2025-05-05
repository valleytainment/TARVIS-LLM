# Jarvis-Core: Local AI Agent

This project aims to build a local AI assistant inspired by Jarvis, running primarily on Windows, with a graphical chat interface and configurable conversation history storage.

## Features

*   Conversational AI using a local LLM (Meta-Llama-3-8B-Q4_0 default, configurable path).
*   Graphical chat window interface using CustomTkinter.
*   Skills: Opening applications, file operations, clipboard access (initial set).
*   Storage: Configurable between local file storage (default: `.jarvis-core/history/jarvis_chat_history.json`, custom path configurable) and Google Drive sync (`Jarvis-Core History/jarvis_chat_history.json` on Drive) via an in-app settings panel.
*   Configuration: Settings UI (⚙️) allows configuring storage mode/path, LLM model path, and system prompt path.
*   Platform: Windows (initial focus).

## Setup

1.  **Clone/Download:** Get the project files into a directory (e.g., `C:\Jarvis-Core`).
2.  **Environment:** Ensure Python 3.10+ is installed on Windows.
3.  **Dependencies:** Install required Python packages. Open Command Prompt or PowerShell, navigate to the project directory (`jarvis-core`), and run:
    ```bash
    pip install -r requirements.txt
    # or python -m pip install -r requirements.txt
    ```
    *Note: This includes backend libraries (LangChain, GPT4All), GUI framework (CustomTkinter), and Google Drive API libraries.*

4.  **Configuration:**
    *   **`.env` file (Backend - Optional):** Create this file in the `jarvis-core` root directory if you need to customize backend settings:
        *   `USE_GPU=1`: Set this if you have a compatible GPU and installed necessary drivers/CUDA. Otherwise, leave as `0` (default) for CPU.
        *   `GOOGLE_DRIVE_CREDENTIALS_FILE=path/to/your/credentials.json`: (Optional) Specify a custom path for your Google Drive credentials file if it's not named `credentials.json` or not in the project root.
    *   **`config/app_paths.yaml`:** Verify application paths match your Windows setup (e.g., for Notepad, Calculator).
    *   **`config/settings.json` (Storage, Model, Prompt):** This file is created automatically with defaults if it doesn't exist. You can edit it directly or use the in-app Settings panel (⚙️ button):
        *   `storage_mode`: Set to `local` (default) or `google_drive`.
        *   `local_storage_path`: (Optional) Absolute path to a custom directory for storing history when `storage_mode` is `local`. If empty or `null`, defaults to `~/.jarvis-core/history`.
        *   `llm_model_path`: (Optional) Absolute path to the `.gguf` model file. If empty or `null`, the application looks for a model in the `models/` directory.
        *   `system_prompt_path`: (Optional) Absolute path to a custom system prompt `.txt` file. If empty or `null`, defaults to `config/prompts/system_prompt.txt`.
        *   `google_drive_credentials_file`: Path to your Google Drive API credentials file (relative to project root or absolute). Defaults to `credentials.json`.
        *   `google_drive_token_file`: Name for the token file storing authentication. Defaults to `token.pickle` (stored in `.jarvis-core` user directory).
        *   `google_drive_folder_name`: Name of the folder to create/use on Google Drive. Defaults to `Jarvis-Core History`.
        *   `history_filename`: Name for the chat history file (used in both local and Google Drive modes). Defaults to `jarvis_chat_history.json`.
    *   **Google Drive Setup (if using `google_drive` mode):**
        *   **Credentials:** Obtain OAuth 2.0 Client ID credentials (`credentials.json`) from Google Cloud Console for the Drive API (choose "Desktop App" type). Place this file in the location specified by `google_drive_credentials_file` in `settings.json` (defaults to the `jarvis-core` project root).
        *   **Authentication:** The *first time* you switch to `google_drive` mode (or click "Authenticate Google Drive" in Settings), the application will attempt to open your web browser to authorize access. Follow the prompts. A token file (`token.pickle` by default) will be created in your user's `.jarvis-core` directory to store authorization for future runs.
5.  **Model:**
    *   **Automatic Download (Default):** The application will automatically download the default LLM model (`Meta-Llama-3-8B-Instruct.Q4_0.gguf`, approx. 4.66 GB) from Hugging Face to the `models/` directory the first time it runs if the file is not found and no custom model path is specified in the settings. This may take some time depending on your internet connection.
    *   **Manual/Custom Model:** You can still manually download a different compatible `.gguf` model and place it in the `models/` directory, or specify the full path to any `.gguf` model using the `llm_model_path` setting in the Settings UI or `config/settings.json`. If a valid custom path is provided, the automatic download will be skipped.

## Usage

Run the graphical chat interface from the `jarvis-core` directory:

```bash
python -m src.gui.main_window
```

*   Type messages in the input box and press Enter or click Send.
*   Click the Settings button (⚙️) to change the conversation history storage mode (`local` or `google_drive`).
    *   Changing the mode requires the application to re-initialize storage. History will be loaded from the new source.
    *   If switching to Google Drive, you may need to click "Authenticate Google Drive" if not previously authorized.

## Important Notes

*   **LLM Download:** The application does *not* automatically download the LLM. You must place a compatible `.gguf` model file in the `models/` directory.
*   **Google Drive Authentication:** The browser-based OAuth flow requires user interaction and cannot be fully tested in automated sandbox environments. Ensure you run the application in a standard Windows desktop environment for the initial Google Drive setup.
*   **GUI Testing:** Full visual and interactive testing of the GUI is best performed in a standard Windows desktop environment.

## Development Phases

*   **Phase 1:** Core backend setup (LLM, orchestrator, basic skills) - **Completed**
*   **Phase 2:** Graphical User Interface (Chat Window) - **Completed**
*   **Phase 3:** Storage options (Local file, Google Drive, Settings Panel) - **Completed**
*   **Phase 4:** Packaging (Windows executable, icon) and Testing - *In Progress*
*   **Phase 5:** Future Enhancements (More skills, cross-platform, etc.).

## Based On

Initial structure and concepts adapted from the user-provided blueprint (`pasted_content.txt`).

