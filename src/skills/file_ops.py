import shutil
import os
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def copy_file(source: str, dest: str) -> str:
    """Copies a file from the source path to the destination path.

    Args:
        source: The path to the source file.
        dest: The path to the destination file or directory.

    Returns:
        A status message indicating success or failure.
    """
    source_path = Path(source).resolve()
    dest_path = Path(dest).resolve()
    logging.info(f"Attempting to copy file from {source_path} to {dest_path}")

    try:
        if not source_path.is_file():
            error_msg = f"❌ Error: Source path {source_path} is not a valid file."
            logging.error(error_msg)
            return error_msg

        # If dest is a directory, copy the file into it with the same name
        if dest_path.is_dir():
            dest_file_path = dest_path / source_path.name
        else:
            # Ensure the destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
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
    """Deletes the file at the specified path.

    Args:
        path: The path to the file to be deleted.

    Returns:
        A status message indicating success or failure.
    """
    file_path = Path(path).resolve()
    logging.info(f"Attempting to delete file: {file_path}")

    try:
        if not file_path.is_file():
            error_msg = f"❌ Error: Path {file_path} is not a valid file or does not exist."
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
        error_msg = f"❌ Error: Path {file_path} is a directory, not a file. Cannot delete."
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ Error deleting file: {e}"
        logging.error(error_msg, exc_info=True)
        return error_msg

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing file_ops skill...")
    # Create dummy files/dirs for testing
    test_dir = Path("./test_file_ops_temp")
    test_dir.mkdir(exist_ok=True)
    source_file = test_dir / "source.txt"
    dest_dir = test_dir / "destination_dir"
    dest_dir.mkdir(exist_ok=True)
    dest_file = dest_dir / "copied.txt"

    try:
        # Create a source file
        with open(source_file, "w") as f:
            f.write("This is a test file.")
        print(f"Created source file: {source_file}")

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

        # Test delete non-existent
        result_delete_nonexistent = delete_file("nonexistentfile123.txt")
        print(f"Delete non-existent result: {result_delete_nonexistent}")

    finally:
        # Clean up test files/directory
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"Cleaned up test directory: {test_dir}")

    print("file_ops test finished.")

