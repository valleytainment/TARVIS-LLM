import subprocess
import yaml
import os
import platform
import logging
import shutil # Added for shutil.which
import re # Added for input validation
from pathlib import Path # Added for Path object handling
from langchain.agents import Tool # Import Tool

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Determine the path to the config file relative to this script
project_root = Path(__file__).resolve().parent.parent.parent
config_path = project_root / "config" / "app_paths.yaml"

# Basic validation for app names to prevent obviously malicious input
# Allows alphanumeric, spaces, hyphens, underscores, periods.
# Disallows shell metacharacters like ;, |, &, $, <, >, `, \, !, etc.
# This is a basic check and might need refinement.
APP_NAME_VALIDATION_PATTERN = re.compile(r"^[a-zA-Z0-9 ._-]+$")

def load_config():
    """Loads the entire app_paths.yaml configuration."""
    try:
        # Use resource_path utility if available, otherwise fallback
        try:
            from ..utils.resource_path import get_resource_path
            resolved_config_path = get_resource_path(Path("config") / "app_paths.yaml")
        except ImportError:
            logging.warning("resource_path utility not found, using relative path for app_paths config.")
            resolved_config_path = config_path # Fallback to path relative to this file
            
        with open(resolved_config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logging.error(f"Configuration file not found at {resolved_config_path}")
        return {}
    except yaml.YAMLError as e:
        logging.error(f"Error parsing configuration file {resolved_config_path}: {e}")
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
        # If path is not absolute, assume it's relative to project root (or handle as needed)
        # For simplicity, let's assume paths in config are absolute or resolvable by shell
        if expanded_path.exists():
            logging.info(f"Resolved '{app_name}' path from config: {expanded_path}")
            return expanded_path
        else:
            logging.warning(f"Path for '{app_name}' found in config ({expanded_path}) but does not exist. Falling back to PATH search.")

    # Fallback to searching in system PATH
    logging.info(f"App '{app_name}' not found or invalid in config for {os_name}. Searching PATH...")
    path_in_env = shutil.which(app_name_lower)
    if path_in_env:
        resolved_path = Path(path_in_env)
        logging.info(f"Resolved '{app_name}' path using shutil.which: {resolved_path}")
        return resolved_path

    logging.error(f"Could not resolve path for application: {app_name}")
    return None

def execute(app_name: str) -> str:
    """Launches the specified application using cross-platform path resolution."""
    logging.info(f"Attempting to launch application: {app_name}")
    
    # --- Security Check: Validate app_name format ---
    if not APP_NAME_VALIDATION_PATTERN.match(app_name):
        error_msg = f"❌ Error: Invalid application name format: '{app_name}'. Contains disallowed characters."
        logging.error(error_msg)
        return error_msg
    # --- End Security Check ---
    
    app_path = resolve_app_path(app_name)

    if not app_path:
        return f"❌ Error: Could not find or resolve path for application '{app_name}'."

    try:
        # Use subprocess.Popen for non-blocking execution
        logging.info(f"Launching '{app_name}' using path: {app_path}")
        # For macOS .app bundles, use 'open' command
        if platform.system() == "Darwin" and str(app_path).endswith(".app"):
             # Check if it's the executable inside Contents/MacOS or the .app dir itself
            if "Contents/MacOS" in str(app_path):
                 subprocess.Popen([str(app_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else: # Assume it's the .app directory
                 subprocess.Popen(["open", str(app_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Pass the resolved path as the first element of the list
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

# --- Tool Definition --- 
def get_tool() -> Tool:
    """Returns the LangChain Tool object for this skill."""
    return Tool(
        name="open_application",
        func=execute,
        description="Opens or launches a specified application on the computer (e.g., Firefox, Notepad, VS Code, Calculator). Input should be the name of the application."
    )

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing open_app skill...")
    # Test tool creation
    tool = get_tool()
    print(f"Tool Name: {tool.name}")
    print(f"Tool Description: {tool.description}")
    
    # Test with an app expected in config (case-insensitive)
    result_notepad = execute("notepad")
    print(f"Notepad launch result: {result_notepad}")
    
    # Test invalid characters
    result_invalid = execute("notepad; ls -la")
    print(f"Invalid name launch result: {result_invalid}")
    
    # Test with an app likely in PATH but maybe not in config
    # result_calc = execute("calc") # Name might differ based on OS/config
    # print(f"Calculator launch result: {result_calc}")
    
    # Test with a non-existent app
    result_fake = execute("nonexistentapp123")
    print(f"Non-existent app launch result: {result_fake}")
    print("open_app test finished.")

