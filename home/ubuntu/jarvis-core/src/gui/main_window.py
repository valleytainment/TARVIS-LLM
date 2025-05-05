import customtkinter as ctk
import tkinter as tk
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog # Added for browsing
import threading
import queue
import logging
from pathlib import Path # Added for path handling

# Import backend components
from src.core.orchestrator import Orchestrator
from src.core.storage_manager import get_storage_manager, save_settings, load_settings, GoogleDriveStorageManager, initialize_storage_manager

# Configure basic logging for the GUI
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - GUI - %(message)s")

class SettingsWindow(ctk.CTkToplevel):
    """Window for configuring application settings."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent # Reference to the main ChatWindow
        self.title("Settings")
        # Increased height to accommodate new settings
        self.geometry("550x550") # Adjusted size
        self.transient(parent) # Keep on top of parent
        self.grab_set() # Modal behavior

        self.settings = load_settings()

        # --- Variables --- 
        self.storage_mode_var = ctk.StringVar(value=self.settings.get("storage_mode", "local"))
        # Use empty string if path is None for Entry widget
        self.local_storage_path_var = ctk.StringVar(value=self.settings.get("local_storage_path") or "") 
        self.llm_model_path_var = ctk.StringVar(value=self.settings.get("llm_model_path") or "")
        self.system_prompt_path_var = ctk.StringVar(value=self.settings.get("system_prompt_path") or "")

        # --- Title ---
        title_label = ctk.CTkLabel(self, text="Application Settings", font=ctk.CTkFont(size=16, weight="bold"))
        title_label.pack(pady=(10, 15))

        # --- Create TabView ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(pady=10, padx=20, fill="both", expand=True)
        self.tab_view.add("Storage")
        self.tab_view.add("Model & Prompt")

        # --- Storage Tab --- 
        storage_tab = self.tab_view.tab("Storage")

        # Storage Mode Frame
        storage_mode_frame = ctk.CTkFrame(storage_tab)
        storage_mode_frame.pack(pady=10, padx=10, fill="x")
        storage_label = ctk.CTkLabel(storage_mode_frame, text="Conversation History Storage:")
        storage_label.pack(side="top", anchor="w", padx=10, pady=(5, 5))
        local_radio = ctk.CTkRadioButton(storage_mode_frame, text="Local File", variable=self.storage_mode_var, value="local", command=self.toggle_local_path_entry)
        local_radio.pack(side="top", anchor="w", padx=20, pady=5)
        gdrive_radio = ctk.CTkRadioButton(storage_mode_frame, text="Google Drive", variable=self.storage_mode_var, value="google_drive", command=self.toggle_local_path_entry)
        gdrive_radio.pack(side="top", anchor="w", padx=20, pady=5)
        auth_button = ctk.CTkButton(storage_mode_frame, text="Authenticate Google Drive", command=self.authenticate_gdrive)
        auth_button.pack(pady=(5, 10), padx=20)

        # Local Storage Path Frame (conditionally shown)
        self.local_path_frame = ctk.CTkFrame(storage_tab)
        # Pack it initially, visibility controlled later
        self.local_path_frame.pack(pady=10, padx=10, fill="x") 
        local_path_label = ctk.CTkLabel(self.local_path_frame, text="Local Storage Directory (Optional):")
        local_path_label.pack(side="top", anchor="w", padx=10, pady=(5, 0))
        local_path_entry_frame = ctk.CTkFrame(self.local_path_frame, fg_color="transparent") # Frame for entry and button
        local_path_entry_frame.pack(fill="x", padx=10, pady=(0, 10))
        local_path_entry_frame.grid_columnconfigure(0, weight=1)
        self.local_path_entry = ctk.CTkEntry(local_path_entry_frame, textvariable=self.local_storage_path_var, placeholder_text="Default: ~/.jarvis-core/history")
        self.local_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        local_path_browse_button = ctk.CTkButton(local_path_entry_frame, text="Browse...", width=80, command=self.browse_directory)
        local_path_browse_button.grid(row=0, column=1, sticky="e")

        # --- Model & Prompt Tab ---
        model_tab = self.tab_view.tab("Model & Prompt")

        # LLM Model Path Frame
        llm_path_frame = ctk.CTkFrame(model_tab)
        llm_path_frame.pack(pady=10, padx=10, fill="x")
        llm_path_label = ctk.CTkLabel(llm_path_frame, text="LLM Model File Path (Optional):")
        llm_path_label.pack(side="top", anchor="w", padx=10, pady=(5, 0))
        llm_path_entry_frame = ctk.CTkFrame(llm_path_frame, fg_color="transparent")
        llm_path_entry_frame.pack(fill="x", padx=10, pady=(0, 10))
        llm_path_entry_frame.grid_columnconfigure(0, weight=1)
        self.llm_path_entry = ctk.CTkEntry(llm_path_entry_frame, textvariable=self.llm_model_path_var, placeholder_text="Default: Selected based on .env")
        self.llm_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        llm_path_browse_button = ctk.CTkButton(llm_path_entry_frame, text="Browse...", width=80, command=self.browse_model_file)
        llm_path_browse_button.grid(row=0, column=1, sticky="e")

        # System Prompt Path Frame
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

        # --- Buttons Frame (Bottom) ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=(15, 10), side="bottom", fill="x", padx=20)
        button_frame.grid_columnconfigure((0, 1), weight=1)

        save_button = ctk.CTkButton(button_frame, text="Save & Restart Backend", command=self.save_and_close)
        save_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self.destroy, fg_color="gray")
        cancel_button.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Initial state update for local path entry
        self.toggle_local_path_entry()

    def toggle_local_path_entry(self):
        """Shows or hides the local storage path entry based on storage mode."""
        if self.storage_mode_var.get() == "local":
            # Show the local path frame and its contents
            self.local_path_frame.pack(pady=10, padx=10, fill="x")
        else:
            # Hide the local path frame
            self.local_path_frame.pack_forget()

    def browse_directory(self):
        """Opens a directory selection dialog for the local storage path."""
        directory = filedialog.askdirectory(title="Select Local Storage Directory", parent=self)
        if directory:
            self.local_storage_path_var.set(directory)

    def browse_model_file(self):
        """Opens a file selection dialog for the LLM model file."""
        # Define file types (adjust as needed for model formats)
        filetypes = (("GGUF files", "*.gguf"), ("All files", "*.*"))
        filepath = filedialog.askopenfilename(title="Select LLM Model File", filetypes=filetypes, parent=self)
        if filepath:
            self.llm_model_path_var.set(filepath)

    def browse_prompt_file(self):
        """Opens a file selection dialog for the system prompt file."""
        filetypes = (("Text files", "*.txt"), ("All files", "*.*"))
        filepath = filedialog.askopenfilename(title="Select System Prompt File", filetypes=filetypes, parent=self)
        if filepath:
            self.system_prompt_path_var.set(filepath)

    def authenticate_gdrive(self):
        """Triggers the Google Drive authentication flow."""
        # Get a temporary instance just for authentication
        # This assumes settings are already loaded
        temp_settings = load_settings()
        if temp_settings.get("storage_mode") != "google_drive":
             # Temporarily set mode to GDrive for auth manager creation
             temp_settings["storage_mode"] = "google_drive"
             # Note: We don't save this temporary change

        creds_file = temp_settings.get("google_drive_credentials_file", "credentials.json")
        token_file = temp_settings.get("google_drive_token_file", "token.pickle")
        folder_name = temp_settings.get("google_drive_folder_name", "Jarvis-Core History")
        history_filename = temp_settings.get("history_filename", "jarvis_chat_history.json")

        gdrive_manager = GoogleDriveStorageManager(
            credentials_file=creds_file,
            token_file=token_file,
            filename=history_filename,
            folder_name=folder_name
        )
        try:
            # Run auth in a separate thread to avoid blocking GUI
            threading.Thread(target=self._run_gdrive_auth_thread, args=(gdrive_manager,), daemon=True).start()
            messagebox.showinfo("Authentication Started", "Google Drive authentication process started. Please follow the instructions in your browser or console.", parent=self)
        except Exception as e:
            logging.error(f"Failed to start GDrive auth thread: {e}")
            messagebox.showerror("Error", f"Failed to start Google Drive authentication: {e}", parent=self)

    def _run_gdrive_auth_thread(self, gdrive_manager):
        """Worker thread for Google Drive authentication."""
        try:
            success = gdrive_manager.authenticate(force_reauth=True)
            if success:
                logging.info("Google Drive authentication successful in thread.")
                # Optionally show success message - needs careful GUI update from thread
                # self.parent.after(0, lambda: messagebox.showinfo("Success", "Google Drive authenticated successfully.", parent=self))
            else:
                logging.warning("Google Drive authentication failed or was cancelled in thread.")
                # self.parent.after(0, lambda: messagebox.showwarning("Authentication Failed", "Google Drive authentication failed or was cancelled.", parent=self))
        except Exception as e:
            logging.exception("Error during Google Drive authentication thread.")
            # self.parent.after(0, lambda: messagebox.showerror("Authentication Error", f"An error occurred during Google Drive authentication: {e}", parent=self))

    def save_and_close(self):
        """Saves all settings, notifies parent to restart backend, and closes."""
        # Track if backend restart is needed
        backend_restart_needed = False

        # --- Storage Settings ---
        new_mode = self.storage_mode_var.get()
        if self.settings.get("storage_mode") != new_mode:
            self.settings["storage_mode"] = new_mode
            backend_restart_needed = True # Storage mode change requires backend restart
            logging.info(f"Storage mode setting changed to: {new_mode}")

        new_local_path = self.local_storage_path_var.get().strip()
        # Save None if path is empty, otherwise save the path
        current_local_path = self.settings.get("local_storage_path")
        new_local_path_to_save = new_local_path if new_local_path else None
        if current_local_path != new_local_path_to_save:
            self.settings["local_storage_path"] = new_local_path_to_save
            backend_restart_needed = True # Storage path change requires backend restart
            logging.info(f"Local storage path setting changed to: {new_local_path_to_save}")

        # --- Model & Prompt Settings ---
        new_llm_path = self.llm_model_path_var.get().strip()
        current_llm_path = self.settings.get("llm_model_path")
        new_llm_path_to_save = new_llm_path if new_llm_path else None
        if current_llm_path != new_llm_path_to_save:
            self.settings["llm_model_path"] = new_llm_path_to_save
            backend_restart_needed = True # LLM path change requires backend restart
            logging.info(f"LLM model path setting changed to: {new_llm_path_to_save}")

        new_prompt_path = self.system_prompt_path_var.get().strip()
        current_prompt_path = self.settings.get("system_prompt_path")
        new_prompt_path_to_save = new_prompt_path if new_prompt_path else None
        if current_prompt_path != new_prompt_path_to_save:
            self.settings["system_prompt_path"] = new_prompt_path_to_save
            backend_restart_needed = True # Prompt path change requires backend restart
            logging.info(f"System prompt path setting changed to: {new_prompt_path_to_save}")

        # --- Save and Notify --- 
        if backend_restart_needed:
            try:
                save_settings(self.settings)
                logging.info("Settings saved successfully.")
                # Notify parent window to re-initialize the entire backend
                self.parent.reinitialize_backend()
            except Exception as e:
                logging.exception("Error saving settings.")
                messagebox.showerror("Error", f"Failed to save settings: {e}", parent=self)
                return # Don't close if save failed
        else:
            logging.info("No settings changed.")

        self.destroy() # Close the settings window

# --- Main Chat Window --- (Modified)
class ChatWindow(ctk.CTk):
    """Main chat window for the Jarvis-Core AI Agent."""

    def __init__(self):
        super().__init__()

        self.title("Jarvis-Core")
        self.geometry("700x550")

        # Configure grid layout (2 rows, 2 columns - added col for settings btn)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        # Column 1 for settings button (no weight)

        # --- Settings Button --- (New)
        self.settings_button = ctk.CTkButton(self, text="⚙️", width=30, command=self.open_settings)
        self.settings_button.grid(row=1, column=1, padx=(0, 10), pady=(5, 10), sticky="e")

        # --- Chat Display Area ---
        self.chat_display = ctk.CTkTextbox(self, state="disabled", wrap="word", font=("Arial", 12))
        self.chat_display.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="nsew") # Span 2 columns

        # --- Input Area Frame ---
        self.input_frame = ctk.CTkFrame(self, corner_radius=0)
        self.input_frame.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew") # Only in column 0
        self.input_frame.grid_columnconfigure(0, weight=1)

        # --- Input Field ---
        self.input_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Type your message here...", font=("Arial", 12))
        self.input_entry.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")
        self.input_entry.bind("<Return>", self.send_message_event)

        # --- Send Button ---
        self.send_button = ctk.CTkButton(self.input_frame, text="Send", width=70, command=self.send_message, font=("Arial", 12))
        self.send_button.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="e")

        # --- Backend Orchestrator & Storage Initialization ---
        self.orchestrator = None
        self.storage_manager = None # Use unified manager
        self.response_queue = queue.Queue()
        self.init_backend_and_storage()

        # Start checking the queue for responses
        self.after(100, self.check_response_queue)

    def init_backend_and_storage(self):
        """Initializes storage manager and backend orchestrator."""
        self.display_message("System", "Initializing storage...")
        self.storage_manager = get_storage_manager() # Initialize based on settings
        self.load_and_display_history()

        self.display_message("System", "Initializing backend AI... Please wait.")
        threading.Thread(target=self._init_orchestrator_thread, daemon=True).start()

    def reinitialize_storage(self):
        """Re-initializes the storage manager after settings change."""
        self.display_message("System", "Re-initializing storage based on new settings...")
        try:
            self.storage_manager = initialize_storage_manager(force_reinit=True)
            # Attempt authentication immediately if Google Drive is selected
            if isinstance(self.storage_manager, GoogleDriveStorageManager):
                 self.display_message("System", "Attempting Google Drive connection...")
                 auth_success = self.storage_manager.authenticate()
                 if auth_success:
                     self.display_message("System", "Google Drive connected successfully.")
                 else:
                     self.display_message("System", "Google Drive connection failed. Please check authentication via Settings.")
            else:
                 self.display_message("System", "Using local storage.")
            # Reload history from the new source
            self.clear_chat_display()
            self.load_and_display_history()
        except Exception as e:
            logging.exception("Error re-initializing storage manager.")
            self.display_message("System", f"Error switching storage: {e}")

    def load_and_display_history(self):
        """Loads history from the current storage manager and displays it."""
        if not self.storage_manager:
            logging.warning("Storage manager not initialized. Cannot load history.")
            return
        try:
            history = self.storage_manager.load_history()
            if history:
                self.display_message("System", f"Loaded {len(history)} messages from history.")
                for entry in history:
                    self.display_message(entry.get("sender", "?"), entry.get("message", ""))
            else:
                 self.display_message("System", "No previous conversation history found.")
        except Exception as e:
            logging.exception("Error loading/displaying history.")
            self.display_message("System", f"Error loading history: {e}")

    def clear_chat_display(self):
        """Clears the chat display area."""
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")

    def _init_orchestrator_thread(self):
        """Worker thread function to initialize the orchestrator."""
        try:
            self.orchestrator = Orchestrator()
            if self.orchestrator and self.orchestrator.agent:
                logging.info("Orchestrator initialized successfully in thread.")
                self.response_queue.put(("System", "Backend AI ready. How can I assist you?"))
            else:
                logging.error("Orchestrator failed to initialize properly in thread.")
                self.response_queue.put(("System", "Error: Backend AI failed to initialize. Please check logs/model file. Functionality may be limited."))
        except Exception as e:
            logging.exception("Critical error during orchestrator initialization thread.")
            self.response_queue.put(("System", f"Critical Error: Backend AI failed: {e}"))

    def send_message_event(self, event):
        self.send_message()

    def send_message(self):
        user_input = self.input_entry.get()
        if not user_input.strip(): return

        self.display_message("You", user_input)
        # Save message using the current storage manager
        if self.storage_manager:
            self.storage_manager.save_message("You", user_input)

        self.input_entry.delete(0, "end")

        if self.orchestrator and self.orchestrator.agent:
            self.input_entry.configure(state="disabled")
            self.send_button.configure(state="disabled")
            self.display_message("System", "Processing...")
            threading.Thread(target=self._get_backend_response_thread, args=(user_input,), daemon=True).start()
        else:
            self.display_message("System", "Error: Backend AI is not available.")
            # Save a placeholder response if backend fails
            if self.storage_manager:
                self.storage_manager.save_message("System", "Error: Backend AI is not available.")

    def _get_backend_response_thread(self, user_input: str):
        response = "Error: Processing failed."
        try:
            response = self.orchestrator.route_command(user_input)
            self.response_queue.put(("Jarvis", response))
        except Exception as e:
            logging.exception("Error getting response from orchestrator thread.")
            response = f"Error processing request: {e}"
            self.response_queue.put(("System", response))
        finally:
            # Save Jarvis/System response
            if self.storage_manager:
                sender = "Jarvis" if "Error" not in response else "System"
                self.storage_manager.save_message(sender, response)

    def check_response_queue(self):
        try:
            while True:
                sender, message = self.response_queue.get_nowait()
                # Re-enable input after response or error
                self.input_entry.configure(state="normal")
                self.send_button.configure(state="normal")
                # Remove "Processing..." message - simplistic approach:
                # If the last message was "Processing...", remove it before adding new one.
                # This requires reading the last line, which is complex in Text widget.
                # For now, we just display the new message.
                self.display_message(sender, message)
        except queue.Empty:
            pass
        finally:
            self.after(100, self.check_response_queue)

    def display_message(self, sender: str, message: str):
        try:
            self.chat_display.configure(state="normal")
            formatted_message = f"{sender}: {message}\n\n"
            self.chat_display.insert("end", formatted_message)
            self.chat_display.configure(state="disabled")
            self.chat_display.see("end")
        except Exception as e:
            logging.error(f"Error displaying message: {e}")

    def open_settings(self):
        """Opens the settings window."""
        settings_win = SettingsWindow(self)

# --- Main Execution ---
if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    logging.info("Starting Jarvis-Core GUI...")
    app = ChatWindow()
    app.mainloop()
    logging.info("Jarvis-Core GUI closed.")

