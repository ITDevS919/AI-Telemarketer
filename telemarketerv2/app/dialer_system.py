"""
Dialer System for AI Telemarketer

This module manages the outbound dialing system, integrating with Twilio
for call handling, managing the call queue, and implementing retry logic.
"""

import asyncio
import datetime
import json
import logging
import os
import time
import uuid
import random
import re
from urllib.parse import quote_plus
from typing import Dict, List, Optional, Set, Any, Tuple
from enum import Enum
import sqlite3
from .database.connection import DatabaseAdapter, get_database_adapter
from pathlib import Path

# Twilio imports
try:
    from twilio.rest import Client as TwilioClient
    from twilio.base.exceptions import TwilioRestException
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    
from .uk_regulations_integration import get_regulations_manager
from .llm_handler import LLMHandler
from .database.models import init_database, CallRecord, LeadRecord

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("dialer_system")

class CallStatus(Enum):
    """Enum for call status tracking"""
    QUEUED = "queued"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"  # Blocked by regulations
    NO_ANSWER = "no-answer"
    BUSY = "busy"
    MACHINE_DETECTED = "machine-detected"
    RETRY_SCHEDULED = "retry-scheduled"

class DialerSystem:
    """
    Manages the outbound dialing system for the telemarketer.
    Handles Twilio integration, call queuing, and retry logic.
    """
    
    def __init__(self, 
                 db_path: str = "telemarketer_calls.db", 
                 max_concurrent_calls: int = 1,
                 max_retries: int = 3,
                 retry_delay_seconds: int = 300,
                 call_timeout_seconds: int = 45):
        """
        Initialize the dialer system.
        
        Args:
            db_path: Path to the SQLite database
            max_concurrent_calls: Maximum number of concurrent calls
            max_retries: Maximum number of retry attempts per number
            retry_delay_seconds: Delay between retry attempts
            call_timeout_seconds: Timeout for calls with no answer
        """
        self.db_path = db_path
        self.max_concurrent_calls = max_concurrent_calls
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.call_timeout_seconds = call_timeout_seconds
        
        # Initialize Twilio client if credentials are available
        self.twilio_client = None
        self.twilio_phone_number = os.environ.get("TWILIO_PHONE_NUMBER")
        self.twilio_webhook_url = os.environ.get("TWILIO_WEBHOOK_URL")
        self.ngrok_websocket_url = os.environ.get("NGROK_WEBSOCKET_URL")
        self._init_twilio()
        
        # Get UK regulations manager
        self.regulations_manager = get_regulations_manager()
        
        # Get LLM handler for AI interactions
        self.llm_handler = LLMHandler()
        
        # Internal state tracking
        self.call_queue = asyncio.Queue()
        self.active_calls = set()
        self.retry_queue = []
        self.call_history = {}
        self.running = False
        self.dialer_lock = asyncio.Lock()
        
        # Database connection
        self.db_conn = None
        self._init_database()
        
        # Start background tasks
        self.background_tasks = []
    
    def _init_twilio(self):
        """Initialize the Twilio client if credentials are available"""
        if not TWILIO_AVAILABLE:
            logger.warning("Twilio package not installed. Calls will be simulated.")
            return
            
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        
        if account_sid and auth_token:
            self.twilio_client = TwilioClient(account_sid, auth_token)
            logger.info("Twilio client initialized successfully")
        else:
            logger.warning("Twilio credentials not found. Calls will be simulated.")
            
        if not self.twilio_phone_number:
            logger.warning("Twilio phone number not set. Using default +18005551234")
            self.twilio_phone_number = "+18005551234"
            
        if not self.twilio_webhook_url:
            logger.warning("Twilio webhook URL not set. Callbacks won't work properly.")
    
    def _init_database(self):
        """Initialize the database connection and tables"""
        try:
            # Initialize the database schema
            init_database(self.db_path)
            
            # Create a database adapter (supports both SQLite and PostgreSQL)
            self.db_adapter = get_database_adapter(self.db_path)
            self.db_adapter.connect()
            
            # For backward compatibility, set db_conn to adapter's connection
            # The adapter handles both SQLite and PostgreSQL connections
            self.db_conn = self.db_adapter
            
            logger.info(f"Database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def initialize(self):
        """Initialize the dialer system and its dependencies"""
        # LLMHandler initializes its prompts in its own __init__
        # await self.call_manager.initialize() # Removed call_manager.initialize()
        
        # Initialize the regulations manager
        await self.regulations_manager.initialize()
        self.initialized = True
        
        # Load any pending calls from database
        await self._load_pending_calls()
        
        logger.info("Dialer system initialized successfully")
    
    async def _load_pending_calls(self):
        """Load any pending calls from the database"""
        if not self.db_conn:
            return
            
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("""
                SELECT * FROM call_records 
                WHERE status IN ('queued', 'retry_scheduled') 
                ORDER BY scheduled_time ASC
            """)
            
            pending_calls = cursor.fetchall()
            logger.info(f"Found {len(pending_calls)} pending calls in database")
            
            for call in pending_calls:
                # Create a call item from the database record
                call_item = {
                    "call_id": call["call_id"],
                    "phone_number": call["phone_number"],
                    "business_type": call["business_type"],
                    "caller_id": call["caller_id"],
                    "retry_count": call["retry_count"],
                    "scheduled_time": datetime.datetime.fromisoformat(call["scheduled_time"]),
                    "status": call["status"]
                }
                
                # Add to appropriate queue
                if call["status"] == "queued":
                    await self.call_queue.put(call_item)
                elif call["status"] == "retry_scheduled":
                    self.retry_queue.append(call_item)
                    
            # Sort retry queue by scheduled time
            self.retry_queue.sort(key=lambda x: x["scheduled_time"])
                
        except Exception as e:
            logger.error(f"Error loading pending calls: {e}")
    
    async def add_call(
        self,
        phone_number: str,
        business_type: str,
        caller_id: str = None,
        scripted: Optional[bool] = None,
        voice_name: Optional[str] = None,
    ) -> Dict:
        """
        Add a call to the queue.

        Args:
            phone_number: Phone number to call
            business_type: Type of business for script selection
            caller_id: Caller ID to use (optional)
            scripted: True = Version A (scripted), False = Version B (interactive). None = use env DIALER_SCRIPTED_MODE
            voice_name: Cloned voice name for Version A (optional). None = use env DIALER_SCRIPTED_VOICE_NAME or Piper

        Returns:
            Dict with call details including call_id
        """
        if not caller_id:
            caller_id = self.twilio_phone_number or "+441234567890"

        # Check if call is permitted by regulations
        permitted, reason, violation_type = await self.regulations_manager.check_call_permitted(
            phone_number, caller_id
        )

        call_id = f"CA{uuid.uuid4().hex[:12].upper()}"

        # Create call record
        call_record = {
            "call_id": call_id,
            "phone_number": phone_number,
            "business_type": business_type,
            "caller_id": caller_id,
            "status": CallStatus.BLOCKED.value if not permitted else CallStatus.QUEUED.value,
            "retry_count": 0,
            "created_at": datetime.datetime.now().isoformat(),
            "scheduled_time": datetime.datetime.now().isoformat(),
            "last_error": None if permitted else reason,
            "regulation_violation": violation_type
        }

        # Save to database
        self._save_call_record(call_record)

        if not permitted:
            logger.info(f"Call to {phone_number} blocked by regulations: {reason}")
            return call_record

        # Add to queue (include scripted/voice_name so _make_call uses them in stream URL)
        call_item = {
            "call_id": call_id,
            "phone_number": phone_number,
            "business_type": business_type,
            "caller_id": caller_id,
            "retry_count": 0,
            "scheduled_time": datetime.datetime.now(),
            "status": CallStatus.QUEUED.value,
            "scripted": scripted,
            "voice_name": (voice_name or "").strip() or None,
        }

        await self.call_queue.put(call_item)
        logger.info(f"Added call to {phone_number} to queue with ID {call_id} (scripted={scripted}, voice_name={voice_name or 'default'})")

        return call_record
    
    async def add_batch_calls(self, calls: List[Dict]) -> Dict:
        """
        Add multiple calls to the queue.
        
        Args:
            calls: List of call details dicts with phone_number and business_type
            
        Returns:
            Dict with summary of added calls
        """
        results = {
            "total": len(calls),
            "queued": 0,
            "blocked": 0,
            "details": []
        }
        
        for call in calls:
            phone_number = call["phone_number"]
            business_type = call["business_type"]
            caller_id = call.get("caller_id", self.twilio_phone_number or "+441234567890")
            scripted = call.get("scripted")
            voice_name = call.get("voice_name")

            call_result = await self.add_call(
                phone_number, business_type, caller_id,
                scripted=scripted, voice_name=voice_name,
            )
            
            if call_result["status"] == CallStatus.QUEUED.value:
                results["queued"] += 1
            elif call_result["status"] == CallStatus.BLOCKED.value:
                results["blocked"] += 1
                
            results["details"].append({
                "call_id": call_result["call_id"],
                "phone_number": phone_number,
                "status": call_result["status"],
                "reason": call_result.get("last_error")
            })
            
        logger.info(f"Added batch of {len(calls)} calls, {results['queued']} queued, {results['blocked']} blocked")
        return results
    
    def _save_call_record(self, call_record: Dict):
        """Save a call record to the database"""
        if not self.db_conn:
            return
            
        try:
            if isinstance(self.db_conn, DatabaseAdapter):
                # Use adapter methods
                cursor = self.db_conn.execute("SELECT call_id FROM call_records WHERE call_id = ?", 
                              (call_record["call_id"],))
                exists = cursor.fetchone()
                
                if exists:
                    # Update existing record
                    self.db_conn.execute("""
                        UPDATE call_records SET
                        status = ?,
                        retry_count = ?,
                        scheduled_time = ?,
                        last_error = ?,
                        regulation_violation = ?,
                        updated_at = ?
                        WHERE call_id = ?
                    """, (
                        call_record["status"],
                        call_record.get("retry_count", 0),
                        call_record.get("scheduled_time", datetime.datetime.now().isoformat()),
                        call_record.get("last_error"),
                        call_record.get("regulation_violation"),
                        datetime.datetime.now().isoformat(),
                        call_record["call_id"]
                    ))
                else:
                    # Insert new record
                    self.db_conn.execute("""
                        INSERT INTO call_records (
                            call_id, phone_number, business_type, caller_id,
                            status, retry_count, created_at, scheduled_time,
                            last_error, regulation_violation, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        call_record["call_id"],
                        call_record["phone_number"],
                        call_record["business_type"],
                        call_record["caller_id"],
                        call_record["status"],
                        call_record.get("retry_count", 0),
                        call_record.get("created_at", datetime.datetime.now().isoformat()),
                        call_record.get("scheduled_time", datetime.datetime.now().isoformat()),
                        call_record.get("last_error"),
                        call_record.get("regulation_violation"),
                        datetime.datetime.now().isoformat()
                    ))
                    
                self.db_conn.commit()
            else:
                # Backward compatibility with direct sqlite3 connection
                cursor = self.db_conn.cursor()
                cursor.execute(
                    self.db_conn.format_query("SELECT call_id FROM call_records WHERE call_id = ?"),
                    (call_record["call_id"],),
                )
                exists = cursor.fetchone()
                
                if exists:
                    cursor.execute(
                        self.db_conn.format_query("""
                        UPDATE call_records SET
                        status = ?,
                        retry_count = ?,
                        scheduled_time = ?,
                        last_error = ?,
                        regulation_violation = ?,
                        updated_at = ?
                        WHERE call_id = ?
                    """),
                        (
                        call_record["status"],
                        call_record.get("retry_count", 0),
                        call_record.get("scheduled_time", datetime.datetime.now().isoformat()),
                        call_record.get("last_error"),
                        call_record.get("regulation_violation"),
                        datetime.datetime.now().isoformat(),
                        call_record["call_id"]
                        ),
                    )
                else:
                    cursor.execute(
                        self.db_conn.format_query("""
                        INSERT INTO call_records (
                            call_id, phone_number, business_type, caller_id,
                            status, retry_count, created_at, scheduled_time,
                            last_error, regulation_violation, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """),
                        (
                        call_record["call_id"],
                        call_record["phone_number"],
                        call_record["business_type"],
                        call_record["caller_id"],
                        call_record["status"],
                        call_record.get("retry_count", 0),
                        call_record.get("created_at", datetime.datetime.now().isoformat()),
                        call_record.get("scheduled_time", datetime.datetime.now().isoformat()),
                        call_record.get("last_error"),
                        call_record.get("regulation_violation"),
                        datetime.datetime.now().isoformat()
                    ),
                    )
                    
                self.db_conn.commit()
        except Exception as e:
            logger.error(f"Error saving call record: {e}")
            if isinstance(self.db_conn, DatabaseAdapter):
                self.db_conn.rollback()
            else:
                self.db_conn.rollback()
    
    async def start_dialer(self):
        """Start the dialer system"""
        if self.running:
            logger.warning("Dialer system is already running")
            return
            
        self.running = True
        
        # Start the worker tasks
        self.background_tasks = [
            asyncio.create_task(self._dialer_worker()),
            asyncio.create_task(self._retry_scheduler()),
            asyncio.create_task(self._call_monitor())
        ]
        
        logger.info("Dialer system started")
    
    async def stop_dialer(self):
        """Stop the dialer system"""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel all background tasks
        for task in self.background_tasks:
            task.cancel()
            
        # Wait for tasks to complete
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        # Clear state
        self.background_tasks = []
        
        logger.info("Dialer system stopped")
    
    async def _dialer_worker(self):
        """Worker process that takes calls from the queue and initiates them"""
        try:
            while self.running:
                # Check if we can make more calls
                if len(self.active_calls) >= self.max_concurrent_calls:
                    # Sleep and check again
                    await asyncio.sleep(1)
                    continue
                
                # Get the next call from the queue
                try:
                    call = await asyncio.wait_for(self.call_queue.get(), timeout=2)
                except asyncio.TimeoutError:
                    # No calls in queue
                    await asyncio.sleep(1)
                    continue
                
                # Check if the call is scheduled for later
                if call["scheduled_time"] > datetime.datetime.now():
                    # Put it back in the queue
                    await self.call_queue.put(call)
                    await asyncio.sleep(1)
                    continue
                
                # Make the call
                asyncio.create_task(self._make_call(call))
                
                # Small delay to avoid hammering the Twilio API
                await asyncio.sleep(0.5)
                
        except asyncio.CancelledError:
            logger.info("Dialer worker task cancelled")
        except Exception as e:
            logger.error(f"Error in dialer worker: {e}")
    
    async def _retry_scheduler(self):
        """Scheduler that moves retry calls to the main queue when ready"""
        try:
            while self.running:
                # Check retry queue
                now = datetime.datetime.now()
                retry_ready = [call for call in self.retry_queue if call["scheduled_time"] <= now]
                
                # Move ready calls to main queue
                for call in retry_ready:
                    # Update status
                    call["status"] = CallStatus.QUEUED.value
                    
                    # Update in database
                    self._save_call_record({
                        "call_id": call["call_id"],
                        "status": CallStatus.QUEUED.value,
                        "scheduled_time": now.isoformat()
                    })
                    
                    # Add to queue
                    await self.call_queue.put(call)
                    
                    # Remove from retry queue
                    self.retry_queue.remove(call)
                    
                    logger.info(f"Moved call {call['call_id']} from retry queue to main queue")
                
                # Sleep before checking again
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("Retry scheduler task cancelled")
        except Exception as e:
            logger.error(f"Error in retry scheduler: {e}")
    
    async def _call_monitor(self):
        """Monitor active calls for timeouts"""
        try:
            while self.running:
                # Get all active calls
                active_calls = self.active_calls.copy()
                
                for call_id in active_calls:
                    call_info = self.call_history.get(call_id)
                    if not call_info:
                        continue
                        
                    # Check for timeout
                    if (call_info["status"] == CallStatus.IN_PROGRESS.value and
                        (datetime.datetime.now() - call_info["started_at"]).total_seconds() > self.call_timeout_seconds):
                        # Call timed out
                        logger.warning(f"Call {call_id} timed out after {self.call_timeout_seconds} seconds")
                        
                        # Handle timeout as no-answer
                        await self._handle_call_result(
                            call_id, 
                            CallStatus.NO_ANSWER.value, 
                            "Call timed out, no answer"
                        )
                
                # Sleep before checking again
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("Call monitor task cancelled")
        except Exception as e:
            logger.error(f"Error in call monitor: {e}")
    
    async def _make_call(self, call: Dict):
        """
        Make an outbound call.
        
        Args:
            call: Call details dict
        """
        call_id = call["call_id"]
        phone_number = call["phone_number"]
        business_type = call["business_type"]
        caller_id = call["caller_id"]
        retry_count = call["retry_count"]
        
        # Add to active calls and history
        self.active_calls.add(call_id)
        self.call_history[call_id] = {
            "call_id": call_id,
            "phone_number": phone_number,
            "business_type": business_type,
            "caller_id": caller_id,
            "retry_count": retry_count,
            "status": CallStatus.IN_PROGRESS.value,
            "started_at": datetime.datetime.now(),
            "twilio_call_sid": None,
            "conversation": []  # Added conversation history
        }
        
        # Update database
        self._save_call_record({
            "call_id": call_id,
            "status": CallStatus.IN_PROGRESS.value,
            "updated_at": datetime.datetime.now().isoformat()
        })
        
        logger.info(f"Starting call {call_id} to {phone_number} (via DialerSystem)")
        
        actual_twilio_sid = None
        error = None

        try:
            if self.twilio_client and TWILIO_AVAILABLE and self.ngrok_websocket_url:
                from twilio.twiml.voice_response import VoiceResponse, Connect, Stream

                # Construct TwiML to connect to WebSocket stream (optional: voice_name + scripted for Version A)
                response = VoiceResponse()
                connect = Connect()
                voice_name = call.get("voice_name") or os.environ.get("DIALER_SCRIPTED_VOICE_NAME", "")
                use_scripted = call.get("scripted")
                scripted_mode = use_scripted if use_scripted is not None else (os.environ.get("DIALER_SCRIPTED_MODE", "").lower() in ("true", "1", "yes"))
                stream_url = f"{self.ngrok_websocket_url}/ws/stream?business_type={quote_plus(business_type or '')}&call_id={quote_plus(call_id)}"
                if voice_name:
                    stream_url += f"&voice_name={quote_plus(voice_name)}"
                if scripted_mode:
                    stream_url += "&scripted=1"
                connect.append(Stream(url=stream_url))
                response.append(connect)
                response.pause(length=60)

                logger.debug(f"[{call_id}] DialerSystem TwiML for WebSocket: {str(response)}")

                twilio_call = self.twilio_client.calls.create(
                    to=phone_number,
                    from_=caller_id,
                    twiml=str(response),
                    status_callback=f"{self.twilio_webhook_url}/status/{call_id}",
                    machine_detection='Enable',
                )
                actual_twilio_sid = twilio_call.sid
                logger.info(f"Initiated Twilio call {actual_twilio_sid} (for internal ID {call_id}) to connect to WebSocket.")

                self.call_history[call_id]["twilio_call_sid"] = actual_twilio_sid
                
            elif not self.ngrok_websocket_url:
                error = "NGROK_WEBSOCKET_URL not configured in DialerSystem. Cannot make stream calls."
                logger.error(f"[{call_id}] {error}")
                await self._handle_call_result(call_id, CallStatus.FAILED.value, error)
                return
            else:
                logger.info(f"Simulating call {call_id} to {phone_number} (DialerSystem)")
                await asyncio.sleep(5)
                await self._handle_call_result(call_id, CallStatus.COMPLETED.value, "Simulated call completed")

        except TwilioRestException as e:
            error = f"Twilio error: {e.msg}"
            logger.error(f"Twilio error making call {call_id}: {e}")
            await self._handle_call_result(call_id, CallStatus.FAILED.value, error)
        except Exception as e:
            error = str(e)
            logger.error(f"Error making call {call_id}: {e}", exc_info=True)
            await self._handle_call_result(call_id, CallStatus.FAILED.value, error)
    
    async def _handle_call_result(self, call_id: str, status: str, error: Optional[str] = None):
        """
        Handle call result and determine if retry is needed.
        
        Args:
            call_id: Call ID
            status: Call status from CallStatus enum
            error: Error message if any
        """
        if call_id not in self.call_history:
            logger.warning(f"Call {call_id} not found in history")
            return
            
        call_info = self.call_history[call_id]
        
        # Update call status in memory
        call_info["status"] = status
        call_info["ended_at"] = datetime.datetime.now()
        
        if error:
            call_info["last_error"] = error
            
        # Remove from active calls set
        if call_id in self.active_calls:
            self.active_calls.remove(call_id)
            
        needs_retry = False
        if status in [CallStatus.FAILED.value, CallStatus.NO_ANSWER.value, CallStatus.BUSY.value, CallStatus.MACHINE_DETECTED.value]:
            if call_info["retry_count"] < self.max_retries:
                needs_retry = True
                
        db_update_payload = {
            "call_id": call_id,
            "status": status, # This might be updated to final_status later
            "last_error": error,
            "updated_at": datetime.datetime.now().isoformat()
        }

        if needs_retry:
            retry_count = call_info["retry_count"] + 1
            retry_delay = self.retry_delay_seconds * (2 ** (retry_count - 1))
            scheduled_time = datetime.datetime.now() + datetime.timedelta(seconds=retry_delay)
            
            retry_item = {
                "call_id": call_id,
                "phone_number": call_info["phone_number"],
                "business_type": call_info["business_type"],
                "caller_id": call_info["caller_id"],
                "retry_count": retry_count,
                "scheduled_time": scheduled_time,
                "status": CallStatus.RETRY_SCHEDULED.value
            }
            self.retry_queue.append(retry_item)
            
            db_update_payload["status"] = CallStatus.RETRY_SCHEDULED.value
            db_update_payload["retry_count"] = retry_count
            db_update_payload["scheduled_time"] = scheduled_time.isoformat()
            
            logger.info(f"Scheduled retry #{retry_count} for call {call_id} at {scheduled_time}")
            
        else: # Call is being finalized (not retried)
            final_status = status
            if status == CallStatus.MACHINE_DETECTED.value and call_info["retry_count"] >= self.max_retries:
                final_status = CallStatus.COMPLETED.value 
            
            db_update_payload["status"] = final_status
            db_update_payload["completed_at"] = datetime.datetime.now().isoformat()

            # Save conversation history for finalized calls
            conversation_json = None
            if 'conversation' in call_info and call_info['conversation']:
                try:
                    conversation_json = json.dumps(call_info['conversation'])
                except TypeError as e:
                    logger.error(f"[{call_id}] Could not serialize conversation history to JSON: {e}")
            db_update_payload["conversation_history"] = conversation_json
            
            # Twilio call termination logic (if applicable)
            if self.twilio_client and call_info.get("twilio_call_sid") and TWILIO_AVAILABLE:
                actual_twilio_sid = call_info.get("twilio_call_sid")
                if status in [CallStatus.NO_ANSWER.value, CallStatus.FAILED.value, CallStatus.BLOCKED.value] or \
                   (status == CallStatus.MACHINE_DETECTED.value and final_status == CallStatus.COMPLETED.value):
                    logger.info(f"[{call_id}] DialerSystem is finalizing call with status '{status}'. Attempting to update Twilio call {actual_twilio_sid} to 'completed' via REST API.")
                    try:
                        self.twilio_client.calls(actual_twilio_sid).update(status="completed")
                        logger.info(f"[{call_id}] Successfully updated Twilio call {actual_twilio_sid} to 'completed' via REST API.")
                    except TwilioRestException as tre:
                        if tre.status == 404:
                            logger.warning(f"[{call_id}] Twilio call {actual_twilio_sid} not found (404) when trying to update via REST. Assumed already terminated.")
                        else:
                            logger.error(f"[{call_id}] TwilioRestException trying to update call {actual_twilio_sid} to 'completed': {tre}", exc_info=True)
                    except Exception as e:
                        logger.error(f"[{call_id}] Generic error updating Twilio call {actual_twilio_sid} to 'completed' via REST: {e}", exc_info=True)
            
            logger.info(f"Call {call_id} finalized in DialerSystem with internal status {final_status} (original trigger status: {status}).")
        
        # Save the consolidated payload to DB
        self._save_call_record(db_update_payload)
    
    async def handle_twilio_webhook(self, request_data: Dict) -> Dict:
        """
        Handle Twilio webhook for call status updates.
        
        Args:
            request_data: Webhook data from Twilio
            
        Returns:
            Dict with TwiML response
        """
        call_sid_twilio = request_data.get("CallSid")
        call_status = request_data.get("CallStatus")
        answered_by = request_data.get("AnsweredBy")
        
        call_id = None
        for cid, info in self.call_history.items():
            if info.get("twilio_call_sid") == call_sid_twilio:
                call_id = cid
                break
                
        if not call_id:
            logger.warning(f"Unknown Twilio call SID: {call_sid_twilio}")
            return {"twiml": "<Response><Say>Call not found</Say><Hangup/></Response>"}
        
        call_info = self.call_history[call_id]

        if call_status == "in-progress":
            if answered_by == "machine_start" or answered_by == "machine_end":
                logger.info(f"Answering machine detected for call {call_id}")
                await self._handle_call_result(call_id, CallStatus.MACHINE_DETECTED.value, "Answering machine detected")
                return {"twiml": "<Response><Hangup/></Response>"}
                
            twiml_response = await self._generate_twiml_for_call(call_id)
            return {"twiml": twiml_response}
            
        elif call_status == "completed":
            await self._handle_call_result(call_id, CallStatus.COMPLETED.value)
        elif call_status == "busy":
            await self._handle_call_result(call_id, CallStatus.BUSY.value, "Line busy")
        elif call_status == "no-answer":
            await self._handle_call_result(call_id, CallStatus.NO_ANSWER.value, "No answer")
        elif call_status == "failed":
            error = request_data.get("ErrorMessage", "Unknown error")
            await self._handle_call_result(call_id, CallStatus.FAILED.value, error)
            
        return {"twiml": "<Response></Response>"}
    
    async def _generate_twiml_for_call(self, call_id: str) -> str:
        """
        Generate TwiML for an active call. Handles initial greeting or continuation.
        
        Args:
            call_id: Call ID
            
        Returns:
            TwiML XML string
        """
        if call_id not in self.call_history:
            logger.error(f"[{call_id}] Call ID not found in call_history for TwiML generation.")
            return "<Response><Say>Error: Call session not found.</Say><Hangup/></Response>"
            
        call_info = self.call_history[call_id]
        business_type = call_info.get("business_type", "MM")
        ai_response_text = ""
        
        try:
            if not call_info.get("conversation"): 
                logger.info(f"[{call_id}] Empty conversation history. Generating initial greeting.")
                greeting = await self.llm_handler.get_initial_greeting(call_sid=call_id, business_type=business_type)
                if not greeting:
                    logger.error(f"[{call_id}] LLMHandler returned no initial greeting. Using fallback.")
                    greeting = "Hello, this is Proactiv. Is the business owner available?"
                call_info["conversation"] = [{'role': 'assistant', 'content': greeting}]
                ai_response_text = greeting
                logger.info(f"[{call_id}] Initial greeting: {ai_response_text}")
            else:
                last_message = call_info["conversation"][-1]
                if last_message['role'] == 'assistant':
                    ai_response_text = last_message['content']
                    logger.info(f"[{call_id}] Continuing conversation. Last AI response: {ai_response_text}")
                else: 
                    logger.error(f"[{call_id}] Last message in history is not from assistant. History: {call_info['conversation']}")
                    ai_response_text = "I'm sorry, I lost my place. Could you remind me what we were talking about?"
                    call_info["conversation"].append({'role': 'assistant', 'content': ai_response_text})

            webhook_base_url = self.ngrok_websocket_url if self.ngrok_websocket_url else self.twilio_webhook_url
            if not webhook_base_url:
                logger.error(f"[{call_id}] Webhook URL not set. Cannot form action URL for Gather.")
                return "<Response><Say>Configuration error: Webhook URL not set.</Say><Hangup/></Response>"

            action_url_input = f"{webhook_base_url}/input/{call_id}"
            redirect_url_no_input = f"{webhook_base_url}/input/{call_id}?SpeechResult=" 

            from xml.sax.saxutils import escape
            safe_ai_response_text = escape(ai_response_text)

            twiml = (
                f'<Response>'
                f'<Say voice="Polly.Amy" language="en-GB">{safe_ai_response_text}</Say>'
                f'<Gather input="speech" timeout="7" speechTimeout="auto" action="{action_url_input}" method="POST"></Gather>'
                f'<Say voice="Polly.Amy" language="en-GB">I\'m sorry, I didn\'t catch that.</Say>'
                f'<Redirect method="POST">{redirect_url_no_input}</Redirect>'
                f'</Response>'
            )
            return twiml
            
        except Exception as e:
            logger.error(f"Error generating TwiML for call {call_id}: {e}", exc_info=True)
            return "<Response><Say>An error occurred while preparing my response.</Say><Hangup/></Response>"
    
    async def handle_twilio_input(self, call_id: str, input_data: Dict) -> Dict:
        """
        Handle user input from Twilio (SpeechResult or timeout from Gather).
        """
        if call_id not in self.call_history:
            logger.warning(f"[{call_id}] Unknown call ID in handle_twilio_input.")
            return {"twiml": "<Response><Say>Call session not found.</Say><Hangup/></Response>"}
            
        call_info = self.call_history[call_id]
        conversation_history = call_info.get("conversation", [])
        business_type = call_info.get("business_type", "MM")
        user_input = input_data.get("SpeechResult", "").strip()
        current_llm_state = 1 
        
        if not user_input:
            logger.info(f"[{call_id}] No speech input received (timeout).")
            current_llm_state = 0
        else:
            logger.info(f"[{call_id}] User input: {user_input}")
            conversation_history.append({'role': 'user', 'content': user_input})

        try:
            raw_response_text, should_hangup = await self.llm_handler.generate_response(
                call_sid=call_id, transcript=user_input, 
                conversation_history=conversation_history, 
                business_type=business_type, state=current_llm_state 
            )
            
            # Process LEAD_EVENT tag before finalizing response_text for speech
            spoken_response_text = raw_response_text
            lead_event_match = re.search(r"\[LEAD_EVENT:([^|]+)\|PAYLOAD:({.*?})\]$", raw_response_text, re.DOTALL)
            
            if lead_event_match:
                event_type = lead_event_match.group(1)
                payload_str = lead_event_match.group(2)
                logger.info(f"[{call_id}] Parsed LEAD_EVENT: Type={event_type}, Payload={payload_str}")
                
                # Remove the tag from the text that will be spoken
                spoken_response_text = raw_response_text[:lead_event_match.start()].strip()
                
                try:
                    payload = json.loads(payload_str)
                    await self._handle_lead_event(call_id, call_info, event_type, payload)
                except json.JSONDecodeError as e:
                    logger.error(f"[{call_id}] Failed to parse LEAD_EVENT payload JSON: {payload_str}. Error: {e}")
                except Exception as e:
                    logger.error(f"[{call_id}] Error handling lead event {event_type}: {e}", exc_info=True)

            if not spoken_response_text: # If tag was the only thing, or LLM returned empty before tag
                if raw_response_text and not lead_event_match: # LLM returned empty actual response
                     logger.error(f"[{call_id}] LLM returned empty spoken_response_text. Raw: {raw_response_text}. Using fallback.")
                elif lead_event_match and not spoken_response_text: # Tag was there, but no spoken part
                     logger.info(f"[{call_id}] LEAD_EVENT tag processed, but no preceding spoken text. Using generic ack if not hanging up.")
                
                if not should_hangup:
                    spoken_response_text = "Okay, I've noted that down."
                else: # If hanging up, and no spoken text, use a generic farewell from tag or default
                    if event_type == "APPOINTMENT_BOOKED": spoken_response_text = "Great, your appointment is set. We look forward to speaking with you!"
                    elif event_type == "NOT_INTERESTED" or event_type == "LEAD_CLOSED_LOST": spoken_response_text = "Alright, thank you for your time. Goodbye."
                    else: spoken_response_text = "Thank you. Goodbye."
            
            conversation_history.append({'role': 'assistant', 'content': spoken_response_text}) # Save the cleaned spoken response
            if lead_event_match: # Also log the raw response with tag for debugging/transparency if needed
                 conversation_history.append({'role': 'system', 'content': f'Raw LLM response with tag: {raw_response_text}'}) 

            call_info['conversation'] = conversation_history
            
            from xml.sax.saxutils import escape
            safe_spoken_response_text = escape(spoken_response_text)

            if should_hangup:
                logger.info(f"[{call_id}] LLM indicated hangup. AI Response (spoken): {spoken_response_text}")
                twiml = f'<Response><Say voice="Polly.Amy" language="en-GB">{safe_spoken_response_text}</Say><Hangup/></Response>'
                return {"twiml": twiml}
            else:
                logger.info(f"[{call_id}] Continuing call. AI Response (spoken): {spoken_response_text}")
                twiml_response = await self._generate_twiml_for_call(call_id)
                return {"twiml": twiml_response}
            
        except Exception as e:
            logger.error(f"[{call_id}] Error processing user input with LLM: {e}", exc_info=True)
            return {"twiml": "<Response><Say>I'm sorry, an error occurred on my end.</Say><Hangup/></Response>"}
    
    async def _handle_lead_event(self, call_id: str, call_info: Dict, event_type: str, payload: Dict):
        """Handles recognized lead events by creating/updating LeadRecord."""
        logger.info(f"[{call_id}] Handling lead event: {event_type} with payload: {payload}")

        lead_id = f"LD{uuid.uuid4().hex[:12].upper()}" # Generate a new lead ID
        now_iso = datetime.datetime.now().isoformat()

        lead_data = {
            "lead_id": lead_id,
            "call_id": call_id,
            "phone_number": call_info.get("phone_number"),
            "business_type": call_info.get("business_type"),
            "contact_name": payload.get("contact_name"),
            "appointment_time": payload.get("appointment_time"),
            "notes": payload.get("notes", payload.get("reason")),
            "created_at": now_iso,
            "updated_at": now_iso,
            # We might add a specific 'lead_status' field to LeadRecord later
            # For now, event_type and notes cover this.
        }

        # For specific event types, update fields more directly
        if event_type == "APPOINTMENT_BOOKED":
            lead_data["notes"] = f"Appointment booked. Details: {payload.get('notes', 'N/A')}"
            # Potentially update call_record status too, if we add a field for it
        elif event_type == "OWNER_IDENTIFIED":
            # Could update a master contact list or just note it here
            if not lead_data["notes"]:
                 lead_data["notes"] = f"Owner identified: {payload.get('contact_name')}"
            else:
                 lead_data["notes"] += f"; Owner identified: {payload.get('contact_name')}"
        elif event_type == "NOT_INTERESTED" or event_type == "LEAD_CLOSED_LOST":
            if not lead_data["notes"]:
                 lead_data["notes"] = f"Lead status: {event_type}. Reason: {payload.get('reason', 'N/A')}"
            else:
                 lead_data["notes"] += f"; Lead status: {event_type}. Reason: {payload.get('reason', 'N/A')}"
        
        # Use the LeadRecord class to save (assuming it exists and has a save method)
        # This part depends on the implementation of LeadRecord.save() from models.py
        # For now, let's assume direct DB interaction for simplicity of this step.
        if not self.db_conn:
            logger.error(f"[{call_id}] No DB connection, cannot save lead record for event {event_type}")
            return

        try:
            cursor = self.db_conn.cursor()
            # Check if a lead for this call_id already exists, if so, update, else insert
            cursor.execute(
                self.db_conn.format_query("SELECT lead_id FROM lead_records WHERE call_id = ?"),
                (call_id,),
            )
            existing_lead = cursor.fetchone()

            if existing_lead:
                existing_lead_id = existing_lead["lead_id"] if isinstance(existing_lead, dict) else existing_lead[0]
                lead_data.pop("created_at", None) # Don't update created_at
                lead_data.pop("lead_id", None)
                lead_data.pop("call_id", None)
                lead_data.pop("phone_number", None)
                lead_data.pop("business_type", None)

                set_clause = ", ".join([f"{key} = ?" for key in lead_data.keys()])
                params = list(lead_data.values()) + [existing_lead_id]
                
                sql = self.db_conn.format_query(f"UPDATE lead_records SET {set_clause} WHERE lead_id = ?")
                cursor.execute(sql, params)
                logger.info(f"[{call_id}] Updated existing lead record {existing_lead_id} for event {event_type}.")
            else:
                columns = ", ".join(lead_data.keys())
                placeholders = ", ".join(["?" for _ in lead_data.keys()])
                sql = self.db_conn.format_query(f"INSERT INTO lead_records ({columns}) VALUES ({placeholders})")
                cursor.execute(sql, list(lead_data.values()))
                logger.info(f"[{call_id}] Created new lead record {lead_id} for event {event_type}.")
            
            self.db_conn.commit()

        except sqlite3.Error as e:
            logger.error(f"[{call_id}] Database error handling lead event {event_type}: {e}", exc_info=True)
            self.db_conn.rollback()
        except Exception as e:
            logger.error(f"[{call_id}] Unexpected error handling lead event {event_type}: {e}", exc_info=True)
            # No rollback here as it might not be a db error
    
    async def get_call_details(self, call_id: str) -> Optional[Dict]:
        """
        Get details for a specific call.
        
        Args:
            call_id: Call ID
            
        Returns:
            Dict with call details or None if not found
        """
        if call_id in self.call_history:
            return self.call_history[call_id]
            
        # Try to get from database
        if not self.db_conn:
            return None
            
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                self.db_conn.format_query("SELECT * FROM call_records WHERE call_id = ?"),
                (call_id,),
            )
            call_record = cursor.fetchone()
            
            if call_record:
                return dict(call_record)
                
        except Exception as e:
            logger.error(f"Error getting call details for {call_id}: {e}")
            
        return None
    
    async def get_queue_status(self) -> Dict:
        """
        Get status of the call queue.
        
        Returns:
            Dict with queue status information
        """
        return {
            "queued_calls": self.call_queue.qsize(),
            "active_calls": len(self.active_calls),
            "retry_calls": len(self.retry_queue),
            "max_concurrent_calls": self.max_concurrent_calls
        }
    
    async def get_recent_calls(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """
        Get a list of recent calls.
        
        Args:
            limit: Maximum number of calls to return
            offset: Offset for pagination
            
        Returns:
            List of call records
        """
        if not self.db_conn:
            # Return from memory if no database
            calls = list(self.call_history.values())
            calls.sort(key=lambda x: x.get("started_at", datetime.datetime.now()), reverse=True)
            return calls[offset:offset+limit]
            
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                self.db_conn.format_query("""
                SELECT * FROM call_records 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """),
                (limit, offset),
            )
            
            call_records = cursor.fetchall()
            return [dict(record) for record in call_records]
            
        except Exception as e:
            logger.error(f"Error getting recent calls: {e}")
            return []
    
    async def get_leads(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """
        Get a list of generated leads.
        
        Args:
            limit: Maximum number of leads to return
            offset: Offset for pagination
            
        Returns:
            List of lead records
        """
        if not self.db_conn:
            return []
            
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                self.db_conn.format_query("""
                SELECT * FROM lead_records 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """),
                (limit, offset),
            )
            
            lead_records = cursor.fetchall()
            return [dict(record) for record in lead_records]
            
        except Exception as e:
            logger.error(f"Error getting leads: {e}")
            return []
    
    async def get_dialer_settings(self) -> Dict:
        """
        Get current dialer settings.
        
        Returns:
            Dict with dialer settings
        """
        return {
            "max_concurrent_calls": self.max_concurrent_calls,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "call_timeout_seconds": self.call_timeout_seconds
        }
    
    async def update_dialer_settings(self, settings: Dict) -> Dict:
        """
        Update dialer settings.
        
        Args:
            settings: Dict with settings to update
            
        Returns:
            Dict with updated settings
        """
        if "max_concurrent_calls" in settings:
            self.max_concurrent_calls = int(settings["max_concurrent_calls"])
            
        if "max_retries" in settings:
            self.max_retries = int(settings["max_retries"])
            
        if "retry_delay_seconds" in settings:
            self.retry_delay_seconds = int(settings["retry_delay_seconds"])
            
        if "call_timeout_seconds" in settings:
            self.call_timeout_seconds = int(settings["call_timeout_seconds"])
            
        logger.info(f"Updated dialer settings: {settings}")
        return await self.get_dialer_settings()
    
    async def cleanup(self):
        """Clean up resources used by the dialer system"""
        await self.stop_dialer()
        # await self.regulations_manager.cleanup() # This was also commented out, ensure it's intended
        if self.db_adapter:
            self.db_adapter.close()
            self.db_adapter = None
        if self.db_conn:
            # Only close if it's a direct sqlite3 connection (not the adapter)
            if isinstance(self.db_conn, sqlite3.Connection):
                self.db_conn.close()
            self.db_conn = None
            
        logger.info("Dialer system resources cleaned up") 