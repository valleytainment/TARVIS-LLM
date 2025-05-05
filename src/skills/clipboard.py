#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pyperclip
import logging
from langchain.tools import tool # Import the decorator

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@tool
def write_to_clipboard(text: str) -> str:
    """Writes the given text content to the system clipboard. Input should be the text to write."""
    logging.info(f"Attempting to write to clipboard (length: {len(text)}). First 50 chars: {text[:50]}...")
    try:
        pyperclip.copy(text)
        success_msg = "✅ Text copied to clipboard."
        logging.info(success_msg + f" (Length: {len(text)})")
        return success_msg
    except pyperclip.PyperclipException as e:
        error_msg = f"❌ Error writing to clipboard: {e}"
        logging.error(error_msg + ". Ensure clipboard access is available (e.g., graphical environment).")
        return error_msg
    except Exception as e:
        error_msg = f"❌ Error writing to clipboard: {e}" 
        logging.error(f"Unexpected error during write: {error_msg}", exc_info=True)
        return error_msg

@tool
def read_from_clipboard(dummy_input: str = "") -> str:
    """Reads the current text content from the system clipboard. Ignores any input provided."""
    # The dummy_input parameter is added to conform to the single-string input requirement of some agents.
    logging.info(f"Attempting to read from clipboard. (Input ignored: {dummy_input[:50]}...)")
    try:
        content = pyperclip.paste()
        logging.info(f"Successfully read from clipboard (length: {len(content)}). First 50 chars: {content[:50]}...")
        return content
    except pyperclip.PyperclipException as e:
        error_msg = f"❌ Error reading from clipboard: {e}"
        logging.error(error_msg + ". Ensure clipboard access is available.")
        return error_msg
    except Exception as e:
        error_msg = f"❌ Error reading from clipboard: {e}"
        logging.error(f"Unexpected error during read: {error_msg}", exc_info=True)
        return error_msg

# Example usage remains the same, but calls the decorated functions
if __name__ == "__main__":
    print("Testing clipboard skill...")
    test_text = "Hello from Jarvis-Core clipboard test!"
    
    write_result = write_to_clipboard(test_text)
    print(f"Write result: {write_result}")

    if "✅" in write_result:
        # Pass a dummy string when calling directly for testing if needed, though agent handles it
        read_content = read_from_clipboard("test") 
        print(f"Read result (content): {read_content}")
        if read_content == test_text:
            print("Verification SUCCESS: Read content matches written content.")
        elif "❌" in read_content:
             print("Verification INFO: Read operation failed, cannot verify.")
        else:
            print("Verification WARNING: Read content does NOT match written content.")
    else:
        print("Skipping read verification because write failed.")
        
    if "❌" in write_result:
        print("Attempting to read existing clipboard content...")
        existing_content = read_from_clipboard()
        print(f"Existing content read result: {existing_content}")

    print("clipboard test finished.")

