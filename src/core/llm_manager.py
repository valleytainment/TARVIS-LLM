import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.llms import GPT4All
import logging
from huggingface_hub import hf_hub_download
from huggingface_hub.errors import HfHubHTTPError
import sys
from tqdm import tqdm # For progress bar
import psutil # Import psutil for CPU core count

# Import load_settings from storage_manager
from .storage_manager import load_settings

# Load environment variables from .env file (still useful for defaults like USE_GPU)
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define default model details
DEFAULT_MODEL_REPO = "QuantFactory/Meta-Llama-3-8B-Instruct-GGUF"
DEFAULT_MODEL_FILENAME_Q4KM = "Meta-Llama-3-8B-Instruct.Q4_K_M.gguf" # Recommended default
DEFAULT_MODEL_FILENAME_Q8 = "Meta-Llama-3-8B-Instruct.Q8_0.gguf" # High accuracy option
DEFAULT_MODEL_DOWNLOAD_SIZE_Q4KM = "~4.37 GB" # Approximate size for Q4_K_M

class LLMLoader:
    """Loads the appropriate local LLM based on environment and settings."""

    def __init__(self):
        """Initializes the LLMLoader, determining model path from settings or env."""
        settings = load_settings()
        custom_model_path = settings.get("llm_model_path")

        # Get base model directory, configurable via env var, default to 'models' relative to project root
        project_root = Path(__file__).resolve().parent.parent.parent
        self.model_dir = Path(os.getenv("MODEL_DIR", project_root / "models"))
        try:
            self.model_dir.mkdir(parents=True, exist_ok=True) # Ensure model dir exists
            logging.info(f"Using model directory: {self.model_dir}")
        except OSError as e:
            logging.error(f"Failed to create or access model directory {self.model_dir}: {e}")
            # Decide how to handle this - maybe raise an error? For now, log and continue, path check will fail later.

        if custom_model_path and Path(custom_model_path).is_file():
            self.model_path = Path(custom_model_path).resolve()
            self.model_name = self.model_path.name
            logging.info(f"Using custom LLM model path from settings: {self.model_path}")
        else:
            if custom_model_path:
                logging.warning(f"Custom LLM path \"{custom_model_path}\" from settings not found or invalid. Falling back to default model selection in {self.model_dir}.")
            # Fallback logic using self.model_dir
            high_accuracy = os.getenv("HIGH_ACCURACY_MODE") == "1"
            self.model_name = (
                DEFAULT_MODEL_FILENAME_Q8 if high_accuracy
                else DEFAULT_MODEL_FILENAME_Q4KM # Use Q4_K_M as default
            )
            self.model_path = self.model_dir / self.model_name # Use self.model_dir here
            logging.info(f"Using default LLM model path: {self.model_path}")

        self.use_gpu = os.getenv("USE_GPU") == "1"
        logging.info(f"LLMLoader Initialized: Model={self.model_name}, Path={self.model_path}, Use GPU={self.use_gpu}")

    def load(self):
        """Loads and returns the GPT4All LLM instance, downloading the default model if necessary."""
        # Ensure model_path is Path object for consistency
        model_file_path = Path(self.model_path)
        model_dir_used = model_file_path.parent # Directory where the model *should* be

        # Check if the model exists
        if not model_file_path.exists():
            logging.warning(f"Model file not found at {model_file_path}.")

            # Determine if this is the default path/name configuration for download trigger
            settings = load_settings()
            custom_model_path_setting = settings.get("llm_model_path")
            # Check if the *current* model_name matches the Q4_K_M default
            is_default_download_config = (not custom_model_path_setting or not Path(custom_model_path_setting).is_file()) and self.model_name == DEFAULT_MODEL_FILENAME_Q4KM

            if is_default_download_config:
                # Attempt to download the default Q4_K_M model
                logging.info(f"Attempting to download default model {self.model_name} to {model_dir_used}...")
                print(f"\nINFO: Default model {self.model_name} not found. Downloading from Hugging Face ({DEFAULT_MODEL_DOWNLOAD_SIZE_Q4KM})... This may take a while.")
                repo_id = DEFAULT_MODEL_REPO
                filename = self.model_name
                try:
                    # Ensure the target directory exists (redundant if __init__ worked, but safe)
                    model_dir_used.mkdir(parents=True, exist_ok=True)

                    downloaded_path_str = hf_hub_download(
                        repo_id=repo_id,
                        filename=filename,
                        local_dir=str(model_dir_used),
                        local_dir_use_symlinks=False,
                        resume_download=True,
                    )
                    downloaded_path = Path(downloaded_path_str)
                    logging.info(f"Model downloaded successfully to {downloaded_path}")
                    print(f"INFO: Model downloaded successfully to {downloaded_path}")

                    # Verify the downloaded path matches expected path
                    if downloaded_path.resolve() != model_file_path.resolve():
                        logging.warning(f"Downloaded path {downloaded_path} differs from expected {model_file_path}. Adjusting internal path.")
                        self.model_path = str(downloaded_path) # Update self.model_path
                        model_file_path = downloaded_path # Update local variable for subsequent check

                except HfHubHTTPError as e:
                    error_msg = f"HTTP error downloading model {filename} from {repo_id}: {e}. Please check internet connection and repository status."
                    logging.error(error_msg)
                    print(f"ERROR: {error_msg}")
                    # Raise FileNotFoundError as download failed
                    raise FileNotFoundError(f"Model download failed: {error_msg}") from e
                except Exception as e:
                    error_msg = f"Failed to download model {filename} from {repo_id}: {e}"
                    logging.error(error_msg, exc_info=True)
                    print(f"ERROR: {error_msg}")
                    # Raise FileNotFoundError as download failed
                    raise FileNotFoundError(f"Model download failed: {error_msg}") from e

                # After download attempt, re-check existence strictly at the expected path
                if not model_file_path.exists():
                    error_msg = f"Model not found at {model_file_path} even after download attempt."
                    logging.error(error_msg)
                    raise FileNotFoundError(error_msg)

            else:
                # Custom path specified but file not found, or not the default model - do not download
                error_msg = f"Model file not found at specified path {model_file_path}. Please ensure the file exists or configure the correct path in settings."
                logging.error(error_msg)
                raise FileNotFoundError(error_msg) # Raise error as per guide

        # Proceed with loading the model if it exists (either initially or after download)
        try:
            logging.info(f"Attempting to load model: {model_file_path}")
            
            # --- Performance Optimizations --- 
            # Get physical core count for thread pinning
            try:
                physical_cores = psutil.cpu_count(logical=False)
                if physical_cores is None or physical_cores <= 0:
                    physical_cores = max(1, os.cpu_count() // 2) # Estimate if psutil fails or returns invalid
                    logging.warning(f"psutil failed to get physical cores or returned invalid value, estimating {physical_cores}")
                else:
                    logging.info(f"Detected {physical_cores} physical CPU cores for thread pinning.")
            except Exception as e:
                logging.warning(f"Error getting physical core count: {e}. Using default thread count.")
                physical_cores = int(os.getenv("N_THREADS", 8)) # Fallback to env or default

            llm = GPT4All(
                model=str(model_file_path), # Ensure it's a string for GPT4All
                device="gpu" if self.use_gpu else "cpu",
                n_threads=physical_cores, # Use physical core count
                use_mmap=True, # Enable memory-mapped loading
                verbose=True
            )
            # --- End Performance Optimizations ---
            
            logging.info("LLM loaded successfully.")
            return llm
        except Exception as e:
            logging.error(f"Failed to load LLM from {model_file_path}: {e}", exc_info=True)
            if self.use_gpu:
                logging.warning("GPU loading failed. Ensure CUDA/ROCm drivers and compatible llama-cpp-python are installed.")
            print(f"ERROR: Failed to load LLM - {e}")
            # Consider re-raising the exception here instead of returning None for clearer error propagation
            raise RuntimeError(f"Failed to load LLM from {model_file_path}") from e

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing LLMLoader...")
    # Ensure .env is in the parent directory relative to this script if run directly
    # Or rely on it being in the project root when run as part of the application
    loader = LLMLoader()
    print(f"Model path determined as: {loader.model_path}")
    print(f"Checking if model exists at path: {os.path.exists(loader.model_path)}")
    # Note: This test requires the model file to be present
    # llm_instance = loader.load()
    # if llm_instance:
    #     print("LLM Instance loaded successfully.")
    #     # Example query (optional, requires model download)
    #     # try:
    #     #     response = llm_instance.invoke("What is the capital of France?")
    #     #     print(f"Test query response: {response}")
    #     # except Exception as e:
    #     #     print(f"Error during test query: {e}")
    # else:
    #     print("Failed to load LLM instance.")
    print("LLMLoader test script finished. Manual check required if model file exists.")

