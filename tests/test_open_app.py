import pytest
import platform
import subprocess # Added import
from unittest.mock import patch, mock_open, MagicMock

# Import the function to be tested
from src.skills import open_app

# Mock config data for Windows
WINDOWS_CONFIG_DATA = """
open_app:
  paths:
    Windows:
      notepad: C:\\Windows\\System32\\notepad.exe
      customapp: C:\\Program Files\\CustomApp\\App.exe
      app with space: C:\\Program Files\\App With Space\\run.exe
    Linux: # Irrelevant for these tests but good to have
      firefox: /usr/bin/firefox
"""

# --- Tests for execute --- 

@patch("platform.system", return_value="Windows")
@patch("builtins.open", new_callable=mock_open, read_data=WINDOWS_CONFIG_DATA)
@patch("src.skills.open_app.subprocess.Popen") # Corrected patch target
def test_execute_success_configured_app(mock_popen, mock_file_open, mock_platform):
    """Test launching a configured application successfully on Windows."""
    result = open_app.execute("notepad")
    assert "✅ Launched notepad" in result
    mock_popen.assert_called_once_with(["C:\\Windows\\System32\\notepad.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@patch("platform.system", return_value="Windows")
@patch("builtins.open", new_callable=mock_open, read_data=WINDOWS_CONFIG_DATA)
@patch("src.skills.open_app.subprocess.Popen") # Corrected patch target
def test_execute_success_configured_app_case_insensitive(mock_popen, mock_file_open, mock_platform):
    """Test launching a configured application successfully using case-insensitive name."""
    result = open_app.execute("NoTePaD")
    assert "✅ Launched NoTePaD" in result
    mock_popen.assert_called_once_with(["C:\\Windows\\System32\\notepad.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@patch("platform.system", return_value="Windows")
@patch("builtins.open", new_callable=mock_open, read_data=WINDOWS_CONFIG_DATA)
@patch("src.skills.open_app.subprocess.Popen") # Corrected patch target
def test_execute_success_app_with_space_in_path(mock_popen, mock_file_open, mock_platform):
    """Test launching a configured application with spaces in its path."""
    result = open_app.execute("app with space")
    assert "✅ Launched app with space" in result
    mock_popen.assert_called_once_with(["C:\\Program Files\\App With Space\\run.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@patch("platform.system", return_value="Windows")
@patch("builtins.open", new_callable=mock_open, read_data=WINDOWS_CONFIG_DATA)
@patch("src.skills.open_app.subprocess.Popen") # Corrected patch target for the fallback case
def test_execute_app_not_in_config_assumed_in_path(mock_popen, mock_file_open, mock_platform):
    """Test launching an app not in config, assuming it's in PATH."""
    result = open_app.execute("calc") # Assume calc is in PATH but not config
    assert "✅ Launched \'calc\' (assumed in PATH)." in result 
    # Assert call on the mock_popen object passed into the test function
    mock_popen.assert_called_once_with(f'start /B "" "calc"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@patch("platform.system", return_value="Windows")
@patch("builtins.open", new_callable=mock_open, read_data=WINDOWS_CONFIG_DATA)
@patch("src.skills.open_app.subprocess.Popen", side_effect=FileNotFoundError("Executable not found")) # Corrected patch target
def test_execute_configured_app_file_not_found(mock_popen, mock_file_open, mock_platform):
    """Test launching a configured app where the executable path is invalid."""
    result = open_app.execute("notepad")
    assert "❌ Error: Application executable not found" in result
    assert "C:\\Windows\\System32\\notepad.exe" in result

@patch("platform.system", return_value="Windows")
@patch("builtins.open", new_callable=mock_open, read_data=WINDOWS_CONFIG_DATA)
@patch("src.skills.open_app.subprocess.Popen", side_effect=PermissionError("Permission denied")) # Corrected patch target
def test_execute_configured_app_permission_error(mock_popen, mock_file_open, mock_platform):
    """Test launching a configured app with insufficient permissions."""
    result = open_app.execute("notepad")
    assert "❌ Error: Permission denied" in result
    assert "C:\\Windows\\System32\\notepad.exe" in result

@patch("platform.system", return_value="Windows")
@patch("builtins.open", side_effect=FileNotFoundError("Config not found"))
def test_execute_config_file_not_found(mock_file_open, mock_platform):
    """Test when the app_paths.yaml configuration file is missing."""
    result = open_app.execute("notepad")
    assert "❌ Error: Application paths configuration is missing or failed to load." in result

@patch("platform.system", return_value="Linux") # Simulate running on Linux
@patch("builtins.open", new_callable=mock_open, read_data=WINDOWS_CONFIG_DATA)
def test_execute_wrong_os(mock_file_open, mock_platform):
    """Test launching on an OS for which paths are not configured (or wrong section)."""
    # Corrected assertion: The code returns an error immediately if paths aren't loaded for the OS.
    with patch("src.skills.open_app.subprocess.Popen") as mock_popen: # Corrected patch target
        result = open_app.execute("someapp")
        assert "❌ Error: Application paths configuration is missing or failed to load." in result
        mock_popen.assert_not_called() # Fallback should not be reached

@patch("platform.system", return_value="Windows")
@patch("builtins.open", new_callable=mock_open, read_data="invalid: yaml: data")
def test_execute_invalid_yaml(mock_file_open, mock_platform):
    """Test when the configuration file contains invalid YAML."""
    result = open_app.execute("notepad")
    assert "❌ Error: Application paths configuration is missing or failed to load." in result

