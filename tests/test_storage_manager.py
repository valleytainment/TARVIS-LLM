import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime

# Add project root to sys.path to allow absolute imports
import sys
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Modules to test
from src.core.storage_manager import (
    LocalStorageManager,
    GoogleDriveStorageManager,
    load_settings,
    save_settings,
    get_storage_manager,
    initialize_storage_manager,
    SCOPES,
    USER_CONFIG_DIR # Import for checking paths
)
from google.oauth2.credentials import Credentials

# --- Test Fixtures ---

@pytest.fixture
def default_settings_values():
    """Provides the expected default settings dictionary (updated token file)."""
    return {
        "storage_mode": "local",
        "local_storage_path": None,
        "google_drive_credentials_file": "credentials.json",
        "google_drive_token_file": "token.json", # Updated default
        "google_drive_folder_name": "Jarvis-Core History",
        "history_filename": "jarvis_chat_history.json",
        "llm_model_path": None,
        "system_prompt_path": None
    }

@pytest.fixture
def mock_settings_file_path(tmp_path):
    """Provides a mock path for the settings file within a temporary directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    settings_file_path = config_dir / "settings.json"
    return settings_file_path

@pytest.fixture
def mock_user_config_dir(tmp_path):
    """Provides a mock path for the user config directory."""
    user_dir = tmp_path / ".jarvis-core"
    user_dir.mkdir(parents=True)
    return user_dir

# --- Test load_settings & save_settings (Simplified, main tests in test_settings_logic.py) ---
# These tests are slightly redundant with test_settings_logic.py but kept for structure

@patch("src.core.storage_manager.get_resource_path")
@patch("pathlib.Path.exists")
def test_load_settings_success_in_storage_manager(
    mock_exists,
    mock_get_resource_path,
    mock_settings_file_path,
    default_settings_values
):
    """Test loading settings works via get_resource_path."""
    mock_get_resource_path.return_value = mock_settings_file_path
    mock_exists.return_value = True
    custom_settings = {"storage_mode": "google_drive"}
    with patch("builtins.open", mock_open(read_data=json.dumps(custom_settings))):
        settings = load_settings()
    
    mock_get_resource_path.assert_called_once_with("config/settings.json")
    mock_exists.assert_called_once_with(mock_settings_file_path)
    expected = default_settings_values.copy()
    expected.update(custom_settings)
    assert settings == expected

@patch("src.core.storage_manager.get_resource_path")
@patch("pathlib.Path.mkdir")
@patch("builtins.open", new_callable=mock_open)
@patch("json.dump")
def test_save_settings_in_storage_manager(
    mock_json_dump,
    mock_file_open,
    mock_mkdir,
    mock_get_resource_path,
    mock_settings_file_path
):
    """Test saving settings works via get_resource_path."""
    mock_get_resource_path.return_value = mock_settings_file_path
    settings_to_save = {"key": "value"}
    save_settings(settings_to_save)
    mock_get_resource_path.assert_called_once_with("config/settings.json")
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_file_open.assert_called_once_with(mock_settings_file_path, "w", encoding="utf-8")
    mock_json_dump.assert_called_once_with(settings_to_save, mock_file_open(), indent=4, ensure_ascii=False)

# --- Test LocalStorageManager ---

@patch("src.core.storage_manager.Path.home") # Mock Path.home specifically
def test_local_storage_init_default_path(mock_path_home, mock_user_config_dir):
    """Test LocalStorageManager initialization uses default path correctly."""
    # Configure Path.home() to return the parent of our mock user config dir
    mock_path_home.return_value = mock_user_config_dir.parent 
    expected_history_dir = mock_user_config_dir / "history"
    expected_filepath = expected_history_dir / "local_test.json"

    # Mock mkdir on the expected history directory path object
    with patch.object(Path, "mkdir") as mock_mkdir:
        manager = LocalStorageManager(filename="local_test.json")

    mock_path_home.assert_called_once()
    # Assert mkdir was called on the correct path
    # Need to find the instance Path was called on
    # Let's check the final path attribute instead
    assert manager.history_dir == expected_history_dir
    assert manager.filepath == expected_filepath
    # Check mkdir was called (might be called multiple times if parents=True)
    assert mock_mkdir.called
    # Check the specific call to the history dir
    mock_mkdir.assert_any_call(parents=True, exist_ok=True)

@patch("src.core.storage_manager.Path.home") # Mock Path.home to avoid real home access
def test_local_storage_init_custom_path(mock_path_home, tmp_path):
    """Test LocalStorageManager initialization uses custom path."""
    custom_path_str = str(tmp_path / "custom_local_storage")
    custom_path = Path(custom_path_str)
    expected_filepath = custom_path / "custom_file.json"

    # Mock mkdir on the expected custom path object
    with patch.object(Path, "mkdir") as mock_mkdir:
        manager = LocalStorageManager(filename="custom_file.json", storage_path=custom_path_str)

    mock_path_home.assert_not_called() # Home should not be used for custom path
    assert manager.history_dir == custom_path.resolve()
    assert manager.filepath == expected_filepath
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

@patch("src.core.storage_manager.Path.home")
@patch("builtins.open", new_callable=mock_open, read_data=\"[{\"sender\": \"Old\", \"message\": \"Msg\"}]\")
@patch("json.dump")
def test_local_storage_save_message(mock_json_dump, mock_file_open, mock_path_home, mock_user_config_dir):
    """Test saving a message with LocalStorageManager (default path)."""
    mock_path_home.return_value = mock_user_config_dir.parent
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
    assert saved_history[0][\"sender\"] == \"Old\"
    assert saved_history[1][\"sender\"] == \"User\"
    assert saved_history[1][\"message\"] == \"Hello\"
    assert \"timestamp\" in saved_history[1]

@patch("src.core.storage_manager.Path.home")
@patch("builtins.open", new_callable=mock_open, read_data=\"[{\"sender\": \"User\", \"message\": \"Hi\"}]\")
@patch("pathlib.Path.exists")
def test_local_storage_load_history_success(mock_exists, mock_file_open, mock_path_home, mock_user_config_dir):
    """Test loading history successfully."""
    mock_path_home.return_value = mock_user_config_dir.parent
    manager = LocalStorageManager(filename="local_test.json")
    filepath = manager.filepath
    
    # Configure mock_exists to return True for the specific filepath
    mock_exists.side_effect = lambda p: p == filepath

    history = manager.load_history()

    mock_exists.assert_called_with(filepath)
    mock_file_open.assert_called_once_with(filepath, "r", encoding="utf-8")
    assert len(history) == 1
    assert history[0][\"sender\"] == \"User\"

@patch("src.core.storage_manager.Path.home")
@patch("pathlib.Path.exists")
def test_local_storage_load_history_file_not_found(mock_exists, mock_path_home, mock_user_config_dir):
    """Test loading history when file doesn\t exist."""
    mock_path_home.return_value = mock_user_config_dir.parent
    manager = LocalStorageManager(filename="local_test.json")
    filepath = manager.filepath
    mock_exists.return_value = False

    history = manager.load_history()
    mock_exists.assert_called_with(filepath)
    assert history == []

@patch("src.core.storage_manager.Path.home")
@patch("builtins.open", new_callable=mock_open, read_data="invalid json")
@patch("pathlib.Path.exists")
def test_local_storage_load_history_invalid_json(mock_exists, mock_file_open, mock_path_home, mock_user_config_dir):
    """Test loading history with invalid JSON."""
    mock_path_home.return_value = mock_user_config_dir.parent
    manager = LocalStorageManager(filename="local_test.json")
    filepath = manager.filepath
    mock_exists.return_value = True

    history = manager.load_history()
    mock_exists.assert_called_with(filepath)
    mock_file_open.assert_called_once_with(filepath, "r", encoding="utf-8")
    assert history == []

# --- Test GoogleDriveStorageManager ---

@patch("src.core.storage_manager.get_resource_path")
@patch("src.core.storage_manager.os.getenv")
@patch("src.core.storage_manager.Path.home")
def test_gdrive_storage_init_paths(
    mock_path_home,
    mock_getenv,
    mock_get_resource_path,
    mock_user_config_dir # Fixture for ~/.jarvis-core
):
    """Test GoogleDriveStorageManager initialization sets paths correctly."""
    # Arrange
    mock_path_home.return_value = mock_user_config_dir.parent # Set home for USER_CONFIG_DIR
    mock_getenv.return_value = None # Use default credentials file name
    
    # Mock get_resource_path used for default credentials path
    mock_default_creds_path = Path("/mock/project/root/credentials.json")
    mock_get_resource_path.return_value = mock_default_creds_path

    # Act
    manager = GoogleDriveStorageManager(
        credentials_file="credentials.json", # Default name
        token_file="my_token.json",
        filename="gdrive_hist.json",
        folder_name="GDrive Test"
    )

    # Assert
    mock_path_home.assert_called() # Called to establish USER_CONFIG_DIR
    mock_getenv.assert_called_once_with("GOOGLE_DRIVE_CREDENTIALS_FILE", "credentials.json")
    # Check get_resource_path was called for the default credentials file
    mock_get_resource_path.assert_called_once_with("credentials.json")
    
    assert manager.token_path == mock_user_config_dir / "my_token.json"
    assert manager.credentials_path == mock_default_creds_path
    assert manager.filename == "gdrive_hist.json"
    assert manager.folder_name == "GDrive Test"
    assert manager.service is None
    assert manager.file_id is None

@patch("src.core.storage_manager.GoogleDriveStorageManager._ensure_file_exists")
@patch("src.core.storage_manager.build")
@patch("src.core.storage_manager.Credentials.from_authorized_user_file")
@patch("builtins.open", new_callable=mock_open)
@patch("src.core.storage_manager.InstalledAppFlow")
@patch("src.core.storage_manager.Path.home")
@patch("pathlib.Path.exists")
@patch("src.core.storage_manager.get_resource_path") # Mock resource path for creds
def test_gdrive_storage_authenticate_new_token_json(
    mock_get_resource_path,
    mock_exists,
    mock_path_home,
    mock_flow,
    mock_file_open,
    mock_creds_from_file, # Mock for loading JSON token
    mock_build,
    mock_ensure_file,
    mock_user_config_dir
):
    """Test the authentication flow using JSON token when no token exists."""
    # Arrange
    mock_path_home.return_value = mock_user_config_dir.parent
    token_path = mock_user_config_dir / "token.json"
    creds_path = Path("/mock/project/root/credentials.json")
    mock_get_resource_path.return_value = creds_path # Mock resolution for credentials

    # Configure mock_exists: token doesn't exist, credentials do
    def exists_side_effect(path_instance):
        if path_instance == token_path:
            return False # Token file does not exist
        if path_instance == creds_path:
            return True # Credentials file exists
        if path_instance == token_path.parent:
             return True # Assume parent dir exists or is created
        return False # Default
    mock_exists.side_effect = exists_side_effect

    # Mock the OAuth flow
    mock_creds_obtained = MagicMock(spec=Credentials)
    mock_creds_obtained.valid = True
    mock_creds_obtained.expired = False
    mock_creds_obtained.refresh_token = "fake_refresh_token"
    # Mock the to_json method needed for saving
    mock_creds_obtained.to_json.return_value = \"{\"token\": \"mock_token_data\"}\"
    
    mock_flow_instance = mock_flow.from_client_secrets_file.return_value
    mock_flow_instance.run_local_server.return_value = mock_creds_obtained

    # Mock build service
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    # Act
    manager = GoogleDriveStorageManager(token_file="token.json", credentials_file="credentials.json")
    # Manually set paths based on mocks for consistency in test
    manager.token_path = token_path
    manager.credentials_path = creds_path
    
    success = manager.authenticate()

    # Assert
    assert success is True
    mock_get_resource_path.assert_called_once_with("credentials.json")
    # Check exists called for token and credentials
    mock_exists.assert_any_call(token_path)
    mock_exists.assert_any_call(creds_path)
    
    mock_flow.from_client_secrets_file.assert_called_once_with(str(creds_path), SCOPES)
    mock_flow_instance.run_local_server.assert_called_once()
    
    # Assert file was opened to *write* the new JSON token
    mock_file_open.assert_called_once_with(token_path, "w", encoding="utf-8")
    # Assert the JSON content was written
    mock_file_open().write.assert_called_once_with(\"{\"token\": \"mock_token_data\"}\")
    
    mock_build.assert_called_once_with(\"drive\", \"v3\", credentials=mock_creds_obtained)
    assert manager.service == mock_service
    mock_ensure_file.assert_called_once() # Ensure file check happens after auth

# --- Test Unified Storage Factory ---

@patch("src.core.storage_manager.LocalStorageManager")
@patch("src.core.storage_manager.GoogleDriveStorageManager")
@patch("src.core.storage_manager.load_settings")
def test_initialize_storage_manager_local_factory(
    mock_load_settings,
    mock_gdrive_init,
    mock_local_init,
    tmp_path
):
    """Test factory initializes Local manager based on settings."""
    custom_path = str(tmp_path / "local_hist")
    mock_load_settings.return_value = {
        "storage_mode": "local", 
        "history_filename": "hist.json",
        "local_storage_path": custom_path,
        # Add other defaults
        "google_drive_credentials_file": "", "google_drive_token_file": "token.json",
        "google_drive_folder_name": "", "llm_model_path": None, "system_prompt_path": None
    }
    # Reset global state
    from src.core import storage_manager
    storage_manager._current_storage_manager = None
    
    manager = initialize_storage_manager(force_reinit=True)
    
    mock_load_settings.assert_called_once()
    mock_local_init.assert_called_once_with(filename="hist.json", storage_path=custom_path)
    mock_gdrive_init.assert_not_called()
    assert manager == mock_local_init.return_value
    
    # Clean up global state
    storage_manager._current_storage_manager = None

@patch("src.core.storage_manager.LocalStorageManager")
@patch("src.core.storage_manager.GoogleDriveStorageManager")
@patch("src.core.storage_manager.load_settings")
def test_initialize_storage_manager_gdrive_factory(
    mock_load_settings,
    mock_gdrive_init,
    mock_local_init
):
    """Test factory initializes GDrive manager based on settings."""
    # Mock the authenticate method of the GDrive manager instance
    mock_gdrive_instance = MagicMock()
    mock_gdrive_instance.authenticate.return_value = True # Assume auth succeeds
    mock_gdrive_init.return_value = mock_gdrive_instance
    
    mock_load_settings.return_value = {
        "storage_mode": "google_drive",
        "history_filename": "g_hist.json",
        "google_drive_credentials_file": "g_creds.json",
        "google_drive_token_file": "g_tok.json", # Updated token file
        "google_drive_folder_name": "g_folder",
        # Add other defaults
        "local_storage_path": None, "llm_model_path": None, "system_prompt_path": None
    }
    # Reset global state
    from src.core import storage_manager
    storage_manager._current_storage_manager = None
    
    manager = initialize_storage_manager(force_reinit=True)
    
    mock_load_settings.assert_called_once()
    mock_gdrive_init.assert_called_once_with(
        credentials_file="g_creds.json",
        token_file="g_tok.json", # Check for .json
        filename="g_hist.json",
        folder_name="g_folder"
    )
    mock_gdrive_instance.authenticate.assert_called_once()
    mock_local_init.assert_not_called()
    assert manager == mock_gdrive_instance
    
    # Clean up global state
    storage_manager._current_storage_manager = None

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

