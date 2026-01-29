#!/usr/bin/env python3
"""
Test script for the Dialer System with integrated LLM Handler
This script provides a way to test the dialer's retry logic, automated response detection,
and sequential batch processing capabilities without making actual calls.
"""

import asyncio
import logging
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("test_dialer_system")

# Determine the root directory and add it to the path
current_dir = Path(__file__).resolve().parent
if current_dir not in sys.path:
    sys.path.append(str(current_dir))

# Import necessary modules
from llm_handler import LLMHandler
from automated_response_detector import AutomatedResponseDetector
from uk_regulations_integration import UKRegulationsManager

# Mock imports for testing without Twilio
class MockTwilioClient:
    """Mock Twilio client for testing."""
    def __init__(self):
        self.calls = {}
        self.next_call_sid = 1000
    
    async def create_call(self, to, from_, **kwargs):
        """Simulate creating a call."""
        call_sid = f"CA{self.next_call_sid}"
        self.next_call_sid += 1
        self.calls[call_sid] = {
            "to": to,
            "from": from_,
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "kwargs": kwargs
        }
        logger.info(f"Created mock call to {to} with SID {call_sid}")
        return {"sid": call_sid}
    
    async def get_call(self, call_sid):
        """Get call details."""
        if call_sid not in self.calls:
            raise ValueError(f"Call {call_sid} not found")
        return self.calls[call_sid]
    
    async def update_call(self, call_sid, status):
        """Update call status."""
        if call_sid not in self.calls:
            raise ValueError(f"Call {call_sid} not found")
        self.calls[call_sid]["status"] = status
        self.calls[call_sid]["updated_at"] = datetime.now().isoformat()
        logger.info(f"Updated call {call_sid} status to {status}")
        return self.calls[call_sid]

class MockDatabase:
    """Mock database for testing."""
    def __init__(self):
        self.calls = {}
        self.leads = {}
    
    async def save_call(self, call_data):
        """Save call data."""
        call_id = call_data.get("call_id")
        if not call_id:
            call_id = f"call_{len(self.calls) + 1}"
            call_data["call_id"] = call_id
        
        self.calls[call_id] = call_data
        logger.info(f"Saved call {call_id} to mock database")
        return call_id
    
    async def get_call(self, call_id):
        """Get call data."""
        return self.calls.get(call_id)
    
    async def update_call(self, call_id, update_data):
        """Update call data."""
        if call_id not in self.calls:
            raise ValueError(f"Call {call_id} not found")
        
        self.calls[call_id].update(update_data)
        logger.info(f"Updated call {call_id} in mock database")
        return self.calls[call_id]
    
    async def save_lead(self, lead_data):
        """Save lead data."""
        lead_id = lead_data.get("lead_id")
        if not lead_id:
            lead_id = f"lead_{len(self.leads) + 1}"
            lead_data["lead_id"] = lead_id
        
        self.leads[lead_id] = lead_data
        logger.info(f"Saved lead {lead_id} to mock database")
        return lead_id
    
    async def get_lead(self, lead_id):
        """Get lead data."""
        return self.leads.get(lead_id)

class TestDialerSystem:
    """Test class for the Dialer System with mocked dependencies."""
    def __init__(self):
        self.twilio_client = MockTwilioClient()
        self.llm_handler = None
        self.response_detector = None
        self.uk_regulations = None
        self.db = MockDatabase()
        self.call_queue = []
        self.active_calls = {}
        self.is_active = False
        self.max_concurrent_calls = 2
        self.max_retries = 3
        self.retry_delay_seconds = 30
        self.call_timeout_seconds = 180
    
    async def initialize(self):
        """Initialize the test system."""
        logger.info("Initializing Dialer System Test...")
        
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
            
            # Initialize Automated Response Detector
            self.response_detector = AutomatedResponseDetector()
            
            # Initialize UK Regulations Manager
            self.uk_regulations = UKRegulationsManager.get_instance(
                db_path=":memory:",
                tps_path=str(current_dir / "mock_tps.csv")
            )
            await self.uk_regulations.initialize()
            
            logger.info("Dialer System Test initialized successfully")
            return True
        except ImportError as e:
            logger.error(f"Failed to import required packages: {e}")
            return False
        except Exception as e:
            logger.error(f"Error initializing dialer system test: {e}")
            return False
    
    async def add_call(self, phone_number, business_type="RETAIL"):
        """Add a call to the queue."""
        call_id = f"call_{len(self.call_queue) + len(self.active_calls) + 1}"
        
        # Check if the call is permitted under UK regulations
        caller_id = "+441234567890"  # Mock Twilio number
        is_permitted, reason, _ = await self.uk_regulations.check_call_permitted(phone_number, caller_id)
        
        if not is_permitted:
            logger.warning(f"Call to {phone_number} is not permitted: {reason}")
            
            # Save the blocked call
            await self.db.save_call({
                "call_id": call_id,
                "phone_number": phone_number,
                "status": "BLOCKED",
                "business_type": business_type,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "notes": f"Call blocked: {reason}"
            })
            
            return call_id, False
        
        # Add to queue
        call_data = {
            "call_id": call_id,
            "phone_number": phone_number,
            "business_type": business_type,
            "status": "QUEUED",
            "retry_count": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        self.call_queue.append(call_data)
        
        # Save the queued call
        await self.db.save_call(call_data)
        
        logger.info(f"Added call to {phone_number} to queue with ID {call_id}")
        return call_id, True
    
    async def add_batch_calls(self, phone_numbers: List[str], business_type="RETAIL"):
        """Add a batch of calls to the queue."""
        results = []
        
        for phone_number in phone_numbers:
            call_id, success = await self.add_call(phone_number, business_type)
            results.append({"call_id": call_id, "phone_number": phone_number, "queued": success})
        
        return results
    
    async def process_calls(self):
        """Process calls from the queue."""
        if not self.is_active:
            logger.warning("Dialer system is not active. Start it first.")
            return
        
        while self.is_active and self.call_queue:
            # Check if we can make more concurrent calls
            if len(self.active_calls) >= self.max_concurrent_calls:
                logger.info(f"Max concurrent calls ({self.max_concurrent_calls}) reached. Waiting...")
                break
            
            # Get the next call from the queue
            call_data = self.call_queue.pop(0)
            call_id = call_data["call_id"]
            phone_number = call_data["phone_number"]
            
            logger.info(f"Processing call {call_id} to {phone_number}")
            
            # Update call status
            call_data["status"] = "IN_PROGRESS"
            call_data["updated_at"] = datetime.now().isoformat()
            await self.db.update_call(call_id, call_data)
            
            # Make the call (mocked)
            try:
                call_result = await self.twilio_client.create_call(
                    to=phone_number,
                    from_="+441234567890",  # Mock Twilio number
                    url="https://example.com/twiml",
                    status_callback="https://example.com/status-callback"
                )
                
                call_sid = call_result["sid"]
                call_data["twilio_sid"] = call_sid
                call_data["call_started_at"] = datetime.now().isoformat()
                
                # Save to active calls
                self.active_calls[call_id] = call_data
                
                # Update in database
                await self.db.update_call(call_id, call_data)
                
                logger.info(f"Call {call_id} to {phone_number} initiated with SID {call_sid}")
                
            except Exception as e:
                logger.error(f"Error initiating call {call_id} to {phone_number}: {str(e)}")
                
                # Update call status
                call_data["status"] = "FAILED"
                call_data["updated_at"] = datetime.now().isoformat()
                call_data["notes"] = f"Call failed: {str(e)}"
                
                # Check if we should retry
                if call_data["retry_count"] < self.max_retries:
                    call_data["retry_count"] += 1
                    call_data["status"] = "RETRY_SCHEDULED"
                    call_data["next_retry_at"] = datetime.now().isoformat()  # In real code, add delay
                    
                    logger.info(f"Scheduling retry for call {call_id} (Attempt {call_data['retry_count']} of {self.max_retries})")
                    
                    # Add back to queue
                    self.call_queue.append(call_data)
                
                # Update in database
                await self.db.update_call(call_id, call_data)
    
    async def handle_call_update(self, call_id, update_data):
        """Handle updates for a call."""
        if call_id not in self.active_calls:
            logger.warning(f"Call {call_id} not found in active calls")
            return
        
        call_data = self.active_calls[call_id]
        call_data.update(update_data)
        
        # Update in database
        await self.db.update_call(call_id, call_data)
        
        # Check if the call is completed or failed
        if call_data["status"] in ["COMPLETED", "FAILED", "NO_ANSWER", "BUSY"]:
            logger.info(f"Call {call_id} ended with status {call_data['status']}")
            
            # Remove from active calls
            del self.active_calls[call_id]
            
            # Process more calls if available
            await self.process_calls()
    
    async def handle_automated_response(self, call_id, response_text):
        """Handle automated responses during a call."""
        if call_id not in self.active_calls:
            logger.warning(f"Call {call_id} not found in active calls")
            return
        
        call_data = self.active_calls[call_id]
        
        # Analyze the response
        analysis = self.response_detector.analyze_response(response_text)
        
        if analysis["is_automated"]:
            logger.info(f"Automated response detected for call {call_id}: {analysis['response_type']}")
            
            # Update call with detection results
            call_data["automated_response_detected"] = True
            call_data["automated_response_type"] = analysis["response_type"]
            call_data["updated_at"] = datetime.now().isoformat()
            
            # Check if we should hang up
            should_hang_up, reason = self.response_detector.should_hang_up(response_text)
            
            if should_hang_up:
                logger.info(f"Hanging up call {call_id}: {reason}")
                
                call_data["status"] = "MACHINE_DETECTED"
                call_data["notes"] = f"Call terminated: {reason}"
                
                # Update in database
                await self.db.update_call(call_id, call_data)
                
                # Remove from active calls
                del self.active_calls[call_id]
                
                # Process more calls if available
                await self.process_calls()
            else:
                # Continue the call but update with the detection info
                await self.db.update_call(call_id, call_data)
        else:
            logger.info(f"Human response detected for call {call_id}")
    
    async def start_dialer(self):
        """Start the dialer system."""
        if self.is_active:
            logger.warning("Dialer system is already active")
            return
        
        self.is_active = True
        logger.info("Dialer system started")
        
        # Start processing calls
        await self.process_calls()
    
    async def stop_dialer(self):
        """Stop the dialer system."""
        if not self.is_active:
            logger.warning("Dialer system is already stopped")
            return
        
        self.is_active = False
        logger.info("Dialer system stopped")
    
    async def get_dialer_status(self):
        """Get the status of the dialer system."""
        return {
            "is_active": self.is_active,
            "queue_size": len(self.call_queue),
            "active_calls": len(self.active_calls),
            "max_concurrent_calls": self.max_concurrent_calls,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds
        }
    
    async def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up resources...")
        
        # Stop the dialer
        if self.is_active:
            await self.stop_dialer()
        
        # Clean up UK Regulations Manager
        if self.uk_regulations:
            await self.uk_regulations.cleanup()
            
        # No need to clean up LLMHandler as it doesn't have a cleanup method

async def run_test():
    """Run a test of the dialer system."""
    dialer = TestDialerSystem()
    
    try:
        await dialer.initialize()
        
        # Add some test calls
        test_numbers = [
            "+441234567890",  # Valid number
            "+441234567891",  # Another valid number
            "+441234567892",  # Another valid number
            "+441234567893",  # Another valid number
        ]
        
        results = await dialer.add_batch_calls(test_numbers)
        logger.info(f"Added {len(results)} calls to the queue")
        
        # Start the dialer
        await dialer.start_dialer()
        
        # Print initial status
        status = await dialer.get_dialer_status()
        logger.info(f"Dialer status: {json.dumps(status, indent=2)}")
        
        # Wait a bit for calls to be processed
        await asyncio.sleep(2)
        
        # Simulate responses for active calls
        for call_id, call_data in list(dialer.active_calls.items()):
            # Simulate an automated response for the first call
            if call_id == list(dialer.active_calls.keys())[0]:
                await dialer.handle_automated_response(
                    call_id, 
                    "Hello, you've reached voicemail. Please leave a message after the tone."
                )
            else:
                # Simulate completing the other calls
                await dialer.handle_call_update(call_id, {
                    "status": "COMPLETED",
                    "duration": 60,
                    "updated_at": datetime.now().isoformat()
                })
        
        # Wait for processing to complete
        await asyncio.sleep(2)
        
        # Print final status
        status = await dialer.get_dialer_status()
        logger.info(f"Final dialer status: {json.dumps(status, indent=2)}")
        
        # Print call records
        logger.info("Call records in database:")
        for call_id, call_data in dialer.db.calls.items():
            logger.info(f"  {call_id}: {call_data['status']} - {call_data['phone_number']}")
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}", exc_info=True)
    finally:
        # Clean up
        await dialer.cleanup()

if __name__ == "__main__":
    # Make sure the GROQ API key is set
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY environment variable not set. This is required for LLM integration.")
        sys.exit(1)
    
    asyncio.run(run_test()) 