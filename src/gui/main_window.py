#!/usr/bin/env python
# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter as tk
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog
import threading
import queue
import logging
from pathlib import Path
import subprocess # Added for running builder script
import sys # Added for getting python executable

# Import backend components
from src.core.orchestrator import Orchestrator, RAG_ENABLED # Import RAG_ENABLED flag
from src.core.storage_manager import get_storage_manager, save_settings, load_settings, GoogleDriveStorageManager, initialize_storage_manager

# Import SecureStorage
try:
    from src.utils.security import SecureStorage
except ImportError:
    logging.error("Could not import SecureStorage. API key functionality will be limited.")
    SecureStorage = None

# Attempt to import RAG builder function for UI integration
try:
    # We don't actually call it directly, but check if module exists
    import src.rag.rag_builder
    RAG_BUILDER_AVAILABLE = RAG_ENABLED # Assume builder is available if RAG deps are met
except ImportError as e:
    logging.error(f"Failed to import necessary LangChain components for RAG building: {e}")
    RAG_BUILDER_AVAILABLE = False

# Configure basic logging for the GUI
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - GUI - %(message)s")

# Define project root relative to this file (src/gui/main_window.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

class SettingsWindow(ctk.CTkToplevel):
    """Window for configuring application settings."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Settings")
        self.geometry("600x700") # Adjusted size
        self.transient(parent)
        self.grab_set()

        self.settings = load_settings()
        if "api_providers" not in self.settings:
            self.settings["api_providers"] = {}

        # --- Variables --- 
        self.storage_mode_var = ctk.StringVar(value=self.settings.get("storage_mode", "local"))
        self.local_storage_path_var = ctk.StringVar(value=self.settings.get("local_storage_path") or "")
        self.llm_model_path_var = ctk.StringVar(value=self.settings.get("llm_model_path") or "")
        self.system_prompt_path_var = ctk.StringVar(value=self.settings.get("system_prompt_path") or "")
        self.active_llm_provider_var = ctk.StringVar(value=self.settings.get("active_llm_provider", "local"))
        self.rag_build_status_var = ctk.StringVar(value="")
        self.gdrive_auth_status_var = ctk.StringVar(value="") # For GDrive auth feedback

        self.provider_vars = {}
        self.provider_key_entry_vars = {}
        self.provider_key_status_vars = {}
        self.provider_widgets = {}

        # --- Title ---
        title_label = ctk.CTkLabel(self, text="Application Settings", font=ctk.CTkFont(size=16, weight="bold"))
        title_label.pack(pady=(10, 15))

        # --- Create TabView ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(pady=10, padx=20, fill="both", expand=True)
        self.tab_view.add("Storage")
        self.tab_view.add("Model & Prompt")
        self.tab_view.add("API Providers")
        self.tab_view.add("RAG")

        # --- Storage Tab --- 
        storage_tab = self.tab_view.tab("Storage")
        storage_mode_frame = ctk.CTkFrame(storage_tab)
        storage_mode_frame.pack(pady=10, padx=10, fill="x")
        storage_label = ctk.CTkLabel(storage_mode_frame, text="Conversation History Storage:")
        storage_label.pack(side="top", anchor="w", padx=10, pady=(5, 5))
        local_radio = ctk.CTkRadioButton(storage_mode_frame, text="Local File", variable=self.storage_mode_var, value="local", command=self.toggle_local_path_entry)
        local_radio.pack(side="top", anchor="w", padx=20, pady=5)
        gdrive_radio = ctk.CTkRadioButton(storage_mode_frame, text="Google Drive", variable=self.storage_mode_var, value="google_drive", command=self.toggle_local_path_entry)
        gdrive_radio.pack(side="top", anchor="w", padx=20, pady=5)

        # GDrive Auth Button and Status
        self.gdrive_auth_button = ctk.CTkButton(storage_mode_frame, text="Authenticate Google Drive", command=self.authenticate_gdrive_thread)
        self.gdrive_auth_button.pack(pady=(5, 0), padx=20)
        gdrive_status_label = ctk.CTkLabel(storage_mode_frame, textvariable=self.gdrive_auth_status_var, text_color="gray")
        gdrive_status_label.pack(pady=(0, 10), padx=20)

        self.local_path_frame = ctk.CTkFrame(storage_tab)
        self.local_path_frame.pack(pady=10, padx=10, fill="x")
        local_path_label = ctk.CTkLabel(self.local_path_frame, text="Local Storage Directory (Optional):")
        local_path_label.pack(side="top", anchor="w", padx=10, pady=(5, 0))
        local_path_entry_frame = ctk.CTkFrame(self.local_path_frame, fg_color="transparent")
        local_path_entry_frame.pack(fill="x", padx=10, pady=(0, 10))
        local_path_entry_frame.grid_columnconfigure(0, weight=1)
        self.local_path_entry = ctk.CTkEntry(local_path_entry_frame, textvariable=self.local_storage_path_var, placeholder_text="Default: ~/.jarvis-core/history")
        self.local_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        local_path_browse_button = ctk.CTkButton(local_path_entry_frame, text="Browse...", width=80, command=self.browse_directory)
        local_path_browse_button.grid(row=0, column=1, sticky="e")

        # --- Model & Prompt Tab ---
        model_tab = self.tab_view.tab("Model & Prompt")
        llm_path_frame = ctk.CTkFrame(model_tab)
        llm_path_frame.pack(pady=10, padx=10, fill="x")
        llm_path_label = ctk.CTkLabel(llm_path_frame, text="Local LLM Model File Path (Optional):")
        llm_path_label.pack(side="top", anchor="w", padx=10, pady=(5, 0))
        llm_path_entry_frame = ctk.CTkFrame(llm_path_frame, fg_color="transparent")
        llm_path_entry_frame.pack(fill="x", padx=10, pady=(0, 10))
        llm_path_entry_frame.grid_columnconfigure(0, weight=1)
        self.llm_path_entry = ctk.CTkEntry(llm_path_entry_frame, textvariable=self.llm_model_path_var, placeholder_text="Default: Selected based on .env")
        self.llm_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        llm_path_browse_button = ctk.CTkButton(llm_path_entry_frame, text="Browse...", width=80, command=self.browse_model_file)
        llm_path_browse_button.grid(row=0, column=1, sticky="e")

        prompt_path_frame = ctk.CTkFrame(model_tab)
        prompt_path_frame.pack(pady=10, padx=10, fill="x")
        prompt_path_label = ctk.CTkLabel(prompt_path_frame, text="System Prompt File Path (Optional):")
        prompt_path_label.pack(side="top", anchor="w", padx=10, pady=(5, 0))
        prompt_path_entry_frame = ctk.CTkFrame(prompt_path_frame, fg_color="transparent")
        prompt_path_entry_frame.pack(fill="x", padx=10, pady=(0, 10))
        prompt_path_entry_frame.grid_columnconfigure(0, weight=1)
        self.prompt_path_entry = ctk.CTkEntry(prompt_path_entry_frame, textvariable=self.system_prompt_path_var, placeholder_text="Default: config/prompts/system_prompt.txt")
        self.prompt_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        prompt_path_browse_button = ctk.CTkButton(prompt_path_entry_frame, text="Browse...", width=80, command=self.browse_prompt_file)
        prompt_path_browse_button.grid(row=0, column=1, sticky="e")

        # --- API Providers Tab --- 
        api_tab = self.tab_view.tab("API Providers")
        active_provider_frame = ctk.CTkFrame(api_tab)
        active_provider_frame.pack(pady=10, padx=10, fill="x")
        active_provider_label = ctk.CTkLabel(active_provider_frame, text="Active LLM Provider:")
        active_provider_label.pack(side="left", padx=(10, 5))
        available_providers = ["local", "openai", "deepseek"]
        provider_dropdown = ctk.CTkOptionMenu(active_provider_frame, variable=self.active_llm_provider_var, values=available_providers)
        provider_dropdown.pack(side="left", padx=(0, 10), fill="x", expand=True)

        sep = tk.Frame(api_tab, height=1, bg="gray70")
        sep.pack(fill="x", padx=10, pady=10)

        scrollable_frame = ctk.CTkScrollableFrame(api_tab, label_text="Provider Settings")
        scrollable_frame.pack(pady=5, padx=10, fill="both", expand=True)

        default_providers = load_settings().get("api_providers", {})
        for provider_name, default_config in default_providers.items():
            self.create_provider_settings_ui(scrollable_frame, provider_name, default_config)

        # --- RAG Tab --- (New)
        rag_tab = self.tab_view.tab("RAG")
        rag_frame = ctk.CTkFrame(rag_tab)
        rag_frame.pack(pady=20, padx=20, fill="x")

        rag_label = ctk.CTkLabel(rag_frame, text="Retrieval-Augmented Generation (RAG) allows the AI to use documents from the \'knowledge_base\' directory.")
        rag_label.pack(pady=(0, 10))

        self.rag_build_button = ctk.CTkButton(rag_frame, text="Build / Rebuild RAG Index", command=self.run_rag_builder_thread)
        self.rag_build_button.pack(pady=10)

        rag_status_label = ctk.CTkLabel(rag_frame, textvariable=self.rag_build_status_var, text_color="gray")
        rag_status_label.pack(pady=5)

        if not RAG_BUILDER_AVAILABLE:
            self.rag_build_button.configure(state=ctk.DISABLED, text="Build RAG Index (Dependencies Missing)")
            self.rag_build_status_var.set("Install chromadb and sentence-transformers/langchain-huggingface to enable RAG.")
        else:
             self.rag_build_status_var.set("Click button to build index from \'knowledge_base\' directory.")

        # --- Buttons Frame (Bottom) ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=(15, 10), side="bottom", fill="x", padx=20)
        button_frame.grid_columnconfigure((0, 1), weight=1)

        self.save_button = ctk.CTkButton(button_frame, text="Save & Restart Backend", command=self.save_and_close)
        self.save_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self.destroy, fg_color="gray")
        self.cancel_button.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Initial state update
        self.toggle_local_path_entry()
        self.update_key_status_labels()

    def create_provider_settings_ui(self, parent_frame, provider_name, config):
        provider_frame = ctk.CTkFrame(parent_frame)
        provider_frame.pack(pady=10, padx=5, fill="x")
        provider_frame.grid_columnconfigure(1, weight=1)

        self.provider_vars[provider_name] = {
            "enabled": ctk.BooleanVar(value=self.settings["api_providers"].get(provider_name, {}).get("enabled", False)),
            "model": ctk.StringVar(value=self.settings["api_providers"].get(provider_name, {}).get("model", config.get("model", ""))),
            "endpoint": ctk.StringVar(value=self.settings["api_providers"].get(provider_name, {}).get("endpoint", config.get("endpoint", "") or "")),
        }
        self.provider_key_entry_vars[provider_name] = ctk.StringVar()
        self.provider_key_status_vars[provider_name] = ctk.StringVar(value="Checking...")
        self.provider_widgets[provider_name] = {}

        title_label = ctk.CTkLabel(provider_frame, text=f"{provider_name.capitalize()} Settings:", font=ctk.CTkFont(weight="bold"))
        title_label.grid(row=0, column=0, padx=10, pady=(5, 2), sticky="w")
        enable_switch = ctk.CTkSwitch(provider_frame, text="Enable", variable=self.provider_vars[provider_name]["enabled"])
        enable_switch.grid(row=0, column=1, padx=10, pady=(5, 2), sticky="e")

        model_label = ctk.CTkLabel(provider_frame, text="Model:")
        model_label.grid(row=1, column=0, padx=10, pady=2, sticky="w")
        model_entry = ctk.CTkEntry(provider_frame, textvariable=self.provider_vars[provider_name]["model"])
        model_entry.grid(row=1, column=1, padx=10, pady=2, sticky="ew")

        endpoint_label = ctk.CTkLabel(provider_frame, text="Endpoint (Optional):")
        endpoint_label.grid(row=2, column=0, padx=10, pady=2, sticky="w")
        endpoint_entry = ctk.CTkEntry(provider_frame, textvariable=self.provider_vars[provider_name]["endpoint"], placeholder_text="Default API endpoint")
        endpoint_entry.grid(row=2, column=1, padx=10, pady=2, sticky="ew")

        key_label = ctk.CTkLabel(provider_frame, text="API Key:")
        key_label.grid(row=3, column=0, padx=10, pady=2, sticky="w")
        key_entry = ctk.CTkEntry(provider_frame, textvariable=self.provider_key_entry_vars[provider_name], show="*", placeholder_text="Enter new key to save")
        key_entry.grid(row=3, column=1, padx=10, pady=2, sticky="ew")
        self.provider_widgets[provider_name]["key_entry"] = key_entry

        key_status_label = ctk.CTkLabel(provider_frame, textvariable=self.provider_key_status_vars[provider_name], text_color="gray")
        key_status_label.grid(row=4, column=1, padx=10, pady=(0, 5), sticky="w")

        clear_key_button = ctk.CTkButton(provider_frame, text="Clear Stored Key", width=120, fg_color="#d9534f", hover_color="#c9302c", command=lambda p=provider_name: self.clear_stored_key(p))
        clear_key_button.grid(row=4, column=0, padx=10, pady=(0, 5), sticky="w")
        self.provider_widgets[provider_name]["clear_key_button"] = clear_key_button

        if not SecureStorage:
            key_entry.configure(state=ctk.DISABLED, placeholder_text="Secure Storage Unavailable")
            clear_key_button.configure(state=ctk.DISABLED)

    def update_key_status_labels(self):
        if not SecureStorage:
            for provider_name in self.provider_key_status_vars:
                self.provider_key_status_vars[provider_name].set("Secure Storage Unavailable")
            return
        threading.Thread(target=self._check_key_status_thread, daemon=True).start()

    def _check_key_status_thread(self):
        for provider_name in self.provider_key_status_vars:
            try:
                key_exists = SecureStorage.retrieve_key(provider_name) is not None
                status = "Key Stored Securely" if key_exists else "No Key Stored"
                self.after(0, self.provider_key_status_vars[provider_name].set, status)
            except Exception as e:
                logging.error(f"Error checking key status for {provider_name}: {e}")
                self.after(0, self.provider_key_status_vars[provider_name].set, "Error Checking Status")

    def clear_stored_key(self, provider_name):
        if not SecureStorage:
            messagebox.showerror("Error", "Secure Storage is not available.", parent=self)
            return
        if messagebox.askyesno("Confirm Clear", f"Are you sure you want to delete the stored API key for {provider_name.capitalize()}? This cannot be undone.", parent=self):
            try:
                SecureStorage.delete_key(provider_name)
                self.provider_key_entry_vars[provider_name].set("") # Clear entry field
                self.update_key_status_labels() # Refresh status
                messagebox.showinfo("Success", f"Stored API key for {provider_name.capitalize()} deleted.", parent=self)
            except Exception as e:
                logging.error(f"Error deleting key for {provider_name}: {e}")
                messagebox.showerror("Error", f"Failed to delete key for {provider_name}: {e}", parent=self)

    def toggle_local_path_entry(self):
        if self.storage_mode_var.get() == "local":
            self.local_path_entry.configure(state=ctk.NORMAL)
            # Find the browse button - assumes it's the second widget in the grid
            browse_button = self.local_path_entry.master.grid_slaves(row=0, column=1)[0]
            browse_button.configure(state=ctk.NORMAL)
            self.gdrive_auth_button.configure(state=ctk.DISABLED)
        else: # google_drive
            self.local_path_entry.configure(state=ctk.DISABLED)
            browse_button = self.local_path_entry.master.grid_slaves(row=0, column=1)[0]
            browse_button.configure(state=ctk.DISABLED)
            self.gdrive_auth_button.configure(state=ctk.NORMAL)
            # Check initial auth status for GDrive
            if isinstance(get_storage_manager(), GoogleDriveStorageManager):
                if get_storage_manager().is_authenticated():
                    self.gdrive_auth_status_var.set("Authenticated")
                else:
                    self.gdrive_auth_status_var.set("Not Authenticated")
            else:
                 self.gdrive_auth_status_var.set("Switch to GDrive mode to authenticate")

    def browse_directory(self):
        directory = filedialog.askdirectory(parent=self)
        if directory:
            self.local_storage_path_var.set(directory)

    def browse_model_file(self):
        # Adjust filetypes based on common model formats
        filetypes = [("GGUF files", "*.gguf"), ("All files", "*.*")]
        filepath = filedialog.askopenfilename(parent=self, filetypes=filetypes)
        if filepath:
            self.llm_model_path_var.set(filepath)

    def browse_prompt_file(self):
        filetypes = [("Text files", "*.txt"), ("All files", "*.*")]
        filepath = filedialog.askopenfilename(parent=self, filetypes=filetypes)
        if filepath:
            self.system_prompt_path_var.set(filepath)

    def authenticate_gdrive_thread(self):
        """Starts the Google Drive authentication process in a separate thread."""
        self.gdrive_auth_button.configure(state=ctk.DISABLED, text="Authenticating...")
        self.gdrive_auth_status_var.set("Authentication in progress...")
        threading.Thread(target=self._gdrive_auth_worker, daemon=True).start()

    def _gdrive_auth_worker(self):
        """Worker function for Google Drive authentication."""
        success = False
        error_msg = ""
        try:
            # Ensure we have a GDrive manager instance for authentication
            if not isinstance(get_storage_manager(), GoogleDriveStorageManager):
                 # Temporarily switch manager for auth if needed, or re-initialize
                 # This assumes initialize_storage_manager can handle mode switching
                 initialize_storage_manager(mode="google_drive", path=None) # Path doesn't matter for auth
            
            if isinstance(get_storage_manager(), GoogleDriveStorageManager):
                get_storage_manager().authenticate() # This might block or open browser
                success = get_storage_manager().is_authenticated()
                if not success:
                    error_msg = "Authentication failed or was cancelled."
            else:
                error_msg = "Could not switch to Google Drive mode for authentication."

        except Exception as e:
            error_msg = f"Authentication error: {e}"
            logging.error(error_msg, exc_info=True)

        # Update UI from the main thread using self.after
        def update_ui():
            self.gdrive_auth_button.configure(state=ctk.NORMAL, text="Authenticate Google Drive")
            if success:
                self.gdrive_auth_status_var.set("Authenticated Successfully")
                messagebox.showinfo("Success", "Google Drive authenticated successfully!", parent=self)
            else:
                self.gdrive_auth_status_var.set(f"Authentication Failed: {error_msg}")
                messagebox.showerror("Error", f"Google Drive authentication failed: {error_msg}", parent=self)
            # Re-initialize storage manager based on the selected mode in the UI
            # This ensures the correct manager is active after authentication attempt
            current_mode = self.storage_mode_var.get()
            current_path = self.local_storage_path_var.get() or None
            initialize_storage_manager(mode=current_mode, path=current_path)
            self.toggle_local_path_entry() # Refresh GDrive button state based on final manager

        self.after(0, update_ui)

    def run_rag_builder_thread(self):
        """Runs the RAG builder script in a separate thread."""
        if not RAG_BUILDER_AVAILABLE:
            messagebox.showwarning("RAG Unavailable", "RAG dependencies (chromadb, sentence-transformers/langchain-huggingface) are not installed. Cannot build index.", parent=self)
            return

        self.rag_build_button.configure(state=ctk.DISABLED, text="Building Index...")
        self.rag_build_status_var.set("Building... This may take some time.")
        threading.Thread(target=self._rag_build_worker, daemon=True).start()

    def _rag_build_worker(self):
        """Worker function to execute the rag_builder script."""
        success = False
        error_msg = ""
        try:
            script_path = str(PROJECT_ROOT / "src" / "rag" / "rag_builder.py")
            python_executable = sys.executable # Use the same python that runs the GUI
            # Use subprocess.run for simplicity if detailed output capture isn't needed immediately
            # Ensure the working directory is the project root for correct relative paths in the script
            result = subprocess.run([python_executable, "-m", "src.rag.rag_builder"], 
                                    capture_output=True, text=True, check=False, cwd=str(PROJECT_ROOT))
            
            if result.returncode == 0:
                success = True
                logging.info("RAG builder script finished successfully.")
                logging.info(f"Builder Output:\n{result.stdout}")
            else:
                error_msg = f"RAG builder script failed with exit code {result.returncode}."
                logging.error(error_msg)
                logging.error(f"Builder Stderr:\n{result.stderr}")
                logging.error(f"Builder Stdout:\n{result.stdout}")
                # Try to extract a more specific error from stderr if possible
                if result.stderr:
                     error_msg += f" Error: {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'Unknown error'}"

        except FileNotFoundError:
            error_msg = "Error: Python executable or rag_builder.py not found."
            logging.error(error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            logging.exception("Error running RAG builder script:")

        # Update UI from the main thread
        def update_rag_ui():
            self.rag_build_button.configure(state=ctk.NORMAL, text="Build / Rebuild RAG Index")
            if success:
                self.rag_build_status_var.set("RAG index built successfully!")
                # Use self.after to schedule the messagebox call in the main thread
                self.after(0, messagebox.showinfo, "Success", "RAG index built successfully!")
            else:
                self.rag_build_status_var.set(f"Error building RAG index. Check logs.")
                # Use self.after for error messagebox too
                self.after(0, messagebox.showerror, "Error", f"{error_msg}\nSee application logs for details.")

        self.after(0, update_rag_ui)

    def save_and_close(self):
        """Saves settings and closes the window."""
        self.settings["storage_mode"] = self.storage_mode_var.get()
        self.settings["local_storage_path"] = self.local_storage_path_var.get() or None # Store None if empty
        self.settings["llm_model_path"] = self.llm_model_path_var.get() or None
        self.settings["system_prompt_path"] = self.system_prompt_path_var.get() or None
        self.settings["active_llm_provider"] = self.active_llm_provider_var.get()

        # Save API provider settings
        keys_to_save = {}
        for provider_name, vars_dict in self.provider_vars.items():
            if provider_name not in self.settings["api_providers"]:
                 self.settings["api_providers"][provider_name] = {}
            self.settings["api_providers"][provider_name]["enabled"] = vars_dict["enabled"].get()
            self.settings["api_providers"][provider_name]["model"] = vars_dict["model"].get()
            self.settings["api_providers"][provider_name]["endpoint"] = vars_dict["endpoint"].get() or None
            
            # Check if a new key was entered
            new_key = self.provider_key_entry_vars[provider_name].get()
            if new_key:
                keys_to_save[provider_name] = new_key

        try:
            save_settings(self.settings)
            logging.info("Settings saved successfully.")
            
            # Save new API keys securely if SecureStorage is available
            if SecureStorage and keys_to_save:
                saved_keys_count = 0
                failed_keys = []
                for provider_name, key in keys_to_save.items():
                    try:
                        SecureStorage.store_key(provider_name, key)
                        saved_keys_count += 1
                        logging.info(f"API key for {provider_name} stored securely.")
                    except Exception as e:
                        failed_keys.append(provider_name)
                        logging.error(f"Failed to store API key for {provider_name}: {e}")
                
                if saved_keys_count > 0:
                     messagebox.showinfo("API Keys Saved", f"Successfully saved {saved_keys_count} new API key(s) securely.", parent=self)
                if failed_keys:
                     messagebox.showerror("API Key Error", f"Failed to save API key(s) for: {', '.join(failed_keys)}. Secure Storage might be unavailable or misconfigured.", parent=self)

            # Trigger backend restart in the parent window
            self.parent.restart_backend_thread()
            self.destroy()
        except Exception as e:
            logging.exception("Error saving settings:")
            messagebox.showerror("Error", f"Failed to save settings: {e}", parent=self)

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TARVIS-LLM")
        self.geometry("800x600")

        # Initialize backend components
        self.orchestrator = None
        self.storage_manager = get_storage_manager() # Get initially configured manager
        self.message_queue = queue.Queue()

        # --- Configure grid layout (2 rows, 2 columns) ---
        self.grid_rowconfigure(0, weight=1) # Chat history takes most space
        self.grid_rowconfigure(1, weight=0) # Input area is fixed height
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0) # Settings button column

        # --- Chat History (Row 0, Col 0) ---
        self.chat_history = ctk.CTkTextbox(self, state=ctk.DISABLED, wrap=tk.WORD, font=ctk.CTkFont(size=14))
        self.chat_history.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="nsew")
        self.chat_history.tag_config("user", foreground="#007bff") # Blue for user
        self.chat_history.tag_config("assistant", foreground="#28a745") # Green for assistant
        self.chat_history.tag_config("error", foreground="#dc3545") # Red for errors
        self.chat_history.tag_config("info", foreground="gray60") # Gray for info/status

        # --- Settings Button (Row 0, Col 1) ---
        settings_button = ctk.CTkButton(self, text="⚙️", width=40, command=self.open_settings)
        settings_button.grid(row=0, column=1, padx=(0, 10), pady=(10, 5), sticky="ne")

        # --- Input Area (Row 1, Col 0 & 1) ---
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(5, 10), sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_entry = ctk.CTkEntry(input_frame, placeholder_text="Enter your message...", font=ctk.CTkFont(size=14))
        self.input_entry.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="ew")
        self.input_entry.bind("<Return>", self.send_message)

        self.send_button = ctk.CTkButton(input_frame, text="Send", width=80, command=self.send_message)
        self.send_button.grid(row=0, column=1, pady=5, sticky="e")

        # --- Status Bar Area (Below Input) ---
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 5), sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(status_frame, mode="indeterminate")
        # Initially hide progress bar
        # self.progress_bar.grid(row=0, column=0, padx=(0, 10), pady=2, sticky="ew") 

        self.status_label = ctk.CTkLabel(status_frame, text="Initializing backend...", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=5) # Changed row to 0

        # --- Load initial history and start backend ---
        self.load_initial_history()
        # IMPORTANT: Move backend restart call AFTER all UI elements are created
        # self.restart_backend_thread() # Initial backend load - MOVED
        self.after(100, self.restart_backend_thread) # Call after a short delay to ensure UI is fully drawn

        # Start checking the message queue
        self.after(100, self.check_message_queue)

    def load_initial_history(self):
        try:
            history = self.storage_manager.load_conversation()
            self.chat_history.configure(state=ctk.NORMAL)
            self.chat_history.delete("1.0", tk.END)
            for message in history:
                role = message.get("role", "unknown")
                content = message.get("content", "")
                self.display_message(f"{role.capitalize()}: {content}\n\n", role)
            self.chat_history.configure(state=ctk.DISABLED)
            self.chat_history.see(tk.END) # Scroll to bottom
            logging.info("Loaded conversation history.")
        except Exception as e:
            logging.error(f"Failed to load conversation history: {e}", exc_info=True)
            self.display_message(f"Error loading history: {e}\n", "error")

    def display_message(self, message, tag):
        """Appends a message to the chat history with a specific tag."""
        self.chat_history.configure(state=ctk.NORMAL)
        self.chat_history.insert(tk.END, message, tag)
        self.chat_history.configure(state=ctk.DISABLED)
        self.chat_history.see(tk.END) # Auto-scroll

    def send_message(self, event=None):
        user_input = self.input_entry.get().strip()
        if not user_input or self.orchestrator is None:
            if not user_input:
                logging.warning("Attempted to send empty message.")
            if self.orchestrator is None:
                 logging.warning("Orchestrator not ready, cannot send message.")
                 self.display_message("Backend not ready. Please wait.\n", "error")
            return

        self.display_message(f"User: {user_input}\n\n", "user")
        self.input_entry.delete(0, tk.END)

        # Disable input and show progress
        self.input_entry.configure(state=ctk.DISABLED)
        self.send_button.configure(state=ctk.DISABLED)
        self.progress_bar.grid(row=0, column=0, padx=(0, 10), pady=2, sticky="ew") # Show progress bar
        self.progress_bar.start()
        self.status_label.configure(text="Assistant is thinking...")

        # Run orchestrator in a separate thread
        threading.Thread(target=self._process_input_thread, args=(user_input,), daemon=True).start()

    def _process_input_thread(self, user_input):
        try:
            response_stream = self.orchestrator.process_input_stream(user_input)
            full_response = ""
            self.message_queue.put(("start_stream", None))
            for chunk in response_stream:
                self.message_queue.put(("stream_chunk", chunk))
                full_response += chunk
            self.message_queue.put(("end_stream", full_response))
        except Exception as e:
            logging.exception("Error processing input:")
            self.message_queue.put(("error", f"Error: {e}"))

    def check_message_queue(self):
        try:
            while True:
                message_type, data = self.message_queue.get_nowait()
                if message_type == "start_stream":
                    self.display_message("Assistant: ", "assistant")
                elif message_type == "stream_chunk":
                    self.display_message(data, "assistant")
                elif message_type == "end_stream":
                    self.display_message("\n\n", "assistant") # Add spacing after response
                    # Re-enable input and hide progress
                    self.input_entry.configure(state=ctk.NORMAL)
                    self.send_button.configure(state=ctk.NORMAL)
                    self.progress_bar.stop()
                    self.progress_bar.grid_forget() # Hide progress bar
                    self.status_label.configure(text="Ready")
                    # Save conversation after full response
                    self.storage_manager.save_conversation(self.orchestrator.get_conversation_history())
                elif message_type == "error":
                    self.display_message(f"{data}\n\n", "error")
                    # Re-enable input even on error
                    self.input_entry.configure(state=ctk.NORMAL)
                    self.send_button.configure(state=ctk.NORMAL)
                    self.progress_bar.stop()
                    self.progress_bar.grid_forget()
                    self.status_label.configure(text="Error occurred. Ready.")
        except queue.Empty:
            pass # No messages
        finally:
            # Check again after 100ms
            self.after(100, self.check_message_queue)

    def open_settings(self):
        if hasattr(self, "settings_window") and self.settings_window.winfo_exists():
            self.settings_window.focus()
        else:
            self.settings_window = SettingsWindow(self)

    def restart_backend_thread(self):
        """Starts the backend restart process in a separate thread."""
        logging.info("Restarting backend...")
        self.status_label.configure(text="Restarting backend...")
        # Disable input during restart
        if hasattr(self, 'input_entry'): # Check if widget exists before configuring
             self.input_entry.configure(state=ctk.DISABLED)
        if hasattr(self, 'send_button'):
             self.send_button.configure(state=ctk.DISABLED)
        if hasattr(self, 'progress_bar'):
             self.progress_bar.grid(row=0, column=0, padx=(0, 10), pady=2, sticky="ew")
             self.progress_bar.start()
        
        threading.Thread(target=self._restart_backend_worker, daemon=True).start()

    def _restart_backend_worker(self):
        """Worker function to initialize/re-initialize the orchestrator."""
        success = False
        error_msg = ""
        try:
            # Re-initialize storage manager based on potentially updated settings
            self.storage_manager = initialize_storage_manager()
            # Load history using the potentially new storage manager
            # We need to update the UI from the main thread
            self.after(0, self.load_initial_history)

            # Initialize Orchestrator
            self.orchestrator = Orchestrator()
            if self.orchestrator.is_ready():
                success = True
                logging.info("Backend restarted successfully.")
            else:
                error_msg = "Orchestrator failed to initialize. LLM might not have loaded. Check logs."
                logging.error(error_msg)
                self.orchestrator = None # Ensure orchestrator is None if not ready
        except Exception as e:
            error_msg = f"Failed to restart backend: {e}"
            logging.exception(error_msg)
            self.orchestrator = None # Ensure orchestrator is None on error

        # Update UI from the main thread
        def update_status():
            if hasattr(self, 'progress_bar'): # Check if widget exists
                 self.progress_bar.stop()
                 self.progress_bar.grid_forget()
            if success:
                self.status_label.configure(text="Backend ready.")
                if hasattr(self, 'input_entry'):
                     self.input_entry.configure(state=ctk.NORMAL)
                if hasattr(self, 'send_button'):
                     self.send_button.configure(state=ctk.NORMAL)
            else:
                self.status_label.configure(text=f"Backend Error: {error_msg}")
                # Keep input disabled if backend failed
                if hasattr(self, 'input_entry'):
                     self.input_entry.configure(state=ctk.DISABLED)
                if hasattr(self, 'send_button'):
                     self.send_button.configure(state=ctk.DISABLED)
                self.display_message(f"CRITICAL ERROR: Backend failed to initialize. Please check settings and logs. {error_msg}\n", "error")

        self.after(0, update_status)

if __name__ == "__main__":
    ctk.set_appearance_mode("System") # Modes: "System" (default), "Dark", "Light"
    ctk.set_default_color_theme("blue") # Themes: "blue" (default), "green", "dark-blue"
    app = MainWindow()
    app.mainloop()

