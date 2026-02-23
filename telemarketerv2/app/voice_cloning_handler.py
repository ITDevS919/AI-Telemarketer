"""
Voice Cloning Handler using ElevenLabs API.

Handles voice cloning from audio samples and TTS synthesis using cloned voices.
Integrates with the existing TTSHandler for dual support: Piper TTS (pre-trained)
and ElevenLabs (cloned voices).
"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from elevenlabs.client import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    ElevenLabs = None


class VoiceCloningHandler:
    """
    Handles voice cloning and synthesis via ElevenLabs.

    - Clone voice from audio files (Instant Voice Cloning).
    - Store voice_id and metadata locally.
    - Synthesize speech with cloned voices.
    """

    DEFAULT_OUTPUT_SAMPLE_RATE = 22050
    ELEVENLABS_PCM_FORMAT = "pcm_22050"

    def __init__(self, voices_dir: str = "data/voices", api_key: Optional[str] = None):
        if not ELEVENLABS_AVAILABLE:
            raise ImportError(
                "ElevenLabs SDK is required for voice cloning. "
                "Install it with: pip install elevenlabs"
            )
        self.voices_dir = Path(voices_dir)
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self._api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self._api_key:
            logger.warning("ELEVENLABS_API_KEY not set. Voice cloning API calls will fail.")
        self._client: Optional[ElevenLabs] = None
        logger.info("VoiceCloningHandler (ElevenLabs) initialized. Voices directory: %s", self.voices_dir)

    def _get_client(self) -> ElevenLabs:
        if not self._api_key:
            raise ValueError("ELEVENLABS_API_KEY is not set. Set it in .env or pass api_key.")
        if self._client is None:
            self._client = ElevenLabs(api_key=self._api_key)
        return self._client

    def clone_voice(
        self,
        audio_sample_path: str,
        voice_name: str,
        language: str = "en",
        description: Optional[str] = None,
    ) -> bool:
        """
        Clone a voice from an audio sample using ElevenLabs Instant Voice Cloning.

        Args:
            audio_sample_path: Path to the audio file (WAV, MP3, etc.).
            voice_name: Name to assign to the cloned voice.
            language: Language code (stored in metadata; ElevenLabs IVC is language-agnostic).
            description: Optional description for the voice.

        Returns:
            True if successful, False otherwise.
        """
        audio_path = Path(audio_sample_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_sample_path}")

        client = self._get_client()
        logger.info("Cloning voice '%s' from %s via ElevenLabs", voice_name, audio_sample_path)

        file_basename = audio_path.name
        if not file_basename.lower().endswith((".wav", ".mp3", ".mpeg")):
            file_basename = "audio.wav"
        # Read file as binary and pass bytes to the SDK so the upload is not corrupted
        # (passing a path string can cause the SDK/httpx to open the file in text mode on some platforms)
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        if not audio_bytes:
            raise ValueError("Audio file is empty")
        voice = client.voices.ivc.create(
            name=voice_name,
            description=description or f"Cloned voice: {voice_name}",
            files=[(file_basename, audio_bytes)],
        )
        voice_id = getattr(voice, "voice_id", None) or getattr(voice, "id", None)
        if not voice_id:
            raise ValueError("ElevenLabs did not return a voice_id")

        voice_dir = self.voices_dir / voice_name
        voice_dir.mkdir(parents=True, exist_ok=True)
        target_audio = voice_dir / "source_audio.wav"
        shutil.copy2(audio_path, target_audio)

        metadata = {
            "name": voice_name,
            "elevenlabs_voice_id": voice_id,
            "source_audio": str(target_audio),
            "language": language,
            "description": description or "",
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        metadata_path = voice_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info("Voice '%s' cloned successfully. voice_id=%s", voice_name, voice_id)
        return True

    def synthesize(
        self,
        text: str,
        voice_name: str,
        language: str = "en",
        output_sample_rate: int = 22050,
    ) -> Optional[bytes]:
        """
        Synthesize speech using a cloned voice via ElevenLabs.

        Args:
            text: Text to synthesize.
            voice_name: Name of the cloned voice (must exist locally with elevenlabs_voice_id).
            language: Language code (passed to API when supported).
            output_sample_rate: Desired sample rate; 22050 is preferred for minimal resampling.

        Returns:
            PCM 16-bit mono audio as bytes, or None on failure.
        """
        try:
            voice_dir = self.voices_dir / voice_name
            metadata_path = voice_dir / "metadata.json"
            if not metadata_path.exists():
                logger.error("Voice '%s' not found (no metadata)", voice_name)
                return None

            with open(metadata_path) as f:
                metadata = json.load(f)
            voice_id = metadata.get("elevenlabs_voice_id")
            if not voice_id:
                logger.error("Voice '%s' has no elevenlabs_voice_id", voice_name)
                return None

            client = self._get_client()
            logger.debug("Synthesizing with voice '%s' (id=%s): '%s...'", voice_name, voice_id, text[:50])

            audio_bytes = client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
                output_format=self.ELEVENLABS_PCM_FORMAT,
            )

            if isinstance(audio_bytes, bytes):
                pcm_data = audio_bytes
            elif hasattr(audio_bytes, "read"):
                pcm_data = audio_bytes.read()
            elif hasattr(audio_bytes, "__iter__") and not isinstance(audio_bytes, (str, bytes)):
                pcm_data = b"".join(audio_bytes)
            else:
                pcm_data = bytes(audio_bytes)

            if not pcm_data:
                logger.error("ElevenLabs returned no audio for voice '%s'", voice_name)
                return None

            if output_sample_rate != self.DEFAULT_OUTPUT_SAMPLE_RATE:
                import numpy as np
                import torch
                import torchaudio.functional as F
                audio_array = np.frombuffer(pcm_data, dtype=np.int16)
                audio_tensor = torch.from_numpy(audio_array).float() / 32768.0
                resampled = F.resample(
                    audio_tensor.unsqueeze(0),
                    orig_freq=self.DEFAULT_OUTPUT_SAMPLE_RATE,
                    new_freq=output_sample_rate,
                )
                pcm_data = (resampled.squeeze(0).numpy() * 32768.0).astype(np.int16).tobytes()

            return pcm_data

        except Exception as e:
            logger.error("Error synthesizing with voice '%s': %s", voice_name, e, exc_info=True)
            return None

    def list_voices(self) -> List[Dict[str, str]]:
        """List all cloned voices (from local metadata)."""
        voices = []
        if not self.voices_dir.exists():
            return voices
        for voice_dir in self.voices_dir.iterdir():
            if not voice_dir.is_dir():
                continue
            metadata_path = voice_dir / "metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path) as f:
                        meta = json.load(f)
                    voices.append(meta)
                except Exception as e:
                    logger.warning("Error reading metadata for %s: %s", voice_dir.name, e)
            else:
                voices.append({
                    "name": voice_dir.name,
                    "elevenlabs_voice_id": "",
                    "source_audio": "unknown",
                    "language": "en",
                })
        return voices

    def delete_voice(self, voice_name: str) -> bool:
        """Delete a cloned voice locally and, if possible, from ElevenLabs."""
        try:
            voice_dir = self.voices_dir / voice_name
            if not voice_dir.exists():
                logger.warning("Voice '%s' not found", voice_name)
                return False

            voice_id = None
            metadata_path = voice_dir / "metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path) as f:
                        voice_id = json.load(f).get("elevenlabs_voice_id")
                except Exception:
                    pass

            if voice_id and self._api_key:
                try:
                    client = self._get_client()
                    if hasattr(client.voices, "delete") and callable(getattr(client.voices, "delete", None)):
                        client.voices.delete(voice_id)
                        logger.info("Deleted voice '%s' from ElevenLabs", voice_name)
                except Exception as e:
                    logger.warning("Could not delete voice from ElevenLabs (may require different plan): %s", e)

            shutil.rmtree(voice_dir)
            logger.info("Voice '%s' deleted locally", voice_name)
            return True

        except Exception as e:
            logger.error("Error deleting voice '%s': %s", voice_name, e, exc_info=True)
            return False

    def voice_exists(self, voice_name: str) -> bool:
        """Check if a cloned voice exists (has local dir and metadata)."""
        voice_dir = self.voices_dir / voice_name
        if not voice_dir.is_dir():
            return False
        metadata_path = voice_dir / "metadata.json"
        if not metadata_path.exists():
            return False
        return True
