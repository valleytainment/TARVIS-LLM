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
    # We don\\'t actually call it directly, but check if module exists
    import src.rag.rag_builder 
    RAG_BUILDER_AVAILABLE = RAG_ENABLED # Assume builder is available if RAG deps are met
except ImportError:
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
            self.rag_build_status_var.set("Install chromadb and sentence-transformers to enable RAG.")
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
        else:
            self.local_path_entry.configure(state=ctk.DISABLED)
            browse_button = self.local_path_entry.master.grid_slaves(row=0, column=1)[0]
            browse_button.configure(state=ctk.DISABLED)

    def browse_directory(self):
        dir_path = filedialog.askdirectory(title="Select Local Storage Directory")
        if dir_path:
            self.local_storage_path_var.set(dir_path)

    def browse_model_file(self):
        file_path = filedialog.askopenfilename(title="Select LLM Model File", filetypes=[("GGUF files", "*.gguf")])
        if file_path:
            self.llm_model_path_var.set(file_path)

    def browse_prompt_file(self):
        file_path = filedialog.askopenfilename(title="Select System Prompt File", filetypes=[("Text files", "*.txt")])
        if file_path:
            self.system_prompt_path_var.set(file_path)

    def authenticate_gdrive_thread(self):
        """Starts the Google Drive authentication process in a separate thread."""
        if self.storage_mode_var.get() != "google_drive":
            messagebox.showwarning("Mode Incorrect", "Please select \'Google Drive\' as the storage mode first.", parent=self)
            return
            
        self.gdrive_auth_button.configure(state=ctk.DISABLED, text="Authenticating...")
        self.gdrive_auth_status_var.set("Starting authentication...")
        threading.Thread(target=self._gdrive_auth_worker, daemon=True).start()

    def _gdrive_auth_worker(self):
        """Worker function for Google Drive authentication."""
        try:
            # Assuming GoogleDriveStorageManager handles its own auth flow
            # We might need to pass the project root or config path if needed
            gdrive_manager = GoogleDriveStorageManager() 
            success = gdrive_manager.authenticate() # This might block
            if success:
                status_msg = "Google Drive authenticated successfully."
                self.after(0, self.gdrive_auth_status_var.set, status_msg)
                self.after(0, messagebox.showinfo, "Success", status_msg, parent=self)
            else:
                status_msg = "Google Drive authentication failed or was cancelled."
                self.after(0, self.gdrive_auth_status_var.set, status_msg)
                self.after(0, messagebox.showerror, "Error", status_msg, parent=self)
        except Exception as e:
            error_msg = f"Error during Google Drive authentication: {e}"
            logging.error(error_msg, exc_info=True)
            self.after(0, self.gdrive_auth_status_var.set, f"Error: {e}")
            self.after(0, messagebox.showerror, "Error", error_msg, parent=self)
        finally:
            # Re-enable button regardless of outcome
            self.after(0, self.gdrive_auth_button.configure, state=ctk.NORMAL, text="Authenticate Google Drive")

    def run_rag_builder_thread(self):
        """Runs the RAG builder script in a separate thread."""
        self.rag_build_button.configure(state=ctk.DISABLED, text="Building...")
        self.rag_build_status_var.set("Starting RAG index build...")
        threading.Thread(target=self._rag_build_worker, daemon=True).start()

    def _rag_build_worker(self):
        """Worker function to run the RAG builder script."""
        script_path = PROJECT_ROOT / "src" / "rag" / "rag_builder.py"
        python_executable = sys.executable # Use the same python that runs the GUI
        try:
            logging.info(f"Running RAG builder script: {script_path} with python {python_executable}")
            # Use subprocess.run for simplicity if detailed output capture isn\'t needed immediately
            # Set cwd to project root to ensure relative paths in builder work correctly
            process = subprocess.run(
                [python_executable, str(script_path)], 
                capture_output=True, text=True, check=True, cwd=str(PROJECT_ROOT)
            )
            logging.info(f"RAG Builder Output:\n{process.stdout}")
            if process.stderr:
                 logging.warning(f"RAG Builder Error Output:\n{process.stderr}")
            status_msg = "RAG index built successfully!"
            self.after(0, self.rag_build_status_var.set, status_msg)
            self.after(0, messagebox.showinfo, "Success", status_msg)
        except subprocess.CalledProcessError as e:
            error_msg = f"RAG builder script failed with exit code {e.returncode}."
            logging.error(f"{error_msg}\nOutput:\n{e.stdout}\nError:\n{e.stderr}")
            self.after(0, self.rag_build_status_var.set, f"Error: {error_msg}")
            self.after(0, messagebox.showerror, "Error", f"{error_msg}\nSee application logs for details.")
        except FileNotFoundError:
            error_msg = f"RAG builder script not found at {script_path}."
            logging.error(error_msg)
            self.after(0, self.rag_build_status_var.set, f"Error: {error_msg}")
            self.after(0, messagebox.showerror, "Error", error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred while running the RAG builder: {e}"
            logging.error(error_msg, exc_info=True)
            self.after(0, self.rag_build_status_var.set, f"Error: {e}")
            self.after(0, messagebox.showerror, "Error", f"{error_msg}\nSee application logs for details.")
        finally:
            # Re-enable button
            self.after(0, self.rag_build_button.configure, state=ctk.NORMAL, text="Build / Rebuild RAG Index")

    def save_and_close(self):
        """Saves the settings and closes the window."""
        logging.info("Saving settings...")
        try:
            # Update settings dictionary from variables
            self.settings["storage_mode"] = self.storage_mode_var.get()
            self.settings["local_storage_path"] = self.local_storage_path_var.get() or None
            self.settings["llm_model_path"] = self.llm_model_path_var.get() or None
            self.settings["system_prompt_path"] = self.system_prompt_path_var.get() or None
            self.settings["active_llm_provider"] = self.active_llm_provider_var.get()

            # Update API provider settings
            for provider_name, vars_dict in self.provider_vars.items():
                if provider_name not in self.settings["api_providers"]:
                    self.settings["api_providers"][provider_name] = {}
                self.settings["api_providers"][provider_name]["enabled"] = vars_dict["enabled"].get()
                self.settings["api_providers"][provider_name]["model"] = vars_dict["model"].get()
                self.settings["api_providers"][provider_name]["endpoint"] = vars_dict["endpoint"].get() or None

                # Save API key if entered and SecureStorage is available
                new_key = self.provider_key_entry_vars[provider_name].get()
                if new_key and SecureStorage:
                    try:
                        SecureStorage.store_key(provider_name, new_key)
                        logging.info(f"Saved new API key for {provider_name} securely.")
                    except Exception as e:
                        logging.error(f"Failed to save API key for {provider_name}: {e}")
                        messagebox.showerror("Key Storage Error", f"Failed to save API key for {provider_name}: {e}", parent=self)
                        # Optionally, decide whether to proceed with saving other settings

            save_settings(self.settings)
            logging.info("Settings saved successfully.")
            messagebox.showinfo("Settings Saved", "Settings saved. Restarting backend services...", parent=self)
            self.parent.restart_backend_thread() # Trigger restart in main window (now threaded)
            self.destroy()
        except Exception as e:
            logging.error(f"Failed to save settings: {e}", exc_info=True)
            messagebox.showerror("Save Error", f"Failed to save settings: {e}", parent=self)

class MainWindow(ctk.CTk):
    """Main application window."""
    def __init__(self):
        super().__init__()
        self.title("TARVIS-LLM")
        self.geometry("800x600")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Backend Initialization ---
        self.settings = load_settings()
        self.orchestrator = None
        self.storage_manager = None
        self.backend_status_var = ctk.StringVar(value="Backend: Initializing...")
        self.restart_backend_thread() # Initial backend load

        # --- UI Elements ---
        # Conversation Display
        self.conversation_display = ctk.CTkTextbox(self, state="disabled", wrap="word", font=("Arial", 12))
        self.conversation_display.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nsew")

        # Input Area
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_entry = ctk.CTkEntry(input_frame, placeholder_text="Enter your command...")
        self.input_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.input_entry.bind("<Return>", self.send_message)

        self.send_button = ctk.CTkButton(input_frame, text="Send", width=80, command=self.send_message)
        self.send_button.grid(row=0, column=1)

        # Status Bar
        status_bar = ctk.CTkFrame(self, height=30)
        status_bar.grid(row=2, column=0, padx=0, pady=0, sticky="ew")
        status_bar.grid_columnconfigure(1, weight=1)

        settings_button = ctk.CTkButton(status_bar, text="⚙️", width=30, command=self.open_settings)
        settings_button.grid(row=0, column=0, padx=(10, 5), pady=5)

        backend_status_label = ctk.CTkLabel(status_bar, textvariable=self.backend_status_var, anchor="w")
        backend_status_label.grid(row=0, column=1, padx=(5, 10), pady=5, sticky="ew")

        # --- Load History ---
        self.load_conversation_history()

        # --- Queue for thread communication ---
        self.response_queue = queue.Queue()
        self.after(100, self.process_queue) # Check queue periodically

    def restart_backend_thread(self):
        """Restarts the backend (Orchestrator, Storage) in a separate thread."""
        self.backend_status_var.set("Backend: Restarting...")
        self.input_entry.configure(state=ctk.DISABLED)
        self.send_button.configure(state=ctk.DISABLED)
        # Optionally disable settings button during restart?
        
        threading.Thread(target=self._restart_backend_worker, daemon=True).start()

    def _restart_backend_worker(self):
        """Worker function to initialize/re-initialize backend components."""
        try:
            logging.info("Restarting backend services...")
            self.settings = load_settings() # Reload settings
            self.storage_manager = initialize_storage_manager(self.settings)
            self.orchestrator = Orchestrator(settings=self.settings) # Pass settings
            
            if self.orchestrator and self.orchestrator.llm: # Check if LLM loaded successfully
                status_msg = "Backend: Ready"
                logging.info("Backend restarted successfully.")
                self.after(0, self.input_entry.configure, state=ctk.NORMAL)
                self.after(0, self.send_button.configure, state=ctk.NORMAL)
            else:
                status_msg = "Backend: Error (LLM Failed to Load)"
                logging.error("Backend restart failed: LLM could not be loaded.")
                # Keep input disabled if backend failed
                self.after(0, self.input_entry.configure, state=ctk.DISABLED)
                self.after(0, self.send_button.configure, state=ctk.DISABLED)
                self.after(0, messagebox.showerror, "Backend Error", "Failed to initialize the language model. Please check settings and logs.")

            self.after(0, self.backend_status_var.set, status_msg)
            # Consider reloading history if storage manager changed, but might be complex
            # self.after(0, self.load_conversation_history)

        except Exception as e:
            error_msg = f"Backend: Error ({e})"
            logging.error(f"Critical error during backend restart: {e}", exc_info=True)
            self.after(0, self.backend_status_var.set, error_msg)
            self.after(0, self.input_entry.configure, state=ctk.DISABLED)
            self.after(0, self.send_button.configure, state=ctk.DISABLED)
            self.after(0, messagebox.showerror, "Backend Error", f"Failed to restart backend: {e}\nCheck logs for details.")

    def load_conversation_history(self):
        """Loads and displays the conversation history."""
        if not self.storage_manager:
            logging.warning("Storage manager not initialized, cannot load history.")
            return
            
        try:
            history = self.storage_manager.load_conversation()
            self.conversation_display.configure(state="normal")
            self.conversation_display.delete("1.0", tk.END)
            for entry in history:
                speaker = entry.get("speaker", "Unknown")
                text = entry.get("text", "")
                self.conversation_display.insert(tk.END, f"{speaker}: {text}\n\n")
            self.conversation_display.configure(state="disabled")
            self.conversation_display.see(tk.END) # Scroll to bottom
            logging.info("Conversation history loaded.")
        except Exception as e:
            logging.error(f"Failed to load conversation history: {e}", exc_info=True)
            self.conversation_display.configure(state="normal")
            self.conversation_display.insert(tk.END, f"\n[Error loading history: {e}]\n")
            self.conversation_display.configure(state="disabled")

    def save_conversation_entry(self, speaker: str, text: str):
        """Saves a single entry to the conversation history."""
        if not self.storage_manager:
            logging.warning("Storage manager not initialized, cannot save history.")
            return
        try:
            self.storage_manager.save_conversation_entry(speaker, text)
        except Exception as e:
            logging.error(f"Failed to save conversation entry: {e}", exc_info=True)
            # Optionally show a non-blocking error in the UI
            self.display_message("System", f"[Error saving history: {e}]")

    def display_message(self, speaker: str, text: str):
        """Appends a message to the conversation display."""
        self.conversation_display.configure(state="normal")
        self.conversation_display.insert(tk.END, f"{speaker}: {text}\n\n")
        self.conversation_display.configure(state="disabled")
        self.conversation_display.see(tk.END) # Scroll to bottom

    def send_message(self, event=None):
        """Handles sending the user input to the backend."""
        user_input = self.input_entry.get().strip()
        if not user_input:
            return
            
        if not self.orchestrator or not self.orchestrator.llm:
             messagebox.showerror("Backend Error", "Backend is not ready or LLM failed to load. Cannot send message.")
             return

        self.display_message("User", user_input)
        self.save_conversation_entry("User", user_input)
        self.input_entry.delete(0, tk.END)
        self.input_entry.configure(state=ctk.DISABLED)
        self.send_button.configure(state=ctk.DISABLED)
        self.backend_status_var.set("Backend: Processing...")

        # Start processing in a separate thread
        threading.Thread(target=self._process_input_thread, args=(user_input,), daemon=True).start()

    def _process_input_thread(self, user_input: str):
        """Worker thread to get response from orchestrator."""
        try:
            full_response = ""
            # Use streaming response
            for chunk in self.orchestrator.route_command_stream(user_input):
                self.response_queue.put(chunk) # Put chunk in queue for main thread
                full_response += chunk
            
            # Signal end of response (e.g., with a special marker or None)
            self.response_queue.put(None) 
            # Save the complete response once streaming is finished
            self.save_conversation_entry("AI", full_response.strip())

        except Exception as e:
            error_msg = f"Error getting response from backend: {e}"
            logging.error(error_msg, exc_info=True)
            self.response_queue.put(f"\n[Error: {e}]\n")
            self.response_queue.put(None) # Signal end even on error
            self.save_conversation_entry("System", f"[Error processing input: {e}]")

    def process_queue(self):
        """Processes messages from the response queue in the main thread."""
        try:
            while True: # Process all available messages
                chunk = self.response_queue.get_nowait()
                if chunk is None: # End of response signal
                    self.input_entry.configure(state=ctk.NORMAL)
                    self.send_button.configure(state=ctk.NORMAL)
                    self.backend_status_var.set("Backend: Ready")
                    # Add a final newline for spacing if needed, after AI response is fully displayed
                    self.conversation_display.configure(state="normal")
                    # Check if last char is already newline, avoid double newline
                    if self.conversation_display.get("end-2c", "end-1c") != "\n":
                        self.conversation_display.insert(tk.END, "\n")
                    self.conversation_display.configure(state="disabled")
                    self.conversation_display.see(tk.END)
                    break # Exit loop for this cycle once None is received
                else:
                    # Append chunk to display
                    self.conversation_display.configure(state="normal")
                    self.conversation_display.insert(tk.END, chunk)
                    self.conversation_display.configure(state="disabled")
                    self.conversation_display.see(tk.END) # Keep scrolling

        except queue.Empty:
            pass # No messages in queue, do nothing
        finally:
            # Schedule the next check
            self.after(100, self.process_queue)

    def open_settings(self):
        """Opens the settings window."""
        # Check if already open?
        if hasattr(self, "settings_window") and self.settings_window.winfo_exists():
            self.settings_window.focus()
        else:
            self.settings_window = SettingsWindow(self)
            self.settings_window.focus()

if __name__ == "__main__":
    ctk.set_appearance_mode("System") # Modes: "System" (default), "Dark", "Light"
    ctk.set_default_color_theme("blue") # Themes: "blue" (default), "green", "dark-blue"
    app = MainWindow()
    app.mainloop()

