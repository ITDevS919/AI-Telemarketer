"""
Call State Manager for AI Telemarketer

This module provides a robust state management system for tracking
conversation states and supporting persistence across calls.
"""

import json
import time
import asyncio
import logging
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from datetime import datetime, timedelta
# import sqlite3 # REMOVE
# import aiosqlite # REMOVE
import uuid
from collections import deque # <<< ADD deque

# Configure logging
logger = logging.getLogger("call_state_manager")

# --- Define Log File --- 
CALL_LOG_FILE_PATH = "call_logs.txt"

# --- Define NEW conversation states based on script ---
class ScriptState(str, Enum):
    # --- Core States (Common or Entry/Exit) ---
    INITIALIZING = "INITIALIZING" # Before call starts
    # START_MM = "START_MM" # DEPRECATED by INITIAL_GREETING_SEQUENCE
    # START_SM = "START_SM" # DEPRECATED by INITIAL_GREETING_SEQUENCE
    FAREWELL = "FAREWELL" # Common state before final HANGUP
    COMPLETED = "COMPLETED" # Final success state (appointment, wamailer, etc.)
    HANGUP = "HANGUP" # General hangup state
    ERROR_HANDLE = "ERROR_HANDLE" # State for handling unexpected errors
    CALL_ENDED_ABRUPTLY = "CALL_ENDED_ABRUPTLY" # Final state for disconnects etc.

    # --- NEW Initial Greeting Flow States ---
    INITIAL_GREETING_SEQUENCE = auto() # Used by main.py to trigger initial greeting logic
    AWAIT_INITIAL_RESPONSE = auto()    # State after initial greeting, awaiting first user input
    IDENTIFY_SELF_AS_ISAAC = auto()
    AWAIT_RESPONSE_AFTER_ISAAC = auto()
    EXPLAIN_CALL_INTRODUCTORY = auto()
    CONFIRM_OWNER_COMING_TO_PHONE = auto()
    PITCH_INTEREST_TO_GATEKEEPER = auto()
    AWAIT_GATEKEEPER_DECISION_AFTER_PITCH = auto()
    SCHEDULE_CALLBACK_MM = auto()
    SCHEDULE_CALLBACK_SM = auto() # <<< ADD MISSING STATE
    DENY_REQUEST_MM = auto()
    DENY_REQUEST_SM = auto()
    PROVIDE_BUSINESS_DETAILS_MM = auto()
    PROVIDE_BUSINESS_DETAILS_SM = auto()
    REQUEST_CALLBACK_LATER_MM = auto()
    REQUEST_CALLBACK_LATER_SM = auto()
    SCHEDULE_CALLBACK_CONFIRMATION_MM = auto()
    SCHEDULE_CALLBACK_CONFIRMATION_SM = auto()
    HANDLE_OBJECTION_COST_MM = auto()
    HANDLE_OBJECTION_COST_SM = auto()
    HANDLE_OBJECTION_TIME_MM = auto()
    HANDLE_OBJECTION_TIME_SM = auto()
    HANDLE_OBJECTION_NOT_INTERESTED_MM = auto()
    HANDLE_OBJECTION_NOT_INTERESTED_SM = auto()
    HANDLE_GENERAL_QUESTION_MM = auto()
    HANDLE_GENERAL_QUESTION_SM = auto()
    PITCH_BENEFITS_MM = auto()
    PITCH_BENEFITS_SM = auto()
    TRANSITION_TO_CLOSING_MM = auto()
    TRANSITION_TO_CLOSING_SM = auto()
    FINAL_CLOSING_STATEMENT_MM = auto()
    FINAL_CLOSING_STATEMENT_SM = auto()
    POST_SALE_CONFIRMATION_MM = auto()
    POST_SALE_CONFIRMATION_SM = auto()
    HANGUP_COMPLETED_MM = auto()
    HANGUP_COMPLETED_SM = auto()
    HANGUP_NOT_INTERESTED_MM = auto()
    HANGUP_NOT_INTERESTED_SM = auto()
    HANGUP_CALLBACK_SCHEDULED_MM = auto()
    HANGUP_CALLBACK_SCHEDULED_SM = auto()
    HANGUP_DO_NOT_CALL_MM = auto()
    HANGUP_DO_NOT_CALL_SM = auto()
    ASK_CLARIFICATION = auto() # Generic clarification state
    FALLBACK_HANGUP = auto() # Generic hangup due to error/unexpected
    GATEKEEPER_INTRODUCTION_MM = auto()
    GATEKEEPER_INTRODUCTION_SM = auto()
    AWAIT_OWNER_AVAILABILITY_RESPONSE = auto()
    OWNER_ON_PHONE_REINTRODUCE = auto() # MM & SM are similar enough for one state
    AWAIT_OWNER_NAME_RESPONSE = auto()
    ACKNOWLEDGE_OWNER_NAME_AND_GREET = auto()
    PITCH_INTEREST_TO_OWNER = auto()
    AWAIT_POST_INTEREST_PITCH_RESPONSE = auto()
    HANGUP_MAX_REPEATS = auto() # <<< Add new HANGUP state for max repeat timeout

    # --- Script Switching States ---
    SCRIPT_SELECTION_MM = "SCRIPT_SELECTION_MM"
    REDIRECT_TO_SAVING = "REDIRECT_TO_SAVING"
    SWITCH_TO_SAVING_SCRIPT = "SWITCH_TO_SAVING_SCRIPT"
    SCRIPT_SELECTION_SM = "SCRIPT_SELECTION_SM"
    REDIRECT_TO_MAKING_MONEY = "REDIRECT_TO_MAKING_MONEY"
    SWITCH_TO_MAKING_SCRIPT = "SWITCH_TO_MAKING_SCRIPT"
    GREETING_RESPONSE_MM = "GREETING_RESPONSE_MM"
    GREETING_RESPONSE_SM = "GREETING_RESPONSE_SM"

    # --- Making Money Script States (v1.2) ---
    GATEKEEPER_DETECTED_MM = "GATEKEEPER_DETECTED_MM"
    CALLBACK_REQUESTED_MM = "CALLBACK_REQUESTED_MM"
    DECLINE_MM = "DECLINE_MM"
    INTRO_PROACTIV_MM = "INTRO_PROACTIV_MM"
    INTRO_RESPONSE_MM = "INTRO_RESPONSE_MM" # Added new state for script flow
    BUSINESS_DISCOVERY_MM = "BUSINESS_DISCOVERY_MM" # Added state for business discovery
    BUSINESS_RESPONSE_MM = "BUSINESS_RESPONSE_MM" # Added state for response to business info
    CLARIFICATION_MM = "CLARIFICATION_MM" # Added new state for handling "What's this about?"
    CLARIFICATION_RESPONSE_MM = "CLARIFICATION_RESPONSE_MM" # Added state for response after clarification
    HANGUP_MM = "HANGUP_MM"
    PRE_CLOSE_INTEREST_MM = "PRE_CLOSE_INTEREST_MM"
    PITCH_APPOINTMENT_MM = "PITCH_APPOINTMENT_MM"
    HANDLE_OBJECTION_MM = "HANDLE_OBJECTION_MM"
    NOT_INTERESTED_MM = "NOT_INTERESTED_MM"
    BOOK_APPOINTMENT_MM = "BOOK_APPOINTMENT_MM"
    PITCH_WAMAILER_MM = "PITCH_WAMAILER_MM"
    HANDLE_OBJECTION_BUSY_NOW_MM = "HANDLE_OBJECTION_BUSY_NOW_MM"
    HANDLE_OBJECTION_BUSY_BUSINESS_MM = "HANDLE_OBJECTION_BUSY_BUSINESS_MM"
    HANDLE_OBJECTION_BUSY_APPOINTMENT_MM = "HANDLE_OBJECTION_BUSY_APPOINTMENT_MM"
    HANDLE_OBJECTION_NI_MM = "HANDLE_OBJECTION_NI_MM"
    HANGUP_NI_MM = "HANGUP_NI_MM"
    PRE_CLOSE_APPOINTMENT_MM = "PRE_CLOSE_APPOINTMENT_MM"
    CONFIRM_APPOINTMENT_MM = "CONFIRM_APPOINTMENT_MM"
    GET_WAMAILER_DETAILS_MM = "GET_WAMAILER_DETAILS_MM"
    PITCH_EMAILER_MM = "PITCH_EMAILER_MM"
    CONFIRM_WAMAILER_MM = "CONFIRM_WAMAILER_MM"
    GET_EMAIL_DETAILS_MM = "GET_EMAIL_DETAILS_MM"
    CONFIRM_EMAILER_MM = "CONFIRM_EMAILER_MM"
    CONFIRM_CALLBACK_MM = "CONFIRM_CALLBACK_MM"
    ERROR_STATE_MM = "ERROR_STATE_MM" # Script-specific error state

    # --- Saving Money Script States (v1.2) ---
    GATEKEEPER_DETECTED_SM = "GATEKEEPER_DETECTED_SM"
    CALLBACK_REQUESTED_SM = "CALLBACK_REQUESTED_SM"
    DECLINE_SM = "DECLINE_SM"
    INTRO_PROACTIV_SM = "INTRO_PROACTIV_SM"
    INTRO_RESPONSE_SM = "INTRO_RESPONSE_SM" # Added for consistency with MM flow
    BUSINESS_DISCOVERY_SM = "BUSINESS_DISCOVERY_SM" # Added for business type discovery
    BUSINESS_RESPONSE_SM = "BUSINESS_RESPONSE_SM" # Added response to business info
    CLARIFICATION_SM = "CLARIFICATION_SM" # Added for clarity questions
    CLARIFICATION_RESPONSE_SM = "CLARIFICATION_RESPONSE_SM" # Added for responses
    HANGUP_SM = "HANGUP_SM"
    PRE_CLOSE_SAVING_SM = "PRE_CLOSE_SAVING_SM"
    PITCH_APPOINTMENT_SM = "PITCH_APPOINTMENT_SM"
    HANDLE_OBJECTION_SM = "HANDLE_OBJECTION_SM"
    NOT_INTERESTED_SM = "NOT_INTERESTED_SM"
    BOOK_APPOINTMENT_SM = "BOOK_APPOINTMENT_SM"
    PITCH_WAMAILER_SM = "PITCH_WAMAILER_SM"
    HANDLE_OBJECTION_BUSY_NOW_SM = "HANDLE_OBJECTION_BUSY_NOW_SM"
    HANDLE_OBJECTION_BUSY_BUSINESS_SM = "HANDLE_OBJECTION_BUSY_BUSINESS_SM"
    HANDLE_OBJECTION_BUSY_APPOINTMENT_SM = "HANDLE_OBJECTION_BUSY_APPOINTMENT_SM"
    HANDLE_OBJECTION_NI_SM = "HANDLE_OBJECTION_NI_SM"
    HANGUP_NI_SM = "HANGUP_NI_SM"
    PRE_CLOSE_APPOINTMENT_SM = "PRE_CLOSE_APPOINTMENT_SM"
    CONFIRM_APPOINTMENT_SM = "CONFIRM_APPOINTMENT_SM"
    GET_WAMAILER_DETAILS_SM = "GET_WAMAILER_DETAILS_SM"
    PITCH_EMAILER_SM = "PITCH_EMAILER_SM"
    CONFIRM_WAMAILER_SM = "CONFIRM_WAMAILER_SM"
    GET_EMAIL_DETAILS_SM = "GET_EMAIL_DETAILS_SM"
    CONFIRM_EMAILER_SM = "CONFIRM_EMAILER_SM"
    CONFIRM_CALLBACK_SM = "CONFIRM_CALLBACK_SM"
    ERROR_STATE_SM = "ERROR_STATE_SM" # Script-specific error state

    # --- New Greeting Flow States (Post Initial "Yes") ---
    CONFIRM_IF_SPEAKER_IS_OWNER = auto() # AI asks "Are you the owner?" and listens
    ACKNOWLEDGE_GETTING_OWNER = auto()   # AI says "Okay, I'll wait" if user is getting owner

    # --- Saving Money Script Specific States (prefix with SM_) ---
    INITIAL_GREETING_SM = auto()

# --- Define _COMMON_EXIT_STATES at module level --- 
_COMMON_EXIT_STATES = {
    ScriptState.HANGUP_COMPLETED_MM, ScriptState.HANGUP_COMPLETED_SM,
    ScriptState.HANGUP_NOT_INTERESTED_MM, ScriptState.HANGUP_NOT_INTERESTED_SM,
    ScriptState.HANGUP_CALLBACK_SCHEDULED_MM, ScriptState.HANGUP_CALLBACK_SCHEDULED_SM,
    ScriptState.HANGUP_DO_NOT_CALL_MM, ScriptState.HANGUP_DO_NOT_CALL_SM,
    ScriptState.FALLBACK_HANGUP, ScriptState.COMPLETED, ScriptState.CALL_ENDED_ABRUPTLY,
    ScriptState.HANGUP_MM, ScriptState.HANGUP_SM,
    ScriptState.HANGUP_MAX_REPEATS
}

# --- ADD LeadStatus Enum --- (Keep Enums at module level)
class LeadStatus(str, Enum):
    APPOINTMENT_BOOKED = "appointment_booked"
    INFO_REQUESTED_WHATSAPP = "info_requested_whatsapp"
    INFO_REQUESTED_EMAIL = "info_requested_email"
    CALLBACK_SCHEDULED = "callback_scheduled"
    NOT_INTERESTED = "not_interested"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    COMPLETED_OTHER = "completed_other" # For calls that finish without a specific lead outcome
    UNKNOWN = "unknown" # Default or if status cannot be determined
    # Add any other specific lead statuses your application might track

# --- ADD ScriptAction Enum --- 
class ScriptAction(str, Enum):
    TALK = "TALK"     # AI should speak
    TALK_PAUSE = "TALK_PAUSE" # AI speaks then expects user to continue (functionally like TALK)
    LISTEN = "LISTEN" # AI should wait for user input
    HANGUP = "HANGUP" # AI should end the call
    SWITCH_SCRIPT = "SWITCH_SCRIPT" # Switch between making money and saving money scripts
    # Add other actions if needed later (e.g., TRANSFER, PLAY_AUDIO)
# --- End ADD --- 

# (Keep ConversationEvent for now, might be useful for logging or specific triggers)
class ConversationEvent(str, Enum):
    CALL_CONNECTED = "call_connected"
    USER_SPEECH_DETECTED = "user_speech_detected" # Replaces USER_RESPONSE
    LLM_RESPONSE_GENERATED = "llm_response_generated"
    LLM_STATE_SUGGESTED = "llm_state_suggested"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    STATE_TRANSITION_VALID = "state_transition_valid"
    STATE_TRANSITION_INVALID = "state_transition_invalid"
    APPOINTMENT_BOOKED = "appointment_booked"
    END_CALL_REQUESTED = "end_call_requested"
    CALL_TERMINATED = "call_terminated"
    ERROR_OCCURRED = "error_occurred"

class CallStateMachine:
    """State machine for tracking the state of a conversation in a call"""
    
    # Use INITIALIZING as a fallback initial state
    def __init__(self, call_sid: str, initial_state: ScriptState = ScriptState.INITIALIZING):
        """Initialize state machine for a call"""
        self.call_sid = call_sid
        self.state = initial_state 
        self.history = []  # Conversation history [{"speaker": "user|assistant", "text": "..."}]
        self.state_history = [(initial_state, time.time())]  # Track state changes with timestamps [(state1, time1), ...]
        self.last_update_time = time.time()
        self.data = {}  # For storing any data attached to this call
        self.call_start_time = time.time()
        
        # For Twilio integration
        self.twilio_call_sid = None  # The Twilio call SID, if available
        self.requires_hangup = False  # Flag to indicate if call should be hung up
        
        # These are typically set by initial_data in create_call_state
        self.script_type = None  # "MM" or "SM"
        self.is_outbound = True  # Default to outbound
        self.is_transferred = False 
        self.to_number = None
        self.from_number = None
        # self.business_type = None # OLD, replaced by more specific business_category
        self.agent_name = "Isaac"  # Default agent name
        self.client_name = "Proactiv"  # Default client
        self.qualifiers = { 
            "s": False, "m": False, "r": False, "x": False
        }
        
        # --- NEW Fields for script data ---
        self.owner_first_name: Optional[str] = None # Parsed first name of the owner
        self.owner_full_name: Optional[str] = None  # Full name if provided
        self.business_category: Optional[str] = None # From CSV or input
        self.gatekeeper_interaction_count: int = 0 # To track gatekeeper interactions
        self.owner_name_confirmed_by_user: bool = False # If user confirms AI's attempt at owner name
        self.owner_on_phone: bool = False # Flag if owner is confirmed to be on the line

        self.owner_name: Optional[str] = None # User-provided owner name if different
        self.gatekeeper_name: Optional[str] = None
        self.qualifiers_met: Dict[str, bool] = {} # e.g., {"A": True, "F": False}
        self.highlighted_problem: Optional[str] = None # e.g., "A"
        self.appointment_time: Optional[str] = None # Store as ISO string or similar
        self.contact_mobile: Optional[str] = None
        self.contact_email: Optional[str] = None
        self.additional_decision_makers: Optional[str] = None
        self.recording_url: Optional[str] = None # ADDED for Twilio recording
        # --- End NEW Fields ---
        
        # --- NEW Lead Generation Fields ---
        self.appointment_booked_time: Optional[str] = None # ISO format timestamp
        self.contact_mobile_collected: Optional[str] = None
        self.contact_email_collected: Optional[str] = None
        self.lead_status: Optional[str] = None # e.g., 'appointment_booked', 'wamailer_sent', ...
        # --- End Lead Generation Fields ---
        
        # --- Dialer Queue Link --- 
        self.queue_id: Optional[int] = None # Link to the dial_queue table ID
        # --- End Dialer Queue Link --- 
        
        # --- NEW: Store Script Context --- 
        self.lock = asyncio.Lock() # <<< ADD Lock for this specific state machine
        self.in_listen_state = False  # Track if we're in a LISTEN state
        self.initial_data = {}  # Initialize initial_data
        self.log_events: List[str] = []  # Add this line to store log events

    def to_dict(self, include_history_list: bool = False) -> Dict[str, Any]:
        """Convert state machine to a dictionary for storage or API response."""
        data = {
            "call_sid": self.call_sid,
            "state": self.state.value, 
            "start_time": self.call_start_time,
            "last_update_time": self.last_update_time,
            "is_outbound": self.is_outbound,
            "script_type": self.script_type,
            "from_number": self.from_number,
            "to_number": self.to_number,
            "duration": self.last_update_time - self.call_start_time,
            # "business_type": self.business_type, # OLD
            "owner_first_name": self.owner_first_name,
            "owner_full_name": self.owner_full_name,
            "business_category": self.business_category,
            "gatekeeper_interaction_count": self.gatekeeper_interaction_count,
            "owner_name_confirmed_by_user": self.owner_name_confirmed_by_user,
            "owner_on_phone": self.owner_on_phone,
            "owner_name": self.owner_name, # This is the one AI might ask for
            "gatekeeper_name": self.gatekeeper_name,
            "agent_name": self.agent_name,
            "client_name": self.client_name,
            "qualifiers_met": self.qualifiers_met,
            "highlighted_problem": self.highlighted_problem,
            "appointment_time": self.appointment_time,
            "contact_mobile": self.contact_mobile,
            "contact_email": self.contact_email,
            "additional_decision_makers": self.additional_decision_makers,
            "recording_url": self.recording_url,
            "appointment_booked_time": self.appointment_booked_time,
            "contact_mobile_collected": self.contact_mobile_collected,
            "contact_email_collected": self.contact_email_collected,
            "lead_status": self.lead_status,
            "queue_id": self.queue_id,
            "log_events": self.log_events  # Add this line to include log events
        }
        # Optionally include the raw history list for API responses
        if include_history_list:
             data['history'] = self.history # <<< Add raw list if requested
        else:
             data['history_preview'] = [f"{h['speaker']}: {h['text'][:30]}..." for h in self.history[-3:]] # Example preview
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CallStateMachine':
        """Create a state machine from a dictionary"""
        # Use INITIALIZING as default if state is missing or invalid
        initial_state = ScriptState.INITIALIZING # Start with initializing
        try:
            # Ensure inner quotes are different from outer f-string quotes
            initial_state = ScriptState(data.get("state", ScriptState.INITIALIZING.value))
        except ValueError:
            logger.warning(f"Invalid state value '{data.get('state')}' found in DB for call {data.get('call_sid', '?')}. Defaulting to INITIALIZING.")
            
        state_machine = cls(data["call_sid"], initial_state=initial_state)
        state_machine.call_start_time = data.get("start_time", time.time())
        state_machine.last_update_time = data.get("last_update_time", time.time())
        # Load history safely
        try:
            state_machine.history = json.loads(data.get("history", "[]"))
        except (json.JSONDecodeError, TypeError):
             logger.warning(f"Failed to load history JSON for call {data.get('call_sid', '?')}. Resetting history.")
             state_machine.history = []
        state_machine.is_outbound = data.get("is_outbound", True)
        state_machine.script_type = data.get("script_type")
        state_machine.from_number = data.get("from_number")
        state_machine.to_number = data.get("to_number")
        # Load qualifiers safely (handle both JSON string and raw dict)
        qualifiers_data = data.get("qualifiers_met", {})
        if isinstance(qualifiers_data, str):
            try:
                state_machine.qualifiers_met = json.loads(qualifiers_data)
            except (json.JSONDecodeError, TypeError):
                 logger.warning(f"Failed to load qualifiers_met JSON for call {data.get('call_sid', '?')}. Resetting qualifiers.")
                 state_machine.qualifiers_met = {}
        elif isinstance(qualifiers_data, dict):
             state_machine.qualifiers_met = qualifiers_data # Assume it's the correct dict
        else:
             logger.warning(f"Unexpected type for qualifiers_met: {type(qualifiers_data)}. Resetting qualifiers.")
             state_machine.qualifiers_met = {}
        state_machine.highlighted_problem = data.get("highlighted_problem")
        state_machine.appointment_time = data.get("appointment_time")
        state_machine.contact_mobile = data.get("contact_mobile")
        state_machine.contact_email = data.get("contact_email")
        state_machine.additional_decision_makers = data.get("additional_decision_makers")
        state_machine.recording_url = data.get("recording_url")
        state_machine.appointment_booked_time = data.get("appointment_booked_time")
        state_machine.contact_mobile_collected = data.get("contact_mobile_collected")
        state_machine.contact_email_collected = data.get("contact_email_collected")
        state_machine.lead_status = data.get("lead_status")
        state_machine.queue_id = data.get("queue_id")
        # Ensure new fields are loaded from data if present
        state_machine.owner_first_name = data.get("owner_first_name")
        state_machine.owner_full_name = data.get("owner_full_name")
        state_machine.business_category = data.get("business_category")
        state_machine.gatekeeper_interaction_count = data.get("gatekeeper_interaction_count", 0)
        state_machine.owner_name_confirmed_by_user = data.get("owner_name_confirmed_by_user", False)
        state_machine.owner_on_phone = data.get("owner_on_phone", False)
        return state_machine
    
    def add_history_entry(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Adds an entry to the conversation history."""
        entry = {"role": role, "content": content, "timestamp": datetime.utcnow().isoformat()}
        if metadata:
            entry["metadata"] = metadata
        self.history.append(entry)
        logger.debug(f"[{self.call_sid}] History entry added: {{'role': '{role}', 'content': '{content[:50]}...'}}")

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Returns the full conversation history."""
        return self.history

    def update_lead_status(self, status: LeadStatus) -> None:
        """Updates the lead status for the call."""
        # ... existing code ...

    # --- Implement NEW transition logic --- 
    def validate_and_set_state(self, suggested_next_state_enum: Optional[ScriptState]) -> bool:
        """
        Sets the state machine to the suggested next state without validation.
        The validation (checking if LLM's choice is in script's Next States)
        should happen *before* calling this method.

        Args:
            suggested_next_state_enum: The suggested next state as a ScriptState enum member.
                                      Assumed to be valid by the caller.

        Returns:
            True if state was changed (i.e., suggested_next_state_enum was not None), False otherwise.
        """
        # If None provided, this is a no-op
        if suggested_next_state_enum is None:
            logger.debug(f"[{self.call_sid}] validate_and_set_state received None. No state change.")
            return False
            
        # Ensure it's an enum member (basic type check)
        if not isinstance(suggested_next_state_enum, ScriptState):
            logger.error(f"[{self.call_sid}] Invalid type passed to validate_and_set_state: {type(suggested_next_state_enum)}. Expected ScriptState.")
            return False
            
        current_state = self.state
        self.state = suggested_next_state_enum
        self.state_history.append((suggested_next_state_enum, time.time()))
        self.last_update_time = time.time()
        
        # Optional: Hangup logic can remain if useful, but might be better handled in CallManager
        # Check if this is a definitive terminal state requiring hangup
        # if self.is_definitive_terminal_state(suggested_next_state_enum):
        #     # Flag this call for immediate hangup
        #     self.requires_hangup = True
        #     logger.info(f"Call {self.call_sid} marked for hangup due to terminal state: {suggested_next_state_enum.value}")
            # Twilio hangup logic removed - should be handled by CallManager after state transition
            
        logger.info(f"State transitioned for call {self.call_sid}: {current_state.value} -> {suggested_next_state_enum.value}")
        return True

    # --- NEW Methods to update data --- 
    def set_data_field(self, field_name: str, value: Any):
        """Sets a specific data field if it exists."""
        if hasattr(self, field_name):
            setattr(self, field_name, value)
            self.last_update_time = time.time()
            logger.debug(f"Set {field_name}={value} for call {self.call_sid}")
        else:
            logger.warning(f"Attempted to set non-existent field '{field_name}' on CallStateMachine for {self.call_sid}")

    def set_qualifier(self, qualifier_letter: str, value: bool):
        """Sets a specific qualifier result."""
        if qualifier_letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
            self.qualifiers_met[qualifier_letter.upper()] = value
            self.last_update_time = time.time()
            logger.debug(f"Set qualifier {qualifier_letter}={value} for call {self.call_sid}")
        else:
            logger.warning(f"Invalid qualifier letter '{qualifier_letter}' provided for call {self.call_sid}")
    # --- End NEW Methods ---

    def is_definitive_terminal_state(self, state: ScriptState = None) -> bool:
        """
        Determine if the given state (or current state if None) is a definitive terminal state
        where the call should be immediately hung up.
        
        Args:
            state: The state to check, or current state if None
            
        Returns:
            True if this is a definitive terminal state requiring immediate hangup
        """
        if state is None:
            state = self.state
            
        # These are states where we're absolutely confident the user has no interest
        # and continuing the call would be pointless or inappropriate
        definitive_terminal_states = {
            # Common terminal states
            ScriptState.HANGUP,
            ScriptState.CALL_ENDED_ABRUPTLY,
            
            # Making Money script terminal states
            ScriptState.HANGUP_MM,
            ScriptState.HANGUP_NI_MM,
            ScriptState.NOT_INTERESTED_MM,
            ScriptState.DECLINE_MM,
            
            # Saving Money script terminal states
            ScriptState.HANGUP_SM,
            ScriptState.HANGUP_NI_SM,
            ScriptState.NOT_INTERESTED_SM,
            ScriptState.DECLINE_SM,
        }
        
        return state in definitive_terminal_states

    def set_twilio_call_sid(self, twilio_call_sid: str):
        """
        Set the Twilio call SID associated with this call.
        This enables automatic hangup for terminal states.
        
        Args:
            twilio_call_sid: The Twilio call SID
        """
        self.twilio_call_sid = twilio_call_sid
        logger.info(f"Set Twilio call SID {twilio_call_sid} for call {self.call_sid}")

    def is_terminal_state(self) -> bool:
        """Check if the current state is a terminal/exit state."""
        return self.state in _COMMON_EXIT_STATES

    def add_log_event(self, event: str):
        self.log_events.append(f"[{datetime.now().isoformat()}] {event}")
        logger.debug(f"[{self.call_sid}] {event}")

class CallStateManager:
    """Manages call states and an IN-MEMORY dial queue."""

    def __init__(self, db_path: str = "telemarketer_calls.db"): # Keep db_path arg for now, though unused
        """Initialize the CallStateManager for in-memory storage and queue."""
        self.state_machines: Dict[str, CallStateMachine] = {} # In-memory call state storage
        self.dial_queue: deque[Dict[str, Any]] = deque() # <<< ADD In-memory queue
        self.queue_lock = asyncio.Lock() # <<< ADD Lock for queue operations
        logger.info("CallStateManager initialized for IN-MEMORY operation with in-memory queue.")

    async def load_states(self):
        """Load call states from storage (in-memory mode, no-op function).
        This method is a placeholder for compatibility with the CallManager which expects it.
        In this in-memory implementation, there are no states to load from persistent storage.
        """
        logger.info("load_states called - no persistent states to load in IN-MEMORY mode")
        return True

    async def set_call_state(self, call_sid: str, state_data: Dict[str, Any]) -> bool:
        """Set the state for a call in memory.
        This is a compatibility method for the CallManager.
        
        Args:
            call_sid: The call SID to update
            state_data: Dictionary containing state data
            
        Returns:
            True if successful
        """
        logger.debug(f"[CSM-MEM][{call_sid}] Setting call state in memory")
        # Create or update a CallStateMachine object in memory
        if call_sid in self.state_machines:
            # Updating existing state machine - would need conversion logic if necessary
            # For now, just store as a separate dictionary for compatibility
            self.state_machines[call_sid] = state_data
        else:
            # Create new state entry
            self.state_machines[call_sid] = state_data
            
        return True
        
    async def get_all_call_states(self) -> Dict[str, Dict[str, Any]]:
        """Get all call states from memory.
        This is a compatibility method for the CallManager.
        
        Returns:
            Dictionary of call states indexed by call_sid
        """
        logger.debug("Getting all call states from memory")
        return self.state_machines

    async def save_states(self):
        """Save call states to persistent storage.
        This is a placeholder for compatibility with the CallManager.
        In the in-memory implementation, there is no persistent storage.
        """
        logger.info("save_states called - no persistent storage in IN-MEMORY mode")
        return True

    # --- REMOVE DB METHODS --- 
    # async def _setup_database_schema(self):
    #     ...
    # async def ensure_db_ready_and_get_conn(self) -> Optional[aiosqlite.Connection]:
    #     ...

    # --- State Methods (Remain Mostly Sync, No DB) --- 
    def get_call_state(self, call_sid: str) -> Optional[CallStateMachine]: # REMOVE async
        """Get the state machine for a call from memory"""
        logger.debug(f"[CSM-MEM][{call_sid}] Getting call state from memory.")
        return self.state_machines.get(call_sid)

    def create_call_state(self, call_sid: str, initial_data: Dict[str, Any]) -> CallStateMachine: # REMOVE async, REMOVE queue_id param
        """Create a new state machine for a call in memory.
        Initial data should contain phone_number, business_type (category), owner_name, etc.
        """
        if call_sid in self.state_machines:
            logger.warning(f"[CSM-MEM][{call_sid}] Attempted to create state for already active call.")
            return self.state_machines[call_sid]
            
        # New entry point
        initial_script_state = ScriptState.INITIAL_GREETING_SEQUENCE 
        
        state_machine = CallStateMachine(call_sid, initial_state=initial_script_state)
        state_machine.initial_data = initial_data # Store initial data

        # Apply initial data (keep this part)
        state_machine.is_outbound = initial_data.get('is_outbound', True)
        
        # Determine script_type based on business_type or other initial_data if needed later.
        # For now, it might be set after the initial interaction.
        # Or, if 'business_type' from CSV still implies MM/SM, use that.
        business_type_indicator = initial_data.get('business_type') # This is old 'script selector'
        if business_type_indicator == '(s)':
            state_machine.script_type = 'SM'
        elif business_type_indicator: # Any other non-empty means MM
            state_machine.script_type = 'MM'
        else: # Default or if not provided
            state_machine.script_type = 'MM' # Default to MM or handle as needed

        state_machine.from_number = initial_data.get('from_number', '')
        state_machine.to_number = initial_data.get('to_number', '')
        state_machine.agent_name = initial_data.get('agent_name', 'Isaac') # Set default here
        state_machine.client_name = initial_data.get('client_name', 'Proactiv') # Set default here
        
        # New fields
        raw_owner_name = initial_data.get('owner_name') # e.g., "John Smith" or "John"
        if raw_owner_name:
            state_machine.owner_full_name = raw_owner_name
            state_machine.owner_first_name = raw_owner_name.split(' ')[0] # Simple first name parsing
        
        state_machine.business_category = initial_data.get('business_category') # Specific category like "Restaurant", "Garage"

        self.state_machines[call_sid] = state_machine
        logger.info(f"[CSM-MEM][{call_sid}] Created new in-memory call state for {state_machine.to_number}. Initial state: {initial_script_state.name}. Owner: {state_machine.owner_first_name}, Category: {state_machine.business_category}")
        return state_machine

    # --- REMOVE save_call_state --- 
    # async def save_call_state(self, call_sid: str) -> bool:
    #     ...

    def end_call(self, call_sid: str, final_state: ScriptState = ScriptState.CALL_ENDED_ABRUPTLY) -> bool: # REMOVE async
        """Mark a call as ended in memory and log outcome to file."""
        state_machine = self.state_machines.get(call_sid)
        
        if state_machine:
            # Update fields on the in-memory object (keep this)
            state_machine.state = final_state 
            state_machine.duration = time.time() - state_machine.call_start_time
            state_machine.last_update_time = time.time()
            
            # --- Map final_state to lead_status (keep this) --- 
            if final_state in {ScriptState.CONFIRM_APPOINTMENT_MM, ScriptState.CONFIRM_APPOINTMENT_SM}:
                 state_machine.lead_status = 'appointment_booked'
                 state_machine.appointment_booked_time = datetime.now().isoformat() # Record booking time
            elif final_state in {ScriptState.CONFIRM_WAMAILER_MM, ScriptState.CONFIRM_WAMAILER_SM}:
                 state_machine.lead_status = 'info_requested_whatsapp'
            elif final_state in {ScriptState.CONFIRM_EMAILER_MM, ScriptState.CONFIRM_EMAILER_SM}:
                 state_machine.lead_status = 'info_requested_email'
            elif final_state in {ScriptState.CONFIRM_CALLBACK_MM, ScriptState.CONFIRM_CALLBACK_SM, ScriptState.CALLBACK_REQUESTED_MM, ScriptState.CALLBACK_REQUESTED_SM}:
                 state_machine.lead_status = 'callback_scheduled' # Or 'callback_requested'?
            elif final_state in {ScriptState.NOT_INTERESTED_MM, ScriptState.NOT_INTERESTED_SM, 
                                   ScriptState.DECLINE_MM, ScriptState.DECLINE_SM, 
                                   ScriptState.HANGUP_NI_MM, ScriptState.HANGUP_NI_SM}:
                 state_machine.lead_status = 'not_interested'
            elif final_state == ScriptState.CALL_ENDED_ABRUPTLY:
                 state_machine.lead_status = 'disconnected'
            elif final_state in {ScriptState.ERROR_STATE_MM, ScriptState.ERROR_STATE_SM, ScriptState.ERROR_HANDLE}:
                 state_machine.lead_status = 'error'
            elif final_state in {ScriptState.HANGUP, ScriptState.HANGUP_MM, ScriptState.HANGUP_SM, ScriptState.FAREWELL}:
                 # If no specific outcome achieved, mark as generic completion
                 if not state_machine.lead_status: # Avoid overwriting if a lead status was set earlier potentially
                     state_machine.lead_status = 'completed_other'
            else:
                 # Default for unhandled final states, check if status already exists
                 if not state_machine.lead_status:
                      state_machine.lead_status = 'unknown'
            # --- End Mapping ---
            
            log_message = f"Call Ended: SID={call_sid}, Start={datetime.fromtimestamp(state_machine.call_start_time)}, End={datetime.fromtimestamp(state_machine.last_update_time)}, Duration={state_machine.duration:.2f}s, FinalState={final_state.value}, LeadStatus={state_machine.lead_status}\n"
            # Corrected history log formatting
            history_log_entries = []
            for entry in state_machine.history:
                try:
                    # Ensure timestamp is a string and parseable
                    ts_str = entry.get('timestamp')
                    if isinstance(ts_str, str):
                        dt_obj = datetime.fromisoformat(ts_str)
                        formatted_ts = dt_obj.strftime('%H:%M:%S') # Format time as H:M:S
                    else:
                        formatted_ts = "InvalidTimestamp"
                    
                    role = entry.get('role', 'UnknownRole')
                    content = entry.get('content', 'NoContent')
                    history_log_entries.append(f"  [{formatted_ts}] {role}: {content}")
                except Exception as e_hist:
                    history_log_entries.append(f"  [ErrorFormattingHistoryEntry: {e_hist}]")
            history_log = "\n".join(history_log_entries)

            full_log = log_message + history_log + "\n" + "-"*20 + "\n"

            # --- Log to File --- 
            try:
                with open(CALL_LOG_FILE_PATH, "a") as f:
                    f.write(full_log)
                logger.info(f"[CSM-MEM][{call_sid}] Logged outcome to {CALL_LOG_FILE_PATH}")
            except Exception as e:
                logger.error(f"[CSM-MEM][{call_sid}] FAILED to log outcome to file: {e}", exc_info=True)
            # --- End Log to File --- 

            logger.info(f"[CSM-MEM][{call_sid}] Ending call. Final state {final_state.value}. Lead Status: {state_machine.lead_status}. Duration: {state_machine.duration:.2f}s")
            
            # Remove from active memory
            if call_sid in self.state_machines:
                 del self.state_machines[call_sid]
                 logger.debug(f"[CSM-MEM][{call_sid}] Removed state machine from memory.")
            return True
        else:
            logger.warning(f"[CSM-MEM][{call_sid}] Attempted to end inactive call.")
            return False

    # --- Rate Limiting / Number History Methods (REMAIN REMOVED) ---
    # async def record_call_attempt(...)
    # async def get_recent_calls_to_number(...)
    
    # --- update_call_data (Remains Sync, In-Memory) --- 
    def update_call_data(self, call_sid: str, updates: Dict[str, Any]): # REMOVE async
        """Updates specific data fields for an active call in memory."""
        if call_sid in self.state_machines:
            state_machine = self.state_machines[call_sid]
            updated = False
            for key, value in updates.items():
                if hasattr(state_machine, key):
                    setattr(state_machine, key, value)
                    updated = True
                else:
                    logger.warning(f"[CSM-MEM][{call_sid}] Attempted to update non-existent field '{key}'")
            
            if updated:
                state_machine.last_update_time = time.time()
            return updated
        else:
            logger.warning(f"[CSM-MEM][{call_sid}] Cannot update data for inactive call")
            return False
            
    # --- Dashboard Methods (Remain Sync, In-Memory) ---
    def get_recent_calls(self, limit: int = 50, offset: int = 0) -> List[Dict]: # REMOVE async
        """Retrieves recent calls (IN-MEMORY ONLY - NOT PERSISTENT)."""
        # This will only show calls active *during this server run*. Probably not useful.
        logger.warning("get_recent_calls called in IN-MEMORY mode. Result is not persistent.")
        # Return basic info from active state machines if needed, but it's ephemeral
        # Example: return [sm.to_dict() for sm in list(self.state_machines.values())[-limit:]]
        return [] # Return empty for now

    def get_call_details(self, call_sid: str) -> Optional[Dict]: # REMOVE async
        """Retrieves details for a specific ACTIVE call_sid (IN-MEMORY ONLY)."""
        logger.warning("get_call_details called in IN-MEMORY mode. Result is not persistent.")
        state_machine = self.state_machines.get(call_sid)
        if state_machine:
            # Convert history back for display if needed
            data = state_machine.to_dict()
            if 'history' in data: data['history'] = state_machine.history # Use actual list
            if 'qualifiers_met' in data: data['qualifiers_met'] = state_machine.qualifiers_met # Use actual dict
            return data
        return None
        
    # --- Sync Methods (REMAIN REMOVED) --- 
    # def get_call_state_sync(...)
    # def create_call_state_sync(...)
    # def save_call_state_sync(...)
    # def end_call_sync(...)

    # --- Dialer Queue Methods (IMPLEMENT IN-MEMORY) ---
    
    async def add_to_dial_queue(self, calls: List[Dict[str, str]]) -> int:
        """Adds a list of call requests to the IN-MEMORY dial queue."""
        added_count = 0
        async with self.queue_lock:
            for call_request in calls:
                phone_number = call_request.get('phone_number')
                business_type = call_request.get('business_type')
                if phone_number and business_type:
                    # Check for duplicates (simple check by phone number in current queue)
                    if any(item['phone_number'] == phone_number for item in self.dial_queue):
                        logger.warning(f"[CSM-QUEUE] Skipped adding duplicate number to in-memory queue: {phone_number}")
                        continue
                    
                    queue_item = {
                        'unique_id': str(uuid.uuid4()),
                        'phone_number': phone_number,
                        'business_type': business_type,
                        'status': 'pending',
                        'added_at': time.time(),
                        'last_attempt_at': None,
                        'retry_count': 0,
                        'call_sid': None # To be added when dialing starts
                    }
                    self.dial_queue.append(queue_item)
                    added_count += 1
                    logger.debug(f"[CSM-QUEUE] Added {phone_number} ({business_type}) to in-memory queue.")
                else:
                    logger.warning(f"[CSM-QUEUE] Skipping call request due to missing phone_number or business_type: {call_request}")
                    
        logger.info(f"[CSM-QUEUE] Attempted to add {len(calls)} calls, {added_count} added to in-memory queue (Size: {len(self.dial_queue)})." )
        return added_count

    async def get_next_call_to_dial(self) -> Optional[Dict]:
        """Retrieves the next 'pending' call from the IN-MEMORY queue (FIFO).
        Does NOT handle retries currently - simple FIFO.
        Returns None if no pending calls are found.
        """
        async with self.queue_lock:
            # Find the first pending item
            for i, item in enumerate(self.dial_queue):
                if item['status'] == 'pending':
                    # Return a copy to avoid modification issues outside the lock
                    logger.debug(f"[CSM-QUEUE] Found pending call in queue: ID {item['unique_id']}, Num {item['phone_number']}")
                    return item.copy()
            
            # If no pending calls found after iterating
            logger.debug("[CSM-QUEUE] No pending calls found in the in-memory queue.")
            return None 

    async def update_queue_status(self, unique_id: str, status: str, call_sid: Optional[str] = None, last_attempt_at: Optional[float] = None, increment_retry: bool = False) -> bool:
        """Updates the status and optionally other fields for a specific item in the IN-MEMORY queue, identified by unique_id.
        Removes completed/failed calls from the queue.
        Returns True if update was successful, False otherwise.
        """
        async with self.queue_lock:
            found_item = None
            item_index = -1
            for i, item in enumerate(self.dial_queue):
                if item['unique_id'] == unique_id:
                    found_item = item
                    item_index = i
                    break
            
            if not found_item:
                logger.warning(f"[CSM-QUEUE] Cannot update status: Item with unique_id {unique_id} not found in queue.")
                return False
                
            # Update fields
            found_item['status'] = status
            current_time = time.time()
            if last_attempt_at is None:
                 last_attempt_at = current_time
            found_item['last_attempt_at'] = last_attempt_at
            
            if call_sid:
                 found_item['call_sid'] = call_sid
                 
            if increment_retry:
                found_item['retry_count'] += 1
                
            logger.debug(f"[CSM-QUEUE] Updated item {unique_id} status to '{status}'. CallSid: {call_sid}, RetryInc: {increment_retry}")
            
            # --- Remove terminal states from queue --- 
            if status in {'completed', 'failed', 'blocked_cooldown'}: # Add any other terminal statuses
                try:
                     del self.dial_queue[item_index]
                     logger.info(f"[CSM-QUEUE] Removed item {unique_id} (Status: {status}) from in-memory queue. New Size: {len(self.dial_queue)}")
                except IndexError:
                    logger.error(f"[CSM-QUEUE] Error removing item at index {item_index} (ID: {unique_id}). Queue may have changed unexpectedly.")
                    # Item might have been removed by another operation between finding and deleting
                    return False # Indicate potential issue

            return True # Indicate successful update (or removal)

    async def get_active_dialing_count(self) -> int:
        """Counts the number of calls currently in 'dialing' status in the IN-MEMORY queue."""
        count = 0
        async with self.queue_lock:
             count = sum(1 for item in self.dial_queue if item['status'] == 'dialing')
        # logger.debug(f"[CSM-QUEUE] Active dialing count in in-memory queue: {count}") # Can be noisy
        return count

    # --- NEW: Method to get queue contents (for potential frontend display) --- 
    async def get_queue_snapshot(self) -> List[Dict]:
         """Returns a snapshot (list of copies) of the current in-memory dial queue."""
         async with self.queue_lock:
              # Return list of copies to prevent external modification
              return [item.copy() for item in self.dial_queue]

    async def transition_call_state(self, call_sid: str, new_state: ScriptState) -> bool:
        """
        Transition a call to a new state.
        
        Args:
            call_sid: The call SID to transition
            new_state: The new state to transition to
            
        Returns:
            True if transition was successful, False otherwise
        """
        state_machine = self.state_machines.get(call_sid)
        if not state_machine:
            logger.warning(f"[CSM-MEM][{call_sid}] Cannot transition state: Call not found")
            return False
            
        # Validate and set the new state
        success = state_machine.validate_and_set_state(new_state)
        if success:
            logger.info(f"[CSM-MEM][{call_sid}] Successfully transitioned to state: {new_state.value}")
        else:
            logger.warning(f"[CSM-MEM][{call_sid}] Failed to transition to state: {new_state.value}")
            
        return success