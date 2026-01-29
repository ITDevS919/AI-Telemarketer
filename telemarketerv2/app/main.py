from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file at the very beginning

import asyncio
from contextlib import asynccontextmanager
import logging
from typing import Dict, List, Any, Optional
import base64 # Added for audio processing
import audioop  # Added for mu-law to PCM conversion
import json     # Added for parsing WebSocket messages
from pathlib import Path # Added for checking file paths
import os # For reading environment variables for configuration

from fastapi import FastAPI, HTTPException, Body, Path as FastApiPath, WebSocket, WebSocketDisconnect # Added WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse # Or XMLResponse
import uvicorn
from pydantic import BaseModel # Import BaseModel

# Assuming your DialerSystem and related enums/models are accessible
# Adjust these imports based on your actual project structure
from .dialer_system import DialerSystem, CallStatus 
# If LLMHandler is needed directly by API (e.g. for specific non-dialer tasks)
# from .llm_handler import LLMHandler 
from .database.models import LeadRecord, CallRecord # For Pydantic models if needed, or direct dicts
from .tts_handler import TTSHandler # Needed to send audio back
from .stt_handler import STTHandler # Placeholder for your STT engine
from .vad_handler import VADHandler # Placeholder for your VAD engine
from .conversation_manager import ConversationManager # To manage conversation flow

# For audio resampling
import torch
import torchaudio.functional as F


# Configure logging
logger = logging.getLogger("uvicorn.error") # Use Uvicorn's logger for API logs

# --- Global Handler Instances ---
# These will be initialized in the lifespan manager
dialer_system_instance: Optional[DialerSystem] = None
tts_handler_instance: Optional[TTSHandler] = None
stt_handler_instance: Optional[STTHandler] = None
vad_handler_instance: Optional[VADHandler] = None
conversation_manager_instance: Optional[ConversationManager] = None

# --- FastAPI Application Lifespan (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global dialer_system_instance, tts_handler_instance, stt_handler_instance, vad_handler_instance, conversation_manager_instance
    logger.info("FastAPI application startup...")
    
    # --- DialerSystem Initialization ---
    # Support both DATABASE_URL (PostgreSQL) and DB_PATH (SQLite)
    database_url = os.getenv("DATABASE_URL")
    db_path = database_url if database_url else os.getenv("DB_PATH", "telemarketer_calls.db")
    dialer_system_instance = DialerSystem(db_path=db_path)
    try:
        await dialer_system_instance.initialize()
        logger.info("DialerSystem initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize DialerSystem: {e}", exc_info=True)
        # Decide if this is critical enough to stop startup

    # --- TTSHandler Initialization ---
    # Construct an absolute default path for the Piper model relative to this script's location
    # main.py is in telemarketerv2/app/, models are in telemarketerv2/data/models/
    _main_script_dir = Path(__file__).resolve().parent # .../telemarketerv2/app
    _telemarketer_v2_dir = _main_script_dir.parent    # .../telemarketerv2
    default_model_filename = "en_GB-northern_english_male-medium.onnx"
    default_piper_model_abs_path_str = str(_telemarketer_v2_dir / "data" / "models" / default_model_filename)

    # Get path from environment variable or use the robust absolute default
    piper_model_path_to_check = os.getenv("PIPER_MODEL_PATH", default_piper_model_abs_path_str)
    
    try:
        from piper.voice import PiperVoice # Assuming PiperVoice is how you load it
        
        model_path_obj = Path(piper_model_path_to_check)
        # Config path is the model path with .onnx replaced by .onnx.json, or just .json appended if no .onnx
        if model_path_obj.suffix == ".onnx":
            config_path_obj = model_path_obj.with_suffix(".onnx.json")
        else:
            # If the provided path doesn't end in .onnx, assume it's a base name
            # and append .json for config. This might need adjustment based on actual Piper needs.
            config_path_obj = model_path_obj.with_suffix(".json")


        # Enhanced logging for debugging
        logger.info(f"Attempting to load Piper TTS model from: {model_path_obj.resolve()}")
        logger.info(f"Attempting to load Piper TTS config from: {config_path_obj.resolve()}")
        logger.info(f"Current working directory for path resolution: {Path.cwd()}")
        if "PIPER_MODEL_PATH" in os.environ:
            logger.info(f"PIPER_MODEL_PATH environment variable was set to: '{os.environ['PIPER_MODEL_PATH']}'")
        else:
            logger.info(f"PIPER_MODEL_PATH environment variable was NOT set, using default path logic resulting in: '{default_piper_model_abs_path_str}'")

        if not model_path_obj.exists() or not config_path_obj.exists():
            err_msg = f"Piper model ({model_path_obj.name}) or config ({config_path_obj.name}) not found. "
            err_msg += f"Searched ONNX at '{model_path_obj.resolve()}' (exists: {model_path_obj.exists()}) "
            err_msg += f"and JSON at '{config_path_obj.resolve()}' (exists: {config_path_obj.exists()}). TTS will not work."
            logger.error(err_msg)
        else:
            piper_voice_instance = PiperVoice.load(str(model_path_obj)) # PiperVoice.load expects a string path
            tts_handler_instance = TTSHandler(tts_voice=piper_voice_instance)
            logger.info(f"TTSHandler initialized successfully with model: {model_path_obj}")
    except ImportError:
        logger.error("Piper TTS library not found. Please install it for TTS functionality.")
    except Exception as e:
        logger.error(f"Failed to initialize TTSHandler: {e}", exc_info=True)

    # --- VADHandler Initialization (Configurable) ---
    try:
        vad_sample_rate = int(os.getenv("VAD_SAMPLE_RATE", "16000"))
        vad_threshold = float(os.getenv("VAD_THRESHOLD", "0.5"))

        vad_handler_instance = VADHandler(
            sample_rate=vad_sample_rate,
            threshold=vad_threshold
        )
        logger.info("VADHandler initialized successfully.")
    except ValueError as ve:
        logger.error(f"Invalid VAD configuration parameter: {ve}. VAD will not work correctly.", exc_info=True)
    except Exception as e:
        logger.error(f"Failed to initialize VADHandler: {e}", exc_info=True)

    # --- STTHandler Initialization (Configurable) ---
    try:
        stt_model_name = os.getenv("STT_MODEL_NAME", "base.en") # e.g., tiny.en, base.en, small.en
        stt_device = os.getenv("STT_DEVICE") # e.g., "cpu", "cuda", or None for auto-detect

        stt_handler_instance = STTHandler(model_name=stt_model_name, device=stt_device)
        logger.info("STTHandler initialized successfully.") # Success/failure logged within STTHandler __init__
    except Exception as e:
        # STTHandler's __init__ already logs errors if model loading fails
        logger.error(f"General error during STTHandler setup in main.py: {e}", exc_info=True)

    # --- ConversationManager Initialization ---
    try:
        # Robust absolute path for the default script, similar to TTS model
        _default_script_filename = "5_steps_script.md"
        _default_cm_script_abs_path_str = str(_telemarketer_v2_dir / "data" / "scripts" / _default_script_filename) # _telemarketer_v2_dir defined in TTS section

        cm_script_path_to_check = os.getenv("CM_SCRIPT_PATH", _default_cm_script_abs_path_str)
        
        # Enhanced logging for script path
        logger.info(f"Attempting to initialize ConversationManager with script path: {Path(cm_script_path_to_check).resolve()}")
        if "CM_SCRIPT_PATH" in os.environ:
            logger.info(f"CM_SCRIPT_PATH environment variable was set to: '{os.environ['CM_SCRIPT_PATH']}'")
        else:
            logger.info(f"CM_SCRIPT_PATH environment variable was NOT set, using default path logic resulting in: '{_default_cm_script_abs_path_str}'")

        if tts_handler_instance and dialer_system_instance and dialer_system_instance.llm_handler:
            conversation_manager_instance = ConversationManager(
                llm_handler=dialer_system_instance.llm_handler,
                tts_handler=tts_handler_instance,
                script_path=cm_script_path_to_check # Use the potentially absolute path
            )
            # The ConversationManager itself should log if the script file is actually found and loaded successfully.
            # We rely on its internal logging for confirmation of successful script loading.
            logger.info(f"ConversationManager instance created. Check ConversationManager logs for script loading status from path: {cm_script_path_to_check}")
        else:
            missing_deps = []
            if not tts_handler_instance: missing_deps.append("TTSHandler")
            if not dialer_system_instance: missing_deps.append("DialerSystem")
            elif not dialer_system_instance.llm_handler: missing_deps.append("LLMHandler from DialerSystem")
            logger.error(f"Cannot initialize ConversationManager due to missing dependencies: {', '.join(missing_deps)}.")
    except Exception as e:
        logger.error(f"Failed to initialize ConversationManager: {e}", exc_info=True)

    yield
    
    logger.info("FastAPI application shutdown...")
    if dialer_system_instance:
        try:
            await dialer_system_instance.cleanup()
            logger.info("DialerSystem cleaned up successfully.")
        except Exception as e:
            logger.error(f"Error during DialerSystem cleanup: {e}", exc_info=True)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="AI Telemarketer V2 API",
    description="API for managing the AI Telemarketer system, calls, and leads.",
    version="0.2.0",
    lifespan=lifespan
)

# --- CORS Middleware ---
# Adjust origins as necessary for your frontend's URL (e.g., http://localhost:5173 for Vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for now, restrict in production
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- Helper Function to Get DialerSystem ---
def get_dialer_system() -> DialerSystem:
    if dialer_system_instance is None or not hasattr(dialer_system_instance, 'initialized') or not dialer_system_instance.initialized:
        logger.error("DialerSystem instance is not available or not initialized.")
        raise HTTPException(status_code=503, detail="Dialer system is not initialized or is unavailable.")
    return dialer_system_instance

# --- API Endpoints ---

# Dialer Endpoints
@app.post("/api/dialer/start", tags=["Dialer"], summary="Start the Dialer System")
async def start_dialer_endpoint():
    dialer = get_dialer_system()
    if dialer.running:
        raise HTTPException(status_code=400, detail="Dialer is already running.")
    try:
        await dialer.start_dialer()
        return {"message": "Dialer system started successfully."}
    except Exception as e:
        logger.error(f"Error starting dialer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start dialer: {str(e)}")

@app.post("/api/dialer/stop", tags=["Dialer"], summary="Stop the Dialer System")
async def stop_dialer_endpoint():
    dialer = get_dialer_system()
    if not dialer.running:
        # Allow stopping even if not running, to ensure cleanup or reset state if needed
        # Could also be a 400 if strict: raise HTTPException(status_code=400, detail="Dialer is not running.")
        logger.info("Stop dialer called, but dialer was not running. Attempting cleanup anyway.")
    try:
        await dialer.stop_dialer() # stop_dialer should be idempotent
        return {"message": "Dialer system stopped successfully."}
    except Exception as e:
        logger.error(f"Error stopping dialer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stop dialer: {str(e)}")

@app.get("/api/dialer/status", tags=["Dialer"], summary="Get Dialer System Status")
async def get_dialer_status_endpoint() -> Dict[str, Any]:
    dialer = get_dialer_system()
    try:
        status = await dialer.get_queue_status() # Should include active_calls, queue_size
        status["running"] = dialer.running
        status["initialized"] = dialer.initialized
        return status
    except Exception as e:
        logger.error(f"Error getting dialer status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get dialer status: {str(e)}")

@app.get("/api/dialer/settings", tags=["Dialer"], summary="Get Dialer Settings")
async def get_dialer_settings_endpoint() -> Dict[str, Any]:
    dialer = get_dialer_system()
    try:
        return await dialer.get_dialer_settings()
    except Exception as e:
        logger.error(f"Error getting dialer settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get dialer settings: {str(e)}")

@app.put("/api/dialer/settings", tags=["Dialer"], summary="Update Dialer Settings")
async def update_dialer_settings_endpoint(settings: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    dialer = get_dialer_system()
    try:
        updated_settings = await dialer.update_dialer_settings(settings)
        return updated_settings
    except ValueError as ve: # Catch specific validation errors from DialerSystem
        logger.warning(f"Invalid settings provided: {ve}")
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"Error updating dialer settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update dialer settings: {str(e)}")

# Call Management Endpoints
class AddCallPayload(BaseModel): # Changed from Dict[str, Any] to BaseModel
    phone_number: str
    business_type: str
    caller_id: Optional[str] = None # Added default None for optional field

@app.post("/api/calls", tags=["Calls"], summary="Add a new call to the queue")
async def add_call_endpoint(payload: AddCallPayload = Body(...)) -> Dict[str, Any]:
    # FastAPI will now automatically validate the payload against the Pydantic model
    # You can access fields directly, e.g., payload.phone_number
    
    dialer = get_dialer_system()
    try:
        call_record_dict = await dialer.add_call(
            phone_number=payload.phone_number, # Access via attribute
            business_type=payload.business_type, # Access via attribute
            caller_id=payload.caller_id # Access via attribute
        )
        return call_record_dict
    except Exception as e:
        logger.error(f"Error adding call: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add call: {str(e)}")

@app.post("/api/calls/batch", tags=["Calls"], summary="Add multiple calls to the queue")
async def add_batch_calls_endpoint(calls: List[AddCallPayload] = Body(...)) -> Dict[str, Any]:
    if not calls:
        raise HTTPException(status_code=422, detail="Calls list cannot be empty")
    # Validation for each item in the list is handled by Pydantic

    dialer = get_dialer_system()
    try:
        # Convert Pydantic models to dicts if dialer.add_batch_calls expects a list of dicts
        # If it can handle Pydantic models directly, this conversion might not be needed.
        # For now, assuming it expects dicts as before.
        calls_as_dicts = [call.model_dump(exclude_none=True) for call in calls]
        batch_result = await dialer.add_batch_calls(calls_as_dicts)
        return batch_result
    except Exception as e:
        logger.error(f"Error adding batch calls: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add batch calls: {str(e)}")

@app.get("/api/calls/recent", tags=["Calls"], summary="Get recent call records")
async def get_recent_calls_endpoint(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    dialer = get_dialer_system()
    try:
        recent_calls = await dialer.get_recent_calls(limit=limit, offset=offset)
        return recent_calls
    except Exception as e:
        logger.error(f"Error getting recent calls: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get recent calls: {str(e)}")

@app.get("/api/calls/{call_id_path}", tags=["Calls"], summary="Get details for a specific call")
async def get_call_details_endpoint(call_id_path: str = FastApiPath(..., alias="call_id_path", description="The ID of the call to retrieve")) -> Dict[str, Any]:
    dialer = get_dialer_system()
    try:
        call_details = await dialer.get_call_details(call_id_path)
        if not call_details:
            raise HTTPException(status_code=404, detail="Call not found")
        return call_details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call details for {call_id_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get call details: {str(e)}")

# Lead Management Endpoints
@app.get("/api/leads", tags=["Leads"], summary="Get recent lead records")
async def get_leads_endpoint(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    dialer = get_dialer_system()
    try:
        leads = await dialer.get_leads(limit=limit, offset=offset)
        return leads
    except Exception as e:
        logger.error(f"Error getting leads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get leads: {str(e)}")

@app.get("/api/leads/{lead_id_path}", tags=["Leads"], summary="Get details for a specific lead")
async def get_lead_details_endpoint(lead_id_path: str = FastApiPath(..., alias="lead_id_path", description="The ID of the lead to retrieve")) -> Dict[str, Any]:
    dialer = get_dialer_system()
    try:
        # This assumes get_lead_by_id is implemented in DialerSystem or uses LeadRecord directly
        # and handles potential db connection issues or None returns cleanly.
        if not dialer.db_conn:
             raise HTTPException(status_code=503, detail="Database connection not available for leads.")
        lead = await asyncio.to_thread(LeadRecord.get_by_id, dialer.db_conn, lead_id_path)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return lead.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lead details for {lead_id_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get lead details: {str(e)}")

# Twilio Webhook Endpoints
@app.post("/twilio/status/{call_id_path}", tags=["Twilio Webhooks"], summary="Twilio Call Status Callback")
async def twilio_status_webhook(request_data: Dict = Body(...), call_id_path: str = FastApiPath(..., alias="call_id_path")):
    dialer = get_dialer_system()
    logger.info(f"Twilio status webhook for call_id {call_id_path}, data: {request_data}")
    try:
        # DialerSystem.handle_twilio_webhook returns a dict like {"twiml": "<Response>...</Response>"}
        response_content = await dialer.handle_twilio_webhook(request_data)
        twiml_str = response_content.get("twiml", "<Response></Response>")
        return PlainTextResponse(twiml_str, media_type="application/xml")
    except Exception as e:
        logger.error(f"Error in Twilio status webhook for call {call_id_path}: {e}", exc_info=True)
        # Twilio expects a 2xx response, so even on error, consider what to return.
        # Returning a generic TwiML response might be better than a 500 for Twilio.
        return PlainTextResponse("<Response><Say>An error occurred. Please try again later.</Say></Response>", media_type="application/xml", status_code=200) # Or 500 if that makes more sense for debugging

@app.post("/twilio/input/{call_id_path}", tags=["Twilio Webhooks"], summary="Twilio Input Callback (Speech/DTMF)")
async def twilio_input_webhook(request_data: Dict = Body(...), call_id_path: str = FastApiPath(..., alias="call_id_path")):
    dialer = get_dialer_system()
    logger.info(f"Twilio input webhook for call_id {call_id_path}, data: {request_data}")
    try:
        response_content = await dialer.handle_twilio_input(call_id_path, request_data)
        twiml_str = response_content.get("twiml", "<Response></Response>")
        return PlainTextResponse(twiml_str, media_type="application/xml")
    except Exception as e:
        logger.error(f"Error in Twilio input webhook for call {call_id_path}: {e}", exc_info=True)
        return PlainTextResponse("<Response><Say>An error occurred processing your input.</Say></Response>", media_type="application/xml", status_code=200)

# --- WebSocket Endpoint for Twilio Media Stream ---
@app.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket, business_type: Optional[str] = None, call_id: Optional[str] = None):
    # Ensure handlers are initialized
    if not vad_handler_instance or not stt_handler_instance or not conversation_manager_instance or not tts_handler_instance:
        logger.error(f"[{call_id}] WebSocket connection rejected: Core handlers (VAD, STT, ConversationManager, TTS) not initialized.")
        await websocket.close(code=1011) # Internal error
        return

    await websocket.accept()
    logger.info(f"WebSocket connection accepted for call_id: {call_id}, business_type: {business_type}")
    
    # Store this websocket connection if DialerSystem needs to access it directly (e.g., to send proactive messages or hangup)
    # This might involve a WebSocketManager class or a dict in DialerSystem
    # For now, assume ConversationManager will handle TTS via its tts_handler

    call_sid_internal = call_id # From query param
    stream_sid_twilio: Optional[str] = None # Will be received in the 'start' message from Twilio

    # Audio accumulation buffer for VAD
    vad_audio_buffer = bytearray()
    # Speech segments detected by VAD for STT
    speech_segments_for_stt = bytearray()
    is_speech_active = False

    try:
        while True:
            message_str = await websocket.receive_text()
            message = json.loads(message_str)
            event = message.get("event")

            if event == "connected":
                logger.info(f"[{call_sid_internal}] Twilio WebSocket stream connected: {message}")
            
            elif event == "start":
                stream_sid_twilio = message.get("start", {}).get("streamSid")
                logger.info(f"[{call_sid_internal}] Twilio WebSocket stream started. Stream SID: {stream_sid_twilio}")
                # Potentially initialize conversation here if not done earlier
                if conversation_manager_instance:
                    await conversation_manager_instance.initialize_conversation(
                        call_sid=call_sid_internal, 
                        business_type=business_type, 
                        websocket=websocket, # Pass websocket for TTS
                        stream_sid=stream_sid_twilio # Pass stream_sid for TTS
                    )

            elif event == "media":
                if not stream_sid_twilio:
                    logger.warning(f"[{call_sid_internal}] Received media before stream_sid was set. Ignoring.")
                    continue

                payload_b64 = message.get("media", {}).get("payload")
                if not payload_b64:
                    logger.warning(f"[{call_sid_internal}] Received media event with no payload.")
                    continue

                try:
                    # 1. Decode Base64
                    mulaw_bytes = base64.b64decode(payload_b64)
                    
                    # 2. Mu-law to linear PCM (16-bit)
                    # audioop.ulaw2lin returns bytes, 2 bytes per sample for 16-bit
                    pcm_8k_s16_bytes = audioop.ulaw2lin(mulaw_bytes, 2)

                    # 3. Resample 8kHz PCM to 16kHz PCM for VAD/STT
                    # Convert bytes to float tensor, normalize
                    pcm_8k_s16_tensor = torch.from_buffer(pcm_8k_s16_bytes, dtype=torch.int16).float() / 32768.0
                    
                    # Resample (input tensor needs to be 1D or 2D [channels, samples])
                    # If pcm_8k_s16_tensor is already 1D, it's fine. Add channel dim if needed: .unsqueeze(0)
                    if pcm_8k_s16_tensor.ndim == 1:
                        pcm_8k_s16_tensor = pcm_8k_s16_tensor.unsqueeze(0) # Add channel dimension
                    
                    pcm_16k_s16_tensor = F.resample(pcm_8k_s16_tensor, orig_freq=8000, new_freq=16000)
                    
                    # Convert back to bytes (16-bit PCM for VAD/STT)
                    # Remove channel dimension if added: .squeeze(0)
                    pcm_16k_s16_bytes = (pcm_16k_s16_tensor.squeeze(0) * 32768.0).to(torch.int16).numpy().tobytes()
                    
                    # --- VAD Processing ---
                    # Accumulate audio for VAD. VAD typically processes in fixed-size chunks (e.g., 30ms at 16kHz = 480 samples = 960 bytes)
                    vad_audio_buffer.extend(pcm_16k_s16_bytes)
                    
                    # Define VAD constants here or globally if preferred
                    VAD_CHUNK_SIZE_BYTES = 960 # 30ms at 16kHz, 16-bit (Silero VAD itself doesn't strictly need this for its direct probability output on a chunk)
                                               # but useful if you were to chunk for it manually using get_speech_timestamps over longer audio.
                                               # For this implementation, process_audio_chunk takes whatever current_chunk is.
                    VAD_MIN_SPEECH_BYTES = 1500 # Example: Minimum speech duration in bytes for STT (e.g., ~300ms at 16kHz, 16-bit mono)
                                               # Adjust this based on desired sensitivity to short utterances.

                    # Process in VAD chunks (example chunk size, adjust to your VAD's needs)
                    # The VAD_CHUNK_SIZE_BYTES here is more about how frequently we check VAD on accumulating audio.
                    # The vad_handler_instance.process_audio_chunk will process whatever chunk it's given.
                    while len(vad_audio_buffer) >= VAD_CHUNK_SIZE_BYTES: # This loop processes fixed chunks from the buffer
                        current_chunk_for_vad = vad_audio_buffer[:VAD_CHUNK_SIZE_BYTES]
                        del vad_audio_buffer[:VAD_CHUNK_SIZE_BYTES]

                        # vad_result is now a boolean from SileroVADHandler
                        vad_is_speech = await vad_handler_instance.process_audio_chunk(current_chunk_for_vad)

                        if vad_is_speech: # Changed from vad_result == "SPEECH"
                            if not is_speech_active:
                                logger.debug(f"[{call_sid_internal}] VAD: Speech started.")
                                is_speech_active = True
                            speech_segments_for_stt.extend(current_chunk_for_vad) # Accumulate the chunk that had speech
                        elif is_speech_active: # Speech was active, but this chunk is silence - end of speech segment
                            logger.debug(f"[{call_sid_internal}] VAD: Speech ended. Segment length: {len(speech_segments_for_stt)} bytes.")
                            is_speech_active = False
                            if len(speech_segments_for_stt) > VAD_MIN_SPEECH_BYTES: # Use defined constant
                                transcript = await stt_handler_instance.transcribe_audio_bytes(bytes(speech_segments_for_stt))
                                speech_segments_for_stt.clear() # Reset for next segment
                                logger.info(f"[{call_sid_internal}] STT Result: '{transcript}'")
                                
                                if transcript and conversation_manager_instance:
                                    # ConversationManager handles LLM and TTS response
                                    await conversation_manager_instance.handle_user_input(
                                        transcript=transcript,
                                        # websocket=websocket, # Already passed during init_conversation
                                        # call_sid=call_sid_internal,
                                        # stream_sid=stream_sid_twilio
                                    )
                            else:
                                logger.debug(f"[{call_sid_internal}] Discarding short speech segment.")
                                speech_segments_for_stt.clear()
                        # If silence and not is_speech_active, do nothing, just consume chunk.
                        
                except audioop.error as e:
                    logger.error(f"[{call_sid_internal}] Audioop error processing media: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"[{call_sid_internal}] Error processing media event: {e}", exc_info=True)
            
            elif event == "mark":
                mark_name = message.get("mark", {}).get("name")
                logger.info(f"[{call_sid_internal}] Received mark: {mark_name}")
                # Handle marks if needed, e.g., TTS finished playing on Twilio side

            elif event == "stop":
                logger.info(f"[{call_sid_internal}] Twilio WebSocket stream stopped: {message}")
                # Clean up call state in DialerSystem or ConversationManager
                if conversation_manager_instance:
                    await conversation_manager_instance.handle_call_stop(call_sid_internal)
                break # Exit the loop as the stream is stopped
            
            else:
                logger.warning(f"[{call_sid_internal}] Received unknown WebSocket event: {event}, message: {message}")

    except WebSocketDisconnect:
        logger.info(f"[{call_sid_internal}] WebSocket disconnected by client (Twilio or other).")
    except ConnectionResetError:
        logger.warning(f"[{call_sid_internal}] WebSocket connection reset by peer.")
    except Exception as e:
        logger.error(f"[{call_sid_internal}] Error in WebSocket handler: {e}", exc_info=True)
    finally:
        logger.info(f"[{call_sid_internal}] Closing WebSocket connection and cleaning up call.")
        # Ensure resources are cleaned up, e.g., notify DialerSystem or ConversationManager
        # if conversation_manager_instance:
        #     await conversation_manager_instance.handle_call_end(call_sid_internal) # Or similar cleanup
        if not websocket.client_state == websocket.client_state.DISCONNECTED: # type: ignore
             try:
                 await websocket.close()
             except RuntimeError as e:
                 logger.warning(f"[{call_sid_internal}] Error closing websocket (already closed or invalid state): {e}")

# --- Main Execution (for local development) ---
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Add parent directory to path if running as module
    if __package__:
        parent_dir = Path(__file__).resolve().parent.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
    
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = '%(asctime)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s'
    log_config["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    
    # Use app.main:app when running as module, main:app when running directly
    module_path = "app.main:app" if __package__ else "main:app"
    
    uvicorn.run(
        module_path, 
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=log_config
    ) 