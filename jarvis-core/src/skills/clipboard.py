import pyperclip
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def write(text: str) -> str:
    """Writes the given text to the system clipboard.

    Args:
        text: The text content to write to the clipboard.

    Returns:
        A status message indicating success or failure.
    """
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
        # Align generic exception message with test expectation
        error_msg = f"❌ Error writing to clipboard: {e}" 
        logging.error(f"Unexpected error during write: {error_msg}", exc_info=True)
        return error_msg

def read() -> str:
    """Reads the current text content from the system clipboard.

    Returns:
        The text content from the clipboard, or an error message.
    """
    logging.info("Attempting to read from clipboard.")
    try:
        content = pyperclip.paste()
        logging.info(f"Successfully read from clipboard (length: {len(content)}). First 50 chars: {content[:50]}...")
        return content
    except pyperclip.PyperclipException as e:
        error_msg = f"❌ Error reading from clipboard: {e}"
        logging.error(error_msg + ". Ensure clipboard access is available.")
        return error_msg
    except Exception as e:
        # Align generic exception message with test expectation
        error_msg = f"❌ Error reading from clipboard: {e}"
        logging.error(f"Unexpected error during read: {error_msg}", exc_info=True)
        return error_msg

# Example usage remains the same
if __name__ == "__main__":
    print("Testing clipboard skill...")
    test_text = "Hello from Jarvis-Core clipboard test!"
    
    write_result = write(test_text)
    print(f"Write result: {write_result}")

    if "✅" in write_result:
        read_content = read()
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
        existing_content = read()
        print(f"Existing content read result: {existing_content}")

    print("clipboard test finished.")

