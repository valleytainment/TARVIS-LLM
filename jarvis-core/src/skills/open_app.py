import subprocess
import yaml
import os
import platform
import logging

# Configure logginglogging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Determine the path to the config file relative to this script
# Assumes this script is in src/skills and config is at project_root/config
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
config_path = os.path.join(project_root, "config", "app_paths.yaml")

def load_app_paths():
    """Loads application paths from the YAML configuration file."""
    try:
      with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            # Get paths for the current OS (Windows in this case)
            os_name = platform.system()
            if os_name == "Windows":
                return config.get("open_app", {}).get("paths", {}).get("Windows", {})
            else:
                # Placeholder for other OS if needed later
                logging.warning(f"Application paths not configured for OS: {os_name}")
                return {}
    except FileNotFoundError:
        logging.error(f"Configuration file not found at {config_path}")
        return {}
    except yaml.YAMLError as e:
        logging.error(f"Error parsing configuration file {config_path}: {e}")
        return {}
    except Exception as e:
        logging.error(f"Unexpected error loading app paths: {e}", exc_info=True)
        return {}

def execute(app_name: str) -> str:
    """Launches the specified application based on the configuration for Windows."""
    app_name_lower = app_name.lower()
    logging.info(f"Attempting to launch application: {app_name}")
    app_paths = load_app_paths()

    if not app_paths:
        return f"❌ Error: Application paths configuration is missing or failed to load."

    # Find the application path (case-insensitive key matching)
    app_path = None
    for key, path in app_paths.items():
        if key.lower() == app_name_lower:
            app_path = path
            break

    if not app_path:
        logging.warning(f"Application 	'{app_name}'	 not found in configuration. Attempting fallback.")
        # Attempt to run directly if not in config, might work for apps in PATH
        try:
            logging.debug(f"Fallback: Attempting to launch '{app_name_lower}' directly.")
            # Use shell=True cautiously on Windows if needed, but prefer direct execution
            # Using start /B to run in background without a new console window
            subprocess.Popen(f'start /B "" "{app_name_lower}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logging.info(f"Launched '{app_name}' directly (not found in config, assumed in PATH).")
            return f"✅ Launched '{app_name}' (assumed in PATH)."
        except Exception as e:
            error_msg = f"❌ Error launching '{app_name}': Not found in config and failed to launch directly. Error: {e}"
            logging.error(error_msg, exc_info=True)
            return error_msg    # Expand environment variables like %USERNAME%
    expanded_path = os.path.expandvars(app_path)

    try:
        # Use subprocess.Popen for non-blocking execution
        # No shell=True needed when providing the full path
        logging.info(f"Launching \'{app_name}\' using path: {expanded_path}")
        subprocess.Popen([expanded_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"✅ Launched {app_name}"
    except FileNotFoundError:
        error_msg = f"❌ Error: Application executable not found at path: {expanded_path}"
        logging.error(error_msg)
        return error_msg
    except PermissionError:
        error_msg = f"❌ Error: Permission denied when trying to execute: {expanded_path}"
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ Error launching {app_name}: {e}"
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

