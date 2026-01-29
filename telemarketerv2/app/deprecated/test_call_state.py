#!/usr/bin/env python3
"""
Test script for the Call State Manager integration with the LLM Handler.
This script tests the interaction between the Call State Manager and the LLM Handler,
using a simplified approach to simulate a telemarketing call.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("test_call_state")

# Determine the root directory and add it to the path
current_dir = Path(__file__).resolve().parent
if current_dir not in sys.path:
    sys.path.append(str(current_dir))

# Import necessary modules
from llm_handler import LLMHandler
from call_state_manager import CallStateManager, CallStateMachine, ScriptState, ScriptAction

# Constants for script files
SCRIPT_DIR = current_dir.parent / "data" / "scripts"
MAKING_MONEY_SCRIPT_FILENAME = SCRIPT_DIR / "making_money_script.md"
SAVING_MONEY_SCRIPT_FILENAME = SCRIPT_DIR / "saving_money_script.md"

# Make sure the GROQ API key is set
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable not set. This is required for LLM integration.")

class CallStateManagerTest:
    def __init__(self, script_type="making_money"):
        """Initialize the test with the specified script type."""
        self.script_type = "MM" if script_type == "making_money" else "SM"
        self.script_filename = MAKING_MONEY_SCRIPT_FILENAME if self.script_type == "MM" else SAVING_MONEY_SCRIPT_FILENAME
        self.state_manager = None
        self.state_machine = None
        self.llm_handler = None
    
    async def initialize(self):
        """Initialize the call state manager and LLM handler."""
        logger.info("Initializing Call State Manager Test...")
        
        try:
            # Import Groq client here to avoid import errors if the package isn't installed
            from groq import AsyncGroq
            
            # Initialize Groq client
            groq_api_key = os.environ.get("GROQ_API_KEY")
            if not groq_api_key:
                raise ValueError("GROQ_API_KEY environment variable not set")
            
            groq_client = AsyncGroq(api_key=groq_api_key)
            
            # Initialize LLM Handler with the Groq client
            self.llm_handler = LLMHandler(groq_client=groq_client)
            
            # Initialize State Manager
            self.state_manager = CallStateManager()
            
            # Create a new state machine for this test
            call_id = f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create a state machine directly
            initial_data = {
                "script_type": self.script_type,
                "phone_number": "+441234567890",  # Test UK number
                "agent_name": "TestAgent",
                "client_name": "TestClient"
            }
            self.state_machine = self.state_manager.create_call_state(call_id, initial_data)
            
            logger.info(f"Created state machine for call {call_id} with initial state {self.state_machine.state.value}")
            self.print_state_info()
            
            return True
        except ImportError as e:
            logger.error(f"Failed to import required packages: {e}")
            return False
        except Exception as e:
            logger.error(f"Error initializing Call State Manager Test: {e}")
            return False
    
    def print_state_info(self):
        """Print information about the current state."""
        if not self.state_machine:
            logger.error("No state machine available")
            return
            
        current_state = self.state_machine.state
        logger.info(f"Current State: {current_state.value}")
        
        # Get possible next states from the _VALID_TRANSITIONS dictionary
        # Instead of trying to transition, we'll just check what's valid
        if hasattr(self.state_machine, '_VALID_TRANSITIONS'):
            next_states = self.state_machine._VALID_TRANSITIONS.get(current_state, set())
            if next_states:
                logger.info("Possible next states:")
                for next_state in next_states:
                    logger.info(f"  - {next_state.value}")
            else:
                logger.info("No valid next states available (terminal state)")
        else:
            logger.warning("Cannot determine valid next states: _VALID_TRANSITIONS not accessible")
    
    def print_dialogue(self, speaker, text):
        """Format and print dialogue."""
        print(f"\n[{speaker}]: {text}\n")
    
    async def process_user_input(self, user_input):
        """Process user input and advance the state machine."""
        if not self.state_machine or not self.llm_handler:
            logger.error("State machine or LLM handler not initialized")
            return False
            
        # Add user input to history
        self.state_machine.add_history_entry("user", user_input)
        self.print_dialogue("User", user_input)
        
        # Get current state info
        current_state = self.state_machine.state
        history = self.state_machine.history
        
        # Get valid next states from the _VALID_TRANSITIONS dictionary
        valid_next_states = []
        if hasattr(self.state_machine, '_VALID_TRANSITIONS'):
            next_states = self.state_machine._VALID_TRANSITIONS.get(current_state, set())
            for state in next_states:
                valid_next_states.append(state.value)
        else:
            logger.warning("Cannot determine valid next states: _VALID_TRANSITIONS not accessible")
        
        logger.info(f"Valid next states: {valid_next_states}")
        
        try:
            # Generate response using LLM
            result = await self.llm_handler.generate_script_response(
                current_state=current_state.value,
                conversation_history=history,
                script_type=self.script_type,
                valid_next_states=valid_next_states
            )
            
            if not result:
                logger.error("Failed to get LLM response")
                return False
                
            # Extract response components
            response_text = result.get("response", "")
            next_state = result.get("next_state")
            
            # Add assistant response to history
            self.state_machine.add_history_entry("assistant", response_text)
            self.print_dialogue("Assistant", response_text)
            
            # Update state if valid
            if next_state and next_state in valid_next_states:
                logger.info(f"Transitioning to state: {next_state}")
                state_changed = self.state_machine.validate_and_set_state(next_state)
                if state_changed:
                    logger.info(f"State changed to: {self.state_machine.state.value}")
                else:
                    logger.warning(f"Failed to transition to {next_state}")
            else:
                logger.warning(f"Invalid next state: {next_state}. Valid states are: {valid_next_states}")
            
            self.print_state_info()
            return True
        except Exception as e:
            logger.error(f"Error processing user input: {str(e)}", exc_info=True)
            return False
    
    async def run_test(self):
        """Run an interactive test session."""
        try:
            success = await self.initialize()
            if not success:
                logger.error("Failed to initialize test")
                return
                
            print("\n=== Call State Manager Test ===")
            print("Enter 'q' or 'quit' to exit")
            print("Enter 'h' or 'help' for commands")
            print("Enter 'history' to see conversation history")
            print("Enter 'state' to see current state info")
            print("Any other input will be treated as user dialogue\n")
            
            while True:
                user_input = input("\nYour response > ").strip()
                
                if user_input.lower() in ['q', 'quit', 'exit']:
                    print("Exiting test...")
                    break
                elif user_input.lower() in ['h', 'help']:
                    print("\nCommands:")
                    print("  q, quit, exit - Exit the test")
                    print("  h, help - Show this help message")
                    print("  history - Show conversation history")
                    print("  state - Show current state information")
                elif user_input.lower() == 'history':
                    print("\n----- CONVERSATION HISTORY -----")
                    for entry in self.state_machine.history:
                        speaker = entry.get("speaker", "unknown")
                        text = entry.get("text", "")
                        print(f"[{speaker}]: {text}")
                    print("--------------------------------\n")
                elif user_input.lower() == 'state':
                    self.print_state_info()
                else:
                    await self.process_user_input(user_input)
                    
        except KeyboardInterrupt:
            print("\nTest interrupted by user.")
        except Exception as e:
            logger.error(f"Error in test: {str(e)}", exc_info=True)
        finally:
            # No cleanup needed
            logger.info("Test completed.")

async def main():
    """Main entry point for the test script."""
    # Get script type from command line arguments if provided
    script_type = "making_money"  # Default
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["making_money", "saving_money", "mm", "sm"]:
        script_type = sys.argv[1].lower()
        if script_type in ["mm", "sm"]:
            script_type = "making_money" if script_type == "mm" else "saving_money"
    
    test = CallStateManagerTest(script_type=script_type)
    await test.run_test()

if __name__ == "__main__":
    asyncio.run(main()) 