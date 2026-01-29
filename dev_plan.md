# AI Telemarketer Development Plan (v1.2 -> Production)

This document outlines the development phases to integrate all components of the AI Telemarketer, refactor existing modules for Twilio compatibility, and build the necessary frontend APIs and dashboard features.

## Phase 1: Core Refactoring & WebSocket Handling

**Goal:** Enable the server to receive and process real-time audio streams from Twilio and send back TTS audio responses.

**Tasks:**

1.  **Refactor `transcriptor.py` (`VoiceAnalysis`):**
    *   Remove direct microphone access (`sounddevice`, `_record_audio`).
    *   Add `process_audio_chunk(audio_bytes: bytes)` method to accept external audio.
    *   Modify `start()` / `start_sync()` to process an internal queue fed by `process_audio_chunk`.
    *   Update `close()` / `stop_transcriptor()` to handle the new structure.
    *   **File:** `Nova2/app/transcriptor.py`

2.  **Implement WebSocket Endpoint (`/ws/{call_sid}`):**
    *   Create the FastAPI endpoint in `telemarketer_server.py`.
    *   Handle WebSocket lifecycle: connect, disconnect.
    *   Process incoming Twilio stream messages: `connected`, `start`, `media`, `stop`.
    *   **On `start`:**
        *   Retrieve `call_sid` from path.
        *   Instantiate `ContextManager` for the call (`call_contexts[call_sid]`).
        *   Instantiate `VoiceAnalysis` for the call.
        *   Retrieve `CallStateMachine` using `CallStateManager.get_call_state(call_sid)`.
        *   Get `business_type` from state machine.
        *   Call `telemarketer.select_script(business_type)`.
        *   Start STT processing task (`process_stt_async` adapted for the new `VoiceAnalysis`).
        *   Trigger initial LLM turn (`process_llm_turn` with `user_input=None`).
    *   **On `media`:**
        *   Decode base64 `payload`.
        *   Get the correct `VoiceAnalysis` instance for `call_sid`.
        *   Call `process_audio_chunk()` with the decoded audio bytes.
    *   **On `stop` / disconnect:**
        *   Trigger cleanup logic (potentially call `terminate_call`).
    *   **File:** `Nova2/app/telemarketer_server.py`

3.  **Implement TTS over WebSocket:**
    *   Modify `handle_next_action` function in `telemarketer_server.py`.
    *   Get TTS audio bytes using `nova.run_tts(..., stream=True)`.
    *   Convert audio chunk format (e.g., to 8kHz mulaw using `librosa` or similar).
    *   Base64 encode the converted chunk.
    *   Construct the Twilio `media` JSON message.
    *   Send the JSON message over the correct WebSocket connection (`active_ws_connections[call_sid]`).
    *   **File:** `Nova2/app/telemarketer_server.py`

## Phase 2: Call Lifecycle & Logic Integration

**Goal:** Connect the core components to manage the full call flow, including initiation, state transitions, regulation checks, and termination.

**Tasks:**

1.  **Refine LLM Turn Processing (`process_llm_turn`):**
    *   Load conversation history from `CallStateMachine` (retrieved via `CallStateManager`).
    *   Pass history to `nova.run_llm`.
    *   Check `LLMResponse.tool_calls` for `end_call` tool.
    *   If `end_call` tool is present, extract `farewell_message` and call `terminate_call(call_sid, farewell_message)`.
    *   If no tool call, use `telemarketer.parse_llm_response()` to get dialogue and suggested state.
    *   Validate suggested state and update `CallStateMachine` using `validate_and_set_state()`.
    *   Save updated state using `CallStateManager.save_call_state()`.
    *   Call `handle_next_action()` to speak the dialogue.
    *   Get the action for the *new* state (`telemarketer.get_script_action(new_state)`).
    *   If the action is `HANGUP`, call `terminate_call(call_sid, farewell_from_script)`.
    *   **File:** `Nova2/app/telemarketer_server.py`

2.  **Implement Outbound Calling & Regulations:**
    *   Create FastAPI endpoint `/start_calls` (POST) to accept a list of `{'phone_number': ..., 'business_type': ...}`.
    *   Inside the endpoint:
        *   Iterate through the list.
        *   For each number, call `uk_regulator.can_call_number(phone_number, TWILIO_DEFAULT_FROM)`.
        *   If permitted:
            *   Generate a unique `call_sid` (or let Twilio generate and retrieve later).
            *   Create the initial call state using `call_state_manager.create_call_state(call_sid, {'to_number': ..., 'business_type': ..., ...})`.
            *   Construct the TwiML URL: `f"{SERVER_BASE_URL}/twilio/initiate_stream/{call_sid}"`.
            *   Use `twilio_client.calls.create(to=..., from_=TWILIO_DEFAULT_FROM, url=twiml_url, record=True, recording_status_callback=f'{SERVER_BASE_URL}/twilio/recording_complete')`.
            *   Record the attempt: `uk_regulator.record_call_attempt(phone_number, call_sid, 'initiated')`.
        *   If not permitted, log the reason.
    *   Implement the TwiML endpoint `/twilio/initiate_stream/{call_sid}`:
        *   Return TwiML: `<Response><Connect><Stream url="wss://{YOUR_SERVER_DOMAIN}/ws/{call_sid}"></Stream></Connect></Response>`.
    *   Implement `/twilio/recording_complete` endpoint:
        *   Receive `RecordingUrl` and `CallSid` from Twilio POST request.
        *   Update the corresponding record in the `calls` database table (add a `recording_url` column).
    *   **Files:** `Nova2/app/telemarketer_server.py`, `Nova2/app/uk_call_regulations.py`, `Nova2/app/call_state_manager.py` (DB schema change).

3.  **Refine Call Termination (`terminate_call`):**
    *   Ensure it gracefully stops the associated `VoiceAnalysis` instance.
    *   Close the WebSocket connection (`active_ws_connections.pop(call_sid, ...)`).
    *   Set the final state and save using `CallStateManager.end_call()`.
    *   Update call status with Twilio API (`client.calls(call_sid).update(status='completed')`).
    *   Update call status in regulations history: `uk_regulator.update_call_status(call_sid, 'completed', duration)`.
    *   **File:** `Nova2/app/telemarketer_server.py`

## Phase 3: Frontend API & Data Logging

**Goal:** Provide necessary APIs for a frontend dashboard and ensure relevant call data is captured and stored.

**Tasks:**

1.  **Implement Frontend API Endpoints:**
    *   Finalize `/start_calls` (POST) from Phase 2.
    *   Create `/calls` (GET) endpoint:
        *   Accept query parameters for pagination (limit, offset).
        *   Call `call_state_manager.get_recent_calls(limit, offset)`.
        *   Return the list of call summaries.
    *   Create `/calls/{call_sid}` (GET) endpoint:
        *   Call `call_state_manager.get_call_details(call_sid)`.
        *   Deserialize JSON fields (like `history`, `qualifiers_met`) before returning.
        *   Return detailed call information including history and recording URL.
    *   **File:** `Nova2/app/telemarketer_server.py`

2.  **Enhance Data Logging & Persistence:**
    *   **Audio:** Ensure Twilio call recording is enabled in `calls.create` and the `recording_complete` webhook updates the database (Phase 2).
    *   **Transcription/LLM History:** Confirm `CallStateMachine.add_history_entry` correctly captures user/assistant turns and is persisted via `CallStateManager`.
    *   **Lead Generation Info:**
        *   Add specific fields to `CallStateMachine` and the `calls` DB table (e.g., `appointment_booked_time`, `whatsapp_number_collected`, `email_collected`, `lead_status`).
        *   Modify `process_llm_turn` or add specific tools for the LLM to update these fields based on the conversation outcome (e.g., a tool `record_appointment(time)`). The tool implementation would call `CallStateManager.update_call_data()`. Alternatively, parse specific states like `CONFIRM_APPOINTMENT_MM` to trigger updates.
    *   **Files:** `Nova2/app/call_state_manager.py` (State machine fields, DB schema), `Nova2/app/telemarketer_server.py` (LLM turn logic/tool execution), Potentially new tool files in `Nova2/tools/`. 

## Phase 4: Dashboard Implementation

**Goal:** Create a web-based dashboard for monitoring and controlling the telemarketer.

**Tasks:**

1.  **Dashboard Frontend Development:**
    *   Choose a frontend framework (e.g., React, Vue, Svelte, basic HTML/JS).
    *   **Call List View:**
        *   Display recent calls using the `/calls` API.
        *   Show key info: To/From Number, Status (State), Duration, Start Time, Script Type.
        *   Implement pagination.
        *   Allow clicking a call to view details.
    *   **Call Detail View:**
        *   Display detailed call info using the `/calls/{call_sid}` API.
        *   Show full conversation history.
        *   Provide a link/player for the call recording (using `recording_url`).
        *   Display collected lead info (Appointment time, WhatsApp/Email, etc.).
    *   **Control Panel:**
        *   Input field/area for pasting phone numbers and business type indicators (e.g., CSV format or line-by-line).
        *   Button to trigger the `/start_calls` API.
        *   Display status/feedback from the call initiation process.
        *   (Optional) Display server status, active calls count.
        *   (Optional) Buttons for Start/Stop server (requires additional server logic/process management).

2.  **Deployment Considerations:**
    *   Configure server domain/IP for Twilio webhooks and WebSocket connections.
    *   Set up necessary environment variables (API keys, DB path, etc.).
    *   Choose hosting (e.g., Cloud VM, Docker container orchestration).
    *   Configure a reverse proxy (like Nginx) for handling HTTPS and WebSocket upgrades. 