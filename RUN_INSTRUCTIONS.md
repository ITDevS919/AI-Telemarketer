# How to Run the AI Telemarketer Project

This guide will walk you through setting up and running the complete AI Telemarketer system.

## Prerequisites

### Required Software
1. **Python 3.12** (or compatible version)
2. **Node.js 18+** and npm
3. **CUDA Toolkit** (if using GPU for STT/TTS) - Optional but recommended
4. **ngrok** (for local development with Twilio WebSocket) - [Download here](https://ngrok.com/)

### Required Accounts & API Keys
1. **Groq API Key** - Get from [Groq Console](https://console.groq.com/)
2. **Twilio Account** - Get from [Twilio Console](https://www.twilio.com/)
   - Account SID
   - Auth Token
   - Phone Number (for outbound calls)
3. **ngrok Account** (free tier works) - For exposing local WebSocket to Twilio

---

## Step 1: Backend Setup

### 1.1 Navigate to Backend Directory
```bash
cd "E:\Temp\AI Voice project\Applications\Applications\AI-telemarketer\telemarketerv2"
```

### 1.2 Create Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 1.3 Install Dependencies
```bash
pip install -r requirements.txt
```

**Note:** If you have CUDA available, you may want to install PyTorch with CUDA support:
```bash
# For CUDA 11.8
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.x
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 1.4 Configure Environment Variables

Edit the `.env` file in `telemarketerv2/` directory:

```env
# Twilio Credentials
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_WEBHOOK_URL=https://your-ngrok-url.ngrok-free.app

# ngrok WebSocket URL (MUST use 'wss://' protocol)
NGROK_WEBSOCKET_URL=wss://your-ngrok-url.ngrok-free.app

# Groq API Key
GROQ_API_KEY=your_groq_api_key

# Optional: Database path
DB_PATH=telemarketer_calls.db

# Optional: TTS Model path (defaults to data/models/en_GB-northern_english_male-medium.onnx)
PIPER_MODEL_PATH=data/models/en_GB-northern_english_male-medium.onnx

# Optional: STT Model (defaults to "base.en")
STT_MODEL_NAME=base.en

# Optional: VAD Settings
VAD_SAMPLE_RATE=16000
VAD_THRESHOLD=0.5
```

### 1.5 Verify TTS Models Exist

Ensure the Piper TTS models are in place:
- `telemarketerv2/data/models/en_GB-northern_english_male-medium.onnx`
- `telemarketerv2/data/models/en_GB-northern_english_male-medium.onnx.json`

If missing, download them from [Piper TTS models](https://github.com/rhasspy/piper/releases).

---

## Step 2: Frontend Setup

### 2.1 Navigate to Frontend Directory
```bash
cd "E:\Temp\AI Voice project\Applications\Applications\AI-telemarketer\frontend\AI Telemarketer"
```

### 2.2 Install Dependencies
```bash
npm install
```

### 2.3 Configure API Endpoint (if needed)

The frontend is configured to connect to `http://localhost:8000/api` by default. If your backend runs on a different port, edit:
- `src/services/api.ts` - Update the `baseURL`

---

## Step 3: Setup ngrok (for Twilio WebSocket)

### 3.1 Install ngrok
Download from [ngrok.com](https://ngrok.com/download) or use package manager:
```bash
# Windows (chocolatey)
choco install ngrok

# Mac (homebrew)
brew install ngrok

# Linux
# Download binary from ngrok.com
```

### 3.2 Authenticate ngrok
```bash
ngrok config add-authtoken YOUR_NGROK_AUTH_TOKEN
```

### 3.3 Start ngrok Tunnel
```bash
# Expose port 8000 (where FastAPI runs)
ngrok http 8000
```

### 3.4 How to set NGROK_WEBSOCKET_URL

1. With the backend running on port 8000, run: **`ngrok http 8000`** (in a separate terminal).
2. ngrok will show a forwarding URL, e.g. **`https://abc123.ngrok-free.app`**.
3. In `telemarketerv2/.env`, set **`NGROK_WEBSOCKET_URL`** to the **same host** but with **`wss://`** (WebSocket Secure), not `https://`:
   ```env
   NGROK_WEBSOCKET_URL=wss://abc123.ngrok-free.app
   ```
4. Restart the backend after changing `.env`. Twilio will connect to `wss://your-subdomain.ngrok-free.app/ws/stream` when placing calls.

**Important:** Use **`wss://`** for the WebSocket; using `https://` will prevent Twilio from connecting to the media stream.

**Note:** The ngrok URL changes each time you restart ngrok (unless you have a paid plan with a static domain).

---

## Step 4: Running the Project

### 4.1 Start ngrok (Terminal 1)
```bash
ngrok http 8000
```
Keep this running and note the WebSocket URL.

### 4.2 Start Backend Server (Terminal 2)
```bash
cd "E:\Temp\AI Voice project\Applications\Applications\AI-telemarketer\telemarketerv2"
# Activate virtual environment if not already active
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Run the FastAPI server (RECOMMENDED)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# OR if you prefer using Python directly (after fixing main.py):
# python -m app.main
```

The backend should start on `http://localhost:8000`

**Verify it's running:**
- Open `http://localhost:8000/docs` to see the Swagger API documentation
- Check console for initialization messages

### 4.3 Start Frontend (Terminal 3)
```bash
cd "E:\Temp\AI Voice project\Applications\Applications\AI-telemarketer\frontend\AI Telemarketer"
npm run dev
```

The frontend should start on `http://localhost:5173` (or another port if 5173 is busy).

---

## Step 5: Using the System

### 5.1 Access the Frontend
Open your browser and navigate to:
```
http://localhost:5173
```

### 5.2 Make a Test Call

1. **Go to Dashboard** - You should see the main dashboard with:
   - Health Status
   - Regulation Checker
   - Single Call Form
   - Control Panel

2. **Add a Call:**
   - Enter a phone number in the Single Call Form
   - Select business type (e.g., "MM" for Making Money)
   - Click "Add Call" or "Make Call"

3. **Start the Dialer:**
   - Use the Control Panel to start the dialer system
   - The dialer will process calls from the queue sequentially

4. **Monitor Calls:**
   - View call status in the Calls view
   - Check leads in the Leads section
   - Review conversation history for completed calls

---

## Troubleshooting

### Backend Issues

**Problem: Module not found errors**
```bash
# Ensure you're in the correct directory and virtual environment is activated
pip install -r requirements.txt
```

**Problem: TTS model not found**
- Verify models exist in `telemarketerv2/data/models/`
- Check the `PIPER_MODEL_PATH` in `.env` matches actual file location
- Download models if missing

**Problem: CUDA/GPU errors**
- If you don't have CUDA, the system will fall back to CPU (slower)
- To force CPU: Set `STT_DEVICE=cpu` in environment or modify code
- For CUDA issues, verify PyTorch CUDA installation:
  ```python
  import torch
  print(torch.cuda.is_available())
  ```

**Problem: Twilio WebSocket connection fails**
- Verify ngrok is running and URL is correct
- Ensure `NGROK_WEBSOCKET_URL` uses `wss://` protocol (not `https://`)
- Check ngrok tunnel is pointing to port 8000
- Verify Twilio webhook URL in Twilio console matches your ngrok URL

### Frontend Issues

**Problem: Cannot connect to backend**
- Verify backend is running on port 8000
- Check CORS settings in `main.py` (should allow all origins in dev)
- Verify API base URL in `src/services/api.ts`

**Problem: npm install fails**
- Try clearing cache: `npm cache clean --force`
- Delete `node_modules` and `package-lock.json`, then reinstall
- Ensure Node.js version is 18+

### General Issues

**Problem: Database errors**
- Ensure write permissions in the project directory
- Check `DB_PATH` in `.env` is correct
- Database will be created automatically on first run

**Problem: API key errors**
- Verify all API keys in `.env` are correct
- Check Groq API key is valid and has credits
- Verify Twilio credentials are correct

---

## Development Mode

### Backend with Auto-reload
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend with Hot Reload
```bash
npm run dev
```

### Running Tests
```bash
# Backend tests (if available)
cd telemarketerv2
pytest

# Frontend tests
cd frontend/"AI Telemarketer"
npm run test:unit
```

---

## Production Deployment

For production deployment:

1. **Update CORS settings** in `main.py` to restrict origins
2. **Use a proper domain** instead of ngrok
3. **Set up SSL/TLS** for WebSocket (wss://)
4. **Use environment variables** for all secrets (never commit `.env`)
5. **Set up proper logging** and monitoring
6. **Configure database backups**
7. **Use a production ASGI server** like Gunicorn with Uvicorn workers

---

## Quick Start Checklist

- [ ] Python 3.12 installed
- [ ] Node.js 18+ installed
- [ ] Virtual environment created and activated
- [ ] Backend dependencies installed (`pip install -r requirements.txt`)
- [ ] Frontend dependencies installed (`npm install`)
- [ ] `.env` file configured with all API keys
- [ ] TTS models present in `data/models/`
- [ ] ngrok installed and authenticated
- [ ] ngrok tunnel running on port 8000
- [ ] Backend server running on port 8000
- [ ] Frontend dev server running
- [ ] Browser opened to frontend URL

---

## Additional Resources

- **API Documentation:** `http://localhost:8000/docs` (Swagger UI)
- **RealtimeSTT Docs:** See `RealtimeStt_docs.md`
- **Script Files:** Located in `telemarketerv2/data/scripts/`
- **Database:** SQLite file created at path specified in `DB_PATH`

---

## Support

If you encounter issues:
1. Check the console logs for error messages
2. Verify all environment variables are set correctly
3. Ensure all services are running (ngrok, backend, frontend)
4. Check that ports 8000 and 5173 are not in use by other applications
