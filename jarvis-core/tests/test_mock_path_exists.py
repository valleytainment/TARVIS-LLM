import pytest
from pathlib import Path
from unittest.mock import patch

# Test 1: Mocking exists directly on the instance within the test
def test_mock_exists_instance_direct(tmp_path):
    test_file = tmp_path / "myfile.txt"
    # Create the file to ensure it exists physically
    test_file.touch()
    assert test_file.exists() # Should be True

    # Patch exists only on this specific instance
    with patch.object(test_file, 'exists', return_value=False) as mock_exists:
        assert not test_file.exists() # Should now be False due to mock
        mock_exists.assert_called_once()

    # Mock should be gone now
    assert test_file.exists() # Should be True again

# Test 2: Mocking exists on the Path class using side_effect

def mock_exists_side_effect(self, *args, **kwargs):
    print(f"Mock exists called for: {self}")
    if isinstance(self, Path):
        # Example logic: only return True for a specific filename
        if self.name == "specific_file.txt":
            return True
        return False
    else:
        print(f"Mock exists called on non-Path object: {self}. Returning True for safety.")
        return True

@patch('pathlib.Path.exists', side_effect=mock_exists_side_effect)
def test_mock_exists_class_side_effect(mock_exists_method, tmp_path):
    file1 = tmp_path / "other_file.txt"
    file2 = tmp_path / "specific_file.txt"

    assert not file1.exists()
    assert file2.exists() # This should be True based on side_effect logic

    # Check calls to the mock
    assert mock_exists_method.call_count == 2

# Test 3: Using a fixture to provide the mock (similar to storage tests)
@pytest.fixture
def mock_path_exists_via_fixture():
    def _mock_logic(self, *args, **kwargs):
        # Accept self and variable args
        print(f"Fixture mock exists called for: {self}")
        if isinstance(self, Path) and self.name == "fixture_file.txt":
            return True
        # Default to False or True? Let's try True for cleanup safety
        print(f"Fixture mock called on non-Path or wrong name: {self}. Returning True.")
        return True
    
    # Apply the patch within the fixture's scope
    with patch('pathlib.Path.exists', side_effect=_mock_logic) as mock_method:
        yield mock_method # Provide the mock object to the test
    # Patch is automatically removed when the fixture scope ends

def test_with_mock_fixture(mock_path_exists_via_fixture, tmp_path):
    file1 = tmp_path / "another_file.txt"
    file2 = tmp_path / "fixture_file.txt"

    assert not file1.exists()
    assert file2.exists()

    assert mock_path_exists_via_fixture.call_count == 2

# Test 4: Patching within the test using a context manager
def test_mock_exists_context_manager(tmp_path):
    file1 = tmp_path / "context_file.txt"
    file2 = tmp_path / "special_context.txt"

    def _mock_logic(self, *args, **kwargs):
         print(f"Context Manager mock exists called for: {self}")
         if isinstance(self, Path) and self.name == "special_context.txt":
             return True
         print(f"Context Manager mock called on non-Path or wrong name: {self}. Returning True.")
         return True

    with patch('pathlib.Path.exists', side_effect=_mock_logic) as mock_method:
        assert not file1.exists()
        assert file2.exists()
        assert mock_method.call_count == 2

    # Verify mock is removed outside the context
    file1.touch() # Create the file physically
    assert file1.exists() # Should now be True (mock is gone)


