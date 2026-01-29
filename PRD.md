# Product Requirements Document: AI Telemarketer - Version 1.2

**Date:** March 22, 2025

**Author:** Gemini (AI Assistant)

**1. Introduction**

1.1. **Purpose:** This document outlines the product requirements for version 1.2 of our AI Telemarketer, a system designed to automate outbound telemarketing calls using advanced conversational AI. This version focuses on establishing the core architecture and integrating the Nova2 framework with the Twilio telephony platform.

1.2. **Goals:**
    * To create a functional AI agent capable of conducting telemarketing calls based on a defined script.
    * To seamlessly integrate the Nova2 conversational AI framework with the Twilio telephony service (for voice calls) and potentially the Twilio WhatsApp API.
    * To establish real-time audio communication between the AI agent and call recipients via Twilio voice.
    * To implement mechanisms for sending follow-up information via WhatsApp or email as fallback options.
    * To lay the foundation for implementing the specific telemarketing script (v1.2 Script - see details below).

1.3. **Target User:** The primary user of this document is the development team responsible for building and deploying the AI Telemarketer.

**2. High-Level Overview**

The AI Telemarketer will leverage the Nova2 framework for its conversational intelligence (including LLM, TTS, STT, and context management) and Twilio for handling the telephony aspects (making calls, managing call states). A dedicated `twilio_manager.py` script will orchestrate the interaction between these two systems.

**3. Functional Requirements**

3.1. **Twilio Integration via `twilio_manager.py`:**
    * The system shall include a separate Python script (`twilio_manager.py`) responsible for interacting directly with the Twilio API for both voice calls and potentially WhatsApp messaging.
    * The `twilio_manager` shall be capable of:
        * Managing a list of phone numbers for outbound calls.
        * Initiating outbound phone calls using the Twilio Voice API.
        * Monitoring the state of calls (e.g., ringing, connected, ended) using Twilio's event mechanisms (e.g., webhooks).
        * Establishing a WebSocket connection with the Nova2 framework upon successful call connection.
        * Forwarding real-time audio from the caller (received by Twilio) to Nova2 via the WebSocket.
        * Receiving real-time audio output from Nova2 (TTS) via the WebSocket and sending it to Twilio for playback to the caller.
        * Handling call termination signals from both Nova2 and Twilio.
        * Potentially initiating outbound WhatsApp messages via the Twilio API based on instructions from Nova2.

3.2. **Nova2 API and WebSocket Functionality:**
    * The Nova2 framework integration shall include:
        * **API Endpoint for Call Initiation:** A lightweight API endpoint (e.g., using Flask or FastAPI) that the `twilio_manager` can call to signal the start of a new conversation and provide essential call metadata (e.g., Twilio Call SID, caller ID, campaign ID).
        * **WebSocket Endpoint for Audio Streaming:** Functionality to establish a WebSocket endpoint within Nova2 to receive the real-time audio stream from the `twilio_manager`.
        * **Speech-to-Text (STT) Integration:** Seamless integration of Nova2's STT capabilities to transcribe the incoming audio stream from the caller.
        * **Conversational Workflow (LLM and Context):** Leveraging Nova2's LLM and context management to process the transcribed text, maintain conversation state, and generate appropriate responses based on the telemarketing script (v1.2 Script). This includes handling different script paths (e.g., "Creating Interest", "Reducing Overheads"), managing objections, and deciding when to aim for an appointment, WhatsApp follow-up, or email follow-up.
        * **Text-to-Speech (TTS) Integration:** Seamless integration of Nova2's TTS capabilities to convert the generated responses into an audio stream.
        * **WebSocket Output for Audio:** Functionality to stream the generated TTS audio back to the `twilio_manager` via the WebSocket connection.
        * **Call/Interaction End Signaling:** A mechanism within Nova2 to signal to the `twilio_manager` when the conversation should be terminated (e.g., upon reaching the end of the script, booking an appointment, agreeing to a WhatsApp/email follow-up, or encountering repeated negative responses). This signaling should include the desired outcome (appointment booked, send WhatsApp, send email, hang up).

3.3. **Telemarketing Script Implementation (v1.2 Script):**
    * The system shall implement the v1.2 telemarketing script within Nova2.
    * **Goals:**
        * Primary: Book an appointment.
        * Secondary: Send a WhatsApp message with info ("Wamailer").
        * Tertiary: Send an email with info.
    * **Structure:**
        * Tailored opening based on business type ("Creating Interest" for most, "Reducing Overheads" for specific categories like garages, car body repair, tattooists).
        * Pre-close questions to gauge interest.
        * Specific objection handling logic (e.g., "Busy", "Not Interested").
        * Logic to transition between goals (appointment -> WhatsApp -> email).
    * The script implementation shall leverage Nova2's conversational pathways, using prompts, system messages, and context management to guide the LLM's responses according to the defined logic.

**4. Non-Functional Requirements**

4.1. **Latency:** The system shall aim for minimal latency in audio transmission and response generation to ensure a natural conversational flow. The target round-trip latency for audio processing and response generation should be within an acceptable range (to be further defined).
4.2. **Reliability:** The integration between Nova2 and Twilio should be reliable and handle potential network issues or API errors gracefully.
4.3. **Scalability (Future Consideration):** While not a primary focus for v1.2, the architecture should be designed with potential future scalability in mind.

**5. High-Level Architecture**

twilio_manager.py (Twilio API Client - Voice & potentially WhatsApp)
<----> (Bi-directional communication for control and signaling)
Nova2 Framework (Conversational AI)
^ WebSocket (Audio Stream for Voice Calls)
|
|
v
  STT Module (within Nova2)
  LLM Module (within Nova2 - handles script logic, goal tracking)
  TTS Module (within Nova2)
  Context Management (within Nova2)
  API Endpoint (within Nova2)
^ WebSocket (Audio Stream for Voice Calls)
|
|
v
Twilio Platform (Telephony Service & WhatsApp API)

The `twilio_manager.py` will connect to the Twilio API for call control and potentially WhatsApp messaging. For voice calls, it establishes a WebSocket connection to the Nova2 framework for real-time audio streaming. Nova2 handles the conversational logic according to the v1.2 script and streams its audio output back to the `twilio_manager` for playback via Twilio Voice, or signals the manager to send a WhatsApp message via the Twilio WhatsApp API.

**6. Twilio Integration Details**

The integration with Twilio will primarily be managed by the `twilio_manager.py`. It will handle the complexities of the Twilio Voice API for initiating and managing calls, and potentially the Twilio WhatsApp API for sending messages. The key integration points with Nova2 will be the WebSocket connection for real-time audio (voice calls) and the API endpoint for initial call setup and receiving instructions (e.g., end call, send WhatsApp).

**7. Nova2 Integration Details**

Nova2 will need to be extended to include an API endpoint (likely using Flask or FastAPI) to receive call initiation requests from the `twilio_manager`. Furthermore, it will require the implementation of WebSocket handling capabilities to receive and send real-time audio streams for voice calls. This WebSocket functionality will need to be tightly integrated with Nova2's STT and TTS modules. Crucially, Nova2 will be responsible for all context management related to the conversation, including tracking the script state, handling objections, and deciding the appropriate outcome (appointment, WhatsApp, email, end call). It will communicate these decisions back to the `twilio_manager` via the API or a control channel.

**8. Future Considerations**

* Integration of long-term memory within Nova2 to personalize interactions over multiple calls.
* More sophisticated call flow management and branching logic based on user responses.
* Implementation of error handling and logging mechanisms in both the `twilio_manager` and Nova2.
* Development of a user interface for managing leads and campaigns.
* Adding email sending capability (either via Twilio SendGrid or another service) triggered by `twilio_manager`.
* Refining the logic for switching between appointment booking, WhatsApp, and email goals.