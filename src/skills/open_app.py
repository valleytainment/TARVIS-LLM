#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import yaml
import os
import platform
import logging
from langchain.tools import tool # Import the decorator

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Determine the path to the config file relative to this script
# Assumes this script is in src/skills and config is at project_root/config
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
config_path = os.path.join(project_root, "config", "app_paths.yaml")

def load_app_paths():
    """Loads application paths from the YAML configuration file."""
    try:
        # Ensure config directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        # Create default config if it doesn't exist
        if not os.path.exists(config_path):
            logging.warning(f"Config file {config_path} not found. Creating default.")
            default_config = {
                "open_app": {
                    "paths": {
                        "Windows": {
                            "notepad": "notepad.exe",
                            "calculator": "calc.exe",
                            "firefox": "C:\\Program Files\\Mozilla Firefox\\firefox.exe"
                        },
                        "Linux": {
                            "gedit": "/usr/bin/gedit",
                            "calculator": "/usr/bin/gnome-calculator",
                            "firefox": "/usr/bin/firefox"
                        },
                        "Darwin": { # macOS
                            "TextEdit": "/System/Applications/TextEdit.app/Contents/MacOS/TextEdit",
                            "Calculator": "/System/Applications/Calculator.app/Contents/MacOS/Calculator",
                            "Firefox": "/Applications/Firefox.app/Contents/MacOS/firefox"
                        }
                    }
                }
            }
            with open(config_path, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            # Get paths for the current OS
            os_name = platform.system()
            return config.get("open_app", {}).get("paths", {}).get(os_name, {})
    except FileNotFoundError:
        logging.error(f"Configuration file not found at {config_path} even after attempting creation.")
        return {}
    except yaml.YAMLError as e:
        logging.error(f"Error parsing configuration file {config_path}: {e}")
        return {}
    except Exception as e:
        logging.error(f"Unexpected error loading app paths: {e}", exc_info=True)
        return {}

@tool
def open_application(app_name: str) -> str:
    """Opens or launches a specified application on the computer (e.g., Firefox, Notepad, Calculator, TextEdit). Input should be the name of the application as defined in the configuration or available in the system's PATH."""
    app_name_lower = app_name.lower()
    logging.info(f"Attempting to launch application: {app_name}")
    app_paths = load_app_paths()
    os_name = platform.system()

    if not app_paths:
        # Even if config load fails, still try PATH fallback
        logging.warning(f"Application paths configuration failed to load or is empty for OS: {os_name}. Will attempt PATH fallback.")

    # Find the application path (case-insensitive key matching)
    app_path = None
    for key, path in app_paths.items():
        if key.lower() == app_name_lower:
            app_path = path
            break

    if app_path:
        # Expand environment variables like %USERNAME% or $HOME
        expanded_path = os.path.expandvars(app_path)
        try:
            logging.info(f"Launching \'{app_name}\' using configured path: {expanded_path}")
            if os_name == "Windows":
                # Use start /B on Windows to avoid blocking and console windows
                subprocess.Popen(f'start /B "" "{expanded_path}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif os_name == "Darwin": # macOS
                 # Use 'open' command on macOS
                 subprocess.Popen(["open", expanded_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else: # Linux and other Unix-like
                # Simple Popen should work, detaches automatically
                subprocess.Popen([expanded_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"✅ Launched {app_name} using configured path."
        except FileNotFoundError:
            error_msg = f"❌ Error: Configured application executable not found at path: {expanded_path}"
            logging.error(error_msg)
            # Fall through to PATH check
        except PermissionError:
            error_msg = f"❌ Error: Permission denied when trying to execute configured path: {expanded_path}"
            logging.error(error_msg)
            return error_msg # Don't fallback if permission denied on specific path
        except Exception as e:
            error_msg = f"❌ Error launching {app_name} using configured path {expanded_path}: {e}"
            logging.error(error_msg, exc_info=True)
            # Fall through to PATH check

    # Fallback: Try launching directly (assumes app is in PATH)
    logging.warning(f"Application \'{app_name}\' not found in configuration or launch failed. Attempting PATH fallback.")
    try:
        if os_name == "Windows":
            subprocess.Popen(f'start /B "" "{app_name_lower}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif os_name == "Darwin":
             # Use 'open -a' to search for app by name/bundle identifier
             subprocess.Popen(["open", "-a", app_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else: # Linux
            # Rely on which/PATH lookup by Popen
            subprocess.Popen([app_name_lower], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f"Launched \'{app_name}\' via PATH fallback.")
        return f"✅ Launched 	'{app_name}	' (assumed in PATH)."
    except Exception as e:
        error_msg = f"❌ Error launching 	'{app_name}	': Not found in config and failed PATH fallback. Error: {e}"
        logging.error(error_msg)
        # Do not include exc_info=True for simple FileNotFoundError during fallback
        if not isinstance(e, FileNotFoundError):
             logging.error("Exception details for PATH fallback failure:", exc_info=True)
        return error_msg

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing open_app skill...")
    # Test with an app expected in config (case-insensitive)
    result_notepad = open_application("notepad") # Use the decorated function name
    print(f"Notepad launch result: {result_notepad}")
    # Test with an app likely in PATH but maybe not in config
    result_calc = open_application("calculator")
    print(f"Calculator launch result: {result_calc}")
    # Test with a non-existent app
    result_fake = open_application("nonexistentapp123")
    print(f"Non-existent app launch result: {result_fake}")
    print("open_app test finished.")

