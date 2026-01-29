import logging
import asyncio # For potential async STT operations
import numpy as np
# import whisper # Import whisper # Commented out
from faster_whisper import WhisperModel # Corrected import
import torch # For checking CUDA availability for Whisper

logger = logging.getLogger(__name__)

class STTHandler:
    """Handles Speech-to-Text (STT) transcription using FasterWhisper."""

    def __init__(self, model_name: str = "large-v2", device: str = None, compute_type: str = "float16"): # Adjusted model_name and added compute_type
        """
        Initializes the STTHandler with a FasterWhisper model.
        Args:
            model_name: Name of the FasterWhisper model to use (e.g., "tiny.en", "base", "small", "medium", "large-v2").
            device: The device to run the model on (e.g., "cpu", "cuda"). Autodetects if None.
            compute_type: The computation type (e.g., "float16", "int8_float16", "int8").
        """
        self.model_name = model_name
        
        if device:
            self.device = device
        else:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        self.compute_type = compute_type if self.device == "cuda" else "int8" # More sensible default for CPU
        
        logger.info(f"Loading FasterWhisper STT model \'{self.model_name}\' onto device \'{self.device}\' with compute_type \'{self.compute_type}\'...")
        try:
            # self.model = whisper.load_model(self.model_name, device=self.device) # Commented out old model loading
            self.model = WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type)
            logger.info(f"FasterWhisper STT model \'{self.model_name}\' loaded successfully on \'{self.device}\'.")
        except Exception as e:
            logger.error(f"Failed to load FasterWhisper model \'{self.model_name}\': {e}", exc_info=True)
            self.model = None 

    async def transcribe_audio_bytes(self, audio_bytes: bytes) -> str:
        """
        Transcribes audio bytes to text using FasterWhisper.

        Args:
            audio_bytes: Audio data in bytes (expected format: 16kHz, 16-bit PCM mono).

        Returns:
            str: The transcribed text, or an empty string if error or no model.
        """
        if not self.model:
            logger.error("STT transcription called but FasterWhisper model is not loaded.")
            return "[STT Model Not Loaded]"
        
        if not audio_bytes:
            return ""

        logger.debug(f"STT (FasterWhisper): Received {len(audio_bytes)} bytes for transcription.")
        
        try:
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
            loop = asyncio.get_running_loop()
            # FasterWhisper's transcribe is CPU-bound for the actual transcription part,
            # but model loading and some ops might involve GIL. run_in_executor is still good.
            segments, info = await loop.run_in_executor(
                None, 
                self.model.transcribe, 
                audio_np,
                language="en", # Make configurable if needed
                beam_size=5 # A common default, can be tuned
            )
            
            # Concatenate text from all segments
            transcript_parts = []
            for segment in segments:
                transcript_parts.append(segment.text)
            transcript = "".join(transcript_parts).strip()
            
            logger.info(f"STT (FasterWhisper): Detected language \'{info.language}\' with probability {info.language_probability:.2f}")
            logger.info(f"STT (FasterWhisper): Transcription: \'{transcript}\'")
            return transcript
            
        except Exception as e:
            logger.error(f"STT (FasterWhisper) transcription error: {e}", exc_info=True)
            return "[STT Transcription Error]" 