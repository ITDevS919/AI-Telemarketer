"""
Utility for parsing the telemarketer script file.
"""

import logging
import os
import re # Added re for parsing next states
import asyncio # Add asyncio import
from typing import Optional, List, Dict, Any, Union

# Assuming ScriptState and ScriptAction are defined elsewhere and accessible
# We might need to adjust imports based on actual structure
from .call_state_manager import ScriptState, ScriptAction

logger = logging.getLogger(__name__)

# Define base path for scripts relative to this file
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'scripts')

# Define default filenames
MAKING_MONEY_SCRIPT_FILENAME = 'making_money_script.md'
SAVING_MONEY_SCRIPT_FILENAME = 'saving_money_script.md'

def _get_script_path(script_filename: str) -> str:
    """Constructs the full path to a script file."""
    return os.path.join(SCRIPTS_DIR, script_filename)

def _parse_action(action_str: str) -> Optional[str]: # Return string for now, handle enum later if needed
    """Parse an action string. Returns uppercase string or None if invalid."""
    if not action_str:
        return ScriptAction.LISTEN.value # Default to LISTEN value
        
    # Strip comments first (anything after #)
    action_str_cleaned = action_str.split('#', 1)[0].strip().upper()
    
    # Check against ScriptAction enum values
    valid_actions = {action.value for action in ScriptAction}
    # Allow custom actions starting with CUSTOM_LOGIC_
    if action_str_cleaned in valid_actions or action_str_cleaned.startswith("CUSTOM_LOGIC_"):
        return action_str_cleaned
    else:
        # Log the original action_str for clarity if it was cleaned
        original_if_different = f" (original: '{action_str}')" if action_str_cleaned != action_str.strip().upper() else ""
        logging.warning(f"Unknown action: '{action_str_cleaned}'{original_if_different}, defaulting to LISTEN")
        return ScriptAction.LISTEN.value

# --- Original Synchronous Function (for use with to_thread) ---
def _load_script_state_data_sync(state_name: str, script_filename: str) -> Optional[Dict[str, Any]]:
    script_path = _get_script_path(script_filename)
    logger.debug(f"Attempting to load data for state '{state_name}' from '{script_path}'")

    if not os.path.exists(script_path):
        logger.error(f"Script file not found at path: {script_path}")
        return None

    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            in_target_state = False
            state_data: Dict[str, Any] = {
                "script": None,  # Default dialogue
                "dialogue_with_name": None,  # Specific dialogue if name exists
                "dialogue_no_name": None,  # Specific dialogue if no name exists
                "action": None,
                "description": None,
                "next_states": [],
                "target_script": None,  # For SWITCH_SCRIPT
                "target_state": None,  # For SWITCH_SCRIPT
                "keywords": {}  # For keyword-based fallback {next_state: [kw1, kw2]}
            }
            state_marker = f"# STATE: {state_name}"
            dialogue_prefix = "Dialogue:"
            dialogue_w_name_prefix = "Dialogue_with_name:"
            dialogue_no_name_prefix = "Dialogue_no_name:"
            action_prefix = "Action:"
            description_prefix = "Description:"
            next_states_prefix = "Next States:"
            target_script_prefix = "Target Script:"
            target_state_prefix = "Target State:"
            keywords_prefix = "Keywords:"

            dialogue_lines: List[str] = []
            current_parsing_key = None  # Changed: Don't default to "script"

            for line in f:
                stripped_line = line.strip()

                if in_target_state:
                    if stripped_line.startswith("# STATE:") or stripped_line == "---":
                        break  # End of current state block

                    # Skip comment lines
                    if stripped_line.startswith("#"):
                        continue

                    # Handle different prefixes
                    if stripped_line.startswith(dialogue_w_name_prefix):
                        state_data["dialogue_with_name"] = stripped_line[len(dialogue_w_name_prefix):].strip()
                        dialogue_lines = []
                        current_parsing_key = None
                    elif stripped_line.startswith(dialogue_no_name_prefix):
                        state_data["dialogue_no_name"] = stripped_line[len(dialogue_no_name_prefix):].strip()
                        dialogue_lines = []
                        current_parsing_key = None
                    elif stripped_line.startswith(dialogue_prefix):
                        content = stripped_line[len(dialogue_prefix):].strip()
                        if content:
                            state_data["script"] = content
                            dialogue_lines = []
                            current_parsing_key = None
                        else:
                            dialogue_lines = []
                            current_parsing_key = "script"
                    elif stripped_line.startswith(action_prefix):
                        action_str = stripped_line[len(action_prefix):].strip()
                        state_data["action"] = _parse_action(action_str)
                        dialogue_lines = []
                        current_parsing_key = None
                    elif stripped_line.startswith(description_prefix):
                        state_data["description"] = stripped_line[len(description_prefix):].strip()
                        dialogue_lines = []
                        current_parsing_key = None
                    elif stripped_line.startswith(next_states_prefix):
                        states_str = stripped_line[len(next_states_prefix):].strip()
                        state_data["next_states"] = [s.strip().upper() for s in states_str.split(',') if s.strip()]
                        dialogue_lines = []
                        current_parsing_key = None
                    elif stripped_line.startswith(target_script_prefix):
                        state_data["target_script"] = stripped_line[len(target_script_prefix):].strip()
                        dialogue_lines = []
                        current_parsing_key = None
                    elif stripped_line.startswith(target_state_prefix):
                        state_data["target_state"] = stripped_line[len(target_state_prefix):].strip().upper()
                        dialogue_lines = []
                        current_parsing_key = None
                    elif stripped_line.startswith(keywords_prefix):
                        kw_data_str = stripped_line[len(keywords_prefix):].strip()
                        pairs = kw_data_str.split(';')
                        for pair in pairs:
                            if '=' in pair:
                                next_state_key, kws = pair.split('=', 1)
                                next_state_key = next_state_key.strip().upper()
                                kw_list = [k.strip().lower() for k in kws.split(',') if k.strip()]
                                if next_state_key and kw_list:
                                    state_data["keywords"][next_state_key] = kw_list
                        dialogue_lines = []
                        current_parsing_key = None
                    # Handle multi-line default dialogue ONLY if we're explicitly in dialogue mode
                    elif current_parsing_key == "script" and stripped_line:
                        dialogue_lines.append(stripped_line)

                elif stripped_line == state_marker:
                    in_target_state = True
                    logger.debug(f"Found state marker: {state_marker}")

            # Finalize default dialogue string
            if dialogue_lines:
                state_data["script"] = " ".join(dialogue_lines)

            # Post-processing and validation
            if in_target_state:
                if state_data["action"] is None:
                    state_data["action"] = ScriptAction.LISTEN.value
                    logger.debug(f"No Action found for state '{state_name}', defaulting to LISTEN")

                # Ensure LISTEN states have a next state
                if state_data["action"] == ScriptAction.LISTEN.value and not state_data["next_states"]:
                    logger.error(f"LISTEN state '{state_name}' has no next states defined!")
                    state_data["next_states"] = ["HANGUP_MM" if "making_money" in script_filename.lower() else "HANGUP_SM"]

                # Log warnings for missing dialogue
                if state_data["action"] == "CUSTOM_LOGIC_INITIAL_GREETING" and (not state_data["dialogue_with_name"] or not state_data["dialogue_no_name"]):
                    logger.warning(f"State '{state_name}' has CUSTOM_LOGIC_INITIAL_GREETING action but is missing Dialogue_with_name or Dialogue_no_name.")
                elif state_data["action"] != "CUSTOM_LOGIC_INITIAL_GREETING" and not state_data["script"] and state_data["action"] != ScriptAction.HANGUP.value:
                    logger.warning(f"No default 'Dialogue:' found for non-hangup/non-custom state '{state_name}'. This state might not speak.")

                logger.debug(f"Loaded data for state '{state_name}': {state_data}")
                return state_data
            else:
                logger.warning(f"State marker '{state_marker}' not found in script: {script_path}")
                return None

    except Exception as e:
        logger.error(f"Error reading or parsing script file {script_path} for state '{state_name}': {e}", exc_info=True)
        return None

# --- New Async Wrapper Function ---
async def load_script_state_data(state_name: str, script_filename: str) -> Optional[Dict[str, Any]]:
    """Asynchronously loads script state data using a thread to avoid blocking."""
    try:
        # Convert state_name (string) to ScriptState enum member
        # Use ScriptState[state_name] for lookup by name, which is more robust
        # than ScriptState(state_name) which looks up by value.
        try:
            state_enum = ScriptState[state_name]
        except KeyError:
            # This will happen if state_name is not a valid member name of ScriptState
            logger.warning(f"State name '{state_name}' is not a valid member of ScriptState enum.")
            # Handle potentially non-enum state names if necessary, or log warning
            # For now, let's assume if it's not in the enum, we can't process it further for special HANGUP logic.
            state_enum = None 


        # Special handling for generic HANGUP state based on script context
        # Ensure state_enum is not None before checking its value
        if state_enum and state_enum == ScriptState.HANGUP:
            effective_state_name = state_name # Keep original
            if "making_money" in script_filename.lower() and ScriptState.HANGUP_MM.value in ScriptState.__members__:
                effective_state_name = ScriptState.HANGUP_MM.value
            elif "saving_money" in script_filename.lower() and ScriptState.HANGUP_SM.value in ScriptState.__members__:
                effective_state_name = ScriptState.HANGUP_SM.value
            
            if effective_state_name != state_name:
                 logger.debug(f"Remapping generic HANGUP state to {effective_state_name} based on script {script_filename}")
                 state_name = effective_state_name
            else:
                 # If no specific hangup state exists, return a generic one
                 logger.debug(f"No specific hangup state for script {script_filename}, using generic hangup data.")
                 return {
                    "script": "Thank you for your time. Goodbye.",
                    "action": ScriptAction.HANGUP.value,
                    "next_states": [], "keywords": {}
                 }

        return await asyncio.to_thread(_load_script_state_data_sync, state_name, script_filename)
    except Exception as e:
        logger.error(f"Error running _load_script_state_data_sync in thread for state '{state_name}': {e}", exc_info=True)
        return None # Return None on error

# Example Usage (can be run directly for testing)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Create dummy script files for testing
    DUMMY_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'scripts')
    os.makedirs(DUMMY_SCRIPTS_DIR, exist_ok=True)
    dummy_script_filename = 'dummy_test_script.md'
    dummy_script_path = os.path.join(DUMMY_SCRIPTS_DIR, dummy_script_filename)

    script_content = """
# STATE: START

Dialogue: Hello there!
Action: LISTEN
Next States: INTRO, DECLINE

---\n\n# STATE: INTRO\n\nDialogue: This is the introduction.\nIt can span multiple lines.\nAction: TALK\nNext States: QUALIFY, NOT_INTERESTED\n\n---\n\n# STATE: QUALIFY\n\nDialogue: Are you qualified?\nAction: LISTEN\nNext States: BOOK, OBJECTION\n\n---\n\n# STATE: NO_ACTION_STATE\n\nDialogue: Something happens here.\nNext States: END\n\n---\n\n# STATE: NO_DIALOGUE_STATE\n\nAction: HANGUP\nNext States: \n\n"""
    with open(dummy_script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)

    print(f"--- Testing with {dummy_script_filename} ---")

    test_state_1 = "START"
    data_1 = asyncio.run(load_script_state_data(test_state_1, dummy_script_filename))
    print(f"Data for '{test_state_1}': {data_1}")

    test_state_2 = "INTRO"
    data_2 = asyncio.run(load_script_state_data(test_state_2, dummy_script_filename))
    print(f"Data for '{test_state_2}': {data_2}")

    test_state_3 = "NON_EXISTENT_STATE"
    data_3 = asyncio.run(load_script_state_data(test_state_3, dummy_script_filename))
    print(f"Data for '{test_state_3}': {data_3}")

    test_state_4 = "NO_ACTION_STATE" # State missing Action
    data_4 = asyncio.run(load_script_state_data(test_state_4, dummy_script_filename))
    print(f"Data for '{test_state_4}': {data_4}")

    test_state_5 = "NO_DIALOGUE_STATE" # State missing Dialogue
    data_5 = asyncio.run(load_script_state_data(test_state_5, dummy_script_filename))
    print(f"Data for '{test_state_5}': {data_5}")

    # Clean up dummy file
    # os.remove(dummy_script_path)
    print("--- Test Complete --- Remember to manually remove dummy_test_script.md if needed ---")

    # Add new test cases
    test_states = [
        ("PAUSE_CALL_SM", SAVING_MONEY_SCRIPT_FILENAME)
    ]

    async def run_tests():
        for state, filename in test_states:
            print(f"--- Testing State: {state} ({filename}) ---")
            data = await load_script_state_data(state, filename) # Use await now
            print(f"Data: {data}\n")

    asyncio.run(run_tests()) # Run tests asynchronously 