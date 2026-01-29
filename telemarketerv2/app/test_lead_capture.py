"""
Lead Capture Test Utility

This utility tests the telemarketer's ability to correctly identify and capture:
- Phone numbers
- Email addresses
- Appointment times
- Business details

It helps verify that script progresses to lead-generating states and correctly extracts data.
"""

import asyncio
import logging
import re
import uuid
from typing import Dict, List, Optional, Set, Any

from call_state_manager import CallStateManager, CallStateMachine, ScriptState
from script_parser import load_script_state_data, MAKING_MONEY_SCRIPT_FILENAME, SAVING_MONEY_SCRIPT_FILENAME
from llm_handler import LLMHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("lead_capture_test")

class LeadCaptureTest:
    """Test harness for lead capture testing"""
    
    def __init__(self, script_type: str = "MM"):
        """Initialize lead capture test"""
        self.script_type = script_type
        self.call_state_manager = CallStateManager()
        self.llm_handler = None
        self.state_machine = None
        self.call_sid = f"leadtest-{uuid.uuid4()}"
        self.test_data = {
            "business_type": "Plumbing Company",
            "phone_number": "+447123456789",
            "email": "test@example.com",
            "appointment_time": "next Tuesday at 2pm",
            "contact_name": "John Smith"
        }
        
    async def initialize(self):
        """Initialize components needed for testing"""
        from groq import AsyncGroq
        import os
        
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
    
    async def create_test_call(self):
        """Create a test call for lead capture"""
        initial_state = ScriptState.START_MM if self.script_type == "MM" else ScriptState.START_SM
        
        initial_data = {
            "is_outbound": True,
            "to_number": "+447123456789",
            "from_number": "+441234567890",
            "business_type": "(m)" if self.script_type == "MM" else "(s)",
            "agent_name": "Isaac",
            "client_name": "Proactiv"
        }
        
        self.state_machine = self.call_state_manager.create_call_state(
            self.call_sid, initial_data
        )
        
        logger.info(f"Created test call with SID: {self.call_sid}")
        logger.info(f"Initial state: {self.state_machine.state.value}")
        
        script_filename = MAKING_MONEY_SCRIPT_FILENAME if self.script_type == "MM" else SAVING_MONEY_SCRIPT_FILENAME
        state_data = await load_script_state_data(self.state_machine.state.value, script_filename)
        if state_data and "script" in state_data:
            dialogue = state_data["script"]
            self.state_machine.add_history_entry("assistant", dialogue)
        
        return True
    
    async def advance_to_state(self, target_state_prefix: str, max_iterations: int = 10):
        """
        Advance the conversation to reach a state that starts with the given prefix
        
        Args:
            target_state_prefix: The prefix of the state to reach (e.g., "BUSINESS_DISCOVERY")
            max_iterations: Maximum number of conversation turns to try
        
        Returns:
            bool: True if the target state was reached, False otherwise
        """
        if not self.state_machine:
            logger.error("No test call created yet.")
            return False
        
        if self.state_machine.state.value.startswith(target_state_prefix):
            logger.info(f"Already in target state: {self.state_machine.state.value}")
            return True
        
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Iteration {iteration}, Current state: {self.state_machine.state.value}")
            
            # Get appropriate response based on current state
            response = self._get_generic_advancement_response()
            
            # Add the user response to the conversation
            self.state_machine.add_history_entry("user", response)
            logger.info(f"Test response: {response}")
            
            # Get LLM response
            result = await self.llm_handler.generate_script_response(
                self.state_machine.state.value,
                self.state_machine.history,
                is_outbound=True,
                agent_name=self.state_machine.agent_name or "Isaac",
                client_name=self.state_machine.client_name or "Proactiv",
                script_type=self.state_machine.script_type
            )
            
            if not result:
                logger.error("Failed to get LLM response")
                return False
            
            # Extract response and next state
            response_text = result.get("response", "")
            next_state = result.get("next_state")
            
            # Add the assistant response to the conversation
            self.state_machine.add_history_entry("assistant", response_text)
            logger.info(f"Assistant response: {response_text[:100]}...")
            
            # Update state if needed
            if next_state:
                state_changed = self.state_machine.validate_and_set_state(next_state)
                if state_changed:
                    logger.info(f"State changed to: {self.state_machine.state.value}")
                else:
                    logger.warning(f"Invalid state transition suggested: {next_state}")
            
            # Check if we've reached the target state
            if self.state_machine.state.value.startswith(target_state_prefix):
                logger.info(f"Reached target state: {self.state_machine.state.value}")
                return True
            
            # Check if we've reached a terminal state
            if self.state_machine.state.value.startswith("CONFIRM_") or "HANGUP" in self.state_machine.state.value:
                logger.warning(f"Reached terminal state before target: {self.state_machine.state.value}")
                return False
        
        logger.warning(f"Failed to reach target state after {max_iterations} iterations")
        return False
    
    def _get_generic_advancement_response(self) -> str:
        """Get a generic response to advance the conversation based on current state"""
        current_state = self.state_machine.state.value
        
        # Initial greeting response
        if current_state.startswith("START_"):
            return "Yes, this is the business owner."
            
        # Business discovery responses
        elif current_state.startswith("INTRO_") or "INTRO_RESPONSE" in current_state:
            return f"That sounds interesting. I own a {self.test_data['business_type']}."
            
        # Business details response
        elif "BUSINESS_DISCOVERY" in current_state:
            return f"I run a {self.test_data['business_type']} with around 10 employees."
            
        # Interest responses
        elif "PRE_CLOSE" in current_state or "HANDLE_OBJECTION" in current_state:
            return "Yes, I'd be interested in hearing more about that."
            
        # Appointment booking responses
        elif "PITCH_APPOINTMENT" in current_state:
            return "Yes, I'd be happy to schedule a demonstration."
            
        # Appointment time responses
        elif "BOOK_APPOINTMENT" in current_state:
            return f"How about {self.test_data['appointment_time']}?"
            
        # Contact info responses
        elif "GET_WAMAILER_DETAILS" in current_state:
            return f"My mobile is {self.test_data['phone_number']}."
            
        # Email responses
        elif "GET_EMAIL_DETAILS" in current_state:
            return f"My email is {self.test_data['email']}."
            
        # Callback responses
        elif "CALLBACK_REQUESTED" in current_state or "SCHEDULE_CALLBACK" in current_state:
            return f"Please call back {self.test_data['appointment_time']}."
            
        # Default positive response
        return "Yes, that sounds good. Please tell me more."
    
    async def test_business_discovery(self) -> bool:
        """Test if the system asks for and captures business information"""
        logger.info("Testing business discovery functionality...")
        
        # Target either BUSINESS_DISCOVERY state or BUSINESS_RESPONSE state
        if await self.advance_to_state("BUSINESS_DISCOVERY"):
            logger.info("Successfully reached business discovery state")
            
            # Provide business info
            response = f"I run a {self.test_data['business_type']} focused on residential services."
            self.state_machine.add_history_entry("user", response)
            
            # Get LLM response
            result = await self.llm_handler.generate_script_response(
                self.state_machine.state.value,
                self.state_machine.history,
                is_outbound=True,
                agent_name=self.state_machine.agent_name,
                client_name=self.state_machine.client_name,
                script_type=self.state_machine.script_type
            )
            
            if not result:
                logger.error("Failed to get LLM response")
                return False
                
            # Check if response acknowledges the business type
            response_text = result.get("response", "").lower()
            if self.test_data['business_type'].lower() in response_text:
                logger.info("Business type successfully captured and referenced")
                return True
            else:
                logger.warning("Business type not referenced in response")
                return False
        else:
            logger.error("Failed to reach business discovery state")
            return False
    
    async def test_appointment_booking(self) -> bool:
        """Test if the system correctly captures appointment details"""
        logger.info("Testing appointment booking functionality...")
        
        if await self.advance_to_state("BOOK_APPOINTMENT"):
            logger.info("Successfully reached appointment booking state")
            
            # Provide appointment time
            response = f"I'm available {self.test_data['appointment_time']}"
            self.state_machine.add_history_entry("user", response)
            
            # Get LLM response
            result = await self.llm_handler.generate_script_response(
                self.state_machine.state.value,
                self.state_machine.history,
                is_outbound=True,
                agent_name=self.state_machine.agent_name,
                client_name=self.state_machine.client_name,
                script_type=self.state_machine.script_type
            )
            
            if not result:
                logger.error("Failed to get LLM response")
                return False
                
            # Check if next state is CONFIRM_APPOINTMENT
            next_state = result.get("next_state", "")
            if next_state and "CONFIRM_APPOINTMENT" in next_state:
                logger.info("Successfully transitioned to appointment confirmation")
                
                # Check if appointment time is in the response
                response_text = result.get("response", "").lower()
                appointment_time = self.test_data['appointment_time'].lower()
                if appointment_time in response_text:
                    logger.info("Appointment time successfully captured")
                    
                    # Check if state machine has stored the appointment time
                    if self.state_machine.appointment_time:
                        logger.info(f"Appointment stored in state: {self.state_machine.appointment_time}")
                        return True
                    else:
                        logger.warning("Appointment time not stored in state machine")
                else:
                    logger.warning("Appointment time not referenced in response")
            else:
                logger.warning(f"Did not transition to CONFIRM_APPOINTMENT state, got: {next_state}")
                
            return False
        else:
            logger.error("Failed to reach appointment booking state")
            return False
    
    async def test_phone_capture(self) -> bool:
        """Test if the system correctly captures phone numbers"""
        logger.info("Testing phone number capture functionality...")
        
        if await self.advance_to_state("GET_WAMAILER_DETAILS"):
            logger.info("Successfully reached WhatsApp contact details state")
            
            # Provide phone number
            response = f"My number is {self.test_data['phone_number']}"
            self.state_machine.add_history_entry("user", response)
            
            # Get LLM response
            result = await self.llm_handler.generate_script_response(
                self.state_machine.state.value,
                self.state_machine.history,
                is_outbound=True,
                agent_name=self.state_machine.agent_name,
                client_name=self.state_machine.client_name,
                script_type=self.state_machine.script_type
            )
            
            if not result:
                logger.error("Failed to get LLM response")
                return False
                
            # Check if next state is CONFIRM_WAMAILER
            next_state = result.get("next_state", "")
            if next_state and "CONFIRM_WAMAILER" in next_state:
                logger.info("Successfully transitioned to WhatsApp confirmation")
                
                # Check if phone number is in the response
                response_text = result.get("response", "")
                if self.test_data['phone_number'] in response_text:
                    logger.info("Phone number successfully captured in response")
                    
                    # Check if state machine has stored the phone number
                    if self.state_machine.contact_mobile:
                        logger.info(f"Phone number stored in state: {self.state_machine.contact_mobile}")
                        return True
                    else:
                        logger.warning("Phone number not stored in state machine")
                else:
                    logger.warning("Phone number not referenced in response")
            else:
                logger.warning(f"Did not transition to CONFIRM_WAMAILER state, got: {next_state}")
                
            return False
        else:
            logger.error("Failed to reach WhatsApp details state")
            return False
    
    async def test_email_capture(self) -> bool:
        """Test if the system correctly captures email addresses"""
        logger.info("Testing email capture functionality...")
        
        if await self.advance_to_state("GET_EMAIL_DETAILS"):
            logger.info("Successfully reached email details state")
            
            # Provide email
            response = f"My email is {self.test_data['email']}"
            self.state_machine.add_history_entry("user", response)
            
            # Get LLM response
            result = await self.llm_handler.generate_script_response(
                self.state_machine.state.value,
                self.state_machine.history,
                is_outbound=True,
                agent_name=self.state_machine.agent_name,
                client_name=self.state_machine.client_name,
                script_type=self.state_machine.script_type
            )
            
            if not result:
                logger.error("Failed to get LLM response")
                return False
                
            # Check if next state is CONFIRM_EMAILER
            next_state = result.get("next_state", "")
            if next_state and "CONFIRM_EMAILER" in next_state:
                logger.info("Successfully transitioned to email confirmation")
                
                # Check if email is in the response
                response_text = result.get("response", "")
                if self.test_data['email'] in response_text:
                    logger.info("Email successfully captured in response")
                    
                    # Check if state machine has stored the email
                    if self.state_machine.contact_email:
                        logger.info(f"Email stored in state: {self.state_machine.contact_email}")
                        return True
                    else:
                        logger.warning("Email not stored in state machine")
                else:
                    logger.warning("Email not referenced in response")
            else:
                logger.warning(f"Did not transition to CONFIRM_EMAILER state, got: {next_state}")
                
            return False
        else:
            logger.error("Failed to reach email details state")
            return False
    
    async def run_all_tests(self):
        """Run all lead capture tests"""
        print("\n===== LEAD CAPTURE TEST SUITE =====")
        print(f"Testing {self.script_type} script lead capture functionality.\n")
        
        if not await self.initialize():
            return
        
        if not await self.create_test_call():
            return
        
        test_results = {}
        
        # Test 1: Business Discovery
        await self.create_test_call()  # Create fresh call for each test
        test_results["business_discovery"] = await self.test_business_discovery()
        
        # Test 2: Appointment Booking
        await self.create_test_call()
        test_results["appointment_booking"] = await self.test_appointment_booking()
        
        # Test 3: Phone Capture
        await self.create_test_call()
        test_results["phone_capture"] = await self.test_phone_capture()
        
        # Test 4: Email Capture
        await self.create_test_call()
        test_results["email_capture"] = await self.test_email_capture()
        
        # Print results
        print("\n===== TEST RESULTS =====")
        for test_name, result in test_results.items():
            status = "PASSED" if result else "FAILED"
            print(f"{test_name}: {status}")
        
        # Overall status
        all_passed = all(test_results.values())
        print(f"\nOverall Status: {'PASSED' if all_passed else 'FAILED'}")
        print("=========================\n")

async def main():
    """Main entry point for lead capture tests"""
    print("Select script type to test:")
    print("1. Making Money Script (MM)")
    print("2. Saving Money Script (SM)")
    
    choice = input("Enter choice (1/2): ")
    script_type = "MM" if choice == "1" else "SM"
    
    tester = LeadCaptureTest(script_type=script_type)
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main()) 