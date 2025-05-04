import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime

# Modules to test
from src.core.storage_manager import (
    LocalStorageManager,
    GoogleDriveStorageManager,
    load_settings,
    save_settings,
    get_storage_manager,
    initialize_storage_manager,
    SCOPES
)

# --- Test Fixtures ---
@pytest.fixture
def mock_settings_file(tmp_path):
    settings_dir = tmp_path / "config"
    settings_dir.mkdir()
    settings_file = settings_dir / "settings.json"
    default_settings = {
        "storage_mode": "local",
        "google_drive_credentials_file": "creds.json",
        "google_drive_token_file": "tok.pickle",
        "google_drive_folder_name": "Test Folder",
        "history_filename": "test_history.json"
    }
    settings_file.write_text(json.dumps(default_settings))
    return settings_file

@pytest.fixture
def mock_home_dir(tmp_path):
    home = tmp_path / "user_home"
    home.mkdir()
    jarvis_dir = home / ".jarvis-core"
    jarvis_dir.mkdir()
    history_dir = jarvis_dir / "history"
    history_dir.mkdir()
    return home

# --- Test load_settings & save_settings ---

@patch("src.core.storage_manager.Path")
@patch("pathlib.Path.exists") # Patch exists globally
@patch("builtins.open", new_callable=mock_open)
def test_load_settings_success(mock_file_open, mock_exists, mock_path, mock_settings_file):
    """Test loading settings from an existing file."""
    # Mock Path().resolve().parent.parent to point to tmp_path
    settings_path_obj = mock_settings_file.parent.parent / "config" / "settings.json"
    mock_path.return_value.resolve.return_value.parent.parent.__truediv__.return_value.__truediv__.return_value = settings_path_obj
    # Configure mock_exists
    mock_exists.side_effect = lambda *args: args[0] == settings_path_obj if args and isinstance(args[0], Path) else False
    # Configure mock_open to read the content of mock_settings_file
    mock_file_open.return_value.read.return_value = mock_settings_file.read_text()

    settings = load_settings()

    # Assertions
    mock_exists.assert_called_with(settings_path_obj)
    mock_file_open.assert_called_once_with(settings_path_obj, "r", encoding="utf-8")
    assert settings["storage_mode"] == "local"
    assert settings["history_filename"] == "test_history.json" # Should now match the file

@patch("src.core.storage_manager.Path")
@patch("pathlib.Path.exists") # Patch exists globally
def test_load_settings_file_not_found(mock_exists, mock_path, tmp_path):
    """Test loading settings when the file doesn\t exist."""
    settings_path_obj = tmp_path / "config" / "settings.json"
    mock_path.return_value.resolve.return_value.parent.parent.__truediv__.return_value.__truediv__.return_value = settings_path_obj
    # Configure mock_exists to always return False
    mock_exists.return_value = False

    settings = load_settings()
    assert settings["storage_mode"] == "local" # Default value
    assert "google_drive_credentials_file" in settings # Default key exists

@patch("src.core.storage_manager.Path")
@patch("pathlib.Path.exists") # Patch exists globally
def test_load_settings_invalid_json(mock_exists, mock_path, tmp_path):
    """Test loading settings from a file with invalid JSON."""
    settings_dir = tmp_path / "config"
    settings_dir.mkdir()
    settings_file = settings_dir / "settings.json"
    settings_file.write_text("invalid json")

    settings_path_obj = tmp_path / "config" / "settings.json"
    mock_path.return_value.resolve.return_value.parent.parent.__truediv__.return_value.__truediv__.return_value = settings_path_obj
       # Configure mock_exists to return True for the settings file
    mock_exists.side_effect = lambda *args: args[0] == settings_path_obj if args and isinstance(args[0], Path) else Falseath_obj if args and isinstance(args[0], Path) else False

    settings = load_settings()
    assert settings["storage_mode"] == "local" # Default value

@patch("src.core.storage_manager.Path")
@patch("builtins.open", new_callable=mock_open)
@patch("json.dump")
def test_save_settings(mock_json_dump, mock_file_open, mock_path, tmp_path):
    """Test saving settings to a file."""
    # Define the expected path object
    settings_path_obj = tmp_path / "config" / "settings.json"

    # Mock the Path object construction within save_settings
    # When Path(__file__) is called, make it return a mock
    # that leads to settings_path_obj after resolve().parent.parent...
    mock_path_instance = MagicMock()
    # Ensure the chained calls return the final path object
    mock_path_instance.resolve.return_value.parent.parent.__truediv__.return_value.__truediv__.return_value = settings_path_obj
    mock_path.return_value = mock_path_instance # Mock Path(__file__)

    new_settings = {"storage_mode": "google_drive", "history_filename": "new_hist.json"}
    save_settings(new_settings)

    # Check that open was called with the correct path object
    mock_file_open.assert_called_once_with(settings_path_obj, "w", encoding="utf-8")
    mock_json_dump.assert_called_once_with(new_settings, mock_file_open(), indent=4, ensure_ascii=False)
# --- Test LocalStorageManager ---

@patch("src.core.storage_manager.Path")
def test_local_storage_init(mock_path):
    """Test LocalStorageManager initialization creates directory."""
    # Create mocks for the path components
    mock_home = MagicMock(spec=Path)
    mock_jarvis_dir = MagicMock(spec=Path)
    mock_history_dir = MagicMock(spec=Path)
    mock_final_filepath = MagicMock(spec=Path)

    # Configure the chain of calls
    mock_path.home.return_value = mock_home
    mock_home.__truediv__.return_value = mock_jarvis_dir
    mock_jarvis_dir.__truediv__.return_value = mock_history_dir
    mock_history_dir.__truediv__.return_value = mock_final_filepath # For self.filepath = self.history_dir / filename

    # Instantiate the manager - this triggers the path creation and mkdir
    manager = LocalStorageManager(filename="local_test.json")

    # Assertions
    mock_path.home.assert_called_once()
    mock_home.__truediv__.assert_called_once_with(".jarvis-core")
    mock_jarvis_dir.__truediv__.assert_called_once_with("history")
    mock_history_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    # Check filepath assignment
    mock_history_dir.__truediv__.assert_called_with("local_test.json")
    assert manager.filepath == mock_final_filepath
@patch("builtins.open", new_callable=mock_open, read_data='[{"sender": "Old", "message": "Msg"}]') # Corrected string literal
@patch("json.dump")
def test_local_storage_save_message(mock_json_dump, mock_file_open, mock_path, mock_home_dir):
    """Test saving a message with LocalStorageManager."""
    mock_path.home.return_value = mock_home_dir
    manager = LocalStorageManager(filename="local_test.json")
    filepath = manager.filepath

    manager.save_message("User", "Hello")

    # Check file was opened for read then write
    assert mock_file_open.call_count == 2
    mock_file_open.assert_any_call(filepath, "r", encoding="utf-8")
    mock_file_open.assert_any_call(filepath, "w", encoding="utf-8")

    # Check json.dump was called with the updated history
    args, kwargs = mock_json_dump.call_args
    saved_history = args[0]
    assert len(saved_history) == 2
    assert saved_history[0]["sender"] == "Old"
    assert saved_history[1]["sender"] == "User"
    assert saved_history[1]["message"] == "Hello"
    assert "timestamp" in saved_history[1]

@patch("src.core.storage_manager.Path")
@patch("builtins.open", new_callable=mock_open, read_data='[{"sender": "User", "message": "Hi"}]')
@patch("pathlib.Path.exists") # Patch exists globally for this test
def test_local_storage_load_history_success(mock_exists, mock_file_open, mock_path, mock_home_dir):
    """Test loading history successfully."""
    mock_path.home.return_value = mock_home_dir
    manager = LocalStorageManager(filename="local_test.json")
    # Configure the mock to always return True for this test
    mock_exists.return_value = True

    history = manager.load_history()

    # Check that exists was called on the correct path
    # We need manager.filepath to be constructed correctly first
    # Let's assume manager init worked and filepath is set
    # Find the actual path object used inside the function if possible, or mock more carefully
    # For now, let's check open was called
    mock_file_open.assert_called_once_with(manager.filepath, "r", encoding="utf-8")
    assert len(history) == 1
    assert history[0]["sender"] == "User"
@patch("src.core.storage_manager.Path")
@patch("pathlib.Path.exists") # Patch exists globally
def test_local_storage_load_history_file_not_found(mock_exists, mock_path, mock_home_dir):
    """Test loading history when file doesn\t exist."""
    mock_path.home.return_value = mock_home_dir
    manager = LocalStorageManager(filename="local_test.json")
    # Configure mock to always return False for this test
    mock_exists.return_value = False

    history = manager.load_history()
    assert history == []

@patch("src.core.storage_manager.Path")
@patch("builtins.open", new_callable=mock_open, read_data="invalid json")
@patch("pathlib.Path.exists") # Patch exists globally
def test_local_storage_load_history_invalid_json(mock_exists, mock_file_open, mock_path, mock_home_dir):
    """Test loading history with invalid JSON."""
    mock_path.home.return_value = mock_home_dir
    manager = LocalStorageManager(filename="local_test.json")
    # Configure mock to return True for the specific filepath
    mock_exists.side_effect = lambda *args: args[0] == manager.filepath if args and isinstance(args[0], Path) else False

    history = manager.load_history()
    assert history == []

# --- Test GoogleDriveStorageManager (Basic Init & Auth Trigger) ---
# Full testing is hard due to OAuth flow, focus on structure

@patch("src.core.storage_manager.os.getenv")
@patch("src.core.storage_manager.Path")
def test_gdrive_storage_init(mock_path, mock_getenv, mock_home_dir):
    """Test GoogleDriveStorageManager initialization."""
    mock_getenv.return_value = "path/to/creds.json"
    mock_path.home.return_value = mock_home_dir
    mock_path.return_value.resolve.return_value = Path("/resolved/path/to/creds.json")

    manager = GoogleDriveStorageManager(
        credentials_file="creds.json",
        token_file="gdrive_token.pickle",
        filename="gdrive_hist.json",
        folder_name="GDrive Test"
    )

    assert manager.token_path == mock_home_dir / ".jarvis-core" / "gdrive_token.pickle"
    assert manager.credentials_path == Path("/resolved/path/to/creds.json")
    assert manager.filename == "gdrive_hist.json"
    assert manager.folder_name == "GDrive Test"
    assert manager.service is None # Not authenticated yet
    assert manager.file_id is None

@patch("src.core.storage_manager.GoogleDriveStorageManager._ensure_file_exists")
@patch("src.core.storage_manager.build")
@patch("pickle.dump")
@patch("builtins.open", new_callable=mock_open)
@patch("src.core.storage_manager.InstalledAppFlow")
@patch("src.core.storage_manager.Path")
@patch("pathlib.Path.exists") # Patch exists globally
def test_gdrive_storage_authenticate_new_token(mock_exists, mock_path, mock_flow, mock_file_open, mock_pickle_dump, mock_build, mock_ensure_file, mock_home_dir):
    """Test the authentication flow when no token exists."""
    mock_path.home.return_value = mock_home_dir
    token_path = mock_home_dir / ".jarvis-core" / "gdrive_token.pickle"
    creds_path = Path("/path/to/creds.json") # Use a dummy Path for comparison
    mock_path.return_value.resolve.return_value = creds_path # Mock resolution

    # Configure mock_exists using side_effect
    def exists_side_effect(*args):
        path_instance = args[0] if args else None
        if isinstance(path_instance, Path):
            if path_instance == token_path:
                return False # Token file does not exist
            if path_instance == creds_path:
                return True # Credentials file exists
        return False # Default
    mock_exists.side_effect = exists_side_effect

    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_flow_instance = mock_flow.from_client_secrets_file.return_value
    mock_flow_instance.run_local_server.return_value = mock_creds

    mock_service = MagicMock()
    mock_build.return_value = mock_service

    manager = GoogleDriveStorageManager(token_file="gdrive_token.pickle")
    manager.credentials_path = creds_path # Set resolved path
    manager.token_path = token_path

    success = manager.authenticate()

    assert success is True
    mock_flow.from_client_secrets_file.assert_called_once_with(creds_path, SCOPES)
    mock_flow_instance.run_local_server.assert_called_once()
    mock_file_open.assert_called_once_with(token_path, "wb")
    mock_pickle_dump.assert_called_once_with(mock_creds, mock_file_open())
    mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)
    assert manager.service == mock_service
    mock_ensure_file.assert_called_once() # Ensure file check happens after auth

# --- Test Unified Storage Factory ---

@patch("src.core.storage_manager.LocalStorageManager")
@patch("src.core.storage_manager.GoogleDriveStorageManager")
@patch("src.core.storage_manager.load_settings")
def test_initialize_storage_manager_local(mock_load_settings, mock_gdrive_init, mock_local_init):
    """Test factory initializes Local manager based on settings."""
    mock_load_settings.return_value = {"storage_mode": "local", "history_filename": "hist.json"}
    manager = initialize_storage_manager(force_reinit=True)
    mock_local_init.assert_called_once_with(filename="hist.json")
    mock_gdrive_init.assert_not_called()
    assert isinstance(manager, MagicMock) # It returns the mocked instance

@patch("src.core.storage_manager.LocalStorageManager")
@patch("src.core.storage_manager.GoogleDriveStorageManager")
@patch("src.core.storage_manager.load_settings")
def test_initialize_storage_manager_gdrive(mock_load_settings, mock_gdrive_init, mock_local_init):
    """Test factory initializes GDrive manager based on settings."""
    mock_load_settings.return_value = {
        "storage_mode": "google_drive",
        "history_filename": "g_hist.json",
        "google_drive_credentials_file": "g_creds.json",
        "google_drive_token_file": "g_tok.pickle",
        "google_drive_folder_name": "g_folder"
    }
    manager = initialize_storage_manager(force_reinit=True)
    mock_gdrive_init.assert_called_once_with(
        credentials_file="g_creds.json",
        token_file="g_tok.pickle",
        filename="g_hist.json",
        folder_name="g_folder"
    )
    mock_local_init.assert_not_called()
    assert isinstance(manager, MagicMock)

@patch("src.core.storage_manager.initialize_storage_manager")
def test_get_storage_manager_initializes_once(mock_init):
    """Test get_storage_manager calls initialize only once."""
    # Reset global state for test isolation
    from src.core import storage_manager
    storage_manager._current_storage_manager = None

    mock_manager_instance = MagicMock()
    mock_init.return_value = mock_manager_instance

    manager1 = get_storage_manager()
    manager2 = get_storage_manager()

    mock_init.assert_called_once() # Should only initialize on the first call
    assert manager1 == mock_manager_instance
    assert manager2 == mock_manager_instance

    # Clean up global state
    storage_manager._current_storage_manager = None

