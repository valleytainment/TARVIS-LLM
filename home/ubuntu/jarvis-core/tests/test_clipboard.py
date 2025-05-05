import pytest
from unittest.mock import patch

# Import the functions to be tested
from src.skills import clipboard

# --- Tests for write ---

@patch("src.skills.clipboard.pyperclip.copy")
def test_write_success(mock_copy):
    """Test writing text to the clipboard successfully."""
    test_text = "Hello, clipboard!"
    result = clipboard.write(test_text)
    assert "✅ Text copied to clipboard." in result
    mock_copy.assert_called_once_with(test_text)

@patch("src.skills.clipboard.pyperclip.copy", side_effect=Exception("Clipboard error"))
def test_write_failure(mock_copy):
    """Test handling failure when writing to the clipboard."""
    test_text = "This will fail."
    result = clipboard.write(test_text)
    assert "❌ Error writing to clipboard:" in result
    assert "Clipboard error" in result
    mock_copy.assert_called_once_with(test_text)

# --- Tests for read ---

@patch("src.skills.clipboard.pyperclip.paste", return_value="Text from clipboard")
def test_read_success(mock_paste):
    """Test reading text from the clipboard successfully."""
    result = clipboard.read()
    assert result == "Text from clipboard"
    mock_paste.assert_called_once()

@patch("src.skills.clipboard.pyperclip.paste", return_value="")
def test_read_empty(mock_paste):
    """Test reading when the clipboard is empty."""
    result = clipboard.read()
    assert result == ""
    mock_paste.assert_called_once()

@patch("src.skills.clipboard.pyperclip.paste", side_effect=Exception("Clipboard access denied"))
def test_read_failure(mock_paste):
    """Test handling failure when reading from the clipboard."""
    result = clipboard.read()
    assert "❌ Error reading from clipboard:" in result
    assert "Clipboard access denied" in result
    mock_paste.assert_called_once()

