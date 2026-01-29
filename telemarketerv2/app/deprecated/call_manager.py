# telemarketerv2/app/call_manager.py
# CORRECTED VERSION - Focused on Live Call Conversation Logic

import asyncio
import datetime
import json
import logging
import os
import re
import time
from typing import Dict, List, Optional, Tuple, Union, Any

import groq
from fastapi import WebSocket # Keep WebSocket for type hinting helpers
from websockets.exceptions import ConnectionClosed

# Core components injected or used
from .call_state_manager import CallStateManager, CallStateMachine, ScriptState, ScriptAction, _COMMON_EXIT_STATES, LeadStatus
from .llm_handler import LLMHandler
from .tts_handler import TTSHandler
from .script_parser import load_script_state_data, MAKING_MONEY_SCRIPT_FILENAME, SAVING_MONEY_SCRIPT_FILENAME
from .uk_regulations_integration import get_regulations_manager, UKRegulationsManager # Keep for health check? Or remove if health is separate?
from .utils import render_dialogue
# Removed: script_selector import - Call creation belongs elsewhere

logger = logging.getLogger(__name__)

# --- Constants for CallManager interaction logic ---
CM_SCRIPT_LOAD_TIMEOUT = 5.0
CM_LLM_CALL_TIMEOUT = 15.0
CM_FALLBACK_HANGUP_MESSAGE = "I seem to have encountered a technical difficulty. Thank you for your time. Goodbye."
CM_FALLBACK_CLARIFY_MESSAGE = "Sorry, I didn't quite understand that. Could you please rephrase?"

# Define script filenames at the module level
MM_SCRIPT = MAKING_MONEY_SCRIPT_FILENAME
SM_SCRIPT = SAVING_MONEY_SCRIPT_FILENAME

class CallManager:
    """
    Manages the CONVERSATION LOGIC for live telemarketer calls.
    Does NOT handle dialing, queue management, or API endpoints for call creation/status.
    """

    def __init__(self,
                 call_state_manager: CallStateManager,
                 llm_handler: LLMHandler,
                 tts_handler: TTSHandler,
                 regulations_manager: Optional[UKRegulationsManager] = None):
        """
        Initialize the CallManager with injected dependencies required for conversation flow.
        """
        self.csm = call_state_manager
        self.llm = llm_handler
        self.tts = tts_handler
        self.regulations = regulations_manager if regulations_manager else UKRegulationsManager()
        logger.info("CallManager initialized (Conversation Logic Focus).")

    async def initialize(self):
        """Initialize dependencies if needed (e.g., regulations for health check)."""
        # Initialize regulations only if needed for health check within CallManager scope
        # Otherwise, initialization might belong solely to DialerSystem
        await self.regulations.initialize()
        # CSM load_states is handled in main lifespan
        # await self.csm.load_states()
        logger.info("CallManager async components initialized (e.g., Regulations for health).")

    # --- Live Call Interaction Logic (Primary role for WebSocket calls) ---

    async def _replace_placeholders_cm(self, text: str, state_machine: CallStateMachine) -> str:
        """Replaces known placeholders in a dialogue string."""
        if not text: return ""
        try:
            return render_dialogue(text, {"state_machine": state_machine})
        except Exception as e:
            call_sid = getattr(state_machine, 'call_sid', 'Unknown')
            logger.error(f"[{call_sid}] Error rendering dialogue in _replace_placeholders_cm: {e}", exc_info=True)
            return text # Fallback

    async def _close_websocket_if_open_cm(self, websocket: WebSocket, call_sid: str, reason: str = "Hangup triggered"):
        """Helper to close WebSocket connection cleanly."""
        ws_state = getattr(websocket, 'client_state', None)
        # Use FastAPI's WebSocketState if available, otherwise assume simple boolean check
        try:
             from starlette.websockets import WebSocketState as StarletteWebSocketState
             is_connected = ws_state is not None and ws_state != StarletteWebSocketState.DISCONNECTED
        except ImportError:
             is_connected = websocket is not None # Basic check

        if websocket and is_connected:
            try:
                logger.info(f"[{call_sid}] CM: Closing WebSocket: {reason}")
                await websocket.close(code=1000, reason=reason)
            except ConnectionClosed:
                 logger.info(f"[{call_sid}] CM: WebSocket ConnectionClosed (already closed by client) during explicit close ({reason}).")
            except RuntimeError as e:
                 logger.warning(f"[{call_sid}] CM: Runtime error closing WebSocket (likely already closing/closed): {e}")
            except Exception as e:
                 logger.error(f"[{call_sid}] CM: Error closing WebSocket ({reason}): {e}", exc_info=True)
        else:
            logger.debug(f"[{call_sid}] CM: WebSocket already closed or not provided when attempting close ({reason}).")

    async def _handle_fallback_hangup_cm(self, websocket: WebSocket, state_machine: CallStateMachine, stream_sid: str, reason: str = "fallback_hangup"):
        """Handles fallback hangups during live call interaction."""
        call_sid = state_machine.call_sid
        current_state_val = state_machine.state.value
        logger.warning(f"[{call_sid}] CM: Fallback hangup. Reason: {reason}. Current state: {current_state_val}")

        target_hangup_state = ScriptState.FALLBACK_HANGUP
        if reason == "max_repeat_timeout":
            target_hangup_state = ScriptState.HANGUP_MAX_REPEATS

        if state_machine.state in _COMMON_EXIT_STATES:
            logger.info(f"[{call_sid}] CM: Already in terminal state ({current_state_val}). Fallback reason: {reason}")
            # Even if in terminal state, ensure Twilio hangup if WS is still open somehow
            if websocket and getattr(websocket, 'client_state', None) != WebSocket.client_state.DISCONNECTED:
                 logger.info(f"[{call_sid}] CM: Sending explicit hangup for already terminal state due to fallback reason: {reason}")
                 asyncio.create_task(self.tts.send_tts_audio(websocket, "", call_sid, stream_sid, hangup_after_speech=True))
            await self._close_websocket_if_open_cm(websocket, call_sid, f"Fallback in terminal: {reason}")
            return

        if not state_machine.validate_and_set_state(target_hangup_state): # Pass Enum member
            logger.error(f"[{call_sid}] CM: Could not transition from {current_state_val} to {target_hangup_state.value}. Forcing state to FALLBACK_HANGUP.")
            state_machine.state = ScriptState.FALLBACK_HANGUP

        final_state_for_end_call = state_machine.state

        self.csm.end_call(call_sid, final_state=final_state_for_end_call)

        try:
            final_message = CM_FALLBACK_HANGUP_MESSAGE
            state_machine.add_history_entry("assistant", final_message)
            asyncio.create_task(self.tts.send_tts_audio(websocket, final_message, call_sid, stream_sid, hangup_after_speech=True))
        except Exception as tts_err:
            logger.error(f"[{call_sid}] CM: Error sending final TTS during fallback hangup: {tts_err}")

        # Close WebSocket after attempting to send hangup TwiML
        # The TTS task is async, so closing immediately might prevent TwiML send.
        # However, _close_websocket_if_open_cm is robust.
        # Consider a short delay or ensuring TTS task completion if issues arise.
        await asyncio.sleep(0.5) # Give a bit more time for async TTS+Hangup task
        await self._close_websocket_if_open_cm(websocket, call_sid, f"Fallback: {reason}, Final State: {final_state_for_end_call.value}")


    async def _ask_for_clarification_cm(self, websocket: WebSocket, state_machine: CallStateMachine, stream_sid: str):
        """Asks the user for clarification during live call interaction."""
        call_sid = state_machine.call_sid
        logger.warning(f"[{call_sid}] CM: Asking user for clarification.")
        try:
            state_machine.add_history_entry("assistant", CM_FALLBACK_CLARIFY_MESSAGE)
            await self.tts.send_tts_audio(websocket, CM_FALLBACK_CLARIFY_MESSAGE, call_sid, stream_sid, hangup_after_speech=False)
            state_machine.in_listen_state = True
        except Exception as tts_err:
            logger.error(f"[{call_sid}] CM: Clarification TTS error: {tts_err}", exc_info=True)
            await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, "clarification_tts_error")


    async def handle_call_interaction(
        self,
        websocket: WebSocket,
        state_machine: CallStateMachine,
        stream_sid: str,
        transcript: str
    ) -> Optional[ScriptState]:
        """
        Main logic for handling a turn in the conversation after STT during a live WebSocket call.
        """
        call_sid = state_machine.call_sid
        current_state_enum = state_machine.state
        logger.info(f"[{call_sid}] CM: Handling STT '{transcript}' from state {current_state_enum.value}")

        if transcript:
            state_machine.add_history_entry("user", transcript)

        next_state_obj: Optional[ScriptState] = None
        try:
            start_time = time.monotonic()
            next_state_obj = await asyncio.wait_for(
                self.llm.get_next_state(state_machine, transcript),
                timeout=CM_LLM_CALL_TIMEOUT
            )
            llm_response_time = time.monotonic() - start_time
            if next_state_obj:
                logger.info(f"[{call_sid}] CM: LLM proposed next state: {next_state_obj.value} (took {llm_response_time:.2f}s)")
            else:
                logger.warning(f"[{call_sid}] CM: LLM returned None.")
                valid_transitions = state_machine._VALID_TRANSITIONS.get(current_state_enum, set())
                if ScriptState.ASK_CLARIFICATION in valid_transitions:
                     next_state_obj = ScriptState.ASK_CLARIFICATION
                     logger.info(f"[{call_sid}] CM: Defaulting to ASK_CLARIFICATION.")
                else:
                    logger.warning(f"[{call_sid}] CM: Cannot transition to ASK_CLARIFICATION from {current_state_enum.value}. Fallback hangup.")
                    await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, "llm_none_clarify_fail")
                    return None

        except asyncio.TimeoutError:
            logger.error(f"[{call_sid}] CM: LLM timed out after {CM_LLM_CALL_TIMEOUT}s.")
            await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, "llm_timeout")
            return None
        except Exception as llm_e:
            logger.error(f"[{call_sid}] CM: LLM Handler error: {llm_e}", exc_info=True)
            await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, f"llm_exception: {type(llm_e).__name__}")
            return None

        if not next_state_obj:
             logger.error(f"[{call_sid}] CM: next_state_obj is None after LLM logic. Fallback hangup.")
             await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, "internal_no_next_state")
             return None

        if not state_machine.validate_and_set_state(next_state_obj):
            logger.warning(f"[{call_sid}] CM: Invalid transition proposed: {current_state_enum.value} -> {next_state_obj.value}. Attempting clarification.")
            valid_transitions = state_machine._VALID_TRANSITIONS.get(current_state_enum, set())
            if ScriptState.ASK_CLARIFICATION in valid_transitions:
                 await self._ask_for_clarification_cm(websocket, state_machine, stream_sid)
            else:
                 logger.error(f"[{call_sid}] CM: Cannot ask for clarification from state {current_state_enum.value} after invalid transition proposal. Fallback hangup.")
                 await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, "invalid_transition_no_clarify")
            return None

        logger.info(f"[{call_sid}] CM: State machine successfully transitioned to: {state_machine.state.value}")

        script_to_load = MM_SCRIPT
        if state_machine.script_type == 'SM' or "_SM" in state_machine.state.value:
            script_to_load = SM_SCRIPT

        new_state_data = None
        try:
            new_state_data = await asyncio.wait_for(
                 load_script_state_data(state_machine.state.name, script_to_load),
                 timeout=CM_SCRIPT_LOAD_TIMEOUT
             )
        except asyncio.TimeoutError:
            logger.error(f"[{call_sid}] CM: Timeout loading script data for state: {state_machine.state.name}")
            await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, "script_load_timeout")
            return None
        except Exception as load_e:
            logger.error(f"[{call_sid}] CM: Error loading script data for state {state_machine.state.name}: {load_e}", exc_info=True)
            await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, "script_load_error")
            return None

        if not new_state_data:
            logger.error(f"[{call_sid}] CM: No script data found for new state: {state_machine.state.name} in {script_to_load}")
            valid_transitions = state_machine._VALID_TRANSITIONS.get(state_machine.state, set())
            if ScriptState.ASK_CLARIFICATION in valid_transitions:
                logger.warning(f"[{call_sid}] CM: Asking clarification because script data was missing for {state_machine.state.name}.")
                await self._ask_for_clarification_cm(websocket, state_machine, stream_sid)
            else:
                 await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, "script_data_not_found")
            return None

        action_str = new_state_data.get("action")
        action = ScriptAction(action_str) if action_str and action_str in ScriptAction._value2member_map_ else ScriptAction.LISTEN

        try:
            if action == ScriptAction.TALK or action_str == "TALK_PAUSE":
                dialogue_template = new_state_data.get("script", "")
                if state_machine.state == ScriptState.ACKNOWLEDGE_OWNER_NAME_AND_GREET and state_machine.owner_name:
                    dialogue_template = f"Ah, {state_machine.owner_name}, thank you."
                    logger.info(f"[{call_sid}] CM: Using dynamic dialogue for {state_machine.state.value}")

                dialogue_to_speak = await self._replace_placeholders_cm(dialogue_template, state_machine)
                if not dialogue_to_speak and action == ScriptAction.TALK :
                     logger.warning(f"[{call_sid}] CM: TALK action for {state_machine.state.value} but no dialogue.")

                logger.info(f"[{call_sid}] CM: Action: {action_str}. Speaking: '{dialogue_to_speak[:70]}...'")
                state_machine.add_history_entry("assistant", dialogue_to_speak)
                await self.tts.send_tts_audio(websocket, dialogue_to_speak, call_sid, stream_sid, hangup_after_speech=False)
                state_machine.in_listen_state = False

            elif action == ScriptAction.LISTEN:
                logger.debug(f"[{call_sid}] Processing LISTEN action for state {state_machine.state.name}.")
                # If there was dialogue for this LISTEN state, speak it first.
                if new_state_data.get("script"):
                    logger.debug(f"[{call_sid}] LISTEN state has dialogue: '{new_state_data['script'][:50]}...'. Attempting TTS.")
                    state_machine.add_history_entry("assistant", new_state_data["script"])
                    try:
                        logger.debug(f"[{call_sid}] Calling self.tts.send_tts_audio NOW...")
                        await self.tts.send_tts_audio(websocket, new_state_data["script"], call_sid, stream_sid)
                        logger.debug(f"[{call_sid}] TTS call completed for LISTEN state dialogue.")
                    except ConnectionClosed:
                        logger.warning(f"[{call_sid}] Connection closed during TTS for LISTEN state.")
                        # Cannot proceed if connection is closed
                        return None # Exit processing for this interaction
                    except Exception as tts_err_listen:
                        logger.error(f"[{call_sid}] Error during TTS for LISTEN state dialogue: {tts_err_listen}", exc_info=True)
                        # Decide if we should still listen or hangup? Let's try listening for now.
                    # After speaking (or attempting to), THEN enter listen state
                    state_machine.in_listen_state = True
                    logger.debug(f"[{call_sid}] Set in_listen_state=True after attempting dialogue for LISTEN state.")
                else:
                    # No dialogue, just listen
                    logger.debug(f"[{call_sid}] LISTEN state has no dialogue.")
                    state_machine.in_listen_state = True
                    logger.debug(f"[{call_sid}] Entering LISTEN state (no dialogue).")

            elif action == ScriptAction.HANGUP or state_machine.state in _COMMON_EXIT_STATES:
                logger.info(f"[{call_sid}] CM: Action HANGUP or terminal state {state_machine.state.value}. Ending call.")
                dialogue_to_speak = await self._replace_placeholders_cm(new_state_data.get("script", CM_FALLBACK_HANGUP_MESSAGE), state_machine)
                state_machine.add_history_entry("assistant", dialogue_to_speak)
                asyncio.create_task(self.tts.send_tts_audio(websocket, dialogue_to_speak, call_sid, stream_sid, hangup_after_speech=True))
                self.csm.end_call(call_sid, final_state=state_machine.state)
                await self._close_websocket_if_open_cm(websocket, call_sid, f"Hangup action/state: {state_machine.state.value}")
                return None

            elif action == ScriptAction.SWITCH_SCRIPT:
                logger.info(f"[{call_sid}] CM: Action: SWITCH_SCRIPT.")
                target_script_file = new_state_data.get("target_script")
                target_state_str = new_state_data.get("target_state")
                if not target_script_file or not target_state_str:
                    logger.error(f"[{call_sid}] CM: SWITCH_SCRIPT misconfig in {state_machine.state.value}.")
                    await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, "switch_script_misconfig")
                    return None
                try:
                    target_state_enum = ScriptState(target_state_str)
                    if "saving_money" in target_script_file: state_machine.script_type = 'SM'
                    elif "making_money" in target_script_file: state_machine.script_type = 'MM'

                    if state_machine.validate_and_set_state(target_state_enum):
                        logger.info(f"[{call_sid}] CM: Switched script. New state: {state_machine.state.value}")
                        await self.handle_call_interaction(websocket, state_machine, stream_sid, "") # Trigger next turn
                    else:
                        logger.error(f"[{call_sid}] CM: Failed to validate switch transition to {target_state_enum.value}.")
                        await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, "switch_target_invalid")
                except ValueError:
                    logger.error(f"[{call_sid}] CM: Invalid target state name '{target_state_str}' in SWITCH_SCRIPT.")
                    await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, "switch_target_bad_name")

            elif action_str and action_str.startswith("CUSTOM_LOGIC_"):
                logger.info(f"[{call_sid}] CM: Action: {action_str}. Assuming LISTEN.")
                state_machine.in_listen_state = True

            else: # Unknown action
                logger.warning(f"[{call_sid}] CM: Unknown action '{action_str}' for {state_machine.state.value}. Defaulting to LISTEN.")
                state_machine.in_listen_state = True

            return next_state_obj

        except Exception as action_e:
             logger.error(f"[{call_sid}] CM: Error executing action {action_str} for state {state_machine.state.value}: {action_e}", exc_info=True)
             await self._handle_fallback_hangup_cm(websocket, state_machine, stream_sid, f"action_execution_error: {type(action_e).__name__}")
             return None

    # --- Utility Methods (If needed within CallManager context) ---

    async def extract_entities(self, text: str) -> Dict[str, Any]:
        """Extracts entities like emails, phone numbers from text."""
        # This is stateless and can remain.
        entities = {}
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails: entities["email"] = emails[0]
        phone_pattern = r'(?:(?:\(?(?:0(?:0|11)\)?[\s-]?\(?|\+?)44\)?[\s-]?(?:\(?0\)?[\s-]?)?)|(?:\(?0))(?:(?:\d{5}\)?[\s-]?\d{4,5})|(?:\d{4}\)?[\s-]?(?:\d{5}|\d{3}[\s-]?\d{3}))|(?:\d{3}\)?[\s-]?\d{3}[\s-]?\d{3,4})|(?:\d{2}\)?[\s-]?\d{4}[\s-]?\d{4}))(?:[\s-]?(?:x|ext\.?|\#)\d{3,4})?'
        phones = re.findall(phone_pattern, text)
        if phones: entities["phone"] = phones[0]
        return entities

    async def get_call_state_machine_details(self, call_sid: str) -> Optional[Dict]:
        """ Get full state machine details for a live call from CSM. """
        state_machine = self.csm.get_call_state(call_sid)
        if state_machine:
            return state_machine.to_dict(include_history_list=True)
        logger.debug(f"CallManager.get_call_state_machine_details: Call {call_sid} not found in CSM.")
        return None

    async def check_health(self) -> Dict:
        """ Checks the health of CallManager's direct dependencies. """
        # This health check focuses on dependencies used by *this* CallManager instance.
        # Health of DialerSystem etc. would be checked separately.
        health = {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "components": {
                "call_manager_logic": "healthy", # This instance is running
                "state_manager": "unknown",
                "llm_handler": "unknown",
                "tts_handler": "unknown",
                # "regulations": "unknown" # Only include if regulations are used by CallManager logic
            },
            "details": {}
        }
        all_healthy = True

        # Check State Manager
        if self.csm:
            health["components"]["state_manager"] = "healthy" # Basic check: instance exists
        else:
            health["components"]["state_manager"] = "unhealthy"
            all_healthy = False
            health["details"]["csm_error"] = "CSM object not injected/found."

        # Check TTS Handler
        if self.tts:
             health["components"]["tts_handler"] = "healthy" # Basic check: instance exists
        else:
            health["components"]["tts_handler"] = "unhealthy"
            all_healthy = False
            health["details"]["tts_error"] = "TTS object not injected/found."

        # Check LLM Handler
        if self.llm and hasattr(self.llm, 'api_key_or_client'):
            try:
                # Simplified test - assumes LLMHandler provides access to client or key
                client_or_key = self.llm.api_key_or_client
                test_client = None
                temp_client = False
                if isinstance(client_or_key, groq.AsyncGroq):
                    test_client = client_or_key
                elif isinstance(client_or_key, str) and client_or_key:
                    test_client = groq.AsyncGroq(api_key=client_or_key, timeout=5.0)
                    temp_client = True

                if test_client:
                    await test_client.chat.completions.create(model="llama3-8b-8192", messages=[{"role": "user", "content": "test"}], max_tokens=1)
                    health["components"]["llm_handler"] = "healthy"
                    if temp_client: await test_client.close()
                else:
                    health["components"]["llm_handler"] = "unhealthy"
                    health["details"]["llm_info"] = "LLM client not configured in LLMHandler."
                    all_healthy = False
            except Exception as e:
                logger.error(f"LLM Health Check Error: {e}", exc_info=False)
                health["components"]["llm_handler"] = "unhealthy"
                health["details"]["llm_error"] = str(e)
                all_healthy = False
        else:
            health["components"]["llm_handler"] = "unhealthy"
            health["details"]["llm_info"] = "LLMHandler not available or not configured."
            all_healthy = False

        # Set overall status
        if not all_healthy:
             is_unhealthy = any(v == "unhealthy" for v in health["components"].values())
             health["status"] = "unhealthy" if is_unhealthy else "degraded"

        return health

    async def cleanup(self):
        """Cleanup resources if CallManager held any directly (unlikely with DI)."""
        logger.info("CallManager cleanup initiated (likely no action needed).")
        # Dependencies (CSM, LLM, TTS) are managed/cleaned up by the main application lifespan
        pass

    async def _process_script_action(self, state_data: Dict[str, Any], state_name: str) -> None:
        """Process the script action for the current state."""
        try:
            action = state_data.get("action")
            if not action:
                logger.error(f"No action found for state {state_name}")
                return

            if action == ScriptAction.LISTEN.value:
                # Set up a more aggressive timeout mechanism for listen states
                listen_timeout = 5  # 5 seconds maximum wait time
                start_time = time.time()
                
                # Create a task for the listen operation
                listen_task = asyncio.create_task(self._handle_listen_state(state_data, state_name))
                
                try:
                    # Wait for either the listen task to complete or timeout
                    await asyncio.wait_for(listen_task, timeout=listen_timeout)
                except asyncio.TimeoutError:
                    logger.warning(f"Listen state {state_name} timed out after {listen_timeout} seconds")
                    # Cancel the listen task immediately
                    listen_task.cancel()
                    try:
                        await listen_task
                    except asyncio.CancelledError:
                        pass
                    
                    # Get the next state from the state data
                    next_states = state_data.get("next_states", [])
                    if next_states:
                        # Use the first next state as fallback
                        next_state = next_states[0]
                        logger.info(f"Timeout in listen state {state_name}, transitioning to {next_state}")
                        await self.transition_to_state(next_state)
                    else:
                        # If no next states defined, transition to hangup
                        logger.error(f"No next states defined for timed out listen state {state_name}, transitioning to hangup")
                        await self.transition_to_state("HANGUP_MM" if self.current_script == "making_money_script.md" else "HANGUP_SM")
                
            elif action == ScriptAction.TALK.value:
                await self._handle_talk_state(state_data, state_name)
            elif action == ScriptAction.HANGUP.value:
                await self._handle_hangup_state(state_data, state_name)
            elif action == "CUSTOM_LOGIC_INITIAL_GREETING":
                await self._handle_initial_greeting(state_data, state_name)
            elif action == "CUSTOM_LOGIC_SWITCH_SCRIPT":
                await self._handle_switch_script(state_data, state_name)
            else:
                logger.warning(f"Unknown action type: {action}")

        except Exception as e:
            logger.error(f"Error processing script action for state {state_name}: {e}", exc_info=True)
            # Ensure we don't get stuck by transitioning to hangup on error
            await self.transition_to_state("HANGUP_MM" if self.current_script == "making_money_script.md" else "HANGUP_SM")

    async def _perform_hangup(self, websocket: WebSocket, state_machine: CallStateMachine, stream_sid: str, reason: str, dialogue: Optional[str] = None):
        """Handles the sequence of speaking a final dialogue (if any) and then hanging up the call."""
        call_sid = state_machine.call_sid
        logger.info(f"[{call_sid}] Performing hangup. Reason: {reason}. Current state: {state_machine.state.name}")

        final_dialogue = dialogue if dialogue else CM_FALLBACK_HANGUP_MESSAGE
        
        # Ensure state is a terminal state or HANGUP variant.
        # If not already a hangup state, try to transition to a generic HANGUP state.
        if state_machine.state not in _COMMON_EXIT_STATES and state_machine.state.name != "HANGUP_MM" and state_machine.state.name != "HANGUP_SM": # etc.
            # Try to find a suitable HANGUP state from the script or default.
            hangup_state_to_set = ScriptState.FALLBACK_HANGUP # Default
            # This logic could be more sophisticated to pick script-specific HANGUP state.
            if state_machine.validate_and_set_state(hangup_state_to_set):
                logger.info(f"[{call_sid}] Transitioned to {hangup_state_to_set.name} before hangup.")
            else:
                logger.warning(f"[{call_sid}] Could not transition to {hangup_state_to_set.name}, state remains {state_machine.state.name}.")
        
        final_state_for_end_call = state_machine.state # Log the state as it is when hangup is performed

        # Add final dialogue to history
        state_machine.add_history_entry("assistant", final_dialogue)
        self.csm.end_call(call_sid, final_state=final_state_for_end_call, status=LeadStatus.COMPLETED) # Or a more specific status

        try:
            # Send TTS with hangup instruction to Twilio
            logger.debug(f"[{call_sid}] Sending final TTS with hangup: '{final_dialogue[:50]}...'")
            # Create a task to ensure it gets a chance to run even if main flow exits
            asyncio.create_task(
                self.tts.send_tts_audio(websocket, final_dialogue, call_sid, stream_sid, hangup_after_speech=True)
            )
        except ConnectionClosed:
            logger.warning(f"[{call_sid}] Connection already closed before sending final hangup TTS for reason: {reason}.")
        except Exception as tts_err:
            logger.error(f"[{call_sid}] Error sending final TTS during hangup ({reason}): {tts_err}", exc_info=True)
            # Even if TTS fails, Twilio should have received a hangup from send_tts_audio if that was attempted.
            # If not, WebSocket closure is the fallback.

        # Give a brief moment for the async TTS+Hangup task to be sent over the WebSocket
        await asyncio.sleep(0.2) # Short delay
        await self._close_websocket_if_open_cm(websocket, call_sid, f"Hangup performed: {reason}, Final State: {final_state_for_end_call.name}")

    async def _handle_listen_state(self, state_data: Dict[str, Any], state_name: str) -> None:
        """Handle a listen state with proper timeout and error handling."""
        try:
            # Get the next states from the state data
            next_states = state_data.get("next_states", [])
            if not next_states:
                logger.error(f"No next states defined for listen state {state_name}")
                await self.transition_to_state("HANGUP_MM" if self.current_script == "making_money_script.md" else "HANGUP_SM")
                return

            # Set up the STT callback
            self.stt_callback_handler.set_current_state(state_name)
            self.stt_callback_handler.set_next_states(next_states)
            
            # Start listening
            await self.stt_handler.start_listening()
            
            # Wait for the STT callback to complete
            await self.stt_callback_handler.wait_for_completion()
            
        except Exception as e:
            logger.error(f"Error in listen state {state_name}: {e}", exc_info=True)
            # Ensure we don't get stuck by transitioning to hangup on error
            await self.transition_to_state("HANGUP_MM" if self.current_script == "making_money_script.md" else "HANGUP_SM")

    async def handle_call_interaction(self, call_sid: str, transcript: str, current_state: ScriptState) -> Optional[ScriptState]:
        """Handle a call interaction, determining the next state based on the transcript."""
        try:
            # Get the state machine for this call
            state_machine = self.csm.get_call_state(call_sid)
            if not state_machine:
                logger.error(f"[{call_sid}] No state machine found for call")
                return None

            # Get the next state from the LLM
            next_state_obj = await asyncio.wait_for(
                self.llm.get_next_state(state_machine, transcript),
                timeout=5.0
            )

            if next_state_obj is None:
                logger.warning(f"[{call_sid}] LLM returned no next state. Attempting recovery...")
                # Try to recover by going back to previous state
                if len(state_machine.state_history) > 1:
                    previous_state = state_machine.state_history[-2][0]  # Get the previous state
                    logger.info(f"[{call_sid}] Recovering by returning to previous state: {previous_state.value}")
                    return previous_state
                else:
                    logger.error(f"[{call_sid}] No previous state available for recovery")
                    return None

            # Validate the next state is in the script
            if not self.script_parser.is_valid_next_state(current_state, next_state_obj):
                logger.warning(f"[{call_sid}] Invalid next state {next_state_obj.value} from {current_state.value}. Attempting recovery...")
                # Try to recover by going back to previous state
                if len(state_machine.state_history) > 1:
                    previous_state = state_machine.state_history[-2][0]  # Get the previous state
                    logger.info(f"[{call_sid}] Recovering by returning to previous state: {previous_state.value}")
                    return previous_state
                else:
                    logger.error(f"[{call_sid}] No previous state available for recovery")
                    return None

            return next_state_obj

        except asyncio.TimeoutError:
            logger.error(f"[{call_sid}] LLM timeout. Attempting recovery...")
            # Try to recover by going back to previous state
            if len(state_machine.state_history) > 1:
                previous_state = state_machine.state_history[-2][0]  # Get the previous state
                logger.info(f"[{call_sid}] Recovering by returning to previous state: {previous_state.value}")
                return previous_state
            else:
                logger.error(f"[{call_sid}] No previous state available for recovery")
                return None
        except Exception as e:
            logger.error(f"[{call_sid}] Error in handle_call_interaction: {str(e)}", exc_info=True)
            # Try to recover by going back to previous state
            if len(state_machine.state_history) > 1:
                previous_state = state_machine.state_history[-2][0]  # Get the previous state
                logger.info(f"[{call_sid}] Recovering by returning to previous state: {previous_state.value}")
                return previous_state
            else:
                logger.error(f"[{call_sid}] No previous state available for recovery")
                return None
