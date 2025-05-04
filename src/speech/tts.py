# src/speech/tts.py

import piper
import sounddevice as sd
import numpy as np
import logging
import os
from pathlib import Path
import wave
import io

# TODO: Add model download/management logic similar to LLM/STT
# For now, assume a voice model (.onnx and .json) exists at a predefined path or is configured
DEFAULT_PIPER_VOICE_MODEL_PATH = "models/en_US-lessac-medium.onnx"
DEFAULT_PIPER_VOICE_CONFIG_PATH = "models/en_US-lessac-medium.onnx.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TextToSpeech:
    def __init__(self, model_path=None, config_path=None, device=None):
        """Initializes the Text-to-Speech engine."""
        self.model_path = model_path or DEFAULT_PIPER_VOICE_MODEL_PATH
        self.config_path = config_path or DEFAULT_PIPER_VOICE_CONFIG_PATH
        self.device = device
        self.voice = None
        self.synthesizer = None

        if not Path(self.model_path).exists():
            # TODO: Implement model download
            logging.error(f"Piper TTS model not found at {self.model_path}. Please download and place it there.")
            raise FileNotFoundError(f"Piper TTS model not found at {self.model_path}")
        if not Path(self.config_path).exists():
            # TODO: Implement config download
            logging.error(f"Piper TTS config not found at {self.config_path}. Please download and place it there.")
            raise FileNotFoundError(f"Piper TTS config not found at {self.config_path}")

        try:
            self.voice = piper.PiperVoice.load(self.model_path, config_path=self.config_path)
            self.synthesizer = self.voice.config.synthesizer
            logging.info(f"TTS Initialized: Model={self.model_path}, SampleRate={self.voice.config.sample_rate}")
        except Exception as e:
            logging.error(f"Failed to initialize Piper TTS: {e}", exc_info=True)
            raise

    def speak(self, text):
        """Synthesizes the given text to speech and plays it."""
        if not self.voice:
            logging.error("TTS engine not initialized.")
            return

        try:
            logging.info(f"Synthesizing: {text[:50]}...")
            # Synthesize audio data in memory
            audio_stream = io.BytesIO()
            self.voice.synthesize(text, audio_stream)
            audio_stream.seek(0)

            # Read the WAV data from memory
            with wave.open(audio_stream, "rb") as wf:
                samplerate = wf.getframerate()
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                nframes = wf.getnframes()
                audio_data = wf.readframes(nframes)

            # Convert bytes to numpy array based on sample width
            if sampwidth == 1:
                dtype = np.uint8 # unsigned 8-bit
            elif sampwidth == 2:
                dtype = np.int16 # signed 16-bit
            elif sampwidth == 3:
                 # Piper doesn't typically output 24-bit, handle if necessary
                 # This requires careful handling, maybe convert to 32-bit float
                 logging.warning("24-bit audio not directly supported by sounddevice, potential issues.")
                 # For simplicity, let's raise an error or handle conversion
                 raise ValueError("24-bit WAV format not directly supported for playback.")
            elif sampwidth == 4:
                dtype = np.int32 # signed 32-bit
            else:
                raise ValueError(f"Unsupported sample width: {sampwidth}")

            # Ensure correct interpretation for multi-channel audio if needed
            # Piper usually outputs mono, but check wf.getnchannels()
            if channels > 1:
                 logging.warning(f"Detected {channels} channels, playback might be affected if device expects mono.")
                 # Reshape might be needed depending on sounddevice expectations

            # Convert byte data to NumPy array
            numpy_data = np.frombuffer(audio_data, dtype=dtype)

            logging.info(f"Playing audio ({nframes} frames, {samplerate} Hz, {channels} channels, {dtype})...")
            sd.play(numpy_data, samplerate=samplerate, device=self.device, blocking=True)
            # sd.wait() # wait until playback is finished (blocking=True does this)
            logging.info("Playback finished.")

        except Exception as e:
            logging.error(f"Failed to synthesize or play speech: {e}", exc_info=True)

# Example Usage (for testing)
if __name__ == "__main__":
    try:
        tts = TextToSpeech()
        print("TTS Initialized. Synthesizing test phrase...")
        tts.speak("Hello, this is a test of the Piper text to speech system.")
        tts.speak("Testing a second phrase to ensure it works multiple times.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("TTS Test Finished.")

