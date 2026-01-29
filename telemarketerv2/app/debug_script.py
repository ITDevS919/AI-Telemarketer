"""
Debug Script Flow Tool

This script allows you to test the telemarketer's script flow without making actual calls.
It simulates user responses and checks if the LLM correctly follows the script states.
"""

import asyncio
import logging
import json
import uuid
import time
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
import datetime

from call_state_manager import CallStateManager, CallStateMachine, ScriptState, ScriptAction
from script_parser import load_script_state_data, MAKING_MONEY_SCRIPT_FILENAME, SAVING_MONEY_SCRIPT_FILENAME
from llm_handler import LLMHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("debug_script")

class ScriptDebugger:
    """Interactive debugger for script flow testing"""
    
    def __init__(self, script_type: str = "MM"):
        """
        Initialize script debugger
        
        Args:
            script_type: "MM" for Making Money script or "SM" for Saving Money script
        """
        self.script_type = script_type
        self.call_state_manager = CallStateManager()
        self.llm_handler = None  # Will be initialized when run
        self.conversation_history = []
        self.state_machine = None
        self.call_sid = f"debug-{uuid.uuid4()}"
        
    async def initialize(self):
        """Initialize components needed for debugging"""
        # No need to check for groq_client here as we'll mock responses if needed
        from groq import AsyncGroq
        import os
        
        # Get GROQ API key from environment or prompt user
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            groq_api_key = input("Enter your GROQ API key: ")
            if not groq_api_key:
                logger.error("No GROQ API key provided. Exiting.")
                return False
        
        try:
            groq_client = AsyncGroq(api_key=groq_api_key)
            self.llm_handler = LLMHandler(groq_client=groq_client)
            logger.info("LLM handler initialized.")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize LLM handler: {e}")
            return False
            
    async def create_debug_call(self):
        """Create a debug call session"""
        initial_state = ScriptState.START_MM if self.script_type == "MM" else ScriptState.START_SM
        
        # Create initial data
        initial_data = {
            "is_outbound": True,
            "to_number": "+447123456789",  # Fake number for testing
            "from_number": "+441234567890",  # Fake number for testing
            "business_type": "(m)" if self.script_type == "MM" else "(s)",
            "agent_name": "Isaac",
            "client_name": "Proactiv"
        }
        
        # Create call state
        self.state_machine = self.call_state_manager.create_call_state(
            self.call_sid, initial_data
        )
        
        # Set a mock Twilio call SID for testing the hangup functionality
        mock_twilio_call_sid = f"CA{self.call_sid.split('-')[0]}"
        self.state_machine.set_twilio_call_sid(mock_twilio_call_sid)
        
        logger.info(f"Created debug call with SID: {self.call_sid}")
        logger.info(f"Initial state: {self.state_machine.state.value}")
        
        # Load initial script dialogue
        script_filename = MAKING_MONEY_SCRIPT_FILENAME if self.script_type == "MM" else SAVING_MONEY_SCRIPT_FILENAME
        state_data = await load_script_state_data(self.state_machine.state.value, script_filename)
        if state_data and "script" in state_data:
            dialogue = state_data["script"]
            self.state_machine.add_history_entry("assistant", dialogue)
            self.print_dialogue("Assistant", dialogue)
        else:
            logger.error(f"Failed to load initial script for state: {self.state_machine.state.value}")
            
        return True
            
    def print_dialogue(self, speaker: str, text: str):
        """Print dialogue with formatting"""
        if speaker.lower() == "assistant":
            print(f"\n🤖 {speaker}: {text}\n")
        else:
            print(f"\n👤 {speaker}: {text}\n")
            
    def print_state_info(self):
        """Print current state information"""
        if not self.state_machine:
            return
            
        state = self.state_machine.state
        print("\n" + "="*80)
        print(f"CURRENT STATE: {state.value}")
        
        # Try to load state data to show next possible states
        asyncio.create_task(self._print_state_data(state.value))
        print("="*80 + "\n")
        
    async def _print_state_data(self, state_value: str):
        """Print state data information"""
        script_filename = MAKING_MONEY_SCRIPT_FILENAME if self.script_type == "MM" else SAVING_MONEY_SCRIPT_FILENAME
        state_data = await load_script_state_data(state_value, script_filename)
        if state_data:
            if "next_states" in state_data:
                next_states = state_data["next_states"]
                # Extract state names, handling both string format and tuple format
                state_names = []
                for next_state in next_states:
                    if isinstance(next_state, str):
                        state_names.append(next_state)
                    elif isinstance(next_state, (list, tuple)) and len(next_state) >= 1:
                        state_names.append(next_state[0])
                
                if state_names:
                    print(f"POSSIBLE NEXT STATES: {', '.join(state_names)}")
                else:
                    print("POSSIBLE NEXT STATES: None (Terminal State)")
            else:
                print("POSSIBLE NEXT STATES: None (Terminal State)")
                
            if "action" in state_data:
                print(f"EXPECTED ACTION: {state_data['action']}")
        
    async def process_user_input(self, user_input: str):
        """Process user input and advance the script flow"""
        if not self.state_machine:
            logger.error("No active debug call. Please create one first.")
            return False
            
        # Add user input to history
        self.state_machine.add_history_entry("user", user_input)
        
        # Get current state and latest messages for LLM context
        current_state = self.state_machine.state
        history = self.state_machine.history
        
        # Get state data to get valid next states
        script_filename = MAKING_MONEY_SCRIPT_FILENAME if self.script_type == "MM" else SAVING_MONEY_SCRIPT_FILENAME
        state_data = await load_script_state_data(current_state.value, script_filename)
        next_states = state_data.get("next_states", []) if state_data else []
        
        # Log valid next states - handle both string format and tuple format
        valid_next_states = []
        for next_state in next_states:
            if isinstance(next_state, str):
                valid_next_states.append(next_state)
            elif isinstance(next_state, (list, tuple)) and len(next_state) >= 1:
                valid_next_states.append(next_state[0])
        
        logger.info(f"Valid next states from script: {valid_next_states}")
        
        # Check if we're in a terminal state (no valid next states)
        is_terminal_state = len(valid_next_states) == 0
        if is_terminal_state:
            logger.info(f"Current state {current_state.value} is a terminal state with no transitions")
        
        # Check if the current state is a definitive terminal state requiring hangup
        is_definitive_terminal = self.state_machine.is_definitive_terminal_state()
        
        # Get LLM response
        logger.info(f"Getting LLM response for state: {current_state.value}")
        try:
            result = await self.llm_handler.generate_script_response(
                current_state=self.state_machine.state.value,
                conversation_history=history,
                is_outbound=True,
                agent_name=self.state_machine.agent_name or "Isaac",
                client_name=self.state_machine.client_name or "Proactiv",
                script_type=self.script_type,
                valid_next_states=valid_next_states  # Pass valid next states to LLM
            )
        except Exception as e:
            logger.error(f"Error getting LLM response: {e}", exc_info=True)
            return False
        
        if not result:
            logger.error("Failed to get LLM response")
            return False
            
        # Extract response components
        response_text = result.get("response", "")
        next_state = result.get("next_state")
        action = result.get("action")
        
        # Update state machine if not in terminal state
        if next_state and not is_terminal_state:
            logger.info(f"LLM suggested next state: {next_state}")
            state_changed = self.state_machine.validate_and_set_state(next_state)
            if state_changed:
                logger.info(f"State changed to: {self.state_machine.state.value}")
            else:
                logger.warning(f"Invalid state transition suggested: {next_state}")
        elif next_state and is_terminal_state:
            logger.warning(f"LLM suggested state {next_state} for terminal state {current_state.value} - ignoring")
            
        # Add assistant response to history
        self.state_machine.add_history_entry("assistant", response_text)
        self.print_dialogue("Assistant", response_text)
        
        self.print_state_info()
        
        # If this is a terminal state with action=HANGUP, inform the user
        if is_terminal_state and state_data and state_data.get("action") == "ScriptAction.HANGUP":
            print("\n🔔 This is a terminal state with HANGUP action. In a real call, the system would now terminate the call.")
            print("You can continue the conversation for testing purposes, but in production this call would have ended.")
        
        # If this is a definitive terminal state, simulate Twilio hangup
        if is_definitive_terminal:
            print("\n🔴 This is a DEFINITIVE terminal state. The system will AUTOMATICALLY hang up the call.")
            print("The conversation is now over.")
            # In a real system, this would trigger twilio_integration.hang_up_call()
            if self.state_machine.requires_hangup:
                print("Call has been marked for hangup.")
            
            # Ask if the user wants to continue or exit
            exit_choice = input("\nWould you like to exit the debug session? (y/n): ")
            if exit_choice.lower() in ['y', 'yes']:
                print("Exiting debug session...")
                return False
        
        return True
    
    async def run_debug_session(self):
        """Run an interactive debug session"""
        print("\n===== TELEMARKETER SCRIPT DEBUGGER =====")
        print(f"Testing {self.script_type} script flow.")
        print("Type 'exit' to quit, 'state' to see current state, 'history' to see the conversation.\n")
        
        if not await self.initialize():
            return
            
        if not await self.create_debug_call():
            return
            
        self.print_state_info()
        
        while True:
            try:
                user_input = input("\nYour response ('exit' to quit): ")
                
                if user_input.lower() == 'exit':
                    break
                elif user_input.lower() == 'state':
                    self.print_state_info()
                    continue
                elif user_input.lower() == 'history':
                    print("\n----- CONVERSATION HISTORY -----")
                    for entry in self.state_machine.history:
                        speaker = entry.get("speaker", "unknown")
                        text = entry.get("text", "")
                        print(f"{speaker.capitalize()}: {text}")
                    print("---------------------------------\n")
                    continue
                    
                await self.process_user_input(user_input)
                
            except KeyboardInterrupt:
                print("\nExiting debug session...")
                break
            except Exception as e:
                logger.error(f"Error in debug session: {e}", exc_info=True)
                
        print("\nDebug session ended.")

async def main():
    """Main entry point for script debugger"""
    print("Select script type to debug:")
    print("1. Making Money Script (MM)")
    print("2. Saving Money Script (SM)")
    
    choice = input("Enter choice (1/2): ")
    script_type = "MM" if choice == "1" else "SM"
    
    debugger = ScriptDebugger(script_type=script_type)
    await debugger.run_debug_session()

if __name__ == "__main__":
    asyncio.run(main()) 