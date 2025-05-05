#!/usr/bin/env python3.11
# tests/test_settings_logic.py

import sys
import os
from pathlib import Path

# Add project root to sys.path to allow absolute imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.core.storage_manager import initialize_storage_manager, LocalStorageManager, load_settings

def test_custom_local_storage_path():
    """Tests if the storage manager uses the custom local path from settings."""
    print("--- Testing Custom Local Storage Path ---")
    settings = load_settings()
    expected_path_str = settings.get("local_storage_path")
    print(f"Loaded settings: {settings}")
    print(f"Expected custom path from settings: {expected_path_str}")
    
    assert expected_path_str == "/home/ubuntu/jarvis_test_history", f"Test setup error: Expected path in settings.json is not '/home/ubuntu/jarvis_test_history', found '{expected_path_str}'"
    
    expected_path = Path(expected_path_str).resolve()
    
    # Force re-initialization to pick up current settings
    manager = initialize_storage_manager(force_reinit=True)
    
    print(f"Initialized manager type: {type(manager).__name__}")
    print(f"Manager history directory: {manager.history_dir}")
    
    assert isinstance(manager, LocalStorageManager), f"Expected LocalStorageManager, got {type(manager).__name__}"
    assert manager.history_dir == expected_path, f"Assertion Failed: Manager history_dir '{manager.history_dir}' does not match expected path '{expected_path}'"
    
    print("Custom local storage path test PASSED.")

# Add tests for other settings later if needed
# def test_custom_llm_path(): ...
# def test_custom_prompt_path(): ...

if __name__ == "__main__":
    test_custom_local_storage_path()
    print("\nSettings logic tests finished.")

