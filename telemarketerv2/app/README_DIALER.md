# AI Telemarketer Dialer System

The AI Telemarketer dialer system is a robust, production-ready component designed to automate outbound calling campaigns with LLM-powered conversations and intelligent call management.

## Features

- **Twilio Integration**: Make real outbound calls through Twilio's API
- **Automatic Retry Logic**: Configurable retry attempts for failed, busy, or unanswered calls
- **Automated Response Detection**: Smart detection of voicemail, IVR systems, and non-human responses
- **Sequential Batch Dialing**: Process large lists of numbers with configurable concurrency limits
- **Database Storage**: Store call data, conversations, and generated leads
- **Call State Management**: Track call progress and manage different call outcomes
- **UK Regulations Compliance**: Built-in compliance with UK telemarketing regulations
- **API Endpoints**: RESTful API for controlling the dialer and retrieving data
- **Graceful Error Handling**: Robust error recovery and logging

## System Architecture

The dialer system consists of several key components:

1. **DialerSystem**: Core class managing the call queue, retries, and Twilio integration
2. **CallManager**: Handles LLM interactions and conversation state
3. **AutomatedResponseDetector**: Detects voicemail and automated systems
4. **UKRegulationsManager**: Ensures compliance with UK telemarketing regulations
5. **Database Models**: Stores call records and lead information
6. **API Endpoints**: FastAPI routes for controlling the dialer

## Setup Instructions

### Prerequisites

- Python 3.9 or higher
- SQLite database
- Twilio account (optional for production use)
- LLM API keys (GROQ or equivalent)

### Environment Variables

Set up the following environment variables:

```bash
# Twilio credentials (for real calls)
export TWILIO_ACCOUNT_SID=your_account_sid
export TWILIO_AUTH_TOKEN=your_auth_token
export TWILIO_PHONE_NUMBER=your_twilio_phone_number
export TWILIO_WEBHOOK_URL=your_webhook_url

# Database paths
export TELEMARKETER_DB_PATH=path_to_telemarketer_db
export UK_REGULATIONS_DB_PATH=path_to_regulations_db

# LLM credentials
export GROQ_API_KEY=your_groq_api_key
```

### Installation

1. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Initialize the database:
   ```bash
   python -m telemarketerv2.app.database.models
   ```

## Usage

### Starting the Dialer

The dialer is automatically initialized when the FastAPI application starts, but it will not process calls until explicitly started:

```bash
# Start the FastAPI application
uvicorn telemarketerv2.app.main:app --host 0.0.0.0 --port 8000
```

Then use the API to start the dialer:

```bash
curl -X POST http://localhost:8000/dialer/start
```

### Making Calls

To make a single call:

```bash
curl -X POST http://localhost:8000/dialer/call \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+441234567890", "business_type": "plumbing"}'
```

To make batch calls:

```bash
curl -X POST http://localhost:8000/dialer/batch \
  -H "Content-Type: application/json" \
  -d '{
    "calls": [
      {"phone_number": "+441234567890", "business_type": "plumbing"},
      {"phone_number": "+441234567891", "business_type": "electrical"}
    ]
  }'
```

### Updating Dialer Settings

```bash
curl -X POST http://localhost:8000/dialer/settings \
  -H "Content-Type: application/json" \
  -d '{
    "max_concurrent_calls": 5,
    "max_retries": 3,
    "retry_delay_seconds": 300,
    "call_timeout_seconds": 60
  }'
```

### Retrieving Call Information

Get recent calls:

```bash
curl http://localhost:8000/dialer/calls?limit=50&offset=0
```

Get call details:

```bash
curl http://localhost:8000/dialer/calls/CA1234567890
```

Get generated leads:

```bash
curl http://localhost:8000/dialer/leads?limit=50&offset=0
```

## Database Schema

### Call Records Table
Stores information about each call attempt:

- `call_id`: Unique identifier for the call
- `phone_number`: Target phone number
- `business_type`: Type of business for script selection
- `caller_id`: Phone number displayed to recipient
- `status`: Current status (queued, in-progress, completed, etc.)
- `retry_count`: Number of retry attempts
- `created_at`: Timestamp when the call was created
- `scheduled_time`: When the call is scheduled to be made
- `started_at`: When the call was started
- `completed_at`: When the call ended
- `last_error`: Last error message if failed
- `regulation_violation`: Type of regulation violation if any
- `call_sid`: Internal call SID
- `twilio_call_sid`: Twilio call SID
- `conversation_history`: JSON string of the conversation
- `call_duration`: Call duration in seconds
- `updated_at`: Last update timestamp

### Lead Records Table
Stores information about generated leads:

- `lead_id`: Unique identifier for the lead
- `call_id`: Associated call ID
- `phone_number`: Phone number called
- `business_name`: Name of the business
- `business_type`: Type of business
- `contact_name`: Name of the contact person
- `contact_email`: Email of the contact person
- `contact_phone`: Phone of the contact person
- `appointment_time`: Scheduled appointment time
- `notes`: Additional notes
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

## Automated Response Detection

The system uses pattern matching to detect different types of automated responses:

1. **Voicemail Detection**: Recognizes common voicemail greeting patterns
2. **IVR System Detection**: Identifies automated attendant systems
3. **Call Screening**: Detects when someone is screening the call
4. **Non-interactive Responses**: Identifies minimal responses that don't add value

When an automated system is detected with high confidence, the dialer can automatically end the call and schedule a retry.

## Retry Logic

The system implements exponential backoff for retry attempts:

1. First retry: Wait `retry_delay_seconds`
2. Second retry: Wait `retry_delay_seconds * 2`
3. Third retry: Wait `retry_delay_seconds * 4`

Calls can be retried for the following reasons:
- Failed calls due to Twilio errors
- No answer
- Busy line
- Voicemail/answering machine detected

## UK Regulations Compliance

The dialer integrates with the UK call regulations module to ensure compliance:

1. **Pre-call Checks**: Verify TPS registration, calling hours, and frequency limits
2. **Call Tracking**: Record call history for compliance purposes
3. **Caller ID Validation**: Ensure caller ID is valid and displayed

## Troubleshooting

### Common Issues

1. **Calls Not Being Made**
   - Check if the dialer is running (`GET /dialer/status`)
   - Verify Twilio credentials if using real calls
   - Check for regulation blocks in the call records

2. **High Failure Rate**
   - Review last_error field in call records
   - Check for Twilio API issues
   - Verify phone number format (should be E.164 format)

3. **Automated Response Issues**
   - Adjust retry logic settings if too many voicemails
   - Review conversation history to tune detection patterns

### Logging

The dialer system produces detailed logs to help troubleshoot issues:

```bash
# View logs
tail -f telemarketer.log
```

## License

This code is proprietary and part of the AI Telemarketer system. 