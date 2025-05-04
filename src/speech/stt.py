# src/speech/stt.py

import vosk
import sounddevice as sd
import queue
import json
import threading
import logging
import os
from pathlib import Path

# Import the resource path utility
from ..utils.resource_path import get_resource_path

# Default model path relative to project root (handled by get_resource_path)
DEFAULT_VOSK_MODEL_PATH_REL = Path("models") / "vosk-model-small-en-us-0.15"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define allowed directories for custom models (e.g., user home, project models dir)
USER_CONFIG_DIR = Path.home() / ".jarvis-core"
ALLOWED_MODEL_DIRS = [get_resource_path("models"), USER_CONFIG_DIR / "models"]

def is_safe_model_path(path_str: str, resolved_path: Path) -> bool:
    """Checks if the resolved model path is within allowed directories or a safe absolute path."""
    if ".." in path_str:
        logging.warning(f"Potential path traversal attempt detected in model path input: {path_str}")
        return False
    try:
        # Check if the resolved path is within any of the allowed directories
        is_safe = any(resolved_path.is_relative_to(allowed_dir) for allowed_dir in ALLOWED_MODEL_DIRS)
        if not is_safe:
            # Allow if the path *is* one of the allowed dirs itself
            is_safe = any(resolved_path == allowed_dir for allowed_dir in ALLOWED_MODEL_DIRS)
            
        if not is_safe:
            # Allow absolute paths outside standard dirs if they don't contain '..'
            if Path(path_str).is_absolute():
                 logging.info(f"Allowing absolute model path outside standard directories: {resolved_path}")
                 is_safe = True
            else:
                 logging.warning(f"Resolved model path {resolved_path} is outside allowed directories: {ALLOWED_MODEL_DIRS}")
                 return False
    except ValueError:
        logging.warning(f"Model path {resolved_path} could not be verified relative to allowed directories.")
        if Path(path_str).is_absolute() and ".." not in path_str:
            logging.info(f"Allowing absolute model path after ValueError: {resolved_path}")
            is_safe = True
        else:
            return False
    except Exception as e:
        logging.error(f"Error checking model path safety for {resolved_path}: {e}", exc_info=True)
        return False
    return is_safe

class SpeechToText:
    def __init__(self, model_path_str=None, device=None, samplerate=None):
        """Initializes the Speech-to-Text engine."""
        self.device = device
        self.samplerate = samplerate
        self.q = queue.Queue()
        self.recognizer = None
        self.stream = None
        self.is_running = False
        self.thread = None
        self.callback_func = None # Function to call with recognized text

        # Resolve and validate model path
        try:
            if model_path_str:
                potential_path = Path(model_path_str)
                if not potential_path.is_absolute():
                    # Assume relative to project root if not absolute
                    resolved_model_path = get_resource_path(model_path_str)
                else:
                    resolved_model_path = potential_path.resolve()
                
                if not is_safe_model_path(model_path_str, resolved_model_path):
                    logging.error(f"Custom STT model path \"{model_path_str}\" is invalid or unsafe. Falling back to default.")
                    self.model_path = get_resource_path(DEFAULT_VOSK_MODEL_PATH_REL)
                else:
                    self.model_path = resolved_model_path
            else:
                # Use default path resolved via utility
                self.model_path = get_resource_path(DEFAULT_VOSK_MODEL_PATH_REL)
        except Exception as e:
            logging.error(f"Error resolving STT model path \"{model_path_str}\": {e}. Using default.")
            self.model_path = get_resource_path(DEFAULT_VOSK_MODEL_PATH_REL)

        logging.info(f"Using STT model path: {self.model_path}")

        if not self.model_path.exists() or not self.model_path.is_dir():
            # TODO: Implement model download
            logging.error(f"Vosk model directory not found at {self.model_path}. Please download and place it there or configure the correct path.")
            raise FileNotFoundError(f"Vosk model directory not found at {self.model_path}")

        try:
            self.model = vosk.Model(str(self.model_path)) # Vosk expects string path
            if self.samplerate is None:
                device_info = sd.query_devices(self.device, "input")
                self.samplerate = int(device_info["default_samplerate"])
            logging.info(f"STT Initialized: Model={self.model_path}, SampleRate={self.samplerate}")
        except Exception as e:
            logging.error(f"Failed to initialize Vosk STT: {e}", exc_info=True)
            raise

    def _audio_callback(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            logging.warning(f"Sounddevice status: {status}")
        self.q.put(bytes(indata))

    def _recognize_thread(self):
        """Runs in a separate thread to process audio queue and recognize speech."""
        try:
            self.recognizer = vosk.KaldiRecognizer(self.model, self.samplerate)
            logging.info("Recognizer thread started.")
            while self.is_running:
                data = self.q.get()
                if not data: # Check for sentinel value to stop thread
                    break 
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    if result.get("text"):
                        recognized_text = result["text"]
                        logging.info(f"Recognized: {recognized_text}")
                        if self.callback_func:
                            try:
                                self.callback_func(recognized_text)
                            except Exception as e:
                                logging.error(f"Error in STT callback: {e}", exc_info=True)
                # else:
                #     partial_result = json.loads(self.recognizer.PartialResult())
                #     if partial_result.get("partial"):
                #         logging.debug(f"Partial: {partial_result["partial"]}")
            logging.info("Recognizer thread finished.")
        except Exception as e:
            logging.error(f"Error in recognizer thread: {e}", exc_info=True)
            self.is_running = False # Ensure loop terminates on error
        finally:
            self.recognizer = None # Clean up recognizer

    def start(self, callback_func):
        """Starts the audio stream and recognition thread."""
        if self.is_running:
            logging.warning("STT is already running.")
            return

        self.callback_func = callback_func
        self.is_running = True
        try:
            self.stream = sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=8000, # 8000 frames = 0.5 seconds at 16kHz
                device=self.device,
                dtype="int16",
                channels=1,
                callback=self._audio_callback
            )
            self.thread = threading.Thread(target=self._recognize_thread)
            self.thread.daemon = True
            self.thread.start()
            self.stream.start()
            logging.info("STT started successfully.")
        except Exception as e:
            logging.error(f"Failed to start STT stream: {e}", exc_info=True)
            self.is_running = False
            if self.stream:
                try:
                    self.stream.close()
                except Exception as close_e:
                    logging.error(f"Error closing stream after start failure: {close_e}")
            self.stream = None
            self.thread = None
            raise

    def stop(self):
        """Stops the audio stream and recognition thread."""
        if not self.is_running:
            logging.warning("STT is not running.")
            return

        logging.info("Stopping STT...")
        self.is_running = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
                logging.info("Audio stream stopped and closed.")
            except Exception as e:
                logging.error(f"Error stopping/closing audio stream: {e}", exc_info=True)
            self.stream = None

        # Signal the thread to exit by putting None or empty bytes
        self.q.put(None) # Use None as sentinel value

        if self.thread:
            self.thread.join(timeout=2) # Wait for thread to finish
            if self.thread.is_alive():
                logging.warning("Recognizer thread did not terminate gracefully.")
            self.thread = None

        self.callback_func = None
        # Clear the queue
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break
        logging.info("STT stopped.")

# Example Usage (for testing)
if __name__ == "__main__":
    def print_result(text):
        print(f"CALLBACK: {text}")

    stt_instance = None
    try:
        # Test with default path
        print("Initializing STT with default model path...")
        stt_instance = SpeechToText()
        print("Starting STT... Speak into the microphone.")
        stt_instance.start(print_result)
        input("Press Enter to stop...\n")
        stt_instance.stop()
        print("STT Stopped.")
        
        # Example of how a custom path would be used (requires model at that path)
        # custom_path = "/path/to/your/custom/vosk-model"
        # if Path(custom_path).exists():
        #     print(f"\nInitializing STT with custom model path: {custom_path}")
        #     stt_instance = SpeechToText(model_path_str=custom_path)
        #     stt_instance.start(print_result)
        #     input("Press Enter to stop...\n")
        #     stt_instance.stop()
        #     print("STT Stopped.")
        # else:
        #     print(f"\nSkipping custom path test: Model not found at {custom_path}")
            
    except FileNotFoundError as e:
        print(f"STT Initialization Error: {e}. Ensure the Vosk model is downloaded and placed correctly.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Ensure stop is called even if initialization failed partially
        if stt_instance and stt_instance.is_running:
            print("Ensuring STT is stopped in finally block...")
            stt_instance.stop()
        print("\nSTT test finished.")

