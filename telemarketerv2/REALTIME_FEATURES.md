# Real-time STT & TTS

The backend supports **real-time (streaming) STT and TTS** for lower latency and a more natural call experience.

## Real-time TTS

- **Streaming delivery:** Audio is sent to Twilio in **20ms frames** (Twilio standard) instead of one large blob, so playback can start immediately and stay in sync.
- **Piper (sentence-by-sentence):** When enabled, each sentence is synthesized and streamed before the next is generated, so the first sentence plays while the rest is still being generated.
- **ElevenLabs:** Full response is synthesized in one API call, then streamed in 20ms frames.

**Environment variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `REALTIME_TTS_STREAMING` | `true` | Send TTS in 20ms frames. Set to `false` to send one blob (old behavior). |
| `REALTIME_TTS_PIPER_SENTENCE_STREAM` | `true` | For Piper only: synthesize and send sentence-by-sentence for faster time-to-first-byte. |

## Real-time STT (partial transcripts)

- **Turn-based final:** The **final** transcript is still produced when the user stops speaking (VAD end) and is the one used for the LLM and conversation.
- **Partial transcripts:** While the user is still speaking, the backend can run STT on the current buffer at a fixed interval and log (or later expose) **partial** transcripts. This gives real-time feedback without changing conversation logic.

**Environment variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `REALTIME_STT_PARTIALS` | `true` | Enable partial STT while the user is speaking. |
| `REALTIME_STT_PARTIAL_INTERVAL_MS` | `400` | How often (ms) to run STT for a partial transcript. |
| `REALTIME_STT_PARTIAL_MIN_BYTES` | `8000` | Minimum audio (~0.5s at 16kHz) before first partial. |

---

## Do I need a GPU?

**No. A GPU is not required.** The server runs on CPU by default.

- **STT (Faster-Whisper)** and **VAD (Silero)** use CUDA if available, otherwise CPU. With real-time partial STT, more frequent transcription runs can increase CPU load.
- **TTS:** Piper runs on CPU (ONNX). ElevenLabs is a cloud API.
- **LLM (Groq):** Cloud API.

**Recommendations:**

| Setup | Notes |
|-------|--------|
| **CPU only** | Use a smaller STT model (`STT_MODEL_NAME=base.en` or `small.en`) for acceptable latency. Partial STT interval ≥ 500ms to reduce load. |
| **With GPU** | Lower latency and smoother experience with real-time partials; you can use larger STT models (e.g. `medium`, `large-v2`) and shorter partial intervals. |

So: **GPU is optional** and improves latency and throughput for real-time STT; it is **not** required to run the server.
