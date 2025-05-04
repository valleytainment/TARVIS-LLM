import shutil
import os
from pathlib import Path
import logging
import platform # Added for platform-specific checks if needed later
from langchain.agents import Tool # Import Tool

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define a base directory to restrict file operations for security
# Use environment variable or default to user's home directory subfolder
# This makes it slightly more flexible than hardcoding /home/ubuntu
DEFAULT_SAFE_DIR = Path.home() / ".jarvis-core-files"
BASE_DIR = Path(os.environ.get("JARVIS_SAFE_DIR", DEFAULT_SAFE_DIR)).resolve()
# Ensure the base directory exists
BASE_DIR.mkdir(parents=True, exist_ok=True)
logging.info(f"File operations restricted to base directory: {BASE_DIR}")

def is_safe_path(path_str: str, target_path: Path) -> bool:
    """Checks if the resolved path is within the allowed BASE_DIR."""
    # Basic check for path traversal components in the original string
    if ".." in path_str:
        logging.warning(f"Potential path traversal attempt detected in input: {path_str}")
        return False
    # Check if the resolved path is relative to the defined BASE_DIR
    try:
        resolved_target = target_path.resolve()
        if not resolved_target.is_relative_to(BASE_DIR):
            logging.warning(f"Resolved path {resolved_target} is outside the allowed base directory {BASE_DIR}")
            return False
    except ValueError:
        # is_relative_to raises ValueError if paths are on different drives (Windows)
        # or cannot be made relative. Treat this as unsafe.
        logging.warning(f"Path {target_path.resolve()} could not be verified relative to {BASE_DIR}")
        return False
    except Exception as e:
        # Catch other potential exceptions during path resolution/checking
        logging.error(f"Error checking path safety for {target_path}: {e}", exc_info=True)
        return False
        
    return True

def copy_file(source: str, dest: str) -> str:
    """Copies a file from the source path to the destination path within the allowed directory.

    Args:
        source: The path to the source file (relative to the safe base directory).
        dest: The path to the destination file or directory (relative to the safe base directory).

    Returns:
        A status message indicating success or failure.
    """
    try:
        # Interpret paths relative to BASE_DIR
        source_path = (BASE_DIR / source).resolve()
        dest_path_input = BASE_DIR / dest # Keep original dest structure for dir check
        dest_path = dest_path_input.resolve()
    except Exception as e:
        error_msg = f"❌ Error resolving paths relative to {BASE_DIR}: {e}"
        logging.error(error_msg)
        return error_msg

    logging.info(f"Attempting to copy file from {source_path} to {dest_path}")

    # --- Security Checks (Paths are resolved relative to BASE_DIR) ---
    if not is_safe_path(str(source_path), source_path):
        error_msg = f"❌ Error: Source path {source} resolves outside the allowed directory."
        logging.error(error_msg)
        return error_msg
        
    # Determine the final destination path for safety check
    final_dest_path_check = dest_path
    # Check if the *intended* destination (relative path) implies a directory
    # This logic is tricky; safer to require explicit file paths or ensure dest dir exists first
    # For simplicity, let's assume 'dest' is the final file path unless it resolves to an existing directory
    if dest_path.is_dir():
         final_dest_path_check = dest_path / source_path.name
    # If dest doesn't exist, check its intended parent
    elif not dest_path.exists():
         final_dest_path_check = dest_path.parent
         
    if not is_safe_path(str(final_dest_path_check), final_dest_path_check):
        error_msg = f"❌ Error: Destination path {dest} resolves outside the allowed directory."
        logging.error(error_msg)
        return error_msg
    # --- End Security Checks ---

    try:
        if not source_path.is_file():
            error_msg = f"❌ Error: Source path {source_path} is not a valid file."
            logging.error(error_msg)
            return error_msg

        # If dest resolves to an existing directory, copy the file into it
        if dest_path.is_dir():
            dest_file_path = dest_path / source_path.name
            # Re-check safety specifically for the final file path inside the directory
            if not is_safe_path(str(dest_file_path), dest_file_path):
                 error_msg = f"❌ Error: Final destination path {dest_file_path} is outside the allowed directory."
                 logging.error(error_msg)
                 return error_msg
        else:
            # Ensure the destination directory exists (using resolved path's parent)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            # Check if parent creation was safe
            if not is_safe_path(str(dest_path.parent), dest_path.parent):
                 error_msg = f"❌ Error: Could not create safe destination directory {dest_path.parent}."
                 logging.error(error_msg)
                 return error_msg
            dest_file_path = dest_path

        shutil.copy2(source_path, dest_file_path) # copy2 preserves metadata
        # Report paths relative to BASE_DIR for clarity
        relative_source = source_path.relative_to(BASE_DIR)
        relative_dest = dest_file_path.relative_to(BASE_DIR)
        success_msg = f"✅ Copied {relative_source} to {relative_dest}"
        logging.info(success_msg)
        return success_msg
    except FileNotFoundError:
        error_msg = f"❌ Error: Source file not found at {source_path}."
        logging.error(error_msg)
        return error_msg
    except PermissionError:
        error_msg = f"❌ Error: Permission denied during copy operation from {source_path} to {dest_path}."
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ Error copying file: {e}"
        logging.error(error_msg, exc_info=True)
        return error_msg

def delete_file(path: str) -> str:
    """Deletes the file at the specified path within the allowed directory.

    Args:
        path: The path to the file to be deleted (relative to the safe base directory).

    Returns:
        A status message indicating success or failure.
    """
    try:
        # Interpret path relative to BASE_DIR
        file_path = (BASE_DIR / path).resolve()
    except Exception as e:
        error_msg = f"❌ Error resolving path relative to {BASE_DIR}: {e}"
        logging.error(error_msg)
        return error_msg
        
    logging.info(f"Attempting to delete file: {file_path}")

    # --- Security Checks ---
    if not is_safe_path(str(file_path), file_path):
        error_msg = f"❌ Error: Path {path} resolves outside the allowed directory or is invalid."
        logging.error(error_msg)
        return error_msg
    # --- End Security Checks ---

    try:
        if not file_path.is_file():
            # Check if it exists but isn't a file (e.g., directory, broken symlink)
            if file_path.exists() or file_path.is_symlink():
                 error_msg = f"❌ Error: Path {file_path} exists but is not a regular file."
            else:
                 error_msg = f"❌ Error: File not found at {file_path}."
            logging.error(error_msg)
            return error_msg

        file_path.unlink()
        relative_path = file_path.relative_to(BASE_DIR)
        success_msg = f"✅ Deleted file: {relative_path}"
        logging.info(success_msg)
        return success_msg
    except FileNotFoundError:
        # This case is technically covered by the is_file() check, but good practice
        error_msg = f"❌ Error: File not found at {file_path}."
        logging.error(error_msg)
        return error_msg
    except PermissionError:
        error_msg = f"❌ Error: Permission denied when trying to delete {file_path}."
        logging.error(error_msg)
        return error_msg
    except IsADirectoryError:
        # This case is also covered by the is_file() check
        error_msg = f"❌ Error: Path {file_path} is a directory, not a file. Cannot delete."
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ Error deleting file: {e}"
        logging.error(error_msg, exc_info=True)
        return error_msg

# --- Tool Definition --- 
def get_tools() -> list[Tool]:
    """Returns a list of LangChain Tool objects for this skill module."""
    return [
        Tool(
            name="copy_file",
            func=copy_file,
            description=f"Copies a file from a source path to a destination path. Both paths must be relative to the secure base directory ({BASE_DIR}). Provide source and destination paths as arguments."
        ),
        Tool(
            name="delete_file",
            func=delete_file,
            description=f"Deletes a file at the specified path. The path must be relative to the secure base directory ({BASE_DIR}). Provide the path to the file as an argument."
        )
    ]

# Example usage (for testing purposes)
if __name__ == "__main__":
    print(f"Testing file_ops skill with safety checks within BASE_DIR: {BASE_DIR}")
    # Create dummy files/dirs for testing within BASE_DIR
    test_dir = BASE_DIR / "test_file_ops_temp"
    test_dir.mkdir(exist_ok=True)
    source_file_rel = "test_file_ops_temp/source.txt"
    dest_dir_rel = "test_file_ops_temp/destination_dir"
    dest_file_rel = "test_file_ops_temp/destination_dir/copied.txt"
    outside_file_abs = BASE_DIR.parent / "outside_test.txt" # Absolute path outside BASE_DIR

    # Resolve paths for local operations
    source_file_abs = BASE_DIR / source_file_rel
    dest_dir_abs = BASE_DIR / dest_dir_rel
    dest_dir_abs.mkdir(exist_ok=True)
    dest_file_abs = BASE_DIR / dest_file_rel

    try:
        # Create a source file
        with open(source_file_abs, "w") as f:
            f.write("This is a test file.")
        print(f"Created source file: {source_file_abs}")

        # --- Test Safe Operations (using relative paths) ---
        print("\n--- Testing Safe Operations ---")
        # Test copy to directory
        result_copy_dir = copy_file(source_file_rel, dest_dir_rel)
        print(f"Copy to directory result: {result_copy_dir}")
        if (dest_dir_abs / Path(source_file_rel).name).exists():
            print(f"Verified copy exists in directory: {dest_dir_abs / Path(source_file_rel).name}")
        else:
            print(f"Verification FAILED: Copy not found in directory.")

        # Test copy with rename
        result_copy_rename = copy_file(source_file_rel, dest_file_rel)
        print(f"Copy with rename result: {result_copy_rename}")
        if dest_file_abs.exists():
            print(f"Verified renamed copy exists: {dest_file_abs}")
        else:
            print(f"Verification FAILED: Renamed copy not found.")

        # Test delete
        result_delete = delete_file(dest_file_rel)
        print(f"Delete result: {result_delete}")
        if not dest_file_abs.exists():
            print(f"Verified file deleted: {dest_file_abs}")
        else:
            print(f"Verification FAILED: File still exists after delete attempt.")

        # --- Test Unsafe Operations (expect errors) ---
        print("\n--- Testing Unsafe Operations (expect errors) ---")
        # Test copy from safe to outside (using absolute path for dest)
        result_copy_out = copy_file(source_file_rel, str(outside_file_abs))
        print(f"Copy to outside result: {result_copy_out}")
        if outside_file_abs.exists():
             print(f"Verification FAILED: File copied outside base directory!")
             outside_file_abs.unlink() # Clean up if created
        else:
             print(f"Verified file was NOT copied outside.")
             
        # Test copy from outside to safe (using absolute path for source)
        try:
            with open(outside_file_abs, "w") as f:
                f.write("Outside file content.")
            result_copy_in = copy_file(str(outside_file_abs), dest_file_rel)
            print(f"Copy from outside result: {result_copy_in}")
            if dest_file_abs.exists():
                 print(f"Verification FAILED: File copied from outside base directory!")
                 dest_file_abs.unlink()
            else:
                 print(f"Verified file was NOT copied from outside.")
        finally:
            if outside_file_abs.exists():
                outside_file_abs.unlink()

        # Test delete outside (using absolute path)
        try:
            with open(outside_file_abs, "w") as f:
                f.write("Outside file content.")
            result_delete_out = delete_file(str(outside_file_abs))
            print(f"Delete outside result: {result_delete_out}")
            if not outside_file_abs.exists():
                 print(f"Verification FAILED: File deleted outside base directory!")
            else:
                 print(f"Verified file was NOT deleted outside.")
                 outside_file_abs.unlink() # Clean up
        finally:
            if outside_file_abs.exists(): # Ensure cleanup
                outside_file_abs.unlink()
                
        # Test path traversal attempt (copy)
        trav_dest = f"../test_trav_copy.txt" # Relative path attempting traversal
        result_copy_trav = copy_file(source_file_rel, trav_dest)
        print(f"Copy path traversal result: {result_copy_trav}")
        if (BASE_DIR.parent / "test_trav_copy.txt").exists():
            print(f"Verification FAILED: Path traversal copy succeeded!")
            (BASE_DIR.parent / "test_trav_copy.txt").unlink()
        else:
            print(f"Verified path traversal copy was blocked.")

        # Test path traversal attempt (delete)
        trav_delete_target_abs = BASE_DIR.parent / "test_trav_delete.txt"
        try:
            with open(trav_delete_target_abs, "w") as f:
                f.write("Delete me via traversal?")
            # Use a relative path from within the allowed dir to try and escape
            trav_delete_path_rel = "test_file_ops_temp/../../test_trav_delete.txt" 
            result_delete_trav = delete_file(trav_delete_path_rel)
            print(f"Delete path traversal result: {result_delete_trav}")
            if not trav_delete_target_abs.exists():
                print(f"Verification FAILED: Path traversal delete succeeded!")
            else:
                print(f"Verified path traversal delete was blocked.")
                trav_delete_target_abs.unlink() # Clean up
        finally:
            if trav_delete_target_abs.exists(): # Ensure cleanup
                 trav_delete_target_abs.unlink()

    finally:
        # Clean up test files/directory within BASE_DIR
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"\nCleaned up test directory: {test_dir}")

    print("\nfile_ops test finished.")

