import torch
import os
import logging
import soundfile as sf
import numpy as np
from pathlib import Path
import io
import time
import glob

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
VOICE_NAME = "Isaac" # Name of the .pth file (without extension)
TEXT_TO_SYNTHESIZE = "Hello, can you hear me? This audio should be saved directly to a file."
LANGUAGE = "en"

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent
VOICES_DIR = PROJECT_ROOT / "nova2" / "data" / "voices"
SPEAKER_EMBEDDING_PATH = VOICES_DIR / f"{VOICE_NAME}.pth"
OUTPUT_DIR = PROJECT_ROOT / "tmp_output"
OUTPUT_FILENAME = "direct_tts_output.wav"
OUTPUT_FILE_PATH = OUTPUT_DIR / OUTPUT_FILENAME

# --- Ensure Output Directory Exists ---
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"Ensured output directory exists: {OUTPUT_DIR}")

# --- Check for Coqui TTS Installation ---
try:
    from TTS.api import TTS as CoquiTTS
except ImportError:
    logger.error("Coqui TTS library not found. Please install it: pip install TTS")
    exit(1)

# --- Check for Speaker Embedding File ---
if not SPEAKER_EMBEDDING_PATH.exists():
    logger.error(f"Speaker embedding file not found: {SPEAKER_EMBEDDING_PATH}")
    logger.error(f"Please ensure the voice embedding file '{VOICE_NAME}.pth' exists in {VOICES_DIR}.")
    exit(1)
else:
    logger.info(f"Found speaker embedding file: {SPEAKER_EMBEDDING_PATH}")

# --- Main Script ---
def main():
    logger.info("--- Starting Standalone XTTS Inference to File ---")

    # Determine device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    # Initialize TTS model
    logger.info(f"Initializing model: {MODEL_NAME}")
    try:
        model = CoquiTTS(model_name=MODEL_NAME, progress_bar=True).to(device)
        logger.info("Model initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing TTS model: {e}", exc_info=True)
        return

    # Perform TTS inference using tts_to_file
    logger.info(f"Attempting TTS inference for text: '{TEXT_TO_SYNTHESIZE[:50]}...'")
    logger.info(f"Using speaker embedding: {SPEAKER_EMBEDDING_PATH}")
    logger.info(f"Target output file: {OUTPUT_FILE_PATH}")

    # Remove existing output file if it exists
    if OUTPUT_FILE_PATH.exists():
        logger.warning(f"Removing existing output file: {OUTPUT_FILE_PATH}")
        try:
            os.remove(OUTPUT_FILE_PATH)
        except OSError as e:
            logger.error(f"Error removing existing file {OUTPUT_FILE_PATH}: {e}")
            return

    try:
        # Use tts_to_file to directly save the synthesized audio
        logger.info(f"Calling model.tts_to_file...")
        model.tts_to_file(
            text=TEXT_TO_SYNTHESIZE,
            speaker_wav=str(SPEAKER_EMBEDDING_PATH), # Use the .pth embedding file
            language=LANGUAGE,
            file_path=str(OUTPUT_FILE_PATH)
        )
        logger.info(f"tts_to_file call completed.")

        # --- Verification ---
        logger.info(f"Checking for output file presence...")
        time.sleep(0.5) # Short delay for filesystem

        if OUTPUT_FILE_PATH.exists():
            logger.info(f"SUCCESS: Audio file saved to: {OUTPUT_FILE_PATH}")
            try:
                # Get file info
                info = sf.info(str(OUTPUT_FILE_PATH))
                logger.info(f"  File details: SR={info.samplerate}, Channels={info.channels}, Duration={info.duration:.2f}s, Format={info.format_info}")
            except Exception as info_e:
                logger.warning(f"Could not get file info for {OUTPUT_FILE_PATH}: {info_e}")
        else:
            logger.error(f"FAILED: Output file was NOT created at {OUTPUT_FILE_PATH}")
            logger.error(f"Please check for errors above and verify file permissions for the directory {OUTPUT_DIR}.")

    except Exception as e:
        logger.error(f"Error during TTS inference or saving: {e}", exc_info=True)

    logger.info("--- Standalone XTTS Inference Finished ---")

if __name__ == "__main__":
    main() 