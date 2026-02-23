"""
Conversation Manager for handling script-based telemarketing conversations.

Supports two modes:
- Scripted (Version A): Deterministic 5-step / 16-sub-step delivery using
  structured script; optional cloned voice.
- Interactive (Version B): LLM-driven responses with script as context; Piper or UK voice.
"""

import logging
import re
from typing import Dict, List, Optional, Any

from fastapi import WebSocket

from .llm_handler import LLMHandler
from .tts_handler import TTSHandler
from .structured_script import get_structured_script, ScriptSegment, StructuredScript

logger = logging.getLogger(__name__)


def _classify_sentiment(transcript: str) -> str:
    """Classify user response for scripted branching: positive, negative, more_info, neutral."""
    t = (transcript or "").strip().lower()
    if not t:
        return "neutral"
    # Positive
    if re.search(r"\b(yes|yeah|sure|sounds good|interested|tell me more|go on|ok|okay|please)\b", t):
        return "positive"
    if re.search(r"\b(not interested|no thanks|busy|not now|don't need|no thank you)\b", t):
        return "negative"
    if re.search(r"\b(what is it|what do you do|tell me about|information|explain|how does it)\b", t):
        return "more_info"
    if re.search(r"\b(no|nope)\b", t) and len(t) < 30:
        return "negative"
    return "neutral"


class ConversationManager:
    def __init__(
        self,
        llm_handler: LLMHandler,
        tts_handler: TTSHandler,
        script_path: str = "telemarketerv2/data/scripts/5_Steps_Marketing_Updated.md",
    ):
        self.llm_handler = llm_handler
        self.tts_handler = tts_handler
        self.script_path = script_path
        self.script: Optional[str] = None
        self.current_step: int = 0
        self.conversation_history: List[Dict[str, str]] = []

        self.active_call_websockets: Dict[str, WebSocket] = {}
        self.active_call_stream_sids: Dict[str, str] = {}
        self.active_call_voice_name: Dict[str, Optional[str]] = {}
        self.active_call_scripted: Dict[str, bool] = {}
        self.active_call_segment_index: Dict[str, int] = {}

        self._load_script()
        self._structured_script: Optional[StructuredScript] = get_structured_script(script_path)
        logger.info("ConversationManager initialized. Script path: %s", script_path)

    def _load_script(self) -> None:
        try:
            with open(self.script_path, "r", encoding="utf-8") as f:
                self.script = f.read()
            logger.info("Script loaded successfully from %s", self.script_path)
        except FileNotFoundError:
            logger.error("Script file not found at %s", self.script_path)
            self.script = "SCRIPT_NOT_FOUND"
        except Exception as e:
            logger.error("Error loading script: %s", e, exc_info=True)
            self.script = "SCRIPT_LOAD_ERROR"

    def _voice_for_call(self, call_sid: str) -> Optional[str]:
        return self.active_call_voice_name.get(call_sid)

    async def initialize_conversation(
        self,
        call_sid: str,
        business_type: Optional[str],
        websocket: WebSocket,
        stream_sid: str,
        voice_name: Optional[str] = None,
        scripted_mode: bool = False,
    ) -> None:
        """Initialize a new conversation. If scripted_mode=True, use structured 5-step script and optional cloned voice."""
        logger.info(
            "[%s] Initializing conversation. business_type=%s voice_name=%s scripted=%s",
            call_sid,
            business_type,
            voice_name,
            scripted_mode,
        )
        self.current_step = 1
        self.conversation_history = []
        self.active_call_websockets[call_sid] = websocket
        self.active_call_stream_sids[call_sid] = stream_sid
        self.active_call_voice_name[call_sid] = voice_name
        self.active_call_scripted[call_sid] = scripted_mode
        self.active_call_segment_index[call_sid] = 0

        if scripted_mode and self._structured_script:
            first = self._structured_script.get_first_segment()
            if first:
                text = self._structured_script.get_speech_for_segment(first)
                self.conversation_history.append({"role": "assistant", "content": text})
                await self.tts_handler.send_tts_audio(
                    websocket=websocket,
                    text_to_speak=text,
                    call_sid=call_sid,
                    stream_sid=stream_sid,
                    voice_name=voice_name,
                )
                logger.info("[%s] Scripted mode: sent first segment (Step 1A).", call_sid)
                return

        initial_greeting = (
            "Hi, can I speak to the owner please? It's nothing serious. It's just a quick introductory call."
        )
        self.conversation_history.append({"role": "assistant", "content": initial_greeting})
        await self.tts_handler.send_tts_audio(
            websocket=websocket,
            text_to_speak=initial_greeting,
            call_sid=call_sid,
            stream_sid=stream_sid,
            voice_name=voice_name,
        )
        logger.info("[%s] Initial greeting sent.", call_sid)

    async def handle_user_input(self, transcript: str, call_sid: Optional[str] = None) -> None:
        """Handle user input: scripted mode uses structured script + branching; else LLM."""
        current_call_sid = call_sid or self._get_call_sid_from_context()
        if not current_call_sid:
            logger.error("handle_user_input called without call_sid context.")
            return

        websocket = self.active_call_websockets.get(current_call_sid)
        stream_sid = self.active_call_stream_sids.get(current_call_sid)
        if not websocket or not stream_sid:
            logger.error("[%s] No active websocket or stream_sid.", current_call_sid)
            return

        voice_name = self._voice_for_call(current_call_sid)
        scripted = self.active_call_scripted.get(current_call_sid, False)

        try:
            if scripted and self._structured_script:
                await self._handle_scripted_input(
                    current_call_sid,
                    transcript,
                    websocket,
                    stream_sid,
                    voice_name,
                )
                return

            await self._handle_interactive_input(
                current_call_sid,
                transcript,
                websocket,
                stream_sid,
                voice_name,
            )
        except Exception as e:
            logger.error("[%s] Error handling user input: %s", current_call_sid, e, exc_info=True)
            fallback = "I apologize, but I'm having trouble processing that. Could you please repeat?"
            await self.tts_handler.send_tts_audio(
                websocket=websocket,
                text_to_speak=fallback,
                call_sid=current_call_sid,
                stream_sid=stream_sid,
                voice_name=voice_name,
            )

    async def _handle_scripted_input(
        self,
        call_sid: str,
        transcript: str,
        websocket: WebSocket,
        stream_sid: str,
        voice_name: Optional[str],
    ) -> None:
        """Advance structured script and speak next segment (or objection/email exit)."""
        idx = self.active_call_segment_index.get(call_sid, 0)
        script = self._structured_script
        assert script is not None

        current = script.get_segment_by_index(idx)
        if not current:
            logger.warning("[%s] Scripted: no segment at index %s", call_sid, idx)
            return

        self.conversation_history.append({"role": "user", "content": transcript})
        sentiment = _classify_sentiment(transcript)

        to_speak: Optional[str] = None
        next_idx = idx

        if sentiment == "negative" and (current.objection_lines or current.email_exit_lines):
            to_speak = script.get_objection_response(current)
            if not to_speak and current.email_exit_lines:
                to_speak = script.get_email_exit_response(current)
            # Don't advance segment; we stay for possible email exit on next turn
        if not to_speak:
            next_seg = script.get_next_segment(current, sentiment)
            if next_seg is not None:
                to_speak = script.get_speech_for_segment(next_seg)
                next_idx = next(
                    (i for i, s in enumerate(script.segments) if s is next_seg),
                    idx + 1,
                )
            elif idx + 1 < len(script.segments):
                next_seg = script.get_segment_by_index(idx + 1)
                if next_seg:
                    to_speak = script.get_speech_for_segment(next_seg)
                    next_idx = idx + 1
        if not to_speak:
            to_speak = script.get_speech_for_segment(current)
            if idx + 1 < len(script.segments):
                next_idx = idx + 1

        if to_speak:
            self.active_call_segment_index[call_sid] = next_idx
            self.conversation_history.append({"role": "assistant", "content": to_speak})
            await self.tts_handler.send_tts_audio(
                websocket=websocket,
                text_to_speak=to_speak,
                call_sid=call_sid,
                stream_sid=stream_sid,
                voice_name=voice_name,
            )
            logger.info("[%s] Scripted: sent segment (index %s)", call_sid, next_idx)

    async def _handle_interactive_input(
        self,
        call_sid: str,
        transcript: str,
        websocket: WebSocket,
        stream_sid: str,
        voice_name: Optional[str],
    ) -> None:
        """LLM-based response using script as context (Version B style)."""
        if not self.script or self.script in ("SCRIPT_NOT_FOUND", "SCRIPT_LOAD_ERROR"):
            fallback = "I apologize, I'm having some technical difficulties with my script right now."
            await self.tts_handler.send_tts_audio(
                websocket=websocket,
                text_to_speak=fallback,
                call_sid=call_sid,
                stream_sid=stream_sid,
                voice_name=voice_name,
            )
            return

        logger.info("[%s] Handling user input for step %s", call_sid, self.current_step)
        self.conversation_history.append({"role": "user", "content": transcript})

        response = await self.llm_handler.get_response(
            script=self.script,
            conversation_history=self.conversation_history[-10:],
            current_transcript=transcript,
            current_step=self.current_step,
        )
        self.conversation_history.append({"role": "assistant", "content": response})

        await self.tts_handler.send_tts_audio(
            websocket=websocket,
            text_to_speak=response,
            call_sid=call_sid,
            stream_sid=stream_sid,
            voice_name=voice_name,
        )

        if "NEXT_STEP" in response:
            try:
                step_val = response.split("NEXT_STEP:")[-1].strip().split()[0]
                if step_val.isdigit():
                    self.current_step = int(step_val)
                    logger.info("[%s] Advanced to step %s", call_sid, self.current_step)
            except Exception:
                pass

    def _get_call_sid_from_context(self) -> Optional[str]:
        if len(self.active_call_websockets) == 1:
            return list(self.active_call_websockets.keys())[0]
        return None

    async def handle_call_stop(self, call_sid: str) -> None:
        logger.info("[%s] Handling call stop/cleanup.", call_sid)
        self.active_call_websockets.pop(call_sid, None)
        self.active_call_stream_sids.pop(call_sid, None)
        self.active_call_voice_name.pop(call_sid, None)
        self.active_call_scripted.pop(call_sid, None)
        self.active_call_segment_index.pop(call_sid, None)

    def get_conversation_history(self) -> List[Dict[str, str]]:
        return self.conversation_history

    def get_current_step(self) -> int:
        return self.current_step
