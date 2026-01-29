# AI Telemarketer Frontend

This is the frontend application for the AI Telemarketer v2 system. It's built with Vue 3 and provides a user interface for managing outbound AI phone calls.

## Features

- Monitor system health (STT, TTS, VAD, LLM)
- Make individual calls with custom phone numbers and script types
- Start batch calls from a list of phone numbers
- View call history and detailed conversation logs
- Real-time status updates

## Prerequisites

- Node.js (v18+)
- npm or yarn
- AI Telemarketer v2 backend server running

## Setup Instructions

1. Navigate to the frontend directory:

```bash
cd frontend/AI\ Telemarketer
```

2. Install dependencies:

```bash
npm install
```

3. Configure API Endpoint:

The default API endpoint is set to `http://localhost:8000`. If your backend is running on a different URL, update the `API_BASE_URL` in `src/services/api.ts`.

## Development

Run the development server:

```bash
npm run dev
```

This will start the development server, typically on http://localhost:5173

## Production Build

Build for production:

```bash
npm run build
```

The built files will be in the `dist` directory, which can be served by any static file server.

## Usage

1. Start the v2 backend server first
2. Start the frontend development server
3. Open the frontend in your browser
4. Check the system health on the dashboard
5. Use the Single Call feature to make individual calls
6. Use the Batch Calls feature to initiate multiple calls

## API Connection

The frontend connects to the telemarketer v2 backend API to:

- Check system health status
- Initiate new calls
- Retrieve call history and details

## Troubleshooting

- If calls aren't showing up in the list, check that the backend server is running
- If the health check fails, ensure all models and services are properly loaded in the backend
- For network errors, verify the `API_BASE_URL` matches your backend server address

## License

This project is proprietary software. 