import pytest
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the functions to be tested
# Assuming tests are run from the project root or PYTHONPATH includes src
from src.skills import file_ops

# Pytest fixture to create a temporary directory for testing
@pytest.fixture
def temp_test_dir(tmp_path):
    """Create a temporary directory structure for file ops tests."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    dest_dir.mkdir()
    source_file = source_dir / "test_source.txt"
    source_file.write_text("This is a test.")
    return {"source_dir": source_dir, "dest_dir": dest_dir, "source_file": source_file}

# --- Tests for copy_file --- 

def test_copy_file_success_to_dir(temp_test_dir):
    """Test copying a file successfully into an existing directory."""
    source = str(temp_test_dir["source_file"])
    dest = str(temp_test_dir["dest_dir"])
    result = file_ops.copy_file(source, dest)
    expected_dest_path = temp_test_dir["dest_dir"] / temp_test_dir["source_file"].name
    assert "✅ Copied" in result
    assert expected_dest_path.exists()
    assert expected_dest_path.read_text() == "This is a test."

def test_copy_file_success_rename(temp_test_dir):
    """Test copying a file successfully and renaming it."""
    source = str(temp_test_dir["source_file"])
    dest_file_path = temp_test_dir["dest_dir"] / "renamed_test.txt"
    dest = str(dest_file_path)
    result = file_ops.copy_file(source, dest)
    assert "✅ Copied" in result
    assert dest_file_path.exists()
    assert dest_file_path.read_text() == "This is a test."

def test_copy_file_source_not_found(temp_test_dir):
    """Test copying when the source file does not exist."""
    source = str(temp_test_dir["source_dir"] / "nonexistent.txt")
    dest = str(temp_test_dir["dest_dir"])
    result = file_ops.copy_file(source, dest)
    assert "❌ Error: Source path" in result
    assert "is not a valid file" in result

@patch("shutil.copy2")
def test_copy_file_permission_error(mock_copy2, temp_test_dir):
    """Test copying when a permission error occurs."""
    mock_copy2.side_effect = PermissionError("Test permission denied")
    source = str(temp_test_dir["source_file"])
    dest = str(temp_test_dir["dest_dir"])
    result = file_ops.copy_file(source, dest)
    assert "❌ Error: Permission denied" in result

# --- Tests for delete_file --- 

def test_delete_file_success(temp_test_dir):
    """Test deleting a file successfully."""
    # Create a file specifically for deletion test
    file_to_delete = temp_test_dir["source_dir"] / "delete_me.txt"
    file_to_delete.write_text("Delete this content.")
    assert file_to_delete.exists()
    
    result = file_ops.delete_file(str(file_to_delete))
    assert "✅ Deleted file" in result
    assert not file_to_delete.exists()

def test_delete_file_not_found(temp_test_dir):
    """Test deleting a file that does not exist."""
    non_existent_file = temp_test_dir["source_dir"] / "nonexistent_to_delete.txt"
    result = file_ops.delete_file(str(non_existent_file))
    assert "❌ Error: Path" in result
    assert "not a valid file or does not exist" in result

@patch("pathlib.Path.unlink")
def test_delete_file_permission_error(mock_unlink, temp_test_dir):
    """Test deleting when a permission error occurs."""
    file_to_delete = temp_test_dir["source_dir"] / "perm_error_delete.txt"
    file_to_delete.write_text("Cannot delete this.")
    mock_unlink.side_effect = PermissionError("Test permission denied")
    
    result = file_ops.delete_file(str(file_to_delete))
    assert "❌ Error: Permission denied" in result
    assert file_to_delete.exists() # File should still exist

def test_delete_file_is_directory(temp_test_dir):
    """Test attempting to delete a directory instead of a file."""
    result = file_ops.delete_file(str(temp_test_dir["source_dir"]))
    assert "❌ Error: Path" in result
    assert "is not a valid file or does not exist" in result # Path.is_file() check catches this first
    assert temp_test_dir["source_dir"].exists() # Directory should still exist

