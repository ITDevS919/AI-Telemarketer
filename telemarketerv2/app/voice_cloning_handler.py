"""
Voice Cloning Handler using XTTS v2 (Coqui TTS)

This module handles voice cloning from audio samples and TTS synthesis
using cloned voices. It integrates with the existing TTSHandler to provide
dual support for both Piper TTS (pre-trained voices) and XTTS (cloned voices).
"""

import logging
import os
import io
import wave
import torch
import torchaudio.functional as F
from pathlib import Path
from typing import Optional, Dict, List
import numpy as np

logger = logging.getLogger(__name__)

try:
    from TTS.api import TTS
    from TTS.utils.manage import ModelManager
    XTTS_AVAILABLE = True
except ImportError:
    XTTS_AVAILABLE = False
    logger.warning("TTS library (Coqui TTS) not available. Voice cloning will be disabled.")


def _register_tts_safe_globals_for_torch_load():
    """Allow TTS checkpoint classes for torch.load under PyTorch 2.6+ (weights_only=True)."""
    if not getattr(torch.serialization, "add_safe_globals", None):
        return
    try:
        from TTS.tts.configs.xtts_config import XttsConfig
        from TTS.config.shared_configs import BaseDatasetConfig
        from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
        torch.serialization.add_safe_globals([XttsConfig, BaseDatasetConfig, XttsAudioConfig, XttsArgs])
    except Exception as e:
        logger.debug("Could not register TTS safe globals: %s", e)


class VoiceCloningHandler:
    """
    Handles voice cloning and synthesis using XTTS v2.
    
    This class manages:
    - Voice cloning from audio samples
    - Voice embedding storage
    - TTS synthesis with cloned voices
    - Integration with existing TTS pipeline
    """
    
    def __init__(self, voices_dir: str = "data/voices", model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"):
        """
        Initialize the Voice Cloning Handler.
        
        Args:
            voices_dir: Directory to store cloned voice embeddings
            model_name: XTTS model name to use
        """
        if not XTTS_AVAILABLE:
            raise ImportError(
                "TTS library (Coqui TTS) is required for voice cloning. "
                "Install it with: pip install TTS>=0.22.0"
            )
        
        self.voices_dir = Path(voices_dir)
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        
        self.model_name = model_name
        self.tts = None
        self.model_loaded = False
        
        # Store voice embeddings in memory for faster access
        self.voice_embeddings: Dict[str, np.ndarray] = {}
        
        logger.info(f"VoiceCloningHandler initialized. Voices directory: {self.voices_dir}")
    
    def load_model(self):
        """Load the XTTS v2 model (lazy loading to avoid loading on import)"""
        if self.model_loaded:
            return
        
        _register_tts_safe_globals_for_torch_load()
        try:
            logger.info(f"Loading XTTS model: {self.model_name}")
            self.tts = TTS(self.model_name)
            self.model_loaded = True
            logger.info("XTTS model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load XTTS model: {e}")
            raise
    
    def clone_voice(
        self, 
        audio_sample_path: str, 
        voice_name: str,
        language: str = "en"
    ) -> bool:
        """
        Clone a voice from an audio sample.
        
        Args:
            audio_sample_path: Path to the audio sample file (WAV, MP3, etc.)
            voice_name: Name to assign to the cloned voice
            language: Language code (default: "en")
            
        Returns:
            True if successful, False otherwise
        """
        if not self.model_loaded:
            self.load_model()
        
        try:
            # Validate audio file exists
            audio_path = Path(audio_sample_path)
            if not audio_path.exists():
                logger.error(f"Audio file not found: {audio_sample_path}")
                return False
            
            # Clone the voice using XTTS
            logger.info(f"Cloning voice '{voice_name}' from {audio_sample_path}")
            
            # XTTS can clone directly from audio file
            # The voice embedding will be stored in the TTS model's internal storage
            # We'll also save it to disk for persistence
            
            # Generate voice embedding
            # Note: XTTS v2 API may vary, this is a general approach
            # The actual implementation depends on the TTS library version
            
            # For TTS >= 0.22.0, we can use the clone method if available
            # Otherwise, we'll use the synthesize method with the audio file as reference
            
            # Save voice metadata
            voice_metadata = {
                "name": voice_name,
                "source_audio": str(audio_path),
                "language": language,
                "created_at": str(Path().cwd())  # Store creation info
            }
            
            # Store the audio file path for later use
            voice_dir = self.voices_dir / voice_name
            voice_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy or reference the source audio
            import shutil
            target_audio = voice_dir / "source_audio.wav"
            shutil.copy2(audio_path, target_audio)
            
            # Save metadata
            import json
            metadata_path = voice_dir / "metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(voice_metadata, f, indent=2)
            
            logger.info(f"Voice '{voice_name}' cloned successfully. Stored in {voice_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Error cloning voice '{voice_name}': {e}", exc_info=True)
            return False
    
    def synthesize(
        self, 
        text: str, 
        voice_name: str,
        language: str = "en",
        output_sample_rate: int = 22050
    ) -> Optional[bytes]:
        """
        Synthesize speech using a cloned voice.
        
        Args:
            text: Text to synthesize
            voice_name: Name of the cloned voice to use
            language: Language code (default: "en")
            output_sample_rate: Desired output sample rate (default: 22050)
            
        Returns:
            PCM audio data as bytes, or None if synthesis fails
        """
        if not self.model_loaded:
            self.load_model()
        
        try:
            # Check if voice exists
            voice_dir = self.voices_dir / voice_name
            if not voice_dir.exists():
                logger.error(f"Voice '{voice_name}' not found")
                return None
            
            source_audio_path = voice_dir / "source_audio.wav"
            if not source_audio_path.exists():
                logger.error(f"Source audio for voice '{voice_name}' not found")
                return None
            
            logger.info(f"Synthesizing text with voice '{voice_name}': '{text[:50]}...'")
            
            # Synthesize using XTTS with the cloned voice
            # XTTS v2 can use a reference audio file for voice cloning
            # The API may vary, but generally:
            # tts.tts_to_file(text=text, file_path=output_path, speaker_wav=source_audio_path, language=language)
            
            # For in-memory synthesis, we'll use a temporary file approach
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                output_path = tmp_file.name
            
            try:
                # Synthesize to file
                self.tts.tts_to_file(
                    text=text,
                    file_path=output_path,
                    speaker_wav=str(source_audio_path),
                    language=language
                )
                
                # Read the generated audio file
                with wave.open(output_path, 'rb') as wav_file:
                    sample_rate = wav_file.getframerate()
                    n_frames = wav_file.getnframes()
                    audio_data = wav_file.readframes(n_frames)
                
                # Resample if needed
                if sample_rate != output_sample_rate:
                    # Convert bytes to numpy array
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                    audio_tensor = torch.from_numpy(audio_array).float() / 32768.0
                    
                    # Resample
                    resampled = F.resample(
                        audio_tensor.unsqueeze(0),
                        orig_freq=sample_rate,
                        new_freq=output_sample_rate
                    )
                    
                    # Convert back to bytes
                    audio_data = (resampled.squeeze(0).numpy() * 32768.0).astype(np.int16).tobytes()
                
                return audio_data
                
            finally:
                # Clean up temporary file
                if os.path.exists(output_path):
                    os.remove(output_path)
                    
        except Exception as e:
            logger.error(f"Error synthesizing with voice '{voice_name}': {e}", exc_info=True)
            return None
    
    def list_voices(self) -> List[Dict[str, str]]:
        """
        List all available cloned voices.
        
        Returns:
            List of voice metadata dictionaries
        """
        voices = []
        
        if not self.voices_dir.exists():
            return voices
        
        for voice_dir in self.voices_dir.iterdir():
            if not voice_dir.is_dir():
                continue
            
            metadata_path = voice_dir / "metadata.json"
            if metadata_path.exists():
                try:
                    import json
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    voices.append(metadata)
                except Exception as e:
                    logger.warning(f"Error reading metadata for {voice_dir.name}: {e}")
            else:
                # Voice exists but no metadata - create basic entry
                voices.append({
                    "name": voice_dir.name,
                    "source_audio": "unknown",
                    "language": "en",
                    "created_at": "unknown"
                })
        
        return voices
    
    def delete_voice(self, voice_name: str) -> bool:
        """
        Delete a cloned voice.
        
        Args:
            voice_name: Name of the voice to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            voice_dir = self.voices_dir / voice_name
            
            if not voice_dir.exists():
                logger.warning(f"Voice '{voice_name}' not found")
                return False
            
            # Remove voice directory
            import shutil
            shutil.rmtree(voice_dir)
            
            # Remove from memory cache if present
            if voice_name in self.voice_embeddings:
                del self.voice_embeddings[voice_name]
            
            logger.info(f"Voice '{voice_name}' deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting voice '{voice_name}': {e}", exc_info=True)
            return False
    
    def voice_exists(self, voice_name: str) -> bool:
        """
        Check if a voice exists.
        
        Args:
            voice_name: Name of the voice to check
            
        Returns:
            True if voice exists, False otherwise
        """
        voice_dir = self.voices_dir / voice_name
        return voice_dir.exists() and (voice_dir / "source_audio.wav").exists()
