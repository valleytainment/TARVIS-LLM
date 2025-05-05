#!/usr/bin/env python
# -*- coding: utf-8 -*-
import shutil
import os
from pathlib import Path
import logging
from langchain.tools import tool # Import the decorator

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define a base directory for file operations to enhance security
BASE_DIR = Path.home() / "jarvis_files"
BASE_DIR.mkdir(parents=True, exist_ok=True)
logging.info(f"File operations restricted to base directory: {BASE_DIR}")

def _is_path_safe(path: Path) -> bool:
    """Checks if the resolved path is within the allowed BASE_DIR."""
    try:
        resolved_path = path.resolve()
        is_safe = resolved_path.is_relative_to(BASE_DIR.resolve())
        if not is_safe:
            logging.warning(f"Path traversal attempt detected or path outside base directory: {resolved_path}")
        return is_safe
    except Exception as e:
        logging.error(f"Error resolving or checking path safety for {path}: {e}")
        return False

@tool
def copy_file(input_str: str) -> str:
    """Copies a file from a source path to a destination path within the allowed directory. 
    Both source and destination paths must be relative to the user's designated file area.
    Input must be a single string with the source and destination paths separated by a pipe character (|).
    Example: copy_file(\"my_document.txt|backup/my_document_copy.txt\")
    Args:
        input_str: A single string containing the relative source and destination paths, separated by '|'.

    Returns:
        A status message indicating success or failure.
    """
    try:
        source, dest = input_str.split("|", 1)
        source = source.strip()
        dest = dest.strip()
        if not source or not dest:
            raise ValueError("Source and destination paths cannot be empty.")
    except ValueError:
        return "❌ Error: Invalid input format for copy_file. Expected 'source_path|destination_path'."

    source_path_relative = Path(source)
    dest_path_relative = Path(dest)

    # Construct absolute paths within the base directory
    source_path = BASE_DIR / source_path_relative
    dest_path = BASE_DIR / dest_path_relative

    logging.info(f"Attempting to copy file from {source_path} to {dest_path} (parsed from 	'{input_str}	')")

    # --- Security Checks ---
    if not _is_path_safe(source_path):
        return f"❌ Error: Source path 	'{source}	' is outside the allowed directory."
    # Check destination safety more carefully
    # If dest is intended as a file, check its parent. If intended as dir, check itself.
    # We check both the path itself and its parent for robustness
    if not _is_path_safe(dest_path.parent):
         return f"❌ Error: Destination directory 	'{dest_path_relative.parent}	' is outside the allowed directory."
    # If the destination path *could* exist and is outside, deny
    if dest_path.exists() and not _is_path_safe(dest_path):
         return f"❌ Error: Destination path 	'{dest}	' is outside the allowed directory."
    # --- End Security Checks ---

    try:
        resolved_source_path = source_path.resolve()
        resolved_dest_path = dest_path.resolve()

        if not resolved_source_path.is_file():
            error_msg = f"❌ Error: Source path {resolved_source_path} is not a valid file."
            logging.error(error_msg)
            return error_msg

        # If resolved dest is an existing directory, copy into it
        if resolved_dest_path.is_dir():
            dest_file_path = resolved_dest_path / resolved_source_path.name
            # Ensure the final destination is still safe
            if not _is_path_safe(dest_file_path):
                 return f"❌ Error: Final destination path 	'{dest_file_path.relative_to(BASE_DIR)}	' is outside the allowed directory."
        else:
            # Ensure the destination parent directory exists
            resolved_dest_path.parent.mkdir(parents=True, exist_ok=True)
            # Check parent safety again after potential creation
            if not _is_path_safe(resolved_dest_path.parent):
                 return f"❌ Error: Destination directory 	'{resolved_dest_path.parent.relative_to(BASE_DIR)}	' became unsafe or is outside the allowed directory."
            dest_file_path = resolved_dest_path
            # Check final file path safety if it's different from parent
            if dest_file_path != resolved_dest_path.parent and not _is_path_safe(dest_file_path):
                 return f"❌ Error: Final destination path 	'{dest_file_path.relative_to(BASE_DIR)}	' is outside the allowed directory."


        shutil.copy2(resolved_source_path, dest_file_path) # copy2 preserves metadata
        success_msg = f"✅ Copied 	'{source_path_relative}	' to 	'{dest_file_path.relative_to(BASE_DIR)}	'"
        logging.info(success_msg)
        return success_msg
    except FileNotFoundError:
        error_msg = f"❌ Error: Source file not found at {resolved_source_path}."
        logging.error(error_msg)
        return error_msg
    except PermissionError:
        error_msg = f"❌ Error: Permission denied during copy operation from {resolved_source_path} to {resolved_dest_path}."
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ Error copying file: {e}"
        logging.error(error_msg, exc_info=True)
        return error_msg

@tool
def delete_file(path: str) -> str:
    """Deletes the file at the specified path within the allowed directory.
    The path must be relative to the user's designated file area.
    Example: delete_file(\"old_report.txt\")
    Args:
        path: The relative path to the file to be deleted.

    Returns:
        A status message indicating success or failure.
    """
    file_path_relative = Path(path)
    file_path = BASE_DIR / file_path_relative
    logging.info(f"Attempting to delete file: {file_path}")

    # --- Security Check ---
    if not _is_path_safe(file_path):
        return f"❌ Error: Path 	'{path}	' is outside the allowed directory."
    # --- End Security Check ---

    try:
        resolved_file_path = file_path.resolve()
        if not resolved_file_path.is_file():
            # Check if it exists but is not a file
            if resolved_file_path.exists():
                 error_msg = f"❌ Error: Path {resolved_file_path} exists but is not a file. Cannot delete."
            else:
                 error_msg = f"❌ Error: File not found at {resolved_file_path}."
            logging.error(error_msg)
            return error_msg

        resolved_file_path.unlink()
        success_msg = f"✅ Deleted file: 	'{file_path_relative}	'"
        logging.info(success_msg)
        return success_msg
    except FileNotFoundError: # Should be caught by is_file() check, but keep for robustness
        error_msg = f"❌ Error: File not found at {resolved_file_path}."
        logging.error(error_msg)
        return error_msg
    except PermissionError:
        error_msg = f"❌ Error: Permission denied when trying to delete {resolved_file_path}."
        logging.error(error_msg)
        return error_msg
    except IsADirectoryError: # Should be caught by is_file() check
        error_msg = f"❌ Error: Path {resolved_file_path} is a directory, not a file. Cannot delete."
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ Error deleting file: {e}"
        logging.error(error_msg, exc_info=True)
        return error_msg

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing file_ops skill...")
    source_rel = "source.txt"
    dest_dir_rel = "destination_dir"
    dest_file_rel = Path(dest_dir_rel) / "copied.txt"

    source_abs = BASE_DIR / source_rel
    dest_dir_abs = BASE_DIR / dest_dir_rel
    dest_file_abs = BASE_DIR / dest_file_rel

    try:
        with open(source_abs, "w") as f:
            f.write("This is a test file.")
        print(f"Created source file: {source_abs}")
        dest_dir_abs.mkdir(exist_ok=True)

        # Test copy to directory using new format
        copy_input_dir = f"{source_rel}|{dest_dir_rel}"
        result_copy_dir = copy_file(copy_input_dir)
        print(f"Copy to directory result (	'{copy_input_dir}	'): {result_copy_dir}")
        if (dest_dir_abs / source_abs.name).exists():
            print(f"Verified copy exists in directory: {dest_dir_abs / source_abs.name}")
        else:
            print(f"Verification FAILED: Copy not found in directory.")

        # Test copy with rename using new format
        copy_input_rename = f"{source_rel}|{str(dest_file_rel)}"
        result_copy_rename = copy_file(copy_input_rename)
        print(f"Copy with rename result (	'{copy_input_rename}	'): {result_copy_rename}")
        if dest_file_abs.exists():
            print(f"Verified renamed copy exists: {dest_file_abs}")
        else:
            print(f"Verification FAILED: Renamed copy not found.")

        # Test delete (delete_file already takes single string)
        result_delete = delete_file(str(dest_file_rel))
        print(f"Delete result: {result_delete}")
        if not dest_file_abs.exists():
            print(f"Verified file deleted: {dest_file_abs}")
        else:
            print(f"Verification FAILED: File still exists after delete attempt.")

        # Test delete non-existent
        result_delete_nonexistent = delete_file("nonexistentfile123.txt")
        print(f"Delete non-existent result: {result_delete_nonexistent}")

        # Test unsafe path using new format
        result_unsafe = copy_file("../unsafe.txt|safe.txt")
        print(f"Unsafe source path result: {result_unsafe}")
        result_unsafe_dest = copy_file(f"{source_rel}|../../unsafe_dest.txt")
        print(f"Unsafe destination path result: {result_unsafe_dest}")
        result_bad_format = copy_file("just_one_path")
        print(f"Bad format result: {result_bad_format}")

    finally:
        if source_abs.exists(): source_abs.unlink()
        if dest_dir_abs.exists(): shutil.rmtree(dest_dir_abs)
        print(f"Cleaned up test files/directory within {BASE_DIR}")

    print("file_ops test finished.")

