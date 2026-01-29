import os
import logging
from dotenv import load_dotenv
from pathlib import Path
import subprocess

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
import sys
sys.path.insert(0, str(project_root))

# Import necessary components
from Nova2.app.API import NovaAPI
from Nova2.app.tts_data import TTSConditioning
from Nova2.app.inference_engines.inference_tts.inference_elevenlabs import InferenceEngineElevenlabs

# Configuration
TEST_TEXT = "Hello. This is the Eleven Labs audio test. If you can hear this, the audio is working through NoMachine."
ELEVENLABS_MODEL = "eleven_flash_v2_5"
ELEVENLABS_VOICE = "JBFqnCBsd6RMkjVDRZzb"

# Save file path
OUTPUT_FILE = "elevenlabs_test.wav"

def main():
    # Initialize API
    print("Initializing NovaAPI...")
    nova = NovaAPI()
    
    # Get API key
    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
    if not elevenlabs_key:
        print("ERROR: ELEVENLABS_API_KEY not found in environment variables (.env file).")
        return
    
    # Configure TTS
    print("Configuring TTS...")
    conditioning = TTSConditioning(
        model=ELEVENLABS_MODEL,
        voice=ELEVENLABS_VOICE,
        expressivness=0.75,
        stability=0.5,
        similarity_boost=0.75,
        use_speaker_boost=True,
        kwargs={"api_key": elevenlabs_key}
    )
    
    tts_engine = InferenceEngineElevenlabs()
    nova.configure_tts(inference_engine=tts_engine, conditioning=conditioning)
    nova.apply_config_tts()
    
    # Generate audio
    print(f"Generating TTS for: '{TEST_TEXT}'")
    audio_data = nova.run_tts(text=TEST_TEXT, stream=False)
    print(f"Audio generation complete. Got {len(audio_data._audio_data)}ms of audio.")
    
    # Save audio to file
    print(f"Saving audio to {OUTPUT_FILE}...")
    audio_data._audio_data.export(OUTPUT_FILE, format="wav")
    print(f"Audio saved to {OUTPUT_FILE}")
    
    # Play with system player
    print("\nPlaying audio with system player (aplay)...")
    try:
        subprocess.run(["aplay", "-D", "plughw:19", OUTPUT_FILE], check=True)
        print("Audio playback complete.")
    except subprocess.CalledProcessError as e:
        print(f"Error playing audio: {e}")
        print("Trying paplay instead...")
        try:
            subprocess.run(["paplay", "--device=19", OUTPUT_FILE], check=True)
            print("Audio playback with paplay complete.")
        except subprocess.CalledProcessError as e:
            print(f"Error playing with paplay: {e}")
            print(f"Audio file is saved at {OUTPUT_FILE} - try playing manually.")

if __name__ == "__main__":
    main() 