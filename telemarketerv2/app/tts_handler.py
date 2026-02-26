"""
Handles Text-to-Speech generation and streaming audio back to the client (Twilio).

Supports both Piper TTS (pre-trained voices) and ElevenLabs (voice cloning).
Real-time TTS: audio is sent in 20ms frames (Twilio standard). Piper can be
synthesized sentence-by-sentence for faster time-to-first-byte.
"""
import logging
import io
import re
import wave
import json
import base64
import audioop
import asyncio
import os
from typing import Optional, List

import numpy as np
import torch
import torchaudio.functional as F
from fastapi import WebSocket
from piper.voice import PiperVoice
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

logger = logging.getLogger(__name__)

# Twilio Media Streams: 20ms frames at 8kHz = 160 samples = 320 bytes PCM 16-bit = 160 bytes mu-law
TTS_FRAME_MS = 20
TTS_SAMPLE_RATE_TWILIO = 8000
TTS_FRAME_BYTES_PCM = (TTS_FRAME_MS * TTS_SAMPLE_RATE_TWILIO // 1000) * 2  # 320

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

    async def _send_pcm_as_stream(
        self,
        websocket: WebSocket,
        pcm_data_8k: bytes,
        stream_sid: str,
        call_sid: str,
    ) -> None:
        """Send 16-bit PCM at 8kHz in 20ms mu-law frames. Optionally pace at real-time so Twilio plays correctly."""
        frame_sec = TTS_FRAME_MS / 1000.0
        pace_frames = os.getenv("REALTIME_TTS_PACE_FRAMES", "true").lower() in ("true", "1", "yes")
        n = len(pcm_data_8k)
        offset = 0
        while offset < n:
            chunk = pcm_data_8k[offset : offset + TTS_FRAME_BYTES_PCM]
            if not chunk:
                break
            offset += len(chunk)
            if len(chunk) < TTS_FRAME_BYTES_PCM:
                chunk = chunk.ljust(TTS_FRAME_BYTES_PCM, b"\x00")
            mulaw_bytes = audioop.lin2ulaw(chunk, 2)
            base64_mulaw = base64.b64encode(mulaw_bytes).decode("utf-8")
            media_message = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": base64_mulaw},
            }
            await websocket.send_text(json.dumps(media_message))
            if pace_frames:
                await asyncio.sleep(frame_sec)
        logger.debug(f"[{call_sid}] Streamed {offset} bytes in 20ms frames")

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text into sentences for chunked Piper synthesis."""
        text = (text or "").strip()
        if not text:
            return []
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if p.strip()]

    async def send_tts_audio(
        self,
        websocket: WebSocket,
        text_to_speak: str,
        call_sid: str,
        stream_sid: str,
        hangup_after_speech: bool = False,
        voice_name: Optional[str] = None,
    ):
        """
        Generates TTS for the given text, resamples to 8kHz, and streams it in 20ms
        frames over the WebSocket (real-time TTS). Optionally hangs up the call.
        """
        if not stream_sid:
            logger.warning(f"[{call_sid}] Cannot send TTS/TwiML: stream_sid is not set.")
            return

        use_streaming = os.getenv("REALTIME_TTS_STREAMING", "true").lower() in ("true", "1", "yes")
        target_sample_rate = TTS_SAMPLE_RATE_TWILIO

        if text_to_speak:
            logger.info(f"[{call_sid}] Generating TTS for: '{text_to_speak[:50]}...' (voice: {voice_name or 'piper'}, streaming={use_streaming})")
            try:
                use_cloned_voice = (
                    voice_name
                    and self.voice_cloning_handler
                    and self.voice_cloning_handler.voice_exists(voice_name)
                )

                if use_cloned_voice:
                    pcm_data = self.voice_cloning_handler.synthesize(
                        text=text_to_speak,
                        voice_name=voice_name,
                        language="en",
                        output_sample_rate=22050,
                    )
                    if not pcm_data:
                        logger.error(f"[{call_sid}] ElevenLabs synthesis failed, falling back to Piper")
                        use_cloned_voice = False
                    else:
                        pcm_tensor = torch.from_numpy(np.frombuffer(pcm_data, dtype=np.int16).copy()).float() / 32768.0
                        pcm_tensor_8k = F.resample(
                            pcm_tensor.unsqueeze(0),
                            orig_freq=22050,
                            new_freq=target_sample_rate,
                        )
                        pcm_data_8k = (
                            (pcm_tensor_8k.squeeze(0) * 32768.0)
                            .clamp(-32768, 32767)
                            .to(torch.int16)
                            .numpy()
                            .tobytes()
                        )
                        if use_streaming:
                            await self._send_pcm_as_stream(websocket, pcm_data_8k, stream_sid, call_sid)
                        else:
                            mulaw_bytes = audioop.lin2ulaw(pcm_data_8k, 2)
                            base64_mulaw = base64.b64encode(mulaw_bytes).decode("utf-8")
                            await websocket.send_text(
                                json.dumps(
                                    {"event": "media", "streamSid": stream_sid, "media": {"payload": base64_mulaw}}
                                )
                            )

                if not use_cloned_voice:
                    # Piper: optional sentence-by-sentence for faster time-to-first-byte
                    piper_stream_sentences = use_streaming and os.getenv("REALTIME_TTS_PIPER_SENTENCE_STREAM", "true").lower() in ("true", "1", "yes")
                    if piper_stream_sentences:
                        sentences = self._split_sentences(text_to_speak)
                        if not sentences:
                            sentences = [text_to_speak]
                        for sent in sentences:
                            if not sent:
                                continue
                            with io.BytesIO() as wav_io:
                                with wave.open(wav_io, "wb") as wav_file:
                                    wav_file.setnchannels(1)
                                    wav_file.setsampwidth(2)
                                    wav_file.setframerate(self.piper_sample_rate)
                                    self.tts_voice.synthesize(sent, wav_file)
                                full_wav_bytes = wav_io.getvalue()
                            with io.BytesIO(full_wav_bytes) as wav_read_io:
                                with wave.open(wav_read_io, "rb") as wav_read_file:
                                    pcm_piper = wav_read_file.readframes(wav_read_file.getnframes())
                            if not pcm_piper:
                                continue
                            pcm_t = torch.from_numpy(np.frombuffer(pcm_piper, dtype=np.int16)).float() / 32768.0
                            if self.piper_sample_rate != target_sample_rate:
                                pcm_t = F.resample(
                                    pcm_t.unsqueeze(0),
                                    orig_freq=self.piper_sample_rate,
                                    new_freq=target_sample_rate,
                                ).squeeze(0)
                            pcm_8k = (pcm_t * 32768.0).clamp(-32768, 32767).to(torch.int16).numpy().tobytes()
                            await self._send_pcm_as_stream(websocket, pcm_8k, stream_sid, call_sid)
                    else:
                        with io.BytesIO() as wav_io:
                            with wave.open(wav_io, "wb") as wav_file:
                                wav_file.setnchannels(1)
                                wav_file.setsampwidth(2)
                                wav_file.setframerate(self.piper_sample_rate)
                                self.tts_voice.synthesize(text_to_speak, wav_file)
                            full_wav_bytes = wav_io.getvalue()
                        with io.BytesIO(full_wav_bytes) as wav_read_io:
                            with wave.open(wav_read_io, "rb") as wav_read_file:
                                pcm_data_piper_sr = wav_read_file.readframes(wav_read_file.getnframes())
                        if not pcm_data_piper_sr:
                            logger.error(f"[{call_sid}] TTS produced no PCM for: '{text_to_speak[:50]}...'")
                            return
                        pcm_s16_tensor_piper = torch.from_numpy(np.frombuffer(pcm_data_piper_sr, dtype=np.int16)).float() / 32768.0
                        if self.piper_sample_rate != target_sample_rate:
                            pcm_s16_tensor_8k = F.resample(
                                pcm_s16_tensor_piper.unsqueeze(0),
                                orig_freq=self.piper_sample_rate,
                                new_freq=target_sample_rate,
                            ).squeeze(0)
                        else:
                            pcm_s16_tensor_8k = pcm_s16_tensor_piper
                        pcm_data_8k = (pcm_s16_tensor_8k * 32768.0).clamp(-32768, 32767).to(torch.int16).numpy().tobytes()
                        if use_streaming:
                            await self._send_pcm_as_stream(websocket, pcm_data_8k, stream_sid, call_sid)
                        else:
                            mulaw_bytes = audioop.lin2ulaw(pcm_data_8k, 2)
                            base64_mulaw = base64.b64encode(mulaw_bytes).decode("utf-8")
                            await websocket.send_text(
                                json.dumps(
                                    {"event": "media", "streamSid": stream_sid, "media": {"payload": base64_mulaw}}
                                )
                            )

                mark_message = {"event": "mark", "streamSid": stream_sid, "mark": {"name": "tts_finished"}}
                await websocket.send_text(json.dumps(mark_message))
                logger.info(f"[{call_sid}] Sent TTS finished mark for '{text_to_speak[:30]}...'.")

            except (ConnectionClosedOK, ConnectionClosedError) as ws_err:
                logger.warning(f"[{call_sid}] WebSocket closed during TTS: {ws_err}")
                return
            except audioop.error as audio_err:
                logger.error(f"[{call_sid}] Audioop error during TTS: {audio_err}")
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

# Real-time TTS: set REALTIME_TTS_STREAMING=true (default) to send audio in 20ms frames.
# For Piper, set REALTIME_TTS_PIPER_SENTENCE_STREAM=true (default) to synthesize and send sentence-by-sentence.