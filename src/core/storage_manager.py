import json
import os
import logging
from pathlib import Path
from datetime import datetime
# Removed pickle import
import io
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
# Import Credentials for JSON handling
from google.oauth2.credentials import Credentials 
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - Storage - %(message)s")

# --- Configuration Loading ---
def load_settings():
    """Loads settings from config/settings.json."""
    settings_path = Path(__file__).resolve().parent.parent.parent / "config" / "settings.json"
    default_settings = {
        "storage_mode": "local",
        "local_storage_path": None, # Default to null, meaning use default path
        "google_drive_credentials_file": "credentials.json",
        # Updated default token filename
        "google_drive_token_file": "token.json", 
        "google_drive_folder_name": "Jarvis-Core History",
        "history_filename": "jarvis_chat_history.json",
        "llm_model_path": None, # Default to null, meaning use model selection logic
        "system_prompt_path": None # Default to null, meaning use default prompt path
    }
    if not settings_path.exists():
        logging.warning(f"Settings file not found at {settings_path}. Using default settings.")
        # Ensure config directory exists before potentially saving defaults later
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        return default_settings
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            loaded_settings = json.load(f)
            # Merge with defaults to ensure all keys are present
            default_settings.update(loaded_settings)
            # Ensure token filename default is updated if loaded from old settings
            if default_settings.get("google_drive_token_file") == "token.pickle":
                logging.warning("Updating default token filename from token.pickle to token.json in loaded settings.")
                default_settings["google_drive_token_file"] = "token.json"
            return default_settings
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error loading settings from {settings_path}: {e}. Using default settings.")
        return default_settings

def save_settings(settings: dict):
    """Saves settings to config/settings.json."""
    settings_path = Path(__file__).resolve().parent.parent.parent / "config" / "settings.json"
    try:
        # Ensure config directory exists
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        logging.info(f"Saved settings to {settings_path}")
    except IOError as e:
        logging.error(f"Error saving settings to {settings_path}: {e}")

# --- Local Storage Manager ---
class LocalStorageManager:
    """Manages saving and loading conversation history to a local JSON file."""

    def __init__(self, filename="jarvis_chat_history.json", storage_path=None):
        """Initializes the LocalStorageManager.

        Args:
            filename (str): The name of the history file.
            storage_path (str | Path | None): The custom directory path to store history.
                                              If None, uses default ~/.jarvis-core/history.
        """
        if storage_path:
            try:
                # Attempt to resolve the provided path
                custom_path = Path(storage_path).resolve()
                self.history_dir = custom_path
                logging.info(f"Using custom local storage path: {self.history_dir}")
            except Exception as e:
                logging.error(f"Invalid custom storage path \"{storage_path}\": {e}. Falling back to default.")
                self.history_dir = Path.home() / ".jarvis-core" / "history"
        else:
            # Default path
            self.history_dir = Path.home() / ".jarvis-core" / "history"
            logging.info("Using default local storage path.")

        try:
            self.history_dir.mkdir(parents=True, exist_ok=True)
            self.filepath = self.history_dir / filename
            logging.info(f"LocalStorageManager initialized. History file path: {self.filepath}")
        except Exception as e:
            logging.error(f"Failed to create history directory or set filepath {self.history_dir / filename}: {e}", exc_info=True)
            # Attempt to set filepath even if mkdir failed, maybe permissions issue later
            self.filepath = self.history_dir / filename

    def save_message(self, sender: str, message: str):
        """Appends a message entry to the local history file."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "sender": sender,
            "message": message
        }
        try:
            history = self._load_raw_history()
            history.append(entry)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4, ensure_ascii=False)
        except IOError as e:
            logging.error(f"IOError saving message to {self.filepath}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error saving message: {e}", exc_info=True)

    def load_history(self) -> list[dict]:
        """Loads the entire conversation history from the local file."""
        logging.info(f"Loading history from {self.filepath}")
        return self._load_raw_history()

    def _load_raw_history(self) -> list[dict]:
        """Helper function to load raw history list from JSON file."""
        if not self.filepath.exists():
            logging.warning(f"History file {self.filepath} not found. Returning empty history.")
            return []
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip(): return []
                history = json.loads(content)
                if not isinstance(history, list): return []
                return history
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Error loading/parsing history from {self.filepath}: {e}. Returning empty history.")
            return []
        except Exception as e:
            logging.error(f"Unexpected error loading history: {e}", exc_info=True)
            return []

    def authenticate(self):
        """Placeholder for compatibility with the unified interface."""
        logging.info("Local storage does not require authentication.")
        return True # Always considered authenticated

# --- Google Drive Storage Manager ---
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

class GoogleDriveStorageManager:
    """Manages saving and loading conversation history to Google Drive."""

    # Updated default token filename
    def __init__(self, credentials_file="credentials.json", token_file="token.json", filename="jarvis_chat_history.json", folder_name="Jarvis-Core History"):
        # Ensure .jarvis-core directory exists
        self.dot_jarvis_dir = Path.home() / ".jarvis-core"
        self.dot_jarvis_dir.mkdir(parents=True, exist_ok=True)
        
        self.token_path = self.dot_jarvis_dir / token_file
        self.credentials_path_str = os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE", credentials_file)
        # Resolve credentials path relative to .jarvis-core if not absolute
        self.credentials_path = Path(self.credentials_path_str)
        if not self.credentials_path.is_absolute():
            self.credentials_path = (self.dot_jarvis_dir / self.credentials_path).resolve()
        else:
            self.credentials_path = self.credentials_path.resolve()
            
        self.filename = filename
        self.folder_name = folder_name
        self.service = None
        self.file_id = None
        logging.info(f"Initializing GoogleDriveStorageManager. Credentials: {self.credentials_path}, Token: {self.token_path}")
        # Authentication is now triggered explicitly via authenticate()

    def authenticate(self, force_reauth=False) -> bool:
        """Authenticates the user with Google Drive API using OAuth 2.0."""
        creds = None
        if not force_reauth and self.token_path.exists():
            try:
                # Load token from JSON
                with open(self.token_path, "r", encoding="utf-8") as token:
                    creds_info = json.load(token)
                    creds = Credentials.from_authorized_user_info(creds_info, SCOPES)
                logging.info("Loaded existing Google Drive token from JSON.")
            except (json.JSONDecodeError, IOError, ValueError) as e:
                logging.warning(f"Error loading token file {self.token_path}: {e}. Will re-authenticate.")
                creds = None
            except Exception as e:
                logging.error(f"Unexpected error loading token: {e}", exc_info=True)
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logging.info("Refreshing expired Google Drive token.")
                    creds.refresh(Request())
                except Exception as e:
                    logging.error(f"Failed to refresh token: {e}. Need full re-authentication.")
                    creds = None
            else:
                logging.info("No valid Google Drive token found or re-auth forced. Starting OAuth flow.")
                if not self.credentials_path.exists():
                    logging.error(f"Credentials file not found at {self.credentials_path}. Cannot authenticate.")
                    print(f"ERROR: Google Drive credentials file ({self.credentials_path}) not found.")
                    print("Please download your OAuth 2.0 Client ID credentials and place the file correctly.")
                    return False
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                    print("\n-- Google Drive Authentication Required --")
                    print("Please follow the instructions in the browser/console to authorize Jarvis-Core.")
                    creds = flow.run_local_server(port=0)
                    print("-- Authentication Successful --\n")
                    logging.info("OAuth flow completed successfully.")
                except Exception as e:
                    logging.error(f"Error during OAuth flow: {e}", exc_info=True)
                    print(f"ERROR: Google Drive authentication failed: {e}")
                    return False
            if creds:
                try:
                    # Save token as JSON
                    with open(self.token_path, "w", encoding="utf-8") as token:
                        # Use Credentials.to_json() which returns a string, then parse and dump
                        token_data = json.loads(creds.to_json())
                        json.dump(token_data, token, indent=4)
                    logging.info(f"Saved new Google Drive token to {self.token_path}")
                except (IOError, json.JSONDecodeError) as e:
                    logging.error(f"Error saving token: {e}", exc_info=True)
                except Exception as e:
                    logging.error(f"Unexpected error saving token: {e}", exc_info=True)

        if creds:
            try:
                self.service = build("drive", "v3", credentials=creds)
                logging.info("Google Drive service built successfully.")
                self._ensure_file_exists() # Ensure file exists after successful auth
                return True
            except Exception as e:
                logging.error(f"Failed to build Google Drive service: {e}", exc_info=True)
                self.service = None
                return False
        else:
            logging.error("Failed to obtain Google Drive credentials.")
            self.service = None
            return False

    def _find_or_create_folder(self):
        """Finds the specified folder or creates it if it doesn't exist. Returns folder ID."""
        if not self.service:
            return None
        try:
            query = f"mimeType='application/vnd.google-apps.folder' and name='{self.folder_name}' and trashed=false"
            response = self.service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
            folders = response.get("files", [])

            if folders:
                folder_id = folders[0].get("id")
                logging.info(f"Found existing folder '{self.folder_name}' with ID: {folder_id}")
                return folder_id
            else:
                logging.info(f"Folder '{self.folder_name}' not found. Creating...")
                file_metadata = {
                    "name": self.folder_name,
                    "mimeType": "application/vnd.google-apps.folder"
                }
                folder = self.service.files().create(body=file_metadata, fields="id").execute()
                folder_id = folder.get("id")
                logging.info(f"Created folder '{self.folder_name}' with ID: {folder_id}")
                return folder_id
        except Exception as e:
            logging.error(f"Error finding or creating folder '{self.folder_name}': {e}", exc_info=True)
            return None

    def _ensure_file_exists(self):
        """Finds the history file ID within the folder, creating the file if necessary."""
        if not self.service:
            return
        folder_id = self._find_or_create_folder()
        if not folder_id:
            logging.error("Cannot ensure file exists without a valid folder ID.")
            return

        try:
            query = f"name='{self.filename}' and '{folder_id}' in parents and trashed=false"
            response = self.service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
            files = response.get("files", [])

            if files:
                self.file_id = files[0].get("id")
                logging.info(f"Found existing history file '{self.filename}' with ID: {self.file_id}")
            else:
                logging.info(f"History file '{self.filename}' not found in folder. Creating...")
                file_metadata = {
                    "name": self.filename,
                    "parents": [folder_id]
                }
                media = MediaFileUpload(io.BytesIO(b"[]"), mimetype="application/json", resumable=True)
                file = self.service.files().create(body=file_metadata,
                                               media_body=media,
                                               fields="id").execute()
                self.file_id = file.get("id")
                logging.info(f"Created history file '{self.filename}' with ID: {self.file_id}")
        except Exception as e:
            logging.error(f"Error finding or creating file '{self.filename}': {e}", exc_info=True)
            self.file_id = None

    def save_message(self, sender: str, message: str):
        """Appends a message entry to the history file on Google Drive."""
        if not self.service or not self.file_id:
            logging.error("Google Drive service not available or file ID not set. Cannot save message.")
            return
        entry = {
            "timestamp": datetime.now().isoformat(),
            "sender": sender,
            "message": message
        }
        try:
            history = self._download_history()
            history.append(entry)
            updated_content = json.dumps(history, indent=4, ensure_ascii=False).encode("utf-8")
            media = MediaFileUpload(io.BytesIO(updated_content), mimetype="application/json", resumable=True)
            self.service.files().update(fileId=self.file_id, media_body=media).execute()
        except Exception as e:
            logging.error(f"Error saving message to Google Drive: {e}", exc_info=True)

    def load_history(self) -> list[dict]:
        """Loads the entire conversation history from the file on Google Drive."""
        logging.info(f"Loading history from Google Drive file ID: {self.file_id}")
        if not self.service or not self.file_id:
            logging.error("Google Drive service not available or file ID not set. Cannot load history.")
            return []
        return self._download_history()

    def _download_history(self) -> list[dict]:
        """Helper function to download and parse history from Google Drive."""
        try:
            request = self.service.files().get_media(fileId=self.file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            fh.seek(0)
            content = fh.read().decode("utf-8")
            if not content.strip(): return []
            history = json.loads(content)
            if not isinstance(history, list): return []
            return history
        except (json.JSONDecodeError, Exception) as e:
            logging.error(f"Error downloading/parsing history from Google Drive: {e}", exc_info=True)
            return []

# --- Unified Storage Factory ---

# Global instance to hold the current storage manager
_current_storage_manager = None

def get_storage_manager():
    """Factory function to get the currently configured storage manager instance."""
    global _current_storage_manager
    if _current_storage_manager is None:
        initialize_storage_manager() # Ensure initialization if accessed directly
    return _current_storage_manager

def initialize_storage_manager():
    """Initializes or re-initializes the storage manager based on current settings."""
    global _current_storage_manager
    settings = load_settings()
    mode = settings.get("storage_mode", "local")
    history_filename = settings.get("history_filename", "jarvis_chat_history.json")
    
    logging.info(f"Initializing storage manager in '{mode}' mode.")

    if mode == "google_drive":
        creds_file = settings.get("google_drive_credentials_file", "credentials.json")
        token_file = settings.get("google_drive_token_file", "token.json") # Use updated default
        folder_name = settings.get("google_drive_folder_name", "Jarvis-Core History")
        _current_storage_manager = GoogleDriveStorageManager(
            credentials_file=creds_file,
            token_file=token_file,
            filename=history_filename,
            folder_name=folder_name
        )
        # Trigger authentication immediately upon initialization for GDrive
        # Run in a thread to avoid blocking if called from main thread
        auth_thread = threading.Thread(target=_current_storage_manager.authenticate, daemon=True)
        auth_thread.start()
        # Note: We don't wait for auth here; operations will fail until auth completes
        
    else: # Default to local
        local_path = settings.get("local_storage_path") # Can be None
        _current_storage_manager = LocalStorageManager(
            filename=history_filename,
            storage_path=local_path
        )
        # Local storage doesn't need explicit authentication
        _current_storage_manager.authenticate() # Call for consistency, logs message

    return _current_storage_manager

# Initialize on module load
# initialize_storage_manager() # Defer initialization until needed by GUI or Orchestrator

