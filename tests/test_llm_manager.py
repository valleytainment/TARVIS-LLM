import pytest
from unittest.mock import patch, MagicMock
import os

# Import the class to be tested
from src.core.llm_manager import LLMLoader

# --- Test Fixtures ---

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Fixture to mock environment variables."""
    # Mock environment variables used by LLMLoader __init__
    monkeypatch.setenv("HIGH_ACCURACY_MODE", "0") # Default to Q4
    monkeypatch.setenv("USE_GPU", "0") # Default to CPU
    monkeypatch.setenv("N_THREADS", "4") # Example thread count
    return monkeypatch

# --- Test Cases ---

# Patch os.path.abspath where it's used in llm_manager.py
@patch("src.core.llm_manager.os.path.abspath", return_value="/home/ubuntu/jarvis-core/src/core/llm_manager.py")
# Patch os.path.exists where it's used
@patch("src.core.llm_manager.os.path.exists")
# Patch the GPT4All class where it's used
@patch("src.core.llm_manager.GPT4All")
def test_llm_loader_init_and_load_success_cpu(mock_gpt4all_class, mock_os_path_exists, mock_os_path_abspath, mock_env_vars):
    """Test successful initialization and loading with default CPU settings."""
    mock_os_path_exists.return_value = True
    mock_llm_instance = MagicMock()
    mock_gpt4all_class.return_value = mock_llm_instance

    loader = LLMLoader()
    # Verify the calculated path inside the loader instance
    expected_model_path = "/home/ubuntu/jarvis-core/models/Meta-Llama-3-8B-Instruct.Q4_0.gguf"
    assert loader.model_path == expected_model_path

    llm = loader.load()

    mock_os_path_exists.assert_called_once_with(expected_model_path)
    mock_gpt4all_class.assert_called_once_with(
        model=expected_model_path,
        device="cpu",
        n_threads=4,
        verbose=True
    )
    assert llm == mock_llm_instance

@patch("src.core.llm_manager.os.path.abspath", return_value="/home/ubuntu/jarvis-core/src/core/llm_manager.py")
@patch("src.core.llm_manager.os.path.exists")
@patch("src.core.llm_manager.GPT4All")
def test_llm_loader_init_and_load_success_gpu(mock_gpt4all_class, mock_os_path_exists, mock_os_path_abspath, mock_env_vars):
    """Test successful initialization and loading with GPU settings."""
    mock_env_vars.setenv("USE_GPU", "1")
    mock_os_path_exists.return_value = True
    mock_llm_instance = MagicMock()
    mock_gpt4all_class.return_value = mock_llm_instance

    loader = LLMLoader()
    expected_model_path = "/home/ubuntu/jarvis-core/models/Meta-Llama-3-8B-Instruct.Q4_0.gguf"
    assert loader.model_path == expected_model_path

    llm = loader.load()

    mock_os_path_exists.assert_called_once_with(expected_model_path)
    mock_gpt4all_class.assert_called_once_with(
        model=expected_model_path,
        device="gpu",
        n_threads=4,
        verbose=True
    )
    assert llm == mock_llm_instance

@patch("src.core.llm_manager.os.path.abspath", return_value="/home/ubuntu/jarvis-core/src/core/llm_manager.py")
@patch("src.core.llm_manager.os.path.exists")
@patch("src.core.llm_manager.GPT4All")
def test_llm_loader_model_file_not_found(mock_gpt4all_class, mock_os_path_exists, mock_os_path_abspath, mock_env_vars):
    """Test behavior when the model file does not exist."""
    mock_os_path_exists.return_value = False

    loader = LLMLoader()
    expected_model_path = "/home/ubuntu/jarvis-core/models/Meta-Llama-3-8B-Instruct.Q4_0.gguf"
    assert loader.model_path == expected_model_path

    llm = loader.load()

    mock_os_path_exists.assert_called_once_with(expected_model_path)
    mock_gpt4all_class.assert_not_called()
    assert llm is None

@patch("src.core.llm_manager.os.path.abspath", return_value="/home/ubuntu/jarvis-core/src/core/llm_manager.py")
@patch("src.core.llm_manager.os.path.exists")
@patch("src.core.llm_manager.GPT4All")
def test_llm_loader_gpt4all_init_fails(mock_gpt4all_class, mock_os_path_exists, mock_os_path_abspath, mock_env_vars):
    """Test behavior when GPT4All initialization raises an exception."""
    mock_os_path_exists.return_value = True
    mock_gpt4all_class.side_effect = Exception("GPT4All init error")

    loader = LLMLoader()
    expected_model_path = "/home/ubuntu/jarvis-core/models/Meta-Llama-3-8B-Instruct.Q4_0.gguf"
    assert loader.model_path == expected_model_path

    llm = loader.load()

    mock_os_path_exists.assert_called_once_with(expected_model_path)
    mock_gpt4all_class.assert_called_once() # It should be called
    assert llm is None # Load should return None on failure

@patch("src.core.llm_manager.os.path.abspath", return_value="/home/ubuntu/jarvis-core/src/core/llm_manager.py")
@patch("src.core.llm_manager.os.path.exists")
@patch("src.core.llm_manager.GPT4All")
def test_llm_loader_high_accuracy_mode(mock_gpt4all_class, mock_os_path_exists, mock_os_path_abspath, mock_env_vars):
    """Test loading with high accuracy mode (Q8)."""
    mock_env_vars.setenv("HIGH_ACCURACY_MODE", "1")
    mock_os_path_exists.return_value = True
    mock_llm_instance = MagicMock()
    mock_gpt4all_class.return_value = mock_llm_instance

    loader = LLMLoader()
    expected_model_path = "/home/ubuntu/jarvis-core/models/Meta-Llama-3-8B-Instruct.Q8_0.gguf"
    assert loader.model_path == expected_model_path

    llm = loader.load()

    mock_os_path_exists.assert_called_once_with(expected_model_path)
    mock_gpt4all_class.assert_called_once_with(
        model=expected_model_path,
        device="cpu", # Default device
        n_threads=4,
        verbose=True
    )
    assert llm == mock_llm_instance

