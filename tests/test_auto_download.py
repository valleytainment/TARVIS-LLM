#!/usr/bin/env python3.11
# tests/test_auto_download.py

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Add project root to sys.path to allow imports from src
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Module to test
from src.core.llm_manager import LLMLoader

# Default model details used in LLMLoader
DEFAULT_MODEL_REPO = "meta-llama/Meta-Llama-3-8B-Instruct"
DEFAULT_MODEL_FILENAME = "Meta-Llama-3-8B-Instruct.Q4_0.gguf"

@pytest.fixture
def mock_settings_default(monkeypatch):
    """Mocks load_settings to return default model path behavior."""
    # Simulate settings where no custom path is provided
    default_settings = {
        "llm_model_path": "", # Empty means use default
        "system_prompt_path": "",
        "storage_mode": "local",
        "google_drive_credentials_file": "",
        "google_drive_token_file": "",
        "google_drive_folder_name": "",
        "history_filename": "chat_history.json",
        "custom_local_path": ""
    }
    # Use monkeypatch for patching within the fixture scope if needed,
    # but patching load_settings directly in the test is often clearer.
    # For simplicity, we'll patch in the test functions.
    return default_settings

@pytest.fixture
def default_model_path_fixture():
    """Provides the expected default model path."""
    # Use the logic from LLMLoader to determine the expected default path
    # Assuming MODEL_DIR env var is NOT set for default behavior test
    return project_root / "models" / DEFAULT_MODEL_FILENAME

# --- Test Cases ---

@patch("src.core.llm_manager.load_settings")
@patch("src.core.llm_manager.hf_hub_download")
@patch("src.core.llm_manager.LLMLoader._load_llm_from_path") # Don't actually load
@patch("pathlib.Path.exists") # Mock exists globally for this test
@patch("os.getenv") # Mock environment variable access
def test_download_triggered_when_model_missing(
    mock_getenv,
    mock_exists,
    mock_load_llm,
    mock_hf_download,
    mock_load_settings,
    mock_settings_default, # Fixture providing default settings dict
    default_model_path_fixture # Fixture providing the expected path
):
    """Verify hf_hub_download is called when the default model file is missing."""
    print(f"\n--- Running: {test_download_triggered_when_model_missing.__name__} ---")
    # Arrange
    mock_load_settings.return_value = mock_settings_default
    mock_getenv.return_value = None # Ensure MODEL_DIR is not set
    expected_model_path = default_model_path_fixture
    print(f"Expecting model path: {expected_model_path}")

    # Configure mock_exists: return False only for the specific default model path
    def exists_side_effect(path_instance):
        print(f"Mock exists check for: {path_instance}")
        return path_instance == expected_model_path and False # False only for the target model
    mock_exists.side_effect = exists_side_effect

    # Mock the download function to return the expected path
    mock_hf_download.return_value = str(expected_model_path)
    # Mock the actual LLM loading to return a dummy object
    mock_load_llm.return_value = MagicMock() # Simulate successful load after download

    # Act
    print("Instantiating LLMLoader and calling load()...")
    loader = LLMLoader()
    llm_instance = loader.load()

    # Assert
    print("Asserting download was called...")
    mock_exists.assert_any_call(expected_model_path)
    mock_hf_download.assert_called_once_with(
        repo_id=DEFAULT_MODEL_REPO,
        filename=DEFAULT_MODEL_FILENAME,
        local_dir=expected_model_path.parent,
        local_dir_use_symlinks=False
    )
    mock_load_llm.assert_called_once_with(str(expected_model_path))
    assert llm_instance is not None
    print("--- Test Passed --- ")

@patch("src.core.llm_manager.load_settings")
@patch("src.core.llm_manager.hf_hub_download")
@patch("src.core.llm_manager.LLMLoader._load_llm_from_path") # Don't actually load
@patch("pathlib.Path.exists") # Mock exists globally for this test
@patch("os.getenv") # Mock environment variable access
def test_download_skipped_when_model_exists(
    mock_getenv,
    mock_exists,
    mock_load_llm,
    mock_hf_download,
    mock_load_settings,
    mock_settings_default,
    default_model_path_fixture
):
    """Verify hf_hub_download is NOT called when the default model file exists."""
    print(f"\n--- Running: {test_download_skipped_when_model_exists.__name__} ---")
    # Arrange
    mock_load_settings.return_value = mock_settings_default
    mock_getenv.return_value = None # Ensure MODEL_DIR is not set
    expected_model_path = default_model_path_fixture
    print(f"Expecting model path: {expected_model_path}")

    # Configure mock_exists: return True only for the specific default model path
    def exists_side_effect(path_instance):
        print(f"Mock exists check for: {path_instance}")
        return path_instance == expected_model_path # True only for the target model
    mock_exists.side_effect = exists_side_effect

    # Mock the actual LLM loading to return a dummy object
    mock_load_llm.return_value = MagicMock() # Simulate successful load

    # Act
    print("Instantiating LLMLoader and calling load()...")
    loader = LLMLoader()
    llm_instance = loader.load()

    # Assert
    print("Asserting download was NOT called...")
    mock_exists.assert_any_call(expected_model_path)
    mock_hf_download.assert_not_called()
    mock_load_llm.assert_called_once_with(str(expected_model_path))
    assert llm_instance is not None
    print("--- Test Passed --- ")

@patch("src.core.llm_manager.load_settings")
@patch("src.core.llm_manager.hf_hub_download")
@patch("src.core.llm_manager.LLMLoader._load_llm_from_path")
@patch("pathlib.Path.exists")
@patch("os.getenv")
def test_custom_model_path_used_when_set(
    mock_getenv,
    mock_exists,
    mock_load_llm,
    mock_hf_download,
    mock_load_settings,
    tmp_path # Use pytest's tmp_path fixture
):
    """Verify a custom model path from settings is used and download is skipped."""
    print(f"\n--- Running: {test_custom_model_path_used_when_set.__name__} ---")
    # Arrange
    custom_path_str = str(tmp_path / "custom_model.gguf")
    custom_path = Path(custom_path_str)
    print(f"Using custom path: {custom_path_str}")

    custom_settings = {
        "llm_model_path": custom_path_str, # Set custom path
        "system_prompt_path": "",
        "storage_mode": "local",
        "google_drive_credentials_file": "",
        "google_drive_token_file": "",
        "google_drive_folder_name": "",
        "history_filename": "chat_history.json",
        "custom_local_path": ""
    }
    mock_load_settings.return_value = custom_settings
    mock_getenv.return_value = None # Ensure MODEL_DIR is not set

    # Configure mock_exists: return True for the custom path
    def exists_side_effect(path_instance):
        print(f"Mock exists check for: {path_instance}")
        return path_instance == custom_path # True only for the custom path
    mock_exists.side_effect = exists_side_effect

    # Mock the actual LLM loading
    mock_load_llm.return_value = MagicMock()

    # Act
    print("Instantiating LLMLoader and calling load()...")
    loader = LLMLoader()
    llm_instance = loader.load()

    # Assert
    print("Asserting custom path was used and download was skipped...")
    mock_exists.assert_any_call(custom_path)
    mock_hf_download.assert_not_called() # Download should not be called
    mock_load_llm.assert_called_once_with(custom_path_str) # Load from custom path
    assert llm_instance is not None
    print("--- Test Passed --- ")

# To run these tests: pytest tests/test_auto_download.py -s
# The -s flag shows print statements

