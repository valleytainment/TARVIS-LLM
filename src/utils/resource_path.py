# src/utils/resource_path.py
import sys
import os
from pathlib import Path

def get_resource_path(relative_path: str) -> Path:
    """ Get absolute path to resource, works for dev and for PyInstaller bundle. """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except Exception:
        # Not running in a bundle, assume running from source
        # Go up levels from this file (src/utils/resource_path.py) to project root
        base_path = Path(__file__).resolve().parent.parent.parent

    return base_path / relative_path

