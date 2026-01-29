"""
Conversation Manager for handling script-based telemarketing conversations.
"""
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio

from fastapi import WebSocket # For type hinting

from .llm_handler import LLMHandler
from .tts_handler import TTSHandler

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self, llm_handler: LLMHandler, tts_handler: TTSHandler, script_path: str = "telemarketerv2/data/scripts/5_steps_script.md"):
        self.llm_handler = llm_handler
        self.tts_handler = tts_handler
        self.script_path = script_path
        self.script: Optional[str] = None # Loaded script content
        self.current_step: int = 0
        self.conversation_history: List[Dict[str, str]] = []
        
        # Per-call state (could be moved to a separate class if complex)
        self.active_call_websockets: Dict[str, WebSocket] = {}
        self.active_call_stream_sids: Dict[str, str] = {}

        # Load script on initialization
        self._load_script()
        logger.info(f"ConversationManager initialized. Script path: {script_path}")

    def _load_script(self):
        try:
            with open(self.script_path, 'r', encoding='utf-8') as f:
                self.script = f.read()
            logger.info(f"Script loaded successfully from {self.script_path}")
        except FileNotFoundError:
            logger.error(f"Script file not found at {self.script_path}. ConversationManager will not function correctly.")
            self.script = "SCRIPT_NOT_FOUND"
        except Exception as e:
            logger.error(f"Error loading script: {e}", exc_info=True)
            self.script = "SCRIPT_LOAD_ERROR"

    async def initialize_conversation(self, call_sid: str, business_type: Optional[str], websocket: WebSocket, stream_sid: str):
        """Initialize a new conversation for a call when WebSocket stream starts."""
        logger.info(f"[{call_sid}] Initializing conversation. Business type: {business_type}")
        self.current_step = 1 # Reset or set to initial step
        self.conversation_history = [] # Clear history for new call
        self.active_call_websockets[call_sid] = websocket
        self.active_call_stream_sids[call_sid] = stream_sid
        
        # TODO: Consider if an initial greeting should be sent from here
        # or if the LLM should generate it based on the first handle_user_input (even if empty for system start)
        # For now, assume first interaction comes from user (or VAD indicating user is ready to speak)
        # Or, send an initial greeting/prompt immediately.
        initial_greeting = "Hello, I\'m calling from ProAutomation Solutions. Is the business owner available?"
        logger.info(f"[{call_sid}] Sending initial greeting: {initial_greeting}")
        self.conversation_history.append({"role": "assistant", "content": initial_greeting})
        await self.tts_handler.send_tts_audio(
            websocket=websocket,
            text_to_speak=initial_greeting,
            call_sid=call_sid,
            stream_sid=stream_sid
        )
        logger.info(f"[{call_sid}] Initial greeting sent.")
    
    async def handle_user_input(self, transcript: str, call_sid: Optional[str] = None) -> None:
        """
        Handle user input and generate appropriate response.
        call_sid is now optional here as it should be known when conversation is initialized.
        If a call_sid is passed, it will be used, otherwise assumes context is already set.
        """
        current_call_sid = call_sid or self._get_call_sid_from_context() # Helper to get current call_sid
        if not current_call_sid:
            logger.error("handle_user_input called without call_sid context.")
            return

        websocket = self.active_call_websockets.get(current_call_sid)
        stream_sid = self.active_call_stream_sids.get(current_call_sid)

        if not websocket or not stream_sid:
            logger.error(f"[{current_call_sid}] No active websocket or stream_sid for handling user input.")
            return

        try:
            if not self.script or self.script in ["SCRIPT_NOT_FOUND", "SCRIPT_LOAD_ERROR"]:
                logger.error(f"[{current_call_sid}] Attempted to handle user input but script is not loaded or failed to load.")
                fallback_error = "I apologize, I\'m having some technical difficulties with my script right now."
                await self.tts_handler.send_tts_audio(websocket, fallback_error, current_call_sid, stream_sid)
                return
                
            logger.info(f"[{current_call_sid}] Handling user input for step {self.current_step}")
            logger.debug(f"[{current_call_sid}] User transcript: {transcript}")
            
            self.conversation_history.append({"role": "user", "content": transcript})
            
            response = await self.llm_handler.get_response(
                script=self.script,
                conversation_history=self.conversation_history[-10:],
                current_transcript=transcript,
                current_step=self.current_step
            )
            
            self.conversation_history.append({"role": "assistant", "content": response})
            
            await self.tts_handler.send_tts_audio(
                websocket=websocket,
                text_to_speak=response,
                call_sid=current_call_sid,
                stream_sid=stream_sid
            )
            
            if "[HANGUP]" in response or "NEXT_STEP: HANGUP" in response: # Example trigger for hangup
                logger.info(f"[{current_call_sid}] LLM indicated hangup. Response: {response}")
                # TTS handler might take care of sending hangup TwiML if configured
                # Or we can explicitly close WebSocket or send hangup TwiML from here/DialerSystem
                # For now, assume TTS has an option or we rely on stream stop
            elif "NEXT_STEP" in response: # Placeholder for advancing step based on LLM
                try:
                    # Simple example: NEXT_STEP: 3
                    step_val = response.split("NEXT_STEP:")[-1].strip().split()[0]
                    if step_val.isdigit():
                        self.current_step = int(step_val)
                        logger.info(f"[{current_call_sid}] LLM indicated NEXT_STEP. Advanced to step {self.current_step}")
                    else:
                        logger.warning(f"[{current_call_sid}] LLM indicated NEXT_STEP but value is not a digit: {step_val}")
                except Exception as e:
                    logger.warning(f"[{current_call_sid}] Could not parse NEXT_STEP from LLM response: {response}. Error: {e}")
            
        except Exception as e:
            logger.error(f"[{current_call_sid}] Error handling user input: {e}", exc_info=True)
            fallback = "I apologize, but I\'m having trouble processing that. Could you please repeat?"
            await self.tts_handler.send_tts_audio(websocket, fallback, current_call_sid, stream_sid)
    
    def _get_call_sid_from_context(self) -> Optional[str]:
        """Helper to get current call_sid if only one active call or unambiguous context."""
        # This is a simplified placeholder. In a multi-call scenario, 
        # call_sid must be explicitly passed or reliably determined.
        if len(self.active_call_websockets) == 1:
            return list(self.active_call_websockets.keys())[0]
        # Add more sophisticated context determination if needed, or remove if call_sid is always passed.
        return None

    async def handle_call_stop(self, call_sid: str):
        """Handle call stop/end, clean up resources for that call."""
        logger.info(f"[{call_sid}] Handling call stop/cleanup in ConversationManager.")
        self.active_call_websockets.pop(call_sid, None)
        self.active_call_stream_sids.pop(call_sid, None)
        # Potentially log final conversation history or trigger other post-call actions here
        # final_history = self.get_conversation_history(call_sid) # This would need call_sid specific history
        # logger.info(f"[{call_sid}] Final conversation history: {final_history}")
        # For now, history is global to the manager, reset on new init_conversation.

    def get_conversation_history(self) -> List[Dict[str, str]]: # Potentially add call_sid if history becomes per-call
        """Get the current conversation history."""
        return self.conversation_history
    
    def get_current_step(self) -> int: # Potentially add call_sid
        """Get the current step in the script."""
        return self.current_step 