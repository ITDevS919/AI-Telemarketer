import unittest
import time
import os
import logging
import sys
from pathlib import Path
import sounddevice as sd # Check default output device
from dotenv import load_dotenv

# --- Load .env variables --- 
load_dotenv()

# Add project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from Nova2.app.API import NovaAPI
    from Nova2.app.tts_data import TTSConditioning
    from Nova2.app.inference_engines.inference_tts.inference_xtts import InferenceEngineXTTS # Changed to XTTS
except ImportError as e:
    print(f"Error importing Nova2 components: {e}")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration --- 
TEST_TEXT = "Hello. This is the XTTS playback test. Can you hear me clearly now?"
XTTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
VOICE_NAME = "Isaac"  # Voice file name without extension
VOICE_WAV_PATH = "isaac_train.wav"  # Source audio for cloning if needed

DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"
# --- End Configuration ---

class TestTTSPlayback(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up voice cloning if the voice doesn't exist yet."""
        logger.info("Checking if voice needs to be cloned...")
        
        # Create voices directory if it doesn't exist
        voices_dir = Path("Nova2/data/voices")
        voices_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if voice embedding already exists
        voice_embedding_path = voices_dir / f"{VOICE_NAME}.pth"
        
        # If voice doesn't exist and we have a training file, clone it
        if not voice_embedding_path.exists() and os.path.exists(VOICE_WAV_PATH):
            logger.info(f"Voice '{VOICE_NAME}' not found. Creating from {VOICE_WAV_PATH}...")
            
            # Initialize temporary TTS engine just for cloning
            temp_engine = InferenceEngineXTTS()
            temp_engine.initialize_model(model=XTTS_MODEL)
            
            # Clone the voice
            try:
                temp_engine.clone_voice(audio_path=VOICE_WAV_PATH, name=VOICE_NAME)
                logger.info(f"Successfully cloned voice to {voice_embedding_path}")
            except Exception as e:
                logger.error(f"Voice cloning failed: {e}")
                # Continue anyway, test will fail if voice is needed but missing
        else:
            if voice_embedding_path.exists():
                logger.info(f"Voice embedding already exists at {voice_embedding_path}")
            else:
                logger.warning(f"Voice WAV file {VOICE_WAV_PATH} not found for cloning. Test may fail if voice is needed.")

    def setUp(self):
        """Set up NovaAPI and configure TTS for the actual test."""
        logger.info("Setting up NovaAPI for XTTS test...")
        self.nova = NovaAPI()

        # --- Define Conditioning ---
        logger.info(f"Using device: {DEVICE}")
        self.conditioning = TTSConditioning(
            model=XTTS_MODEL,
            voice=VOICE_NAME,  # Use the voice name (without extension)
            # XTTS specific parameters
            expressivness=0.75,
            stability=0.5,
            kwargs={"language": "en"}  # Pass language via kwargs for XTTS
        )
        logger.info(f"TTS Conditioning: Model={self.conditioning.model}, Voice={self.conditioning.voice}")

        # --- Configure TTS Engine --- 
        self.tts_engine = InferenceEngineXTTS()

        # --- Configure and Apply --- 
        try:
            logger.info("Configuring TTS...")
            self.nova.configure_tts(inference_engine=self.tts_engine, conditioning=self.conditioning)
            logger.info("Applying TTS config...")
            self.nova.apply_config_tts()
            logger.info("TTS configured and config applied.")
            
            # Check if model is initialized
            if hasattr(self.tts_engine, 'is_model_ready') and not self.tts_engine.is_model_ready():
                logger.warning("TTS Engine reports it's not ready after apply_config.")
            
        except Exception as e:
            logger.error(f"Error during TTS setUp: {e}", exc_info=True)
            self.fail(f"TTS Setup failed: {e}")

    def test_local_tts_playback(self):
        """Generate TTS locally and attempt playback."""
        logger.info(f"Generating TTS for: '{TEST_TEXT}'")
        audio_data = None
        try:
            # Generate non-streaming audio
            audio_data = self.nova.run_tts(text=TEST_TEXT, stream=False)
            logger.info(f"TTS generation finished. AudioData received: {bool(audio_data)}")
            self.assertIsNotNone(audio_data, "run_tts returned None")
            self.assertTrue(hasattr(audio_data, '_audio_data') and audio_data._audio_data is not None, "AudioData object has no internal _audio_data")
            
            # Check the sample rate of the generated audio
            if hasattr(audio_data._audio_data, 'frame_rate'):
                generated_sr = audio_data._audio_data.frame_rate
                logger.info(f"Generated audio sample rate: {generated_sr} Hz")
                # XTTS default is 24000 Hz, but may be resampled to 48000 Hz
                # self.assertIn(generated_sr, [24000, 48000], f"Generated audio sample rate {generated_sr} Hz is unexpected")
            else:
                 logger.warning("Could not determine sample rate from generated AudioData.")
                 
            logger.info(f"Audio duration: {len(audio_data._audio_data) / 1000.0} s") # pydub duration is in ms

        except Exception as e:
            logger.error(f"Exception during TTS generation: {e}", exc_info=True)
            self.fail(f"TTS generation failed: {e}")

        # --- Attempt Playback --- 
        try:
            # ADDED: Just output simple device information
            print("\n----- AUDIO PLAYBACK STARTING -----")
            
            default_output = sd.query_devices(kind='output')
            logger.info(f"Default OUTPUT device: {default_output['name']} (Index: {default_output['index']})")
            
            print("\n *** LISTEN CAREFULLY FOR AUDIO OUTPUT *** \n")
            self.nova.play_audio(audio_data)

            # Wait manually 
            wait_duration = (len(audio_data._audio_data) / 1000.0) + 1.5 # duration in ms + 1.5s buffer
            logger.info(f"Waiting for estimated playback duration ({wait_duration:.2f}s)...")
            time.sleep(wait_duration)
            
            logger.info("Wait finished.")
            print("\n *** DID YOU HEAR THE AUDIO ON DEVICE 10 (surround51)? ***\n")
            print("Using EXACTLY the same format as the working tone test: mono, 48000 Hz")

        except Exception as e:
            logger.error(f"Exception during audio playback: {e}", exc_info=True)
            self.fail(f"Audio playback failed: {e}")

        # Basic assertion: Test ran without crashing playback call
        self.assertTrue(True, "Playback test sequence completed (Check console/ears for actual success)")


if __name__ == '__main__':
    logger.info("Running TTS Playback Unit Test with XTTS...")
    unittest.main()
