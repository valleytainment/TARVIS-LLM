#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.llms import GPT4All
import logging
from huggingface_hub import hf_hub_download
from huggingface_hub.errors import HfHubHTTPError
import sys
from tqdm import tqdm # For progress bar

# Import load_settings from storage_manager
from .storage_manager import load_settings

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define supported quantization levels and their filenames
SUPPORTED_QUANTS = {
    "Q4_0": "Meta-Llama-3-8B-Instruct.Q4_0.gguf", # Original default
    "Q4_K_M": "Meta-Llama-3-8B-Instruct.Q4_K_M.gguf", # Recommended balance
    "Q5_K_M": "Meta-Llama-3-8B-Instruct.Q5_K_M.gguf",
    "Q8_0": "Meta-Llama-3-8B-Instruct.Q8_0.gguf", # Higher accuracy
}
DEFAULT_QUANT = "Q4_K_M" # Default preference

class LLMLoader:
    """Loads the appropriate local LLM based on environment and settings."""

    def __init__(self):
        """Initializes the LLMLoader, determining model path and configuration."""
        settings = load_settings()
        custom_model_path = settings.get("llm_model_path")

        # --- Performance/Configuration Settings ---
        self.use_gpu = os.getenv("USE_GPU") == "1"
        # Read N_GPU_LAYERS, default to 0 (no layers offloaded)
        try:
            self.n_gpu_layers = int(os.getenv("N_GPU_LAYERS", 0))
            if self.n_gpu_layers < 0:
                logging.warning(f"N_GPU_LAYERS cannot be negative, defaulting to 0. Value provided: {self.n_gpu_layers}")
                self.n_gpu_layers = 0
        except ValueError:
            logging.warning(f"Invalid N_GPU_LAYERS value, must be an integer. Defaulting to 0. Value provided: {os.getenv('N_GPU_LAYERS')}")
            self.n_gpu_layers = 0

        # Read USE_MLOCK, default to False
        self.use_mlock = os.getenv("USE_MLOCK") == "1"

        # Read LLM_QUANT_PREFERENCE, default to DEFAULT_QUANT
        self.quant_preference = os.getenv("LLM_QUANT_PREFERENCE", DEFAULT_QUANT)
        if self.quant_preference not in SUPPORTED_QUANTS:
            logging.warning(f"Invalid LLM_QUANT_PREFERENCE '{self.quant_preference}'. Must be one of {list(SUPPORTED_QUANTS.keys())}. Defaulting to {DEFAULT_QUANT}.")
            self.quant_preference = DEFAULT_QUANT
        # --- End Performance/Configuration Settings ---

        # Determine model path and name
        if custom_model_path and Path(custom_model_path).is_file():
            self.model_path = str(Path(custom_model_path).resolve())
            self.model_name = Path(self.model_path).name
            logging.info(f"Using custom LLM model path from settings: {self.model_path}")
        else:
            if custom_model_path:
                logging.warning(f"Custom LLM path \"{custom_model_path}\" from settings not found or invalid. Falling back to default model selection.")
            # Determine default model name based on quantization preference
            self.model_name = SUPPORTED_QUANTS[self.quant_preference]
            project_root = Path(__file__).resolve().parent.parent.parent
            # Default model directory (can be overridden by MODEL_DIR env var)
            model_dir_base = os.getenv("MODEL_DIR", str(project_root / "models"))
            self.model_path = str(Path(model_dir_base).resolve() / self.model_name)
            logging.info(f"Using default LLM model path based on preference '{self.quant_preference}': {self.model_path}")

        # Log final configuration
        logging.info(
            f"LLMLoader Initialized: Model={self.model_name}, Path={self.model_path}, "
            f"Use GPU={self.use_gpu}, GPU Layers={self.n_gpu_layers}, "
            f"Use MLock={self.use_mlock}, Quant Preference='{self.quant_preference}'"
        )

    def _download_default_model(self, model_dir):
        """Attempts to download the selected default model."""
        logging.info(f"Attempting to download default model {self.model_name}...")
        print(f"\nINFO: Default model {self.model_name} not found. Downloading from Hugging Face... This may take a while.")
        # Assuming QuantFactory repo structure is consistent
        repo_id = "QuantFactory/Meta-Llama-3-8B-Instruct-GGUF"
        filename = self.model_name
        try:
            # Ensure the target directory exists
            model_dir.mkdir(parents=True, exist_ok=True)

            downloaded_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=str(model_dir),
                local_dir_use_symlinks=False, # Download the actual file
                resume_download=True,
                # Progress bar is usually handled automatically by huggingface_hub if tqdm is installed
            )
            logging.info(f"Model downloaded successfully to {downloaded_path}")
            print(f"INFO: Model downloaded successfully to {downloaded_path}")
            # Verify the downloaded path matches expected path
            if Path(downloaded_path) != Path(self.model_path):
                logging.warning(f"Downloaded path {downloaded_path} differs from expected {self.model_path}. Adjusting internal path.")
                self.model_path = str(downloaded_path)
            return True # Download successful

        except HfHubHTTPError as e:
            error_msg = f"HTTP error downloading model {filename} from {repo_id}: {e}. Please check your internet connection and the Hugging Face repository status."
            logging.error(error_msg)
            print(f"ERROR: {error_msg}")
            return False # Download failed
        except Exception as e:
            error_msg = f"Failed to download model {filename} from {repo_id}: {e}"
            logging.error(error_msg, exc_info=True)
            print(f"ERROR: {error_msg}")
            return False # Download failed

    def load(self):
        """Loads and returns the GPT4All LLM instance, downloading the default model if necessary."""
        model_file_path = Path(self.model_path)
        model_dir = model_file_path.parent

        # Check if the model exists
        if not model_file_path.exists():
            logging.warning(f"Model file not found at {self.model_path}.")

            # Determine if this is a default path or a custom path
            settings = load_settings()
            custom_model_path_setting = settings.get("llm_model_path")
            is_default_path = not custom_model_path_setting or not Path(custom_model_path_setting).is_file()

            if is_default_path and self.model_name in SUPPORTED_QUANTS.values():
                # Attempt to download the selected default model
                if not self._download_default_model(model_dir):
                    return None # Download failed
                # Update model_file_path in case download adjusted self.model_path
                model_file_path = Path(self.model_path)
            else:
                # Custom path specified but file not found, or not a downloadable default model
                error_msg = f"Model file not found at specified path {self.model_path}. Please ensure the file exists or configure the correct path in settings."
                logging.error(error_msg)
                print(f"ERROR: {error_msg}")
                return None

        # Proceed with loading the model if it exists (either initially or after download)
        if model_file_path.exists():
            try:
                logging.info(f"Attempting to load model: {self.model_path} with {self.n_gpu_layers} GPU layers and mlock={self.use_mlock}")

                # Determine device based on n_gpu_layers
                # llama.cpp backend often handles device automatically when n_gpu_layers > 0
                # Setting device explicitly might conflict, let's rely on n_gpu_layers
                # device_setting = "gpu" if self.n_gpu_layers > 0 else "cpu"
                # logging.info(f"Setting device based on n_gpu_layers: {device_setting}")

                llm = GPT4All(
                    model=self.model_path,
                    # device=device_setting, # Let llama.cpp handle device based on n_gpu_layers
                    n_gpu_layers=self.n_gpu_layers,
                    use_mlock=self.use_mlock,
                    n_threads=int(os.getenv("N_THREADS", 8)), # Keep configurable thread count
                    verbose=True # Enable backend logging
                )
                logging.info("LLM loaded successfully.")
                return llm
            except Exception as e:
                logging.error(f"Failed to load LLM: {e}", exc_info=True)
                if self.n_gpu_layers > 0:
                    logging.warning("GPU loading failed (n_gpu_layers > 0). Ensure CUDA/ROCm drivers and compatible llama-cpp-python are installed.")
                print(f"ERROR: Failed to load LLM - {e}")
                return None
        else:
            # Should not happen if download logic is correct, but as a fallback
            logging.error(f"Model file still not found at {self.model_path} after download attempt.")
            return None

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing LLMLoader with new optimizations...")
    # Ensure .env is in the parent directory relative to this script if run directly
    # Or rely on it being in the project root when run as part of the application
    loader = LLMLoader()
    print(f"Model path determined as: {loader.model_path}")
    print(f"Model Name: {loader.model_name}")
    print(f"Use GPU: {loader.use_gpu}")
    print(f"GPU Layers: {loader.n_gpu_layers}")
    print(f"Use MLock: {loader.use_mlock}")
    print(f"Quant Preference: {loader.quant_preference}")
    print(f"Checking if model exists at path: {os.path.exists(loader.model_path)}")

    # Note: The actual loading test requires the model file to be present
    # print("\nAttempting to load LLM instance (requires model file)...")
    # llm_instance = loader.load()
    # if llm_instance:
    #     print("LLM Instance loaded successfully.")
    #     # Example query (optional, requires model download)
    #     # try:
    #     #     response = llm_instance.invoke("Explain the concept of GPU offloading in LLMs.")
    #     #     print(f"Test query response: {response}")
    #     # except Exception as e:
    #     #     print(f"Error during test query: {e}")
    # else:
    #     print("Failed to load LLM instance.")
    print("\nLLMLoader test script finished. Manual check required if model file exists.")

