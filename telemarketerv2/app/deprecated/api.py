# This file has been moved from telemarketerv2/app/api.py
# Its functionality is superseded by API endpoints defined in main.py.

import datetime
import logging
import os
from typing import Dict, List, Optional, Any

# from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query, Request # Commented out
# from fastapi.middleware.cors import CORSMiddleware # Commented out
# from pydantic import BaseModel, Field # Commented out

# from .call_manager import CallManager # Commented out

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create a router instead of an app
# router = APIRouter( # Commented out
#     prefix="/api",
#     tags=["api"],
#     responses={404: {"description": "Not found"}},
# )

# Pydantic models for request validation
# class CallRequest(BaseModel):
#     phone_number: str = Field(..., description="Phone number to call")
#     business_type: str = Field(
#         ..., description="Type of business for script selection (e.g., 'plumbing', 'hvac')"
#     )
#     caller_id: str = Field(
#         default="+441234567890", description="Caller ID to use for the call"
#     )


# class BatchCallRequest(BaseModel):
#     phone_numbers: List[str] = Field(..., description="List of phone numbers to call")
#     business_type: str = Field(
#         ..., description="Type of business for script selection (e.g., 'plumbing', 'hvac')"
#     )
#     caller_id: str = Field(
#         default="+441234567890", description="Caller ID to use for the calls"
#     )


# class UserInputRequest(BaseModel):
#     user_input: str = Field(..., description="User's input text")


# class RegulationCheckRequest(BaseModel):
#     phone_number: str = Field(..., description="Phone number to check regulations for")
#     caller_id: str = Field(
#         default="+441234567890", description="Caller ID to use for the check"
#     )


# @router.get("/health")
async def health_check(request: Any): # Changed Request to Any
    """
    Check health of the telemarketer system and its components.
    """
    # cm: CallManager = request.app.state.call_manager
    # if not cm:
    #     raise HTTPException(status_code=503, detail="CallManager not initialized")
    # try:
    #     health = await cm.check_health()
    #     return health
    # except Exception as e:
    #     logger.error(f"Error checking health: {e}")
    #     raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
    logger.warning("Deprecated health_check from api.py called.")
    return {"status": "deprecated"}


# @router.post("/calls", status_code=201)
async def create_call(request: Any, call_request: Any): # Changed types to Any
    """
    Create a new call with the specified parameters.

    - **phone_number**: Phone number to call
    - **business_type**: Type of business for script selection
    - **caller_id**: Caller ID to use for the call
    """
    # cm: CallManager = request.app.state.call_manager
    # if not cm:
    #     raise HTTPException(status_code=503, detail="CallManager not initialized")
    # The CallManager no longer has create_call. This endpoint likely needs to 
    # interact with DialerSystem or CallStateManager directly to add to the queue.
    # For now, let's comment out the body as it will fail.
    # try:
    #     call = await cm.create_call(
    #         call_request.phone_number,
    #         call_request.business_type,
    #         call_request.caller_id,
    #     )
    #     return call
    # except HTTPException as he:
    #     raise he
    # except Exception as e:
    #     logger.error(f"Error creating call: {e}")
    #     raise HTTPException(status_code=500, detail=f"Failed to create call: {str(e)}")
    # raise HTTPException(status_code=501, detail="Call creation via this API endpoint needs reimplementation to use DialerSystem/Queue.")
    logger.warning("Deprecated create_call from api.py called.")
    return {"status": "deprecated", "detail": "Functionality moved to main.py"}


@router.post("/calls/batch", status_code=201)
async def create_batch_calls(request: Request, batch_request: BatchCallRequest, background_tasks: BackgroundTasks):
    """
    Create multiple calls with the specified parameters.

    - **phone_numbers**: List of phone numbers to call
    - **business_type**: Type of business for script selection
    - **caller_id**: Caller ID to use for the calls
    """
    # cm: CallManager = request.app.state.call_manager # CallManager no longer handles this
    # Get CallStateManager or DialerSystem instead?
    # For now, return 501 Not Implemented
    raise HTTPException(status_code=501, detail="Batch call creation via this API endpoint needs reimplementation to use DialerSystem/Queue.")
    # results = []
    # for phone_number in batch_request.phone_numbers:
    #     try:
    #         call = await cm.create_call(
    #             phone_number, batch_request.business_type, batch_request.caller_id
    #         )
    #         results.append({"phone_number": phone_number, "call_sid": call["call_sid"], "status": "created"})
    #     except HTTPException as he:
    #         # This could be a regulation violation - capture details
    #         results.append({
    #             "phone_number": phone_number, 
    #             "status": "error", 
    #             "error": str(he.detail) if isinstance(he.detail, str) else he.detail.get("message", str(he.detail))
    #         })
    #     except Exception as e:
    #         results.append({"phone_number": phone_number, "status": "error", "error": str(e)})

    # return {"calls": results}


@router.post("/calls/{call_sid}/start")
async def start_call(request: Request, call_sid: str):
    """
    Start a call with the specified ID.

    - **call_sid**: Call ID to start
    """
    # cm: CallManager = request.app.state.call_manager # CallManager no longer handles this
    raise HTTPException(status_code=501, detail="Starting calls manually via API is likely handled by DialerSystem now.")
    # try:
    #     call = await cm.start_call(call_sid)
    #     return call
    # except Exception as e:
    #     logger.error(f"Error starting call {call_sid}: {e}")
    #     raise HTTPException(status_code=500, detail=f"Failed to start call: {str(e)}")


@router.post("/calls/{call_sid}/input")
async def process_user_input(request: Request, call_sid: str, input_request: UserInputRequest):
    """
    Process user input for a call.

    - **call_sid**: Call ID to process input for
    - **user_input**: User's input text
    """
    # cm: CallManager = request.app.state.call_manager # CallManager no longer handles this via API
    raise HTTPException(status_code=501, detail="User input is processed via WebSocket, not this API endpoint.")
    # try:
    #     call = await cm.process_user_input(call_sid, input_request.user_input)
    #     return call
    # except Exception as e:
    #     logger.error(f"Error processing user input for call {call_sid}: {e}")
    #     raise HTTPException(
    #         status_code=500, detail=f"Failed to process user input: {str(e)}"
    #     )


@router.post("/calls/{call_sid}/end")
async def end_call(request: Request, call_sid: str, reason: Optional[str] = "user_ended"):
    """
    End a call with the specified ID.

    - **call_sid**: Call ID to end
    - **reason**: Reason for ending the call
    """
    # cm: CallManager = request.app.state.call_manager # CallManager no longer handles this via API
    # It might make sense to allow API termination via DialerSystem?
    raise HTTPException(status_code=501, detail="Call ending is handled internally, API endpoint needs review/reimplementation if required.")
    # try:
    #     call = await cm.end_call(call_sid, reason)
    #     return call
    # except Exception as e:
    #     logger.error(f"Error ending call {call_sid}: {e}")
    #     raise HTTPException(status_code=500, detail=f"Failed to end call: {str(e)}")


@router.get("/calls/{call_sid}")
async def get_call(request: Request, call_sid: str):
    """
    Get call details by ID.

    - **call_sid**: Call ID to retrieve
    """
    csm = request.app.state.call_state_manager # Get CallStateManager
    if not csm:
        raise HTTPException(status_code=503, detail="CallStateManager not initialized")
    try:
        # Use CSM's method (assuming it exists and is appropriate)
        # This might need adjustment based on CSM's final implementation
        call_details = csm.get_call_details(call_sid) # Assuming sync method access
        if not call_details:
            # Maybe check DialerSystem history too?
            # dialer = request.app.state.dialer_system # If dialer is stored on app.state
            # call_details = await dialer.get_call_details(call_sid) # Assuming async method
            # if not call_details:
            raise HTTPException(status_code=404, detail=f"Call {call_sid} not found")
        return call_details
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting call {call_sid}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get call details: {str(e)}")


@router.get("/calls/recent")
async def get_recent_calls(request: Request, limit: int = 10):
    """
    Get a list of recent calls.

    - **limit**: Maximum number of calls to return (default: 10)
    """
    csm = request.app.state.call_state_manager
    if not csm:
        raise HTTPException(status_code=503, detail="CallStateManager not initialized")
    # Using CSM's sync method for in-memory mode - may not be persistent
    # For persistent logs, should query DialerSystem's DB access method
    # dialer = request.app.state.dialer_system
    # calls = await dialer.get_recent_calls(limit=limit, offset=0)
    calls = csm.get_recent_calls(limit=limit, offset=0) 
    return {"calls": calls}


@router.get("/calls/history/{phone_number}")
async def get_call_history(request: Request, phone_number: str, days: int = 30):
    """
    Get call history for a specific phone number.

    - **phone_number**: Phone number to get history for
    - **days**: Number of days to look back (default: 30)
    """
    # dialer = request.app.state.dialer_system
    # history = await dialer.get_call_history_for_number(phone_number, days)
    # return {"history": history}
    raise HTTPException(status_code=501, detail="Call history endpoint not implemented.")


@router.post("/regulations/check")
async def check_number_callable(request: Any, check_request: Any):
    logger.warning("Deprecated check_number_callable from api.py called.")
    return {"status": "deprecated"}


@router.get("/regulations/history/{phone_number}")
async def get_regulations_history(request: Any, phone_number: str, days: int = 30):
    logger.warning("Deprecated get_regulations_history from api.py called.")
    return {"status": "deprecated"}


@router.get("/regulations/status")
async def get_regulations_status(request: Any):
    logger.warning("Deprecated get_regulations_status from api.py called.")
    return {"status": "deprecated"}

# Consider adding endpoints to interact with DialerSystem/Queue if needed
# e.g., add calls to queue, get queue status, pause/resume dialer

# Consider adding endpoints to interact with DialerSystem/Queue if needed
# e.g., add calls to queue, get queue status, pause/resume dialer 