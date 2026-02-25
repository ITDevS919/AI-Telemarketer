"""
LLM Handler for AI Telemarketer v2

This module handles all interactions with the LLM (Groq) for generating responses
and managing conversation flow.
"""

import os
import json
import logging
import re
import time
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from groq import AsyncGroq
from groq.types.chat import ChatCompletion

# Configure logging
logger = logging.getLogger("telemarketerv2")

# Constants for script types
MAKING_MONEY = "MM"  # Corresponds to the 5_steps_script.md logic
SAVING_MONEY = "SM" # This might need its own script or different handling

class LLMHandler:
    """Handles all LLM interactions for the AI Telemarketer."""
    
    def __init__(self, api_key_or_client: Optional[AsyncGroq] = None):
        """
        Initialize the LLM handler.
        
        Args:
            api_key_or_client: Either a Groq API key string or an AsyncGroq client instance
        """
        if isinstance(api_key_or_client, AsyncGroq):
            self.client = api_key_or_client
        else:
            self.client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY")) # Ensure API key is loaded
            
        self.prompts = self._load_prompts()
        self.main_script_content = self._load_main_script()
        
    def _load_prompts(self) -> Dict[str, str]:
        """Load base prompts from JSON file."""
        try:
            prompts_path = Path(__file__).parent.parent / "data" / "prompts.json"
            with open(prompts_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading prompts.json: {e}")
            # Return a default structure to prevent crashes if file is missing/corrupt
            return {
                "system_base": "You are Isaac, a professional telemarketing agent.",
                "timeout_instruction": "The user has not responded. End the call politely.",
                "repeat_instruction": "The user has not responded. Repeat your last message."
            }

    def _load_main_script(self) -> str:
        """Load the main 5-step / 16-sub-step script content (5_Steps_Marketing_Updated.md)."""
        try:
            script_path = Path(__file__).parent.parent / "data" / "scripts" / "5_Steps_Marketing_Updated.md"
            if not script_path.exists():
                script_path = Path(__file__).parent.parent / "data" / "scripts" / "5_steps_script.md"
            with open(script_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading script: {e}")
            return "Error: Main script could not be loaded. Please proceed with caution."

    async def get_initial_greeting(
        self,
        call_sid: str, # Added call_sid for consistency, though not directly used in this version
        business_type: str = MAKING_MONEY # Default to making money script
    ) -> str:
        """
        Generate the initial greeting based on the main script.
        """
        try:
            if not self.main_script_content or "Error: Main script could not be loaded" in self.main_script_content:
                 logger.error(f"[{call_sid}] Main script not loaded. Cannot generate initial greeting based on script.")
                 return "Hello, I'm calling from Proactiv. Is the business owner available?" # Fallback

            system_message_content = (
                f"{self.prompts.get('system_base', 'You are Isaac, a professional telemarketing agent.')}\n\n"
                f"Your primary task is to initiate a conversation following this script:\n\n"
                f"--- SCRIPT START ---\n{self.main_script_content}\n--- SCRIPT END ---\n\n"
                f"Based on the 'Introduction' section of the script, what is the very first thing you should say to the person who answers the phone? "
                f"If the script mentions asking for the owner, phrase that as your first line. Respond with ONLY that first line of dialogue."
            )
            
            messages = [{"role": "system", "content": system_message_content}]
            
            response = await self.client.chat.completions.create(
                model="llama3-8b-8192", # Consider a more capable model for script adherence
                messages=messages,
                temperature=0.3, # Lower temperature for more predictable script start
                max_tokens=100
            )
            
            greeting = response.choices[0].message.content.strip()
            # Ensure the greeting is not empty and is a plausible opening line
            if not greeting or len(greeting) < 5:
                logger.warning(f"[{call_sid}] LLM generated an empty or too short initial greeting. Using fallback.")
                # Fallback based on script's intent
                return "Hi. Can I speak to the owner, please?" 
            return greeting
            
        except Exception as e:
            logger.error(f"[{call_sid}] Error generating initial greeting from script: {e}", exc_info=True)
            return "Hello, this is an automated call from Proactiv. How are you today?" # Generic fallback

    async def generate_response(
        self,
        call_sid: str,
        transcript: str,
        conversation_history: List[Dict[str, str]],
        business_type: str = MAKING_MONEY, # Default to making money script
        state: int = 1  # 0=timeout, 1=speech, 2=repeat
    ) -> Tuple[str, bool]:
        """
        Generate a response based on the transcript, conversation history, and the main script.
        """
        try:
            if not self.main_script_content or "Error: Main script could not be loaded" in self.main_script_content:
                logger.error(f"[{call_sid}] Main script not loaded. Cannot generate response based on script.")
                return "I'm having trouble accessing my script right now. Let's end this call.", True

            # Base system prompt + main script
            system_prompt_lines = [
                self.prompts.get('system_base', 'You are Isaac, a professional telemarketing agent.'),
                "You MUST strictly follow the 5-step telemarketing script provided below to guide the conversation.",
                "Your primary objective is to book an appointment for a 10-15 minute remote demonstration, as outlined in the 'Close' and 'Consolidation' sections of the script.",
                "Identify whether you are speaking with a gatekeeper or the business owner and use the appropriate sections of the script (e.g., 'Dealing With Gatekeepers', 'OWNER - Relax').",
                "Adapt your dialogue based on the user's responses, smoothly progressing through the script's stages: Introduction, Presentation (Qualify, Highlight Problem, Fact Find), Explanation, Close, and Consolidation.",
                
                # New instructions for lead event reporting
                'IMPORTANT: When a key lead event occurs as per the script, you MUST include a special tag in your response. The tag should be at the VERY END of your response text, on a new line if possible, and formatted exactly as: [LEAD_EVENT:{EVENT_TYPE}|PAYLOAD:{\"key\":\"value\"}].',
                'Valid EVENT_TYPEs are: APPOINTMENT_BOOKED, OWNER_IDENTIFIED, GATEKEEPER_INFO, CALLBACK_REQUESTED, NOT_INTERESTED, LEAD_CLOSED_LOST.',
                'For APPOINTMENT_BOOKED, PAYLOAD must be a JSON string like: {\"appointment_time\": \"YYYY-MM-DD HH:MM\", \"contact_name\": \"Name\", \"notes\": \"Optional notes about appointment\"}. Use 24-hour format for time.',
                'For OWNER_IDENTIFIED, PAYLOAD: {\"contact_name\": \"Owner Name\"}.',
                'For GATEKEEPER_INFO, PAYLOAD: {\"contact_name\": \"Gatekeeper Name\", \"notes\": \"e.g., Owner not in, best time to call back is X\"}.',
                'For CALLBACK_REQUESTED, PAYLOAD: {\"notes\": \"User asked to call back at specific time/reason\"}.',
                'For NOT_INTERESTED, PAYLOAD: {\"reason\": \"Brief reason given by user\"}.',
                'For LEAD_CLOSED_LOST, PAYLOAD: {\"reason\": \"Reason why lead is definitely lost, e.g., out of business\"}.',
                'Only include ONE such [LEAD_EVENT:...] tag per response, and only when a definitive event occurs. Your spoken dialogue should NOT mention this tag; it is for system processing only.',

                "If the user indicates they are not interested, or is rude, use the script's guidance to politely end the call or attempt to re-engage if appropriate. If not specified, politely end the call.",
                "When the script indicates the end of the call (e.g., after booking an appointment and giving farewells, or if the lead is unsuitable), ensure your response is the final one and set the hangup flag.",
                "Pay close attention to user cues to determine the current stage of the conversation within the script.",
                "Your responses should be natural and conversational while adhering to the script's directives.",
                "--- SCRIPT START ---",
                self.main_script_content,
                "--- SCRIPT END ---"
            ]

            # Add state-specific instructions
            if state == 0:  # Timeout
                system_prompt_lines.append(self.prompts.get('timeout_instruction', 'The user has not responded. Politely end the call or ask if they are still there as per script guidance.'))
            elif state == 2:  # Repeat
                system_prompt_lines.append(self.prompts.get('repeat_instruction', 'The user has not responded or asked you to repeat. Repeat your last message, or rephrase slightly if appropriate, then continue with the script.'))
            
            system_message_content = "\n\n".join(system_prompt_lines)
            
            messages = [{"role": "system", "content": system_message_content}]
            
            # Add conversation history
            for msg in conversation_history:
                messages.append({"role": msg["role"], "content": msg["content"]})
                
            # Add current transcript if not a timeout/repeat (and transcript exists)
            if state == 1 and transcript:
                messages.append({"role": "user", "content": transcript})
            elif not transcript and state == 1 and not conversation_history: # Very first turn after initial greeting from get_initial_greeting
                 # This case might indicate the LLM should proceed with the script after its opening line
                 # or it's a silent response to the initial greeting.
                 # If get_initial_greeting already provided the first line, and user is silent,
                 # LLM might need to prompt again or handle silence.
                 # For now, we assume transcript will be empty if user is silent to the very first greeting.
                 # This 'state' handling needs to be robust in DialerSystem.
                 pass


            response = await self.client.chat.completions.create(
                model="llama3-70b-8192", # Using a more capable model for complex script following
                messages=messages,
                temperature=0.5, # Moderately creative but still script-focused
                max_tokens=300 # Allow for longer, more detailed script-based responses
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Determine if LLM intends to hang up.
            # The LLM should use phrases from the script's "Farewells" or similar terminal statements.
            # We can augment this with keyword spotting if needed, but ideally, the LLM handles it.
            # For now, rely on LLM saying goodbye clearly.
            # A more robust way would be for the LLM to output a special token like [HANGUP]
            # or for the prompt to ask it to state "I will now hang up." if it's ending.
            
            # Simple check for now:
            should_hangup = False
            farewell_keywords = ["goodbye", "bye for now", "take care", "look forward to meeting you", "end the call"] # From script + general
            response_lower = response_text.lower()
            if any(keyword in response_lower for keyword in farewell_keywords):
                 # More specific check for appointment booking
                if "look forward to meeting you" in response_lower or "appointment is booked" in response_lower :
                    logger.info(f"[{call_sid}] LLM indicated appointment booked/farewell. Setting hangup.")
                    should_hangup = True
                elif "end the call" in response_lower and len(conversation_history) > 2: # Avoid premature hangup
                    logger.info(f"[{call_sid}] LLM indicated generic end of call. Setting hangup.")
                    should_hangup = True
                # If only "goodbye" or "bye", ensure it's not a mid-conversation polite phrase.
                # This logic can be refined.

            # If the LLM's response is very short and implies hangup, also consider it.
            if len(response_text.split()) < 5 and any(fw in response_lower for fw in ["bye." "goodbye."]):
                 should_hangup = True


            # If an error occurred in script loading, always hang up
            if "Error: Main script could not be loaded" in response_text:
                should_hangup = True
            
            return response_text, should_hangup
            
        except Exception as e:
            logger.error(f"[{call_sid}] Error generating response from script: {e}", exc_info=True)
            return "I apologize, I'm experiencing a technical difficulty. Let's end this call.", True

    async def get_response(
        self,
        script: str,
        conversation_history: List[Dict[str, str]],
        current_transcript: str,
        current_step: int,
    ) -> str:
        """
        Version B (interactive): Get LLM response from script context and conversation.
        Used by ConversationManager when scripted_mode=False.
        """
        response_text, _ = await self.generate_response(
            call_sid="",
            transcript=current_transcript,
            conversation_history=conversation_history,
            business_type=MAKING_MONEY,
            state=1,
        )
        return response_text or ""