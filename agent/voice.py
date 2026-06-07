import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dotenv
import asyncio
import tempfile
import pathlib
import time

# Dynamic injection of PrerecordedOptions into the deepgram package
# to ensure 'from deepgram import PrerecordedOptions' works in modern SDK versions (like v7+)
# where PrerecordedOptions is not exported from the root namespace.
import deepgram
class PrerecordedOptions:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
deepgram.PrerecordedOptions = PrerecordedOptions
sys.modules['deepgram'].PrerecordedOptions = PrerecordedOptions

# Load environment variables
dotenv.load_dotenv()

class VoiceEngine:
    def __init__(self):
        # Load API keys from environment
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        self.elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        
        # Initialize Deepgram client: from deepgram import DeepgramClient, PrerecordedOptions
        from deepgram import DeepgramClient, PrerecordedOptions
        # Use dummy key if none exists to avoid crash during mock initialization
        api_key = self.deepgram_api_key or "dummy_deepgram_api_key"
        self.dg_client = DeepgramClient(api_key=api_key)
        
        # Initialize ElevenLabs client: from elevenlabs.client import ElevenLabs
        from elevenlabs.client import ElevenLabs
        el_api_key = self.elevenlabs_api_key or "dummy_elevenlabs_api_key"
        self.el_client = ElevenLabs(api_key=el_api_key)
        
        self.sample_rate = 16000
        print("Voice engine initialized.")

    def transcribe_file(self, audio_file_path: str) -> str:
        try:
            with open(audio_file_path, "rb") as file:
                buffer_data = file.read()
            
            from deepgram import PrerecordedOptions
            options = PrerecordedOptions(
                model="nova-2",
                language="en-IN",
                smart_format=True
            )
            
            # Check version features of deepgram client to route appropriately
            if hasattr(self.dg_client, "listen") and hasattr(self.dg_client.listen, "v1"):
                # Deepgram SDK v7+
                response = self.dg_client.listen.v1.media.transcribe_file(
                    request=buffer_data,
                    model="nova-2",
                    language="en-IN",
                    smart_format=True
                )
            else:
                # Deepgram SDK v3-v6
                response = self.dg_client.listen.rest.v("1").transcribe_file(
                    {"buffer": buffer_data},
                    options
                )
            
            transcript = response.results.channels[0].alternatives[0].transcript
            return transcript
        except Exception as e:
            print(f"Deepgram transcription error: {e}")
            return ""

    def transcribe_from_mic(self, duration_seconds: int = 5) -> str:
        try:
            import sounddevice as sd
            from scipy.io import wavfile
        except ImportError:
            print("Install sounddevice and scipy for mic input")
            return ""
            
        fs = self.sample_rate
        print(f"* Recording from microphone for {duration_seconds} seconds...")
        recording = sd.rec(int(duration_seconds * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()
        print("* Recording finished.")
        
        temp_wav_path = os.path.join(tempfile.gettempdir(), f"mic_record_{int(time.time())}.wav")
        try:
            wavfile.write(temp_wav_path, fs, recording)
            transcript = self.transcribe_file(temp_wav_path)
            return transcript
        finally:
            if os.path.exists(temp_wav_path):
                try:
                    os.remove(temp_wav_path)
                except Exception:
                    pass

    def speak(self, text: str, output_file: str = None) -> str:
        try:
            # Clean the text by replacing ₹ with rupees, and removing/replacing double quotes and backticks
            cleaned_text = text.replace("₹", "rupees").replace('"', "'").replace('`', "'").replace('$', '\\$')
            print("🔊 Speaking...")
            os.system(f'say -v Samantha "{cleaned_text}"')
            return "mac_tts"
        except Exception as e:
            print(f"Mac TTS error: {e}")
            return ""

    def speak_and_wait(self, text: str) -> None:
        self.speak(text)


class VoiceConversation:
    def __init__(self, borrower_identifier: str):
        self.voice_engine = VoiceEngine()
        from agent.agent import BorrowerAgent
        self.agent = BorrowerAgent()
        self.borrower_identifier = borrower_identifier
        self.turn_count = 0

    def run_turn(self, use_mic: bool = False, audio_file: str = None) -> tuple[str, str]:
        transcript = ""
        if use_mic:
            transcript = self.voice_engine.transcribe_from_mic()
        elif audio_file:
            transcript = self.voice_engine.transcribe_file(audio_file)
            
        if not transcript:
            transcript = input("Enter your message: ")
            
        print(f"You said: {transcript}")
        response = self.agent.chat(self.borrower_identifier, transcript)
        print(f"Agent: {response}")
        self.voice_engine.speak_and_wait(response)
        self.turn_count += 1
        return (transcript, response)

    def run_demo(self, scenario: int = 3):
        if scenario == 3:
            inputs = [
                "Why was a penalty charged on my account?",
                "Can you waive it? The payment failed because of a bank error.",
                "Please create a ticket for the waiver request."
            ]
        elif scenario == 6:
            inputs = [
                "My salary got delayed. I will pay my EMI next Friday.",
                "I have paid the EMI now."
            ]
        else:
            print(f"Unknown scenario {scenario}")
            return
            
        print(f"\n--- Running Demo Scenario {scenario} ---")
        for i, user_input in enumerate(inputs, 1):
            print(f"\n[Turn {i}]")
            print(f"User: {user_input}")
            response = self.agent.chat(self.borrower_identifier, user_input)
            print(f"Agent: {response}")
            self.voice_engine.speak_and_wait(response)
            self.turn_count += 1

    def run_interactive(self):
        print("\n🎙️  CredResolve Voice Agent - Interactive Mode")
        print("=" * 50)
        print("Type your message and press Enter. Samantha will respond.")
        print("Type 'quit' or 'exit' to end the call.")
        print("=" * 50 + "\n")

        # Opening greeting
        opening = f"Thank you for calling CredResolve. This is your loan servicing agent. How can I help you today?"
        print(f"Agent: {opening}")
        os.system(f'say -v Samantha "{opening}"')

        while True:
            print()
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("quit", "exit", "bye", "goodbye", "thank you bye"):
                farewell = "Thank you for calling CredResolve. Have a great day. Goodbye!"
                print(f"Agent: {farewell}")
                os.system(f'say -v Samantha "{farewell}"')
                break
            
            # Get response from agent
            response = self.agent.chat(self.borrower_identifier, user_input)
            print(f"Agent: {response}")
            
            # Clean text for Mac TTS
            cleaned = response.replace("₹", "rupees ").replace('"', "'").replace('`', "'").replace('$', '')
            os.system(f'say -v Samantha "{cleaned}"')


    def run_voice_interactive(self):
        import sounddevice as sd
        import scipy.io.wavfile as wav
        import numpy as np
        import tempfile

        print("\n🎙️  CredResolve Voice Agent - Voice Mode")
        print("=" * 50)
        print("Press ENTER to start speaking, speak your question, then press ENTER again to stop.")
        print("Type 'quit' and press ENTER to end the call.")
        print("=" * 50 + "\n")

        # Opening greeting
        opening = "Thank you for calling CredResolve. This is your AI loan servicing agent. How can I help you today?"
        print(f"Agent: {opening}")
        os.system(f'say -v Samantha "{opening}"')

        SAMPLE_RATE = 16000

        while True:
            print()
            command = input("Press ENTER to speak (or type 'quit' to exit)... ").strip().lower()
            
            if command == "quit":
                farewell = "Thank you for calling CredResolve. Goodbye!"
                print(f"Agent: {farewell}")
                os.system(f'say -v Samantha "{farewell}"')
                break

            print("🎤 Listening... (press ENTER to stop)")
            
            # Start recording in a thread
            frames = []
            recording = True

            def record_audio():
                with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16') as stream:
                    while recording:
                        data, _ = stream.read(SAMPLE_RATE // 10)
                        frames.append(data.copy())

            import threading
            thread = threading.Thread(target=record_audio)
            thread.start()
            
            input()  # Wait for ENTER to stop
            recording = False
            thread.join()

            if not frames:
                print("No audio captured. Try again.")
                continue

            # Save to temp WAV file
            audio_data = np.concatenate(frames, axis=0)
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            wav.write(tmp.name, SAMPLE_RATE, audio_data)
            
            print("🔄 Transcribing...")
            
            # Transcribe with Deepgram
            transcript = self.voice_engine.transcribe_file(tmp.name)
            os.unlink(tmp.name)
            
            if not transcript or transcript.strip() == "":
                print("Could not understand audio. Please try again.")
                retry = "Sorry, I could not hear you clearly. Could you please repeat that?"
                os.system(f'say -v Samantha "{retry}"')
                continue

            print(f"You said: {transcript}")
            
            # Get agent response
            response = self.agent.chat(self.borrower_identifier, transcript)
            print(f"Agent: {response}")
            
            # Speak response
            cleaned = response.replace("₹", "rupees ").replace('"', "'").replace('`', "'").replace('$', '')
            os.system(f'say -v Samantha "{cleaned}"')


if __name__ == "__main__":
    import sqlite3
    
    # Get DB_PATH from environment or default
    db_path = os.getenv("DB_PATH", "data/borrowers.db")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT phone FROM borrowers WHERE delinquency_status='OVERDUE_30' AND penalty_amount > 0 LIMIT 1;")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        phone = row[0]
        conversation = VoiceConversation(phone)
        conversation.run_voice_interactive()
    else:
        print("No borrowers found in data/borrowers.db")
