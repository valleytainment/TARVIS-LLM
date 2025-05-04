import subprocess
import yaml
import os
import platform
import logging
import shutil # Added for shutil.which
from pathlib import Path # Added for Path object handling

# Configure logginglogging.basicConfig(level=logging.INFO, format=\"%(asctime)s - %(levelname)s - %(message)s\")
# Determine the path to the config file relative to this script
project_root = Path(__file__).resolve().parent.parent.parent
config_path = project_root / "config" / "app_paths.yaml"

def load_config():
    """Loads the entire app_paths.yaml configuration."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logging.error(f"Configuration file not found at {config_path}")
        return {}
    except yaml.YAMLError as e:
        logging.error(f"Error parsing configuration file {config_path}: {e}")
        return {}
    except Exception as e:
        logging.error(f"Unexpected error loading app paths config: {e}", exc_info=True)
        return {}

def resolve_app_path(app_name: str) -> Path | None:
    """Resolves the application path based on OS and configuration, falling back to shutil.which."""
    os_name = platform.system()
    config = load_config()
    os_paths = config.get("open_app", {}).get("paths", {}).get(os_name, {})
    app_name_lower = app_name.lower()

    # Check config first (case-insensitive key matching)
    config_path_str = None
    for key, path_str in os_paths.items():
        if key.lower() == app_name_lower:
            config_path_str = path_str
            break

    if config_path_str:
        # Expand environment variables and resolve ~/
        expanded_path = Path(os.path.expandvars(config_path_str)).expanduser()
        if expanded_path.exists():
            logging.info(f"Resolved 	'{app_name}	' path from config: {expanded_path}")
            return expanded_path
        else:
            logging.warning(f"Path for 	'{app_name}	' found in config ({expanded_path}) but does not exist. Falling back to PATH search.")

    # Fallback to searching in system PATH
    logging.info(f"App 	'{app_name}	' not found or invalid in config for {os_name}. Searching PATH...")
    path_in_env = shutil.which(app_name_lower)
    if path_in_env:
        resolved_path = Path(path_in_env)
        logging.info(f"Resolved 	'{app_name}	' path using shutil.which: {resolved_path}")
        return resolved_path

    logging.error(f"Could not resolve path for application: {app_name}")
    return None

def execute(app_name: str) -> str:
    """Launches the specified application using cross-platform path resolution."""
    logging.info(f"Attempting to launch application: {app_name}")
    app_path = resolve_app_path(app_name)

    if not app_path:
        return f"❌ Error: Could not find or resolve path for application 	'{app_name}	'."

    try:
        # Use subprocess.Popen for non-blocking execution
        logging.info(f"Launching \'{app_name}\' using path: {app_path}")
        # For macOS .app bundles, use 'open' command
        if platform.system() == "Darwin" and str(app_path).endswith(".app"):
             # Check if it's the executable inside Contents/MacOS or the .app dir itself
            if "Contents/MacOS" in str(app_path):
                 subprocess.Popen([str(app_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else: # Assume it's the .app directory
                 subprocess.Popen(["open", str(app_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen([str(app_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"✅ Launched {app_name}"
    except FileNotFoundError: # Should be less likely now with resolve_app_path
        error_msg = f"❌ Error: Application executable not found at resolved path: {app_path}"
        logging.error(error_msg)
        return error_msg
    except PermissionError:
        error_msg = f"❌ Error: Permission denied when trying to execute: {app_path}"
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ Error launching {app_name} with path {app_path}: {e}"
        logging.error(error_msg, exc_info=True)
        return error_msg

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing open_app skill...")
    # Test with an app expected in config (case-insensitive)
    result_notepad = execute("notepad")
    print(f"Notepad launch result: {result_notepad}")
    # Test with an app likely in PATH but maybe not in config
    # result_calc = execute("calc")
    # print(f"Calculator launch result: {result_calc}")
    # Test with a non-existent app
    result_fake = execute("nonexistentapp123")
    print(f"Non-existent app launch result: {result_fake}")
    print("open_app test finished.")

