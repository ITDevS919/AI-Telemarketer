import logging
# import webrtcvad # Commented out
import numpy as np
import torch
import torchaudio # Often used with Silero for resampling if needed, or for types

logger = logging.getLogger(__name__)

class VADHandler:
    """Handles Voice Activity Detection (VAD) using Silero VAD."""

    # Silero VAD typically works with 16kHz mono audio.
    # Chunks for Silero are often larger than webrtcvad frames.
    # For instance, a common window size is 512 samples (32ms at 16kHz).
    # This is just an example; optimal chunking depends on use case.
    # This implementation will assume audio_chunk_bytes are PCM 16-bit mono.

    def __init__(self, 
                 sample_rate: int = 16000, 
                 threshold: float = 0.5, # Speech probability threshold
                 device: str = None):
        """
        Initializes the VADHandler with Silero VAD.
        Args:
            sample_rate: Expected sample rate of the audio (Silero VAD is trained on 16kHz).
            threshold: Confidence threshold for classifying as speech.
            device: The device to run the model on (e.g., "cpu", "cuda"). Autodetects if None.
        """
        if sample_rate != 16000:
            # While Silero can be fed other sample rates, it's best to resample to 16kHz for optimal performance.
            # For simplicity, we'll log a warning here, but a real implementation might resample.
            logger.warning(f"Silero VAD is optimized for 16kHz audio, but received sample_rate={sample_rate}Hz.")
        
        self.sample_rate = sample_rate
        self.threshold = threshold

        if device:
            self.device = device
        else:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(f"Loading Silero VAD model onto device '{self.device}'...")
        try:
            # Ensure torch.hub.set_dir() is configured if needed, or models are pre-downloaded.
            self.model, self.utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', 
                                                   model='silero_vad', 
                                                   force_reload=False, # Set to True to always redownload
                                                   onnx=False) # Set to True if you want ONNX runtime version
            (self.get_speech_timestamps, _, self.read_audio, _, _) = self.utils # Unpack utils
            self.model.to(self.device) # Ensure model is on the correct device
            logger.info(f"Silero VAD model loaded successfully on '{self.device}'.")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}", exc_info=True)
            self.model = None
            self.utils = None

    async def process_audio_chunk(self, audio_chunk_bytes: bytes) -> bool:
        """
        Processes an audio chunk for voice activity using Silero VAD.

        Args:
            audio_chunk_bytes: A chunk of audio data (PCM 16-bit mono, at self.sample_rate).

        Returns:
            bool: True if speech is detected in the chunk, False otherwise.
        """
        if not self.model:
            logger.error("VAD processing called but Silero VAD model is not loaded.")
            return False
        
        if not audio_chunk_bytes:
            return False

        try:
            # Convert PCM 16-bit bytes to float32 tensor (numpy buffer then torch; from_numpy expects ndarray)
            audio_int16 = torch.from_numpy(np.frombuffer(audio_chunk_bytes, dtype=np.int16))
            audio_float32 = audio_int16.to(torch.float32) / 32768.0
            
            # Move tensor to the correct device
            audio_float32 = audio_float32.to(self.device)

            # Get speech probability for the chunk
            # Silero VAD's `self.model` directly can give speech probability of the last frame in a chunk
            # For simplicity here, we process the whole chunk and check its speech probability.
            # A more sophisticated implementation might use `get_speech_timestamps`.
            speech_prob = self.model(audio_float32, self.sample_rate).item()
            
            is_speech = speech_prob >= self.threshold
            # logger.debug(f"Silero VAD: speech_prob: {speech_prob:.2f}, is_speech: {is_speech} for chunk of {len(audio_chunk_bytes)} bytes")
            return is_speech
        except Exception as e:
            logger.error(f"Silero VAD processing error: {e}", exc_info=True)
            return False # Treat errors as silence 