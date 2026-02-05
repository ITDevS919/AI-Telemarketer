"""
Handles Text-to-Speech generation and streaming audio back to the client (Twilio).

Supports both Piper TTS (pre-trained voices) and XTTS v2 (voice cloning).
"""
import logging
import io
import wave
import json
import base64
import audioop
import asyncio
from typing import Optional

import torch
import torchaudio.functional as F
from fastapi import WebSocket # Assuming WebSocket type from FastAPI
from piper.voice import PiperVoice
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError # For catching closure

logger = logging.getLogger(__name__)

# Import voice cloning handler (optional)
try:
    from .voice_cloning_handler import VoiceCloningHandler
    VOICE_CLONING_AVAILABLE = True
except ImportError:
    VOICE_CLONING_AVAILABLE = False
    VoiceCloningHandler = None


class TTSHandler:
    """Manages TTS synthesis and sending audio data."""

    def __init__(self, tts_voice: PiperVoice, voice_cloning_handler: Optional['VoiceCloningHandler'] = None):
        """
        Initializes the TTSHandler.

        Args:
            tts_voice: The loaded PiperVoice model instance.
            voice_cloning_handler: Optional VoiceCloningHandler for cloned voices.
        """
        if not tts_voice:
            raise ValueError("TTS Voice (Piper) must be provided and loaded.")
        self.tts_voice = tts_voice
        self.piper_sample_rate = tts_voice.config.sample_rate
        self.voice_cloning_handler = voice_cloning_handler
        
        if voice_cloning_handler:
            logger.info(f"TTSHandler initialized with Piper voice and voice cloning support. Sample rate: {self.piper_sample_rate}Hz")
        else:
            logger.info(f"TTSHandler initialized with Piper voice only. Sample rate: {self.piper_sample_rate}Hz")

    async def send_tts_audio(
        self,
        websocket: WebSocket,
        text_to_speak: str,
        call_sid: str,
        stream_sid: str,
        hangup_after_speech: bool = False,
        voice_name: Optional[str] = None
    ):
        """
        Generates TTS for the given text, resamples to 8kHz mu-law,
        streams it back over the WebSocket connection. Optionally hangs up the call.

        Args:
            websocket: The active WebSocket connection.
            text_to_speak: The text to synthesize.
            call_sid: The call SID for logging.
            stream_sid: The Twilio stream SID for sending media.
            hangup_after_speech: If True, sends a Hangup TwiML command after speech.
            voice_name: Optional name of cloned voice to use. If None, uses Piper TTS.
        """
        if not stream_sid:
            logger.warning(f"[{call_sid}] Cannot send TTS/TwiML: stream_sid is not set.")
            return

        if text_to_speak:
            logger.info(f"[{call_sid}] Generating TTS for: '{text_to_speak[:50]}...' (voice: {voice_name or 'piper'})")
            target_sample_rate = 8000  # Twilio expects 8kHz

            try:
                # Check if we should use cloned voice
                use_cloned_voice = (
                    voice_name and 
                    self.voice_cloning_handler and 
                    self.voice_cloning_handler.voice_exists(voice_name)
                )
                
                if use_cloned_voice:
                    # Use XTTS for cloned voice
                    pcm_data = self.voice_cloning_handler.synthesize(
                        text=text_to_speak,
                        voice_name=voice_name,
                        language="en",
                        output_sample_rate=22050  # XTTS default
                    )
                    
                    if not pcm_data:
                        logger.error(f"[{call_sid}] XTTS synthesis failed, falling back to Piper")
                        use_cloned_voice = False
                    else:
                        # Convert to tensor for resampling
                        pcm_tensor = torch.frombuffer(pcm_data, dtype=torch.int16).float() / 32768.0
                        # Resample from 22050 to 8000
                        pcm_tensor_8k = F.resample(
                            pcm_tensor.unsqueeze(0),
                            orig_freq=22050,
                            new_freq=target_sample_rate
                        )
                        pcm_data_8k = (pcm_tensor_8k.squeeze(0) * 32768.0).clamp(-32768, 32767).to(torch.int16).numpy().tobytes()
                
                if not use_cloned_voice:
                    # Use Piper TTS (default)
                    pcm_data_piper_sr = b'' # Initialize
                    with io.BytesIO() as wav_io:
                        # PiperVoice.synthesize expects a wave.Wave_write object
                        with wave.open(wav_io, "wb") as wav_file:
                            self.tts_voice.synthesize(text_to_speak, wav_file)
                        full_wav_bytes = wav_io.getvalue()
                    
                    # Re-open the WAV bytes to read frames
                    with io.BytesIO(full_wav_bytes) as wav_read_io:
                        with wave.open(wav_read_io, 'rb') as wav_read_file:
                            if wav_read_file.getframerate() != self.piper_sample_rate:
                                logger.warning(f"[{call_sid}] Piper output sample rate {wav_read_file.getframerate()}Hz mismatch with config {self.piper_sample_rate}Hz. Using config rate.")
                            pcm_data_piper_sr = wav_read_file.readframes(wav_read_file.getnframes())

                    if not pcm_data_piper_sr:
                        logger.error(f"[{call_sid}] TTS synthesis produced no PCM data for: '{text_to_speak[:50]}...'")
                        return

                    # Convert raw PCM 16-bit bytes to a float32 tensor
                    pcm_s16_tensor_piper = torch.frombuffer(pcm_data_piper_sr, dtype=torch.int16).float() / 32768.0

                    if self.piper_sample_rate != target_sample_rate:
                        pcm_s16_tensor_8k = F.resample(pcm_s16_tensor_piper, orig_freq=self.piper_sample_rate, new_freq=target_sample_rate)
                    else:
                        pcm_s16_tensor_8k = pcm_s16_tensor_piper

                    # Convert float32 tensor back to 16-bit PCM bytes
                    pcm_data_8k = (pcm_s16_tensor_8k * 32768.0).clamp(-32768, 32767).to(torch.int16).numpy().tobytes()

                # Convert 16-bit linear PCM to 8-bit mu-law
                mulaw_audio_bytes = audioop.lin2ulaw(pcm_data_8k, 2) # 2 indicates 2 bytes per sample (16-bit)
                base64_mulaw = base64.b64encode(mulaw_audio_bytes).decode('utf-8')

                media_message = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": base64_mulaw}
                }
                await websocket.send_text(json.dumps(media_message))
                
                mark_message = {
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": "tts_finished"}
                }
                await websocket.send_text(json.dumps(mark_message))
                logger.info(f"[{call_sid}] Sent TTS finished mark for '{text_to_speak[:30]}...'.")

            except (ConnectionClosedOK, ConnectionClosedError) as ws_err:
                logger.warning(f"[{call_sid}] WebSocket closed during TTS sending for '{text_to_speak[:30]}...': {ws_err}")
                return
            except audioop.error as audio_err:
                logger.error(f"[{call_sid}] Audioop error during TTS processing for '{text_to_speak[:30]}...': {audio_err}")
            except Exception as e:
                logger.error(f"[{call_sid}] Error during TTS synthesis: {e}", exc_info=True)

        elif hangup_after_speech:
            logger.info(f"[{call_sid}] No text to speak, but hangup_after_speech is true. Proceeding to hangup.")

        if hangup_after_speech:
            try:
                hangup_twiml = "<Response><Hangup/></Response>"
                base64_twiml = base64.b64encode(hangup_twiml.encode('utf-8')).decode('utf-8')
                
                hangup_message = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {
                        "payload": base64_twiml
                    }
                }
                await asyncio.sleep(0.1) 
                await websocket.send_text(json.dumps(hangup_message))
                logger.info(f"[{call_sid}] Sent Hangup TwiML command to Twilio stream {stream_sid}.")
            except (ConnectionClosedOK, ConnectionClosedError) as ws_err:
                logger.warning(f"[{call_sid}] WebSocket closed before Hangup TwiML could be sent: {ws_err}")
            except Exception as e:
                logger.error(f"[{call_sid}] Error sending Hangup TwiML: {e}", exc_info=True)

# Note: This handler assumes the PiperVoice model is loaded and passed during initialization.
# It doesn't handle streaming TTS generation chunk-by-chunk, but processes the whole synthesized audio.
# For very long TTS responses, a chunking approach within this handler might be needed later. 