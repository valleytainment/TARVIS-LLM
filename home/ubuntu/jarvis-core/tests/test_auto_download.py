#!/usr/bin/env python3.11
# tests/test_auto_download.py

import sys
import os
from pathlib import Path

# Add project root to sys.path to allow imports from src
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.core.llm_manager import LLMLoader

def test_download():
    print("--- Testing Automatic LLM Download ---")
    # Ensure the default model is not present (should have been removed earlier)
    default_model_name = "Meta-Llama-3-8B-Instruct.Q4_0.gguf"
    default_model_path = project_root / "models" / default_model_name
    if default_model_path.exists():
        print(f"WARNING: Default model found at {default_model_path}. Removing it to test download.")
        os.remove(default_model_path)
    else:
        print(f"Confirmed: Default model not present at {default_model_path}.")

    # Instantiate loader (this determines the path)
    print("Instantiating LLMLoader...")
    loader = LLMLoader()

    # Call load() - this should trigger the download if the default model is selected and missing
    print("Calling loader.load()... This might take a while if download is triggered.")
    llm_instance = loader.load()

    if llm_instance:
        print("--- Test Result: SUCCESS ---")
        print("LLM instance loaded successfully (download likely completed if model was missing).")
        # Verify the model file now exists
        if default_model_path.exists():
            print(f"Confirmed: Model file now exists at {default_model_path}.")
        else:
            # This case might happen if a custom path was somehow still active
            print(f"WARNING: LLM loaded, but default model file not found at {default_model_path}. Check loader logic or settings.")
    else:
        print("--- Test Result: FAILED ---")
        print("Failed to load LLM instance. Download may have failed or another error occurred.")

if __name__ == "__main__":
    test_download()

