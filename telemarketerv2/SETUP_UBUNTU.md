# Running the AI Telemarketer Backend on Ubuntu

This guide covers setting up and running the backend on a **local Ubuntu server** (or any Linux machine).

---

## 1. Prerequisites

- **Ubuntu** 20.04 or 22.04 (or similar Debian-based system).
- **Python 3.10 or 3.11** (3.12 may work; avoid 3.13 until dependencies are confirmed).
- **Optional:** NVIDIA GPU + CUDA for faster STT/VAD (see [REALTIME_FEATURES.md](REALTIME_FEATURES.md)).

### Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
# Optional: for some audio/ML libs
sudo apt install -y build-essential portaudio19-dev libsndfile1 ffmpeg
```

Check Python version:

```bash
python3 --version   # e.g. 3.10 or 3.11
```

---

## 2. Project setup

### 2.1 Get the code on the server

Copy or clone the project so the **backend** folder is available, e.g.:

```bash
# If using git
cd /opt   # or ~/projects
git clone <your-repo-url> AI-telemarketer
cd AI-telemarketer/backend
```

Or copy the whole project (including `backend/`) to the server via SCP, rsync, or USB.

### 2.2 Use the backend as the working directory

All following commands assume you are **inside the backend directory**:

```bash
cd /path/to/AI-telemarketer/backend
pwd   # e.g. /home/user/AI-telemarketer/backend
```

---

## 3. Python environment and dependencies

### 3.1 Create and activate a virtual environment

```bash
cd /path/to/AI-telemarketer/backend
python3 -m venv venv
source venv/bin/activate
```

Your prompt should show `(venv)`.

### 3.2 Install Python packages

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

- First run may take a few minutes (PyTorch, Whisper, etc.).
- If you have a **GPU and want CUDA**, install the matching PyTorch build after `requirements.txt`, e.g.:
  ```bash
  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
  ```

### 3.3 Piper TTS model (required for TTS)

The app expects a Piper model under `backend/data/models/`:

- **If you already have** `en_GB-northern_english_male-medium.onnx` and `en_GB-northern_english_male-medium.onnx.json` in `backend/data/models/`, you’re set.
- **If not**, download from [Piper voice catalog](https://huggingface.co/rhasspy/piper-voices) (e.g. `en_GB/northern_english_male/medium`) and place:
  - `en_GB-northern_english_male-medium.onnx`
  - `en_GB-northern_english_male-medium.onnx.json`  
  in `backend/data/models/`.

You can override the path with:

```bash
export PIPER_MODEL_PATH=/absolute/path/to/your/model.onnx
```

---

## 4. Environment configuration

Create a `.env` file in the **backend** directory:

```bash
cd /path/to/AI-telemarketer/backend
nano .env
```

### 4.1 Minimum required variables

```env
# Twilio (for outbound calls and media)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+44xxxxxxxxxx

# WebSocket URL Twilio uses to reach this server (must be reachable from the internet)
# Use ngrok or your public URL with wss://
NGROK_WEBSOCKET_URL=wss://your-ngrok-or-domain.com

# LLM
GROQ_API_KEY=your_groq_api_key

# Database (SQLite by default)
DB_PATH=telemarketer_calls.db
```

### 4.2 Optional

```env
# Voice cloning (ElevenLabs)
ELEVENLABS_API_KEY=your_elevenlabs_key

# PostgreSQL (if not using SQLite)
# DATABASE_URL=postgresql://user:pass@localhost:5432/telemarketer_db

# STT model size: base.en, small.en, medium, large-v2 (larger = slower, more accurate)
STT_MODEL_NAME=base.en

# Real-time features (see REALTIME_FEATURES.md)
REALTIME_TTS_STREAMING=true
REALTIME_STT_PARTIALS=true
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X` in nano).

---

## 5. Run the server

### 5.1 Development (foreground, auto-reload)

From the **backend** directory with the venv activated:

```bash
cd /path/to/AI-telemarketer/backend
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Host `0.0.0.0`** allows access from other machines on your network.
- **Port 8000** – change with `--port 8080` if needed.
- **`--reload`** restarts the app when code changes (development only).

You should see logs and “Application startup complete.” Open:

- API: `http://<server-ip>:8000`
- Docs: `http://<server-ip>:8000/docs`

### 5.2 Production (no reload, recommended for server)

```bash
cd /path/to/AI-telemarketer/backend
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Omit `--reload` so the process stays stable.

### 5.3 Using the run script

From the **backend** directory:

```bash
chmod +x run.sh
./run.sh           # Production (no reload)
./run.sh --reload  # Development (auto-reload)
```

The script uses the `venv` in the same folder and listens on `0.0.0.0:8000`.

---

## 6. Exposing the server to the internet (for Twilio)

Twilio must reach your WebSocket endpoint. Options:

### Option A: ngrok (quick testing)

```bash
# Install ngrok, then:
ngrok http 8000
```

Use the **HTTPS** URL ngrok shows (e.g. `https://abc123.ngrok-free.app`). In `.env` set:

```env
NGROK_WEBSOCKET_URL=wss://abc123.ngrok-free.app
```

Twilio will connect to `wss://abc123.ngrok-free.app/ws/stream` (your app serves the WebSocket at `/ws/stream`). Ensure your Twilio webhook / dial config uses this base URL and path.

### Option B: Public IP + port forward

1. On your router, forward **TCP 8000** (or your chosen port) to the Ubuntu machine’s LAN IP.
2. Use your **public IP** or a domain pointing to it.
3. For **WSS**, put a reverse proxy (e.g. Nginx) in front with SSL and proxy to `http://127.0.0.1:8000`, then set:

   ```env
   NGROK_WEBSOCKET_URL=wss://your-domain.com
   ```

---

## 7. Run as a systemd service (optional, production)

So the server starts on boot and restarts on failure:

### 7.1 Create the service file

```bash
sudo nano /etc/systemd/system/ai-telemarketer.service
```

Use your actual paths and user:

```ini
[Unit]
Description=AI Telemarketer Backend
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
Group=YOUR_USERNAME
WorkingDirectory=/path/to/AI-telemarketer/backend
Environment="PATH=/path/to/AI-telemarketer/backend/venv/bin"
ExecStart=/path/to/AI-telemarketer/backend/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Replace:

- `YOUR_USERNAME` with your Linux user.
- `/path/to/AI-telemarketer/backend` with the real backend path.

### 7.2 Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-telemarketer
sudo systemctl start ai-telemarketer
sudo systemctl status ai-telemarketer
```

Useful commands:

```bash
sudo systemctl stop ai-telemarketer
sudo systemctl restart ai-telemarketer
journalctl -u ai-telemarketer -f
```

---

## 8. Firewall (optional)

If UFW is enabled:

```bash
sudo ufw allow 8000/tcp
sudo ufw reload
```

---

## 9. Quick checklist

- [ ] Python 3.10+ and venv created in `backend`
- [ ] `pip install -r requirements.txt` done
- [ ] Piper model in `backend/data/models/` (or `PIPER_MODEL_PATH` set)
- [ ] `.env` in `backend` with Twilio, Groq, and `NGROK_WEBSOCKET_URL` (or your WSS URL)
- [ ] Run: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- [ ] Twilio webhook/dial config points to your public WSS URL + `/ws/stream`

For real-time behaviour and GPU notes, see [REALTIME_FEATURES.md](REALTIME_FEATURES.md).
