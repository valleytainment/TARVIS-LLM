#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys
import warnings # Import warnings module

# --- Suppress specific CUDA/Torch warnings ---
# Filter the specific UserWarning from Torch about DLL loading
# Corrected syntax: message pattern must be a string
warnings.filterwarnings("ignore", message=r".*Failed to load image Python extension.*", category=UserWarning)
warnings.filterwarnings("ignore", message=r".*`GPT4All` model path is not specified.*", category=UserWarning) # Also suppress this common one
# You might need to add more specific filters if other warnings appear
# ---------------------------------------------

from langchain_community.llms import GPT4All
from huggingface_hub import hf_hub_download
from huggingface_hub.errors import HfHubHTTPError
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
        try:
            # Default to -1 for n_gpu_layers if USE_GPU is true, 0 otherwise
            # This lets llama.cpp decide how many layers to offload if not specified
            default_gpu_layers = -1 if self.use_gpu else 0
            self.n_gpu_layers = int(os.getenv("N_GPU_LAYERS", default_gpu_layers))
            # Allow -1 as a valid value (means max possible layers)
            if self.n_gpu_layers < -1:
                logging.warning(f"N_GPU_LAYERS cannot be less than -1, defaulting to {default_gpu_layers}. Value provided: {self.n_gpu_layers}")
                self.n_gpu_layers = default_gpu_layers
        except ValueError:
            logging.warning(f"Invalid N_GPU_LAYERS value, must be an integer. Defaulting to {default_gpu_layers}. Value provided: {os.getenv('N_GPU_LAYERS')}")
            self.n_gpu_layers = default_gpu_layers

        self.use_mlock = os.getenv("USE_MLOCK") == "1"

        self.quant_preference = os.getenv("LLM_QUANT_PREFERENCE", DEFAULT_QUANT)
        if self.quant_preference not in SUPPORTED_QUANTS:
            logging.warning(f"Invalid LLM_QUANT_PREFERENCE '{self.quant_preference}'. Must be one of {list(SUPPORTED_QUANTS.keys())}. Defaulting to {DEFAULT_QUANT}.")
            self.quant_preference = DEFAULT_QUANT
        # --- End Performance/Configuration Settings ---

        if custom_model_path and Path(custom_model_path).is_file():
            self.model_path = str(Path(custom_model_path).resolve())
            self.model_name = Path(self.model_path).name
            logging.info(f"Using custom LLM model path from settings: {self.model_path}")
        else:
            if custom_model_path:
                logging.warning(f"Custom LLM path \"{custom_model_path}\" from settings not found or invalid. Falling back to default model selection.")
            self.model_name = SUPPORTED_QUANTS[self.quant_preference]
            project_root = Path(__file__).resolve().parent.parent.parent
            model_dir_base = os.getenv("MODEL_DIR", str(project_root / "models"))
            self.model_path = str(Path(model_dir_base).resolve() / self.model_name)
            logging.info(f"Using default LLM model path based on preference '{self.quant_preference}': {self.model_path}")

        logging.info(
            f"LLMLoader Initialized: Model={self.model_name}, Path={self.model_path}, "
            f"Use GPU={self.use_gpu}, GPU Layers={self.n_gpu_layers}, "
            f"Use MLock={self.use_mlock}, Quant Preference='{self.quant_preference}'"
        )

    def _download_default_model(self, model_dir):
        """Attempts to download the selected default model."""
        logging.info(f"Attempting to download default model {self.model_name}...")
        print(f"\nINFO: Default model {self.model_name} not found. Downloading from Hugging Face... This may take a while.")
        repo_id = "QuantFactory/Meta-Llama-3-8B-Instruct-GGUF"
        filename = self.model_name
        try:
            model_dir.mkdir(parents=True, exist_ok=True)
            downloaded_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=str(model_dir),
                local_dir_use_symlinks=False,
                resume_download=True,
            )
            logging.info(f"Model downloaded successfully to {downloaded_path}")
            print(f"INFO: Model downloaded successfully to {downloaded_path}")
            if Path(downloaded_path) != Path(self.model_path):
                logging.warning(f"Downloaded path {downloaded_path} differs from expected {self.model_path}. Adjusting internal path.")
                self.model_path = str(downloaded_path)
            return True
        except HfHubHTTPError as e:
            error_msg = f"HTTP error downloading model {filename} from {repo_id}: {e}. Please check your internet connection and the Hugging Face repository status."
            logging.error(error_msg)
            print(f"ERROR: {error_msg}")
            return False
        except Exception as e:
            error_msg = f"Failed to download model {filename} from {repo_id}: {e}"
            logging.error(error_msg, exc_info=True)
            print(f"ERROR: {error_msg}")
            return False

    def load(self):
        """Loads and returns the GPT4All LLM instance, downloading the default model if necessary."""
        model_file_path = Path(self.model_path)
        model_dir = model_file_path.parent

        if not model_file_path.exists():
            logging.warning(f"Model file not found at {self.model_path}.")
            settings = load_settings()
            custom_model_path_setting = settings.get("llm_model_path")
            is_default_path = not custom_model_path_setting or not Path(custom_model_path_setting).is_file()

            if is_default_path and self.model_name in SUPPORTED_QUANTS.values():
                if not self._download_default_model(model_dir):
                    return None
                model_file_path = Path(self.model_path) # Update path after potential download
            else:
                error_msg = f"Model file not found at specified path {self.model_path}. Please ensure the file exists or configure the correct path in settings."
                logging.error(error_msg)
                print(f"ERROR: {error_msg}")
                return None

        if model_file_path.exists():
            try:
                # --- Prepare backend_kwargs for GPU layers (COMMENTED OUT) ---
                # backend_kwargs = {}
                # if self.use_gpu:
                #     backend_kwargs["n_gpu_layers"] = self.n_gpu_layers
                #     logging.info(f"GPU enabled. Passing n_gpu_layers={self.n_gpu_layers} to backend.")
                # else:
                #     logging.info("GPU not enabled. n_gpu_layers setting ignored.")
                # --- End backend_kwargs preparation ---

                # Note: GPT4All doesn't directly use `device` kwarg like some other LangChain LLMs.
                # It relies on backend compilation flags.
                # backend_kwargs removed due to ValidationError in current GPT4All version.
                # GPU layer offloading via N_GPU_LAYERS might not work with this wrapper.
                # Consider using LlamaCpp directly if GPU offloading is critical.
                logging.info(f"Attempting to load model: {self.model_path} with n_threads={int(os.getenv('N_THREADS', 8))}, mlock={self.use_mlock}, streaming=True")

                llm = GPT4All(
                    model=self.model_path,
                    # backend_kwargs=backend_kwargs, # Removed: Causes ValidationError
                    use_mlock=self.use_mlock,
                    n_threads=int(os.getenv('N_THREADS', 8)), # Use single quotes inside f-string
                    streaming=True,
                    verbose=True
                )
                logging.info("LLM loaded successfully with streaming enabled.")
                return llm
            except Exception as e:
                logging.error(f"Failed to load LLM: {e}", exc_info=True)
                if self.use_gpu:
                    logging.warning("GPU loading failed. Ensure CUDA/ROCm drivers and compatible llama-cpp-python (with GPU support) are installed.")
                print(f"ERROR: Failed to load LLM - {e}")
                return None
        else:
            # This case should ideally not be reached if download logic works
            logging.error(f"Model file still not found at {self.model_path} after download attempt.")
            return None

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing LLMLoader with new optimizations...")
    loader = LLMLoader()
    print(f"Model path determined as: {loader.model_path}")
    print(f"Model Name: {loader.model_name}")
    print(f"Use GPU Setting: {loader.use_gpu}")
    print(f"GPU Layers Setting: {loader.n_gpu_layers}")
    print(f"Use MLock: {loader.use_mlock}")
    print(f"Quant Preference: {loader.quant_preference}")
    print(f"Checking if model exists at path: {os.path.exists(loader.model_path)}")
    print("\nAttempting to load model (this might download if missing or fail if backend issues exist)...")
    loaded_llm = loader.load()
    if loaded_llm:
        print("Model loaded successfully (instance created).")
    else:
        print("Model loading failed. Check logs above.")
    print("\nLLMLoader test script finished.")

