#!/usr/bin/env python3.11
# tests/test_settings_logic.py

import pytest
import sys
import os
import json
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# Add project root to sys.path to allow absolute imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Modules to test
from src.core.storage_manager import (
    load_settings,
    save_settings,
    initialize_storage_manager,
    LocalStorageManager,
    GoogleDriveStorageManager
)

# --- Test Fixtures ---

@pytest.fixture
def default_settings_values():
    """Provides the expected default settings dictionary (updated token file)."""
    return {
        "storage_mode": "local",
        "local_storage_path": None,
        "google_drive_credentials_file": "credentials.json",
        "google_drive_token_file": "token.json", # Updated from .pickle
        "google_drive_folder_name": "Jarvis-Core History",
        "history_filename": "jarvis_chat_history.json",
        "llm_model_path": None,
        "system_prompt_path": None
    }

@pytest.fixture
def mock_settings_file_path(tmp_path):
    """Provides a mock path for the settings file within a temporary directory."""
    # Simulate the structure: tmp_path / config / settings.json
    # This path will be returned by the mocked get_resource_path
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    settings_file_path = config_dir / "settings.json"
    return settings_file_path

# --- Test load_settings ---

@patch("src.core.storage_manager.get_resource_path")
@patch("pathlib.Path.exists") # Still need to mock exists on the returned path
def test_load_settings_file_not_found(
    mock_exists,
    mock_get_resource_path,
    mock_settings_file_path, # Fixture providing the path
    default_settings_values # Fixture providing default dict
):
    """Test load_settings returns defaults when file doesn't exist."""
    # Configure get_resource_path to return the mock path
    mock_get_resource_path.return_value = mock_settings_file_path

    # Configure mock_exists to return False for the settings file path
    mock_exists.return_value = False

    settings = load_settings()

    # Assert get_resource_path was called correctly
    mock_get_resource_path.assert_called_once_with("config/settings.json")
    # Assert exists was called on the path returned by get_resource_path
    mock_exists.assert_called_once_with(mock_settings_file_path)
    assert settings == default_settings_values

@patch("src.core.storage_manager.get_resource_path")
@patch("pathlib.Path.exists")
@patch("builtins.open", new_callable=mock_open)
def test_load_settings_success(
    mock_file_open,
    mock_exists,
    mock_get_resource_path,
    mock_settings_file_path,
    default_settings_values
):
    """Test load_settings reads and merges settings from an existing file."""
    # Configure get_resource_path
    mock_get_resource_path.return_value = mock_settings_file_path

    # Configure mock_exists to return True
    mock_exists.return_value = True

    # Prepare custom settings data to be read from the mock file
    custom_settings_data = {
        "storage_mode": "google_drive",
        "llm_model_path": "/custom/model.gguf",
        "google_drive_token_file": "old_token.pickle", # Test update logic
        "new_key": "new_value" # Test merging with defaults
    }
    mock_file_open.return_value.read.return_value = json.dumps(custom_settings_data)

    settings = load_settings()

    mock_get_resource_path.assert_called_once_with("config/settings.json")
    mock_exists.assert_called_once_with(mock_settings_file_path)
    mock_file_open.assert_called_once_with(mock_settings_file_path, "r", encoding="utf-8")

    # Check that defaults are updated, not replaced, and token file updated
    expected_settings = default_settings_values.copy()
    expected_settings.update(custom_settings_data)
    expected_settings["google_drive_token_file"] = "token.json" # Should be updated

    assert settings == expected_settings
    assert settings["storage_mode"] == "google_drive"
    assert settings["llm_model_path"] == "/custom/model.gguf"
    assert settings["history_filename"] == "jarvis_chat_history.json" # Default value retained
    assert settings["new_key"] == "new_value" # New key added
    assert settings["google_drive_token_file"] == "token.json" # Verify update

@patch("src.core.storage_manager.get_resource_path")
@patch("pathlib.Path.exists")
@patch("builtins.open", new_callable=mock_open)
def test_load_settings_invalid_json(
    mock_file_open,
    mock_exists,
    mock_get_resource_path,
    mock_settings_file_path,
    default_settings_values
):
    """Test load_settings returns defaults on JSONDecodeError."""
    # Configure get_resource_path
    mock_get_resource_path.return_value = mock_settings_file_path

    mock_exists.return_value = True
    mock_file_open.return_value.read.return_value = "invalid json data{"

    settings = load_settings()

    mock_get_resource_path.assert_called_once_with("config/settings.json")
    mock_exists.assert_called_once_with(mock_settings_file_path)
    mock_file_open.assert_called_once_with(mock_settings_file_path, "r", encoding="utf-8")
    assert settings == default_settings_values
    assert settings["google_drive_token_file"] == "token.json" # Ensure default is correct

@patch("src.core.storage_manager.get_resource_path")
@patch("pathlib.Path.exists")
@patch("builtins.open", side_effect=IOError("Permission denied"))
def test_load_settings_io_error(
    mock_file_open,
    mock_exists,
    mock_get_resource_path,
    mock_settings_file_path,
    default_settings_values
):
    """Test load_settings returns defaults on IOError."""
    # Configure get_resource_path
    mock_get_resource_path.return_value = mock_settings_file_path

    mock_exists.return_value = True

    settings = load_settings()

    mock_get_resource_path.assert_called_once_with("config/settings.json")
    mock_exists.assert_called_once_with(mock_settings_file_path)
    mock_file_open.assert_called_once_with(mock_settings_file_path, "r", encoding="utf-8")
    assert settings == default_settings_values
    assert settings["google_drive_token_file"] == "token.json" # Ensure default is correct

# --- Test save_settings ---

@patch("src.core.storage_manager.get_resource_path")
@patch("pathlib.Path.mkdir") # Mock mkdir used in save_settings
@patch("builtins.open", new_callable=mock_open)
@patch("json.dump")
def test_save_settings_success(
    mock_json_dump,
    mock_file_open,
    mock_mkdir, # Add mkdir mock
    mock_get_resource_path,
    mock_settings_file_path
):
    """Test save_settings writes the dictionary to the correct file."""
    # Configure get_resource_path
    mock_get_resource_path.return_value = mock_settings_file_path

    settings_to_save = {"key1": "value1", "key2": 123, "google_drive_token_file": "old.pickle"}
    expected_saved_settings = {"key1": "value1", "key2": 123, "google_drive_token_file": "token.json"} # Expect update

    save_settings(settings_to_save)

    mock_get_resource_path.assert_called_once_with("config/settings.json")
    # Assert mkdir was called on the parent directory
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_file_open.assert_called_once_with(mock_settings_file_path, "w", encoding="utf-8")
    # Check that json.dump was called with the correct arguments (and updated token file)
    mock_json_dump.assert_called_once_with(expected_saved_settings, mock_file_open(), indent=4, ensure_ascii=False)

@patch("src.core.storage_manager.get_resource_path")
@patch("pathlib.Path.mkdir") # Mock mkdir
@patch("builtins.open", side_effect=IOError("Disk full"))
@patch("json.dump") # Mock dump to prevent it running before open fails
def test_save_settings_io_error(
    mock_json_dump,
    mock_file_open,
    mock_mkdir,
    mock_get_resource_path,
    mock_settings_file_path
):
    """Test save_settings handles IOError during file writing."""
    # Configure get_resource_path
    mock_get_resource_path.return_value = mock_settings_file_path

    settings_to_save = {"key1": "value1"}
    # We expect save_settings to catch the IOError and log it, not raise it
    try:
        save_settings(settings_to_save)
    except IOError:
        pytest.fail("save_settings should handle IOError internally and not raise it.")

    mock_get_resource_path.assert_called_once_with("config/settings.json")
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_file_open.assert_called_once_with(mock_settings_file_path, "w", encoding="utf-8")
    mock_json_dump.assert_not_called() # Dump shouldn't be reached if open fails

# --- Test initialize_storage_manager --- (Focus on settings usage)

@patch("src.core.storage_manager.LocalStorageManager")
@patch("src.core.storage_manager.GoogleDriveStorageManager")
@patch("src.core.storage_manager.load_settings")
def test_initialize_storage_manager_uses_local_setting(
    mock_load_settings,
    mock_gdrive_init,
    mock_local_init,
    tmp_path # Use tmp_path for custom local path test
):
    """Test initialize uses LocalStorageManager with custom path if set."""
    custom_path_str = str(tmp_path / "my_custom_history")
    mock_load_settings.return_value = {
        "storage_mode": "local",
        "local_storage_path": custom_path_str,
        "history_filename": "local_hist.json",
        # Other keys needed by defaults
        "google_drive_credentials_file": "", "google_drive_token_file": "token.json", # Use updated default
        "google_drive_folder_name": "", "llm_model_path": None, "system_prompt_path": None
    }

    # Reset global manager for test isolation
    from src.core import storage_manager
    storage_manager._current_storage_manager = None

    manager = initialize_storage_manager(force_reinit=True)

    mock_load_settings.assert_called_once()
    mock_local_init.assert_called_once_with(filename="local_hist.json", storage_path=custom_path_str)
    mock_gdrive_init.assert_not_called()
    assert manager == mock_local_init.return_value

    # Clean up global state
    storage_manager._current_storage_manager = None

@patch("src.core.storage_manager.LocalStorageManager")
@patch("src.core.storage_manager.GoogleDriveStorageManager")
@patch("src.core.storage_manager.load_settings")
def test_initialize_storage_manager_uses_gdrive_setting(
    mock_load_settings,
    mock_gdrive_init,
    mock_local_init
):
    """Test initialize uses GoogleDriveStorageManager if set."""
    # Mock the authenticate method of the GDrive manager instance
    mock_gdrive_instance = MagicMock()
    mock_gdrive_instance.authenticate.return_value = True # Assume auth succeeds
    mock_gdrive_init.return_value = mock_gdrive_instance

    mock_load_settings.return_value = {
        "storage_mode": "google_drive",
        "local_storage_path": None,
        "history_filename": "gdrive_hist.json",
        "google_drive_credentials_file": "creds.json",
        "google_drive_token_file": "tok.json", # Expect .json now
        "google_drive_folder_name": "GDriveFolder",
        "llm_model_path": None, "system_prompt_path": None
    }

    # Reset global manager for test isolation
    from src.core import storage_manager
    storage_manager._current_storage_manager = None

    manager = initialize_storage_manager(force_reinit=True)

    mock_load_settings.assert_called_once()
    mock_gdrive_init.assert_called_once_with(
        credentials_file="creds.json",
        token_file="tok.json", # Check for .json
        filename="gdrive_hist.json",
        folder_name="GDriveFolder"
    )
    # Check that authenticate was called after initialization
    mock_gdrive_instance.authenticate.assert_called_once()
    mock_local_init.assert_not_called()
    assert manager == mock_gdrive_instance

    # Clean up global state
    storage_manager._current_storage_manager = None

@patch("src.core.storage_manager.LocalStorageManager")
@patch("src.core.storage_manager.GoogleDriveStorageManager")
@patch("src.core.storage_manager.load_settings")
def test_initialize_storage_manager_gdrive_auth_fails_fallback(
    mock_load_settings,
    mock_gdrive_init,
    mock_local_init
):
    """Test initialize falls back to LocalStorageManager if GDrive auth fails."""
    # Mock the authenticate method to return False
    mock_gdrive_instance = MagicMock()
    mock_gdrive_instance.authenticate.return_value = False # Simulate auth failure
    mock_gdrive_init.return_value = mock_gdrive_instance

    mock_load_settings.return_value = {
        "storage_mode": "google_drive",
        "local_storage_path": "/fallback/path",
        "history_filename": "gdrive_hist.json",
        "google_drive_credentials_file": "creds.json",
        "google_drive_token_file": "tok.json",
        "google_drive_folder_name": "GDriveFolder",
        "llm_model_path": None, "system_prompt_path": None
    }

    # Reset global manager for test isolation
    from src.core import storage_manager
    storage_manager._current_storage_manager = None

    manager = initialize_storage_manager(force_reinit=True)

    mock_load_settings.assert_called_once()
    mock_gdrive_init.assert_called_once() # GDrive init is still attempted
    mock_gdrive_instance.authenticate.assert_called_once() # Auth is attempted
    # Check that LocalStorageManager was called as fallback
    mock_local_init.assert_called_once_with(filename="gdrive_hist.json", storage_path="/fallback/path")
    assert manager == mock_local_init.return_value # Manager should be the local one

    # Clean up global state
    storage_manager._current_storage_manager = None

# Note: The original test_custom_local_storage_path in the file was more of an integration test.
# The tests above focus specifically on mocking and unit testing the settings load/save functions
# and the initialization logic based on settings.

