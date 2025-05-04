import shutil
import os
from pathlib import Path
import logging
import platform # Added for platform-specific checks if needed later

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define a base directory to restrict file operations for security
# For now, restrict to the project directory. This could be made configurable.
BASE_DIR = Path("/home/ubuntu/jarvis-core").resolve()

def is_safe_path(path_str: str, target_path: Path) -> bool:
    """Checks if the resolved path is within the allowed BASE_DIR."""
    # Basic check for path traversal components in the original string
    if ".." in path_str:
        logging.warning(f"Potential path traversal attempt detected in input: {path_str}")
        return False
    # Check if the resolved path is relative to the defined BASE_DIR
    try:
        # Ensure the target path exists or its parent exists before checking relativity
        check_path = target_path
        if not target_path.exists():
            check_path = target_path.parent
            # If even the parent doesn't exist relative to BASE_DIR, it's unsafe
            # unless the parent *is* BASE_DIR itself (allowing creation in BASE_DIR)
            if not check_path.is_relative_to(BASE_DIR) and check_path != BASE_DIR:
                 logging.warning(f"Target path {target_path} parent {check_path} is outside the allowed base directory {BASE_DIR}")
                 return False
        
        if not target_path.resolve().is_relative_to(BASE_DIR):
            logging.warning(f"Resolved path {target_path.resolve()} is outside the allowed base directory {BASE_DIR}")
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
    """Copies a file from the source path to the destination path, with safety checks.

    Args:
        source: The path to the source file.
        dest: The path to the destination file or directory.

    Returns:
        A status message indicating success or failure.
    """
    try:
        source_path = Path(source).resolve()
        dest_path_input = Path(dest) # Keep original dest structure for dir check
        dest_path = dest_path_input.resolve()
    except Exception as e:
        error_msg = f"❌ Error resolving paths: {e}"
        logging.error(error_msg)
        return error_msg

    logging.info(f"Attempting to copy file from {source_path} to {dest_path}")

    # --- Security Checks ---
    if not is_safe_path(source, source_path):
        error_msg = f"❌ Error: Source path {source} is outside the allowed directory."
        logging.error(error_msg)
        return error_msg
        
    # Determine the final destination path for safety check
    final_dest_path_check = dest_path
    if dest_path_input.is_dir(): # Check original input path if it was intended as a dir
         final_dest_path_check = dest_path / source_path.name
    elif not dest_path.exists():
         final_dest_path_check = dest_path.parent # Check parent dir if file doesn't exist
         
    if not is_safe_path(dest, final_dest_path_check):
        error_msg = f"❌ Error: Destination path {dest} is outside the allowed directory."
        logging.error(error_msg)
        return error_msg
    # --- End Security Checks ---

    try:
        if not source_path.is_file():
            error_msg = f"❌ Error: Source path {source_path} is not a valid file."
            logging.error(error_msg)
            return error_msg

        # If dest is a directory, copy the file into it with the same name
        # Use the resolved dest_path here
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
            # Check if parent creation was safe (should be covered by initial check, but belt-and-suspenders)
            if not is_safe_path(str(dest_path.parent), dest_path.parent):
                 error_msg = f"❌ Error: Could not create safe destination directory {dest_path.parent}."
                 logging.error(error_msg)
                 return error_msg
            dest_file_path = dest_path

        shutil.copy2(source_path, dest_file_path) # copy2 preserves metadata
        success_msg = f"✅ Copied {source_path.name} from {source_path.parent} to {dest_file_path}"
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
    """Deletes the file at the specified path, with safety checks.

    Args:
        path: The path to the file to be deleted.

    Returns:
        A status message indicating success or failure.
    """
    try:
        file_path = Path(path).resolve()
    except Exception as e:
        error_msg = f"❌ Error resolving path: {e}"
        logging.error(error_msg)
        return error_msg
        
    logging.info(f"Attempting to delete file: {file_path}")

    # --- Security Checks ---
    if not is_safe_path(path, file_path):
        error_msg = f"❌ Error: Path {path} is outside the allowed directory or invalid."
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
        success_msg = f"✅ Deleted file: {file_path}"
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

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing file_ops skill with safety checks...")
    # Create dummy files/dirs for testing within BASE_DIR
    test_dir = BASE_DIR / "test_file_ops_temp"
    test_dir.mkdir(exist_ok=True)
    source_file = test_dir / "source.txt"
    dest_dir = test_dir / "destination_dir"
    dest_dir.mkdir(exist_ok=True)
    dest_file = dest_dir / "copied.txt"
    outside_file = BASE_DIR.parent / "outside_test.txt" # File outside BASE_DIR

    try:
        # Create a source file
        with open(source_file, "w") as f:
            f.write("This is a test file.")
        print(f"Created source file: {source_file}")

        # --- Test Safe Operations ---
        print("\n--- Testing Safe Operations ---")
        # Test copy to directory
        result_copy_dir = copy_file(str(source_file), str(dest_dir))
        print(f"Copy to directory result: {result_copy_dir}")
        if (dest_dir / source_file.name).exists():
            print(f"Verified copy exists in directory: {dest_dir / source_file.name}")
        else:
            print(f"Verification FAILED: Copy not found in directory.")

        # Test copy with rename
        result_copy_rename = copy_file(str(source_file), str(dest_file))
        print(f"Copy with rename result: {result_copy_rename}")
        if dest_file.exists():
            print(f"Verified renamed copy exists: {dest_file}")
        else:
            print(f"Verification FAILED: Renamed copy not found.")

        # Test delete
        result_delete = delete_file(str(dest_file))
        print(f"Delete result: {result_delete}")
        if not dest_file.exists():
            print(f"Verified file deleted: {dest_file}")
        else:
            print(f"Verification FAILED: File still exists after delete attempt.")

        # --- Test Unsafe Operations ---
        print("\n--- Testing Unsafe Operations (expect errors) ---")
        # Test copy from safe to outside
        result_copy_out = copy_file(str(source_file), str(outside_file))
        print(f"Copy to outside result: {result_copy_out}")
        if outside_file.exists():
             print(f"Verification FAILED: File copied outside base directory!")
             outside_file.unlink() # Clean up if created
        else:
             print(f"Verified file was NOT copied outside.")
             
        # Test copy from outside to safe (should fail on source check)
        # Create a temporary outside file for this test
        try:
            with open(outside_file, "w") as f:
                f.write("Outside file content.")
            result_copy_in = copy_file(str(outside_file), str(dest_file))
            print(f"Copy from outside result: {result_copy_in}")
            if dest_file.exists():
                 print(f"Verification FAILED: File copied from outside base directory!")
                 dest_file.unlink()
            else:
                 print(f"Verified file was NOT copied from outside.")
        finally:
            if outside_file.exists():
                outside_file.unlink()

        # Test delete outside
        # Create a temporary outside file again
        try:
            with open(outside_file, "w") as f:
                f.write("Outside file content.")
            result_delete_out = delete_file(str(outside_file))
            print(f"Delete outside result: {result_delete_out}")
            if not outside_file.exists():
                 print(f"Verification FAILED: File deleted outside base directory!")
            else:
                 print(f"Verified file was NOT deleted outside.")
                 outside_file.unlink() # Clean up
        finally:
            if outside_file.exists(): # Ensure cleanup even if test logic failed
                outside_file.unlink()
                
        # Test path traversal attempt (copy)
        trav_dest = f"../test_trav_copy.txt" # Relative path attempting traversal
        result_copy_trav = copy_file(str(source_file), trav_dest)
        print(f"Copy path traversal result: {result_copy_trav}")
        if (BASE_DIR.parent / "test_trav_copy.txt").exists():
            print(f"Verification FAILED: Path traversal copy succeeded!")
            (BASE_DIR.parent / "test_trav_copy.txt").unlink()
        else:
            print(f"Verified path traversal copy was blocked.")

        # Test path traversal attempt (delete)
        # Create a file to attempt deleting via traversal
        trav_delete_target = BASE_DIR.parent / "test_trav_delete.txt"
        try:
            with open(trav_delete_target, "w") as f:
                f.write("Delete me via traversal?")
            # Use a relative path from within the allowed dir to try and escape
            trav_delete_path = str(test_dir / "../../test_trav_delete.txt") 
            result_delete_trav = delete_file(trav_delete_path)
            print(f"Delete path traversal result: {result_delete_trav}")
            if not trav_delete_target.exists():
                print(f"Verification FAILED: Path traversal delete succeeded!")
            else:
                print(f"Verified path traversal delete was blocked.")
                trav_delete_target.unlink() # Clean up
        finally:
            if trav_delete_target.exists(): # Ensure cleanup
                 trav_delete_target.unlink()

    finally:
        # Clean up test files/directory within BASE_DIR
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"\nCleaned up test directory: {test_dir}")

    print("\nfile_ops test finished.")

