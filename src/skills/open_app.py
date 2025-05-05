#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import yaml
import os
import platform
import logging
import shutil # Added for finding executables in PATH
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
        # Create default config if it doesn\\\\'t exist
        if not os.path.exists(config_path):
            logging.warning(f"Config file {config_path} not found. Creating default.")
            default_config = {
                "open_app": {
                    "paths": {
                        "Windows": {
                            "notepad": "notepad.exe",
                            "calculator": "calc.exe",
                            "firefox": "C:\\\\Program Files\\\\Mozilla Firefox\\\\firefox.exe"
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
            with open(config_path, \'w\') as f:
                yaml.dump(default_config, f, default_flow_style=False)

        with open(config_path, \'r\') as f:
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
    """Opens or launches a specified application based on pre-configured paths or system PATH.
    
    SECURITY WARNING: This tool executes external applications. Ensure the configuration 
    (app_paths.yaml) is secure and the underlying system PATH is trusted. Avoid using 
    this tool with untrusted application names if possible.
    
    Args:
        app_name: The name of the application (e.g., \'Firefox\
', \'Notepad\
', \'Calculator\
', \'TextEdit\
'). 
                  Matches against keys in app_paths.yaml (case-insensitive) or attempts to find in PATH.

    Returns:
        A status message indicating success or failure.
    """
    # Basic input validation
    if not app_name or not isinstance(app_name, str):
        logging.error("Invalid app_name provided to open_application.")
        return "❌ Error: Invalid or empty application name provided."
        
    # Sanitize app_name slightly? For now, rely on config lookup and shutil.which
    # Avoid complex sanitization that might break valid names.
    app_name_cleaned = app_name.strip() # Remove leading/trailing whitespace
    if not app_name_cleaned:
        return "❌ Error: Empty application name provided after stripping whitespace."
        
    app_name_lower = app_name_cleaned.lower()
    logging.info(f"Attempting to launch application: {app_name_cleaned}")
    app_paths = load_app_paths()
    os_name = platform.system()

    if not app_paths:
        logging.warning(f"Application paths configuration failed to load or is empty for OS: {os_name}. Will attempt PATH fallback.")

    # 1. Try launching using configured path (case-insensitive key matching)
    app_path_from_config = None
    for key, path in app_paths.items():
        if key.lower() == app_name_lower:
            app_path_from_config = path
            break

    if app_path_from_config:
        # Expand environment variables like %USERNAME% or $HOME
        expanded_path = os.path.expandvars(app_path_from_config)
        # Ensure the path is absolute for security, especially before executing
        if not os.path.isabs(expanded_path):
             logging.warning(f"Configured path \"{expanded_path}\" for \"{app_name_cleaned}\" is not absolute. Attempting to resolve via PATH.")
             # Try to find the non-absolute path in PATH
             resolved_path = shutil.which(expanded_path)
             if not resolved_path:
                 error_msg = f"❌ Error: Configured relative path \"{expanded_path}\" for \"{app_name_cleaned}\" not found in PATH."
                 logging.error(error_msg)
                 # Fall through to general PATH fallback below
             else:
                 expanded_path = resolved_path # Use the absolute path found
                 logging.info(f"Resolved relative path to: {expanded_path}")
                 
        # Check if the resolved path is actually a file
        if not os.path.isfile(expanded_path):
            error_msg = f"❌ Error: Configured path \"{expanded_path}\" for \"{app_name_cleaned}\" does not exist or is not a file."
            logging.error(error_msg)
            # Fall through to general PATH fallback below
        else:
            try:
                logging.info(f"Launching \"{app_name_cleaned}\" using configured absolute path: {expanded_path}")
                # Use safer subprocess calls without shell=True
                if os_name == "Windows":
                    # Use DETACHED_PROCESS and CREATE_NO_WINDOW for GUI apps on Windows
                    subprocess.Popen([expanded_path], 
                                     stdout=subprocess.DEVNULL, 
                                     stderr=subprocess.DEVNULL, 
                                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
                elif os_name == "Darwin": # macOS
                     # Use \'open\' command on macOS - handles .app bundles correctly
                     subprocess.Popen(["open", expanded_path], 
                                      stdout=subprocess.DEVNULL, 
                                      stderr=subprocess.DEVNULL)
                else: # Linux and other Unix-like
                    # Simple Popen should work, detaches automatically
                    subprocess.Popen([expanded_path], 
                                     stdout=subprocess.DEVNULL, 
                                     stderr=subprocess.DEVNULL)
                return f"✅ Launched {app_name_cleaned} using configured path."
            except PermissionError:
                error_msg = f"❌ Error: Permission denied when trying to execute configured path: {expanded_path}"
                logging.error(error_msg)
                return error_msg # Don\\'t fallback if permission denied on specific path
            except Exception as e:
                error_msg = f"❌ Error launching {app_name_cleaned} using configured path {expanded_path}: {e}"
                logging.error(error_msg, exc_info=True)
                # Fall through to PATH check if launch fails for other reasons

    # 2. Fallback: Try finding the application in the system PATH
    logging.warning(f"Application \"{app_name_cleaned}\" not found in configuration or launch failed. Attempting PATH fallback.")
    found_path_in_path = shutil.which(app_name_lower) # Use lower case for PATH lookup consistency
    
    if not found_path_in_path:
        # Specific check for macOS .app bundles using `open -a` logic
        if os_name == "Darwin":
            try:
                logging.info(f"Attempting macOS \'open -a\" fallback for: {app_name_cleaned}")
                # Use check=True to raise CalledProcessError if \'open -a\' fails
                subprocess.run(["open", "-a", app_name_cleaned], 
                                 check=True, 
                                 stdout=subprocess.DEVNULL, 
                                 stderr=subprocess.DEVNULL)
                logging.info(f"Launched \"{app_name_cleaned}\" via macOS \'open -a\" fallback.")
                return f"✅ Launched \'{app_name_cleaned}\' (via macOS app search)."
            except FileNotFoundError: # If \'open\' command itself is missing (unlikely)
                 error_msg = f"❌ Error: \'open\' command not found on macOS."
                 logging.error(error_msg)
                 return error_msg
            except subprocess.CalledProcessError:
                 error_msg = f"❌ Error: Application \"{app_name_cleaned}\" not found via config, PATH, or macOS app search."
                 logging.warning(error_msg) # Log as warning as it\'s a common failure
                 return error_msg
            except Exception as e:
                 error_msg = f"❌ Unexpected error during macOS \'open -a\" fallback for \"{app_name_cleaned}\": {e}"
                 logging.error(error_msg, exc_info=True)
                 return error_msg
        else:
            # If not macOS and not found by shutil.which
            error_msg = f"❌ Error: Application \"{app_name_cleaned}\" not found in config or system PATH."
            logging.warning(error_msg) # Log as warning
            return error_msg

    # If found via shutil.which
    try:
        logging.info(f"Launching \"{app_name_cleaned}\" via PATH fallback using: {found_path_in_path}")
        if os_name == "Windows":
            subprocess.Popen([found_path_in_path], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL, 
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
        # No need for specific macOS \'open\' here as shutil.which found the executable path
        else: # Linux, macOS (if executable found directly), etc.
            subprocess.Popen([found_path_in_path], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL)
        return f"✅ Launched \'{app_name_cleaned}\' (found in PATH)."
    except PermissionError:
        error_msg = f"❌ Error: Permission denied when trying to execute from PATH: {found_path_in_path}"
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ Error launching \'{app_name_cleaned}\' via PATH fallback ({found_path_in_path}): {e}"
        logging.error(error_msg, exc_info=True)
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

