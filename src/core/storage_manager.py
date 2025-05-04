import json
import os
import logging
from pathlib import Path
from datetime import datetime
import io
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials # Import Credentials for loading
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from dotenv import load_dotenv

# Import the new utility function
from src.utils.resource_path import get_resource_path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - Storage - %(message)s")

# Define base directories using the utility function or standard paths
PROJECT_ROOT = get_resource_path(".") # Get project root dynamically
USER_CONFIG_DIR = Path.home() / ".jarvis-core"
ALLOWED_CREDENTIAL_DIRS = [PROJECT_ROOT, USER_CONFIG_DIR]

def is_safe_credential_path(path_str: str, resolved_path: Path) -> bool:
    """Checks if the resolved credentials path is within allowed directories."""
    if ".." in path_str:
        logging.warning(f"Potential path traversal attempt detected in credential path input: {path_str}")
        return False
    try:
        # Check if the resolved path is within any of the allowed directories
        is_safe = any(resolved_path.is_relative_to(allowed_dir) for allowed_dir in ALLOWED_CREDENTIAL_DIRS)
        if not is_safe:
            # Allow if the path *is* one of the allowed dirs itself (e.g., reading creds from project root)
            is_safe = any(resolved_path == allowed_dir for allowed_dir in ALLOWED_CREDENTIAL_DIRS)
            
        if not is_safe:
            # Allow absolute paths outside project/user config if they don't contain '..'
            # This allows users to place credentials anywhere, but warns if relative traversal is used.
            # Check if path_str is absolute and doesn't contain '..'
            if Path(path_str).is_absolute():
                 logging.info(f"Allowing absolute credential path outside standard directories: {resolved_path}")
                 is_safe = True # Allow absolute paths specified by user
            else:
                 logging.warning(f"Resolved credential path {resolved_path} is outside allowed directories: {ALLOWED_CREDENTIAL_DIRS}")
                 return False
    except ValueError:
        logging.warning(f"Credential path {resolved_path} could not be verified relative to allowed directories.")
        # Allow absolute paths here too?
        if Path(path_str).is_absolute() and ".." not in path_str:
            logging.info(f"Allowing absolute credential path after ValueError: {resolved_path}")
            is_safe = True
        else:
            return False
    except Exception as e:
        logging.error(f"Error checking credential path safety for {resolved_path}: {e}", exc_info=True)
        return False
    return is_safe

# --- Configuration Loading ---
def load_settings():
    """Loads settings from config/settings.json using resource path helper."""
    settings_path = get_resource_path("config/settings.json")
    default_settings = {
        "storage_mode": "local",
        "local_storage_path": None,
        "google_drive_credentials_file": "credentials.json", # User's OAuth client ID file
        "google_drive_token_file": "token.json", # Changed from .pickle to .json
        "google_drive_folder_name": "Jarvis-Core History",
        "history_filename": "jarvis_chat_history.json",
        "llm_model_path": None,
        "system_prompt_path": None
    }
    if not settings_path.exists():
        logging.warning(f"Settings file not found at {settings_path}. Using default settings.")
        return default_settings
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            loaded_settings = json.load(f)
            # Merge with defaults to ensure all keys are present
            default_settings.update(loaded_settings)
            # Ensure token file uses .json if loaded from old settings
            if default_settings.get("google_drive_token_file", "").endswith(".pickle"):
                logging.warning("Updating token file extension from .pickle to .json in loaded settings.")
                default_settings["google_drive_token_file"] = "token.json"
            return default_settings
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error loading settings from {settings_path}: {e}. Using default settings.")
        # Ensure default token file is .json even on error
        default_settings["google_drive_token_file"] = "token.json"
        return default_settings

def save_settings(settings: dict):
    """Saves settings to config/settings.json using resource path helper."""
    settings_path = get_resource_path("config/settings.json")
    try:
        # Ensure token file is .json before saving
        if settings.get("google_drive_token_file", "").endswith(".pickle"):
            settings["google_drive_token_file"] = "token.json"
            
        # Ensure config directory exists before saving
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        logging.info(f"Saved settings to {settings_path}")
    except IOError as e:
        logging.error(f"Error saving settings to {settings_path}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error saving settings: {e}", exc_info=True)

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
                # Basic safety check for custom local path (could be enhanced)
                if ".." in str(storage_path):
                     raise ValueError("Path traversal attempt detected in custom local storage path.")
                # Maybe restrict to home directory subfolders? For now, just resolve.
                self.history_dir = custom_path
                logging.info(f"Using custom local storage path: {self.history_dir}")
            except Exception as e:
                logging.error(f"Invalid custom storage path \"{storage_path}\": {e}. Falling back to default.")
                self.history_dir = USER_CONFIG_DIR / "history"
        else:
            # Default path
            self.history_dir = USER_CONFIG_DIR / "history"
            logging.info("Using default local storage path.")

        try:
            self.history_dir.mkdir(parents=True, exist_ok=True)
            self.filepath = self.history_dir / filename
            logging.info(f"LocalStorageManager initialized. History file path: {self.filepath}")
        except Exception as e:
            logging.error(f"Failed to create history directory or set filepath {self.history_dir / filename}: {e}", exc_info=True)
            self.filepath = self.history_dir / filename # Attempt to set anyway

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

    def __init__(self, credentials_file="credentials.json", token_file="token.json", filename="jarvis_chat_history.json", folder_name="Jarvis-Core History"):
        # Ensure token file is .json
        if token_file.endswith(".pickle"):
            token_file = "token.json"
            
        self.token_path = USER_CONFIG_DIR / token_file
        self.credentials_path_str = os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE", credentials_file)
        
        # --- Security Check for Credentials Path ---
        # Resolve the path relative to project root if not absolute, then check safety
        try:
            potential_path = Path(self.credentials_path_str)
            if not potential_path.is_absolute():
                # If relative, assume it's relative to project root (or bundled equivalent)
                resolved_creds_path = get_resource_path(self.credentials_path_str)
            else:
                resolved_creds_path = potential_path.resolve()

            if not is_safe_credential_path(self.credentials_path_str, resolved_creds_path):
                 # If safety check fails, log error and use a default safe path
                 logging.error(f"Credentials path 	\'{self.credentials_path_str}	\' resolved to 	\'{resolved_creds_path}	\' which is outside allowed directories or invalid. Using default path.")
                 self.credentials_path = get_resource_path("credentials.json") # Default relative to project root
            else:
                 self.credentials_path = resolved_creds_path
                 
        except Exception as e:
            logging.error(f"Error resolving or validating credentials path 	\'{self.credentials_path_str}\	': {e}. Using default path.")
            self.credentials_path = get_resource_path("credentials.json") # Fallback to a safe default
        # --- End Security Check ---
            
        self.filename = filename
        self.folder_name = folder_name
        self.service = None
        self.file_id = None
        logging.info(f"Initializing GoogleDriveStorageManager. Credentials: {self.credentials_path}, Token: {self.token_path}")

    def authenticate(self, force_reauth=False) -> bool:
        """Authenticates the user with Google Drive API using OAuth 2.0. Uses JSON token storage."""
        creds = None
        # Ensure token directory exists
        try:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logging.error(f"Failed to create directory for token file {self.token_path}: {e}")
            # Continue, maybe token exists anyway or user has permissions

        if not force_reauth and self.token_path.exists():
            try:
                # Load credentials from JSON file
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
                logging.info("Loaded existing Google Drive token from JSON.")
            except Exception as e:
                logging.warning(f"Error loading token file {self.token_path}: {e}. Will re-authenticate.")
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logging.info("Refreshing expired Google Drive token.")
                    creds.refresh(Request())
                    # Save the refreshed token
                    try:
                        with open(self.token_path, "w", encoding="utf-8") as token_file:
                            token_file.write(creds.to_json())
                        logging.info(f"Saved refreshed Google Drive token to {self.token_path}")
                    except Exception as e:
                        logging.error(f"Error saving refreshed token: {e}", exc_info=True)
                except Exception as e:
                    logging.error(f"Failed to refresh token: {e}. Need full re-authentication.")
                    creds = None # Ensure re-auth happens
                    # Attempt to delete potentially corrupted token file
                    try:
                        self.token_path.unlink(missing_ok=True)
                    except OSError as unlink_e:
                        logging.error(f"Failed to delete invalid token file {self.token_path}: {unlink_e}")
            else:
                logging.info("No valid Google Drive token found or re-auth forced. Starting OAuth flow.")
                if not self.credentials_path.exists():
                    logging.error(f"Credentials file not found at {self.credentials_path}. Cannot authenticate.")
                    print(f"ERROR: Google Drive credentials file ({self.credentials_path}) not found.")
                    print("Please download your OAuth 2.0 Client ID credentials and place the file correctly.")
                    return False
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                    print("\n-- Google Drive Authentication Required --")
                    print("Please follow the instructions in the browser/console to authorize Jarvis-Core.")
                    creds = flow.run_local_server(port=0)
                    print("-- Authentication Successful --\n")
                    logging.info("OAuth flow completed successfully.")
                except FileNotFoundError:
                    logging.error(f"Credentials file not found at {self.credentials_path} during OAuth flow.")
                    print(f"ERROR: Google Drive credentials file ({self.credentials_path}) not found.")
                    return False
                except Exception as e:
                    logging.error(f"Error during OAuth flow: {e}", exc_info=True)
                    print(f"ERROR: Google Drive authentication failed: {e}")
                    return False
                
            # Save the new credentials if obtained through flow
            if creds and (not self.token_path.exists() or force_reauth or not creds.refresh_token): # Save if new or forced
                try:
                    with open(self.token_path, "w", encoding="utf-8") as token_file:
                        token_file.write(creds.to_json())
                    logging.info(f"Saved new Google Drive token to {self.token_path}")
                except Exception as e:
                    logging.error(f"Error saving new token: {e}", exc_info=True)

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
        """Finds the specified folder or creates it if it doesn\t exist. Returns folder ID."""
        if not self.service:
            return None
        try:
            query = f"mimeType=\'application/vnd.google-apps.folder\' and name=\'{self.folder_name}\' and trashed=false"
            response = self.service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
            folders = response.get("files", [])

            if folders:
                folder_id = folders[0].get("id")
                logging.info(f"Found existing folder 	\'{self.folder_name}	\\' with ID: {folder_id}")
                return folder_id
            else:
                logging.info(f"Folder 	\'{self.folder_name}	\\' not found. Creating...")
                file_metadata = {
                    "name": self.folder_name,
                    "mimeType": "application/vnd.google-apps.folder"
                }
                folder = self.service.files().create(body=file_metadata, fields="id").execute()
                folder_id = folder.get("id")
                logging.info(f"Created folder 	\'{self.folder_name}	\\' with ID: {folder_id}")
                return folder_id
        except Exception as e:
            logging.error(f"Error finding or creating folder 	\'{self.folder_name}\	': {e}", exc_info=True)
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
            query = f"name=\'{self.filename}\' and 	\'{folder_id}	\\' in parents and trashed=false"
            response = self.service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
            files = response.get("files", [])

            if files:
                self.file_id = files[0].get("id")
                logging.info(f"Found existing history file 	\'{self.filename}	\\' with ID: {self.file_id}")
            else:
                logging.info(f"History file 	\'{self.filename}	\\' not found in folder. Creating...")
                file_metadata = {
                    "name": self.filename,
                    "parents": [folder_id]
                }
                # Create an empty JSON array as initial content
                media = MediaFileUpload(io.BytesIO(b"[]"), mimetype="application/json", resumable=True)
                file = self.service.files().create(body=file_metadata,
                                               media_body=media,
                                               fields="id").execute()
                self.file_id = file.get("id")
                logging.info(f"Created history file 	\'{self.filename}	\\' with ID: {self.file_id}")
        except Exception as e:
            logging.error(f"Error finding or creating file 	\'{self.filename}\	': {e}", exc_info=True)
            self.file_id = None

    def save_message(self, sender: str, message: str):
        """Appends a message entry to the history file on Google Drive."""
        if not self.service or not self.file_id:
            # Attempt re-authentication if service/file_id is missing
            logging.warning("Google Drive service/file_id missing. Attempting re-authentication before saving.")
            if not self.authenticate():
                logging.error("Re-authentication failed. Cannot save message to Google Drive.")
                return
            if not self.file_id:
                 logging.error("File ID still missing after re-authentication. Cannot save message.")
                 return
                 
        entry = {
            "timestamp": datetime.now().isoformat(),
            "sender": sender,
            "message": message
        }
        try:
            history = self._download_history() # Get current history
            history.append(entry)
            updated_content = json.dumps(history, indent=4, ensure_ascii=False).encode("utf-8")
            media = MediaFileUpload(io.BytesIO(updated_content), mimetype="application/json", resumable=True)
            self.service.files().update(fileId=self.file_id, media_body=media).execute()
            logging.info(f"Saved message to Google Drive file ID: {self.file_id}")
        except Exception as e:
            logging.error(f"Error saving message to Google Drive: {e}", exc_info=True)

    def load_history(self) -> list[dict]:
        """Loads the entire conversation history from the file on Google Drive."""
        if not self.service or not self.file_id:
            # Attempt re-authentication if service/file_id is missing
            logging.warning("Google Drive service/file_id missing. Attempting re-authentication before loading.")
            if not self.authenticate():
                logging.error("Re-authentication failed. Cannot load history from Google Drive.")
                return []
            if not self.file_id:
                 logging.error("File ID still missing after re-authentication. Cannot load history.")
                 return []
                 
        logging.info(f"Loading history from Google Drive file ID: {self.file_id}")
        return self._download_history()

    def _download_history(self) -> list[dict]:
        """Helper function to download and parse history from Google Drive."""
        if not self.service or not self.file_id:
             logging.error("Cannot download history: Google Drive service or file ID missing.")
             return []
        try:
            request = self.service.files().get_media(fileId=self.file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                # logging.debug(f"Download {int(status.progress() * 100)}%.") # Optional progress
            fh.seek(0)
            content = fh.read().decode("utf-8")
            if not content.strip(): return []
            history = json.loads(content)
            if not isinstance(history, list): 
                logging.warning(f"Downloaded history from GDrive is not a list: {type(history)}. Returning empty list.")
                return []
            return history
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON history from Google Drive: {e}. Content: 	\'{content[:100]}...	\\'", exc_info=True)
            return []
        except Exception as e:
            # Catch specific API errors if possible, e.g., HttpError from googleapiclient.errors
            logging.error(f"Error downloading/parsing history from Google Drive: {e}", exc_info=True)
            return []

# --- Unified Storage Factory ---

# Global instance to hold the current storage manager
_current_storage_manager = None

def get_storage_manager():
    """Factory function to get the currently configured storage manager instance."""
    global _current_storage_manager
    if _current_storage_manager is None:
        _current_storage_manager = initialize_storage_manager()
    return _current_storage_manager

def initialize_storage_manager(force_reinit=False):
    """Initializes the storage manager based on settings. Returns the instance."""
    global _current_storage_manager
    if _current_storage_manager is not None and not force_reinit:
        return _current_storage_manager

    settings = load_settings()
    storage_mode = settings.get("storage_mode", "local")
    filename = settings.get("history_filename", "jarvis_chat_history.json")

    logging.info(f"Initializing storage manager in 	\'{storage_mode}	\\' mode.")

    if storage_mode == "google_drive":
        creds_file = settings.get("google_drive_credentials_file", "credentials.json")
        token_file = settings.get("google_drive_token_file", "token.json") # Ensure .json
        folder_name = settings.get("google_drive_folder_name", "Jarvis-Core History")
        manager = GoogleDriveStorageManager(
            credentials_file=creds_file,
            token_file=token_file,
            filename=filename,
            folder_name=folder_name
        )
        # Trigger authentication immediately upon initialization for GDrive
        if not manager.authenticate():
            logging.warning("Google Drive authentication failed during initialization. Falling back to local storage.")
            # Fallback to local storage
            custom_local_path = settings.get("local_storage_path")
            manager = LocalStorageManager(filename=filename, storage_path=custom_local_path)
    else: # Default to local storage
        custom_local_path = settings.get("local_storage_path")
        manager = LocalStorageManager(filename=filename, storage_path=custom_local_path)

    _current_storage_manager = manager
    return manager

# Example usage:
if __name__ == "__main__":
    print("Initializing storage manager based on settings...")
    storage = initialize_storage_manager(force_reinit=True)
    print(f"Storage manager type: {type(storage).__name__}")

    if isinstance(storage, GoogleDriveStorageManager):
        print("Attempting to authenticate Google Drive (if not already done)...")
        # Use force_reauth=True for testing the auth flow
        # if storage.authenticate(force_reauth=True):
        if storage.authenticate():
            print("Google Drive authenticated.")
            print("Saving test message to Google Drive...")
            storage.save_message("System", "Test message saved via GDrive.")
            print("Loading history from Google Drive...")
            history = storage.load_history()
            print(f"Loaded {len(history)} entries from Google Drive.")
            if history:
                print("Last entry:", history[-1])
        else:
            print("Google Drive authentication failed.")
    elif isinstance(storage, LocalStorageManager):
        print("Saving test message to local file...")
        storage.save_message("System", "Test message saved locally.")
        print("Loading history from local file...")
        history = storage.load_history()
        print(f"Loaded {len(history)} entries from local file.")
        if history:
            print("Last entry:", history[-1])

    print("Storage manager test finished.")

