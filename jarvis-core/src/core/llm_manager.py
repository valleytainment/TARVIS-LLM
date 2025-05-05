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

# Load environment variables from .env file (still useful for defaults like USE_GPU)
load_dotenv()

# Configure logginglogging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
class LLMLoader:
    """Loads the appropriate local LLM based on environment and settings."""

    def __init__(self):
        """Initializes the LLMLoader, determining model path from settings or .env."""
        settings = load_settings()
        custom_model_path = settings.get("llm_model_path")

        if custom_model_path and Path(custom_model_path).is_file():
            self.model_path = str(Path(custom_model_path).resolve())
            self.model_name = Path(self.model_path).name
            logging.info(f"Using custom LLM model path from settings: {self.model_path}")
        else:
            if custom_model_path:
                logging.warning(f"Custom LLM path \"{custom_model_path}\" from settings not found or invalid. Falling back to default model selection.")
            # Fallback logic (existing behavior)
            high_accuracy = os.getenv("HIGH_ACCURACY_MODE") == "1"
            self.model_name = (
                "Meta-Llama-3-8B-Instruct.Q8_0.gguf" if high_accuracy
                else "Meta-Llama-3-8B-Instruct.Q4_0.gguf"
            )
            project_root = Path(__file__).resolve().parent.parent.parent
            self.model_path = str(project_root / "models" / self.model_name)
            logging.info(f"Using default LLM model path: {self.model_path}")

        self.use_gpu = os.getenv("USE_GPU") == "1"
        logging.info(f"LLMLoader Initialized: Model={self.model_name}, Path={self.model_path}, Use GPU={self.use_gpu}")

    def load(self):
        """Loads and returns the GPT4All LLM instance, downloading the default model if necessary."""
        model_file_path = Path(self.model_path)
        model_dir = model_file_path.parent

        # Check if the model exists
        if not model_file_path.exists():
            logging.warning(f"Model file not found at {self.model_path}.")

            # Determine if this is the default path or a custom path
            settings = load_settings()
            custom_model_path_setting = settings.get("llm_model_path")
            is_default_path = not custom_model_path_setting or not Path(custom_model_path_setting).is_file()

            if is_default_path and self.model_name == "Meta-Llama-3-8B-Instruct.Q4_0.gguf":
                # Attempt to download the default model
                logging.info(f"Attempting to download default model {self.model_name}...")
                print(f"\nINFO: Default model {self.model_name} not found. Downloading from Hugging Face (approx. 4.66 GB)... This may take a while.")
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
                    # Verify the downloaded path matches expected path (it should if local_dir is set correctly)
                    if Path(downloaded_path) != model_file_path:
                        logging.warning(f"Downloaded path {downloaded_path} differs from expected {model_file_path}. Adjusting internal path.")
                        self.model_path = str(downloaded_path)
                        model_file_path = Path(self.model_path)

                except HfHubHTTPError as e:
                    error_msg = f"HTTP error downloading model {filename} from {repo_id}: {e}. Please check your internet connection and the Hugging Face repository status."
                    logging.error(error_msg)
                    print(f"ERROR: {error_msg}")
                    return None
                except Exception as e:
                    error_msg = f"Failed to download model {filename} from {repo_id}: {e}"
                    logging.error(error_msg, exc_info=True)
                    print(f"ERROR: {error_msg}")
                    return None
            else:
                # Custom path specified but file not found, or not the default model - do not download
                error_msg = f"Model file not found at specified path {self.model_path}. Please ensure the file exists or configure the correct path in settings."
                logging.error(error_msg)
                print(f"ERROR: {error_msg}")
                return None

        # Proceed with loading the model if it exists (either initially or after download)
        if model_file_path.exists():
            try:
                logging.info(f"Attempting to load model: {self.model_path}")
                llm = GPT4All(
                    model=self.model_path,
                    device="gpu" if self.use_gpu else "cpu",
                    n_threads=int(os.getenv("N_THREADS", 8)),
                    verbose=True
                )
                logging.info("LLM loaded successfully.")
                return llm
            except Exception as e:
                logging.error(f"Failed to load LLM: {e}", exc_info=True)
                if self.use_gpu:
                    logging.warning("GPU loading failed. Ensure CUDA/ROCm drivers and compatible llama-cpp-python are installed.")
                print(f"ERROR: Failed to load LLM - {e}")
                return None
        else:
            # Should not happen if download logic is correct, but as a fallback
            logging.error(f"Model file still not found at {self.model_path} after download attempt.")
            return None

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

