# UK Call Regulations Integration

This module provides UK call regulations compliance for the AI Telemarketer v2 system. It ensures calls adhere to UK regulations regarding calling hours, frequency limits, TPS compliance, and caller ID requirements.

## Features

- **Time restrictions enforcement**: Only permits calls during legal calling hours
- **Frequency restrictions**: Limits calls to the same number within daily and weekly periods
- **TPS compliance**: Checks numbers against the Telephone Preference Service registry
- **Caller ID validation**: Ensures valid caller IDs are used
- **Call logging**: Records all call attempts for compliance tracking
- **Call history**: Provides access to call history for reporting and auditing

## System Architecture

The UK regulations integration consists of these core components:

1. **`uk_regulations_integration.py`**: The main integration module that connects the telemarketer system with the UK regulations logic
2. **`UKRegulationsManager`**: The primary class that manages regulation checks and call logging
3. **`UKCallRegulator`**: The core regulator implementation (imported from `uk_call_regulations.py`)

The system uses a database to track call history and ensure compliance with frequency limits.

## Setup Instructions

### Prerequisites

- Python 3.9+
- SQLite (used by default for call history tracking)
- Optional: A TPS registry file (CSV format with TPS-registered numbers)

### Installation

1. Ensure the `uk_call_regulations.py` file is accessible in either:
   - The same directory as `uk_regulations_integration.py`
   - The parent directory
   - The `/backend/Nova2/` directory

2. The integration will automatically locate the regulations module or use a stub implementation if unavailable.

### Configuration

You can configure the following parameters when initializing the regulations manager:

- `db_path`: Path to the SQLite database for call history (default: "telemarketer_calls.db")
- `tps_path`: Path to the TPS registry file (optional)

Example:
```python
from uk_regulations_integration import get_regulations_manager

# Default configuration
regulations = get_regulations_manager()

# Custom configuration
regulations = get_regulations_manager(
    db_path="/path/to/custom/database.db",
    tps_path="/path/to/tps_registry.csv"
)
```

## Usage in the Telemarketer System

### Integration with the Call Manager

The regulations system is integrated with the `CallManager` by:

1. **Initialization**: The call manager initializes the regulations manager during startup
2. **Pre-call checks**: Before making a call, the call manager checks if it's permitted
3. **Call tracking**: The call manager records all call attempts and outcomes
4. **Call history**: The call manager can retrieve call history for reporting

Example from `call_manager.py`:
```python
# In the CallManager.__init__ method
self.regulations_manager = get_regulations_manager()

# Check if a call is permitted before making it
permitted, reason, violation_type = await self.regulations_manager.check_call_permitted(
    phone_number, caller_id
)
if not permitted:
    # Handle non-permitted call
    raise HTTPException(...)
```

### API Endpoints

The regulations system exposes the following API endpoints:

- `POST /regulations/check`: Check if a call to a number is permitted
- `GET /regulations/history/{phone_number}`: Get call history for a phone number
- `GET /regulations/status`: Get the status of the regulations system

## Testing the Integration

### Manual Testing

You can use the built-in example function to test the system:

```python
from uk_regulations_integration import example_usage
import asyncio

asyncio.run(example_usage())
```

This will perform a basic check of the regulations system.

### API Testing

You can test the API endpoints using tools like curl or Python requests:

```bash
# Check if a call is permitted
curl -X POST http://localhost:8000/regulations/check \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+447123456789", "caller_id": "+441234567890"}'

# Get regulations status
curl http://localhost:8000/regulations/status

# Get history for a number
curl http://localhost:8000/regulations/history/+447123456789
```

### Frontend Testing

The frontend includes a RegulationChecker component for testing compliance:

1. Navigate to the Dashboard page
2. Find the "UK Regulations Compliance Check" section
3. Enter a phone number and caller ID
4. Click "Check Compliance" to see if the number can be called

## Regulatory Requirements

The system enforces the following UK telemarketing regulations:

1. **Calling hours**:
   - Weekdays: 8:00 AM to 9:00 PM
   - Saturdays: 9:00 AM to 5:00 PM
   - Sundays and bank holidays: No calls permitted

2. **Call frequency**:
   - Maximum 3 calls to the same number in a day
   - Maximum 7 calls to the same number in a week

3. **TPS compliance**:
   - Numbers registered with the Telephone Preference Service must not be called
   - Exceptions for existing customers with consent

4. **Caller ID**:
   - Valid caller ID must be provided
   - Caller ID must be a UK number
   - Caller ID must not be withheld

## Troubleshooting

### Common Issues

1. **Missing TPS registry**:
   - If the TPS registry file is not found, the system will log a warning and continue without TPS checking
   - Provide a valid TPS registry file path to enable TPS compliance checks

2. **Database errors**:
   - Check that the database path is writable
   - Ensure the SQLite database is not locked by another process

3. **Stub implementation activated**:
   - If you see the message "Using stub UK call regulations implementation", the system could not find the real implementation
   - Check the paths for `uk_call_regulations.py`

### Logs

The integration logs detailed information about regulation checks and call tracking in the application logs.

Check the logs for messages with the prefix `uk_regulations_integration` to debug issues.

## Contributing

To extend or modify the regulations system:

1. Update the `UKCallRegulator` class in `uk_call_regulations.py` for core regulatory logic
2. Modify the `UKRegulationsManager` in `uk_regulations_integration.py` for integration changes
3. Update the API endpoints in `api.py` for new regulation-related functionality

## License

This code is proprietary and part of the AI Telemarketer system. 