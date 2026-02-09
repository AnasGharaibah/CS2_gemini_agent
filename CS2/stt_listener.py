import speech_recognition as sr
import keyboard
import time
import mss
import mss.tools

class STTListener:
    def __init__(self, brain_instance, tts_callback, trigger_key='v'):
        self.brain = brain_instance
        self.tts_callback = tts_callback
        self.trigger_key = trigger_key
        
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300 
        self.recognizer.dynamic_energy_threshold = True
        self.microphone = sr.Microphone()
        
        print("🎤 Calibrating Microphone... (Please remain silent)")
        with self.microphone as source:
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                print("✅ Microphone Calibrated.")
            except Exception:
                pass

    def listen_loop(self, get_latest_payload_func, get_match_history_func):
        print(f"👂 STT Listener Active. Hold '{self.trigger_key.upper()}' to speak.")
        
        with self.microphone as source:
            while True:
                try:
                    # 1. Wait for Key Press
                    keyboard.wait(self.trigger_key)
                    
                    if not get_latest_payload_func():
                        time.sleep(1) # Wait longer if no game found
                        continue

                    print("\n🔴 Listening...")
                    
                    # --- VISION: Capture screen at the moment of the request ---
                    screenshot_data = None
                    try:
                        with mss.mss() as sct:
                            # Capture the primary monitor
                            monitor = sct.monitors[1]
                            sct_img = sct.grab(monitor)
                            screenshot_data = mss.tools.to_png(sct_img.rgb, sct_img.size)
                    except Exception as e:
                        print(f"⚠️ Vision Error: Could not capture screen: {e}")

                    # 2. Record Audio
                    try:
                        # reduced phrase_time_limit to avoid hanging
                        audio_data = self.recognizer.listen(source, timeout=2, phrase_time_limit=5)
                    except sr.WaitTimeoutError:
                        print("❌ No speech detected.")
                        continue

                    # 3. Transcribe
                    try:
                        user_text = self.recognizer.recognize_google(audio_data)
                        print(f"🗣️ You said: '{user_text}'")
                        
                        # --- SAFETY CHECK: Ignore short/empty garbage ---
                        if not user_text or len(user_text) < 2:
                            print("⚠️ Ignoring short/empty input.")
                            continue

                        # 4. Ask Brain (Now protected by Rate Limiter inside AgentBrain)
                        # Adding a small retry loop for potential 409 errors or rate limiting
                        max_retries = 2
                        response = "My brain is overloaded. Give me a second."
                        for attempt in range(max_retries):
                            response = self.brain.ask_coach(
                                user_query=user_text, 
                                gsi_payload=get_latest_payload_func(), 
                                match_history=get_match_history_func(),
                                image_data=screenshot_data
                            )
                            # If we get a real answer, stop retrying
                            if "Hold on, I'm thinking." not in response and "My brain is overloaded" not in response and "tired from too many questions" not in response:
                                break
                            if attempt < max_retries - 1:
                                print(f"🔄 Retrying coaching request ({attempt + 1}/{max_retries})...")
                                time.sleep(2)
                        
                        print(f"🤖 Coach: {response}")
                        self.tts_callback(response)
                        
                    except sr.UnknownValueError:
                        print("🤷 Unintelligible noise.")
                    except sr.RequestError:
                        print("⚠️ STT Connection Error.")

                    # 5. CRITICAL: Wait for key release to prevent loops
                    # If the user is still holding V, this loop waits here until they let go.
                    while keyboard.is_pressed(self.trigger_key):
                        time.sleep(0.1)

                except Exception as e:
                    print(f"STT Loop Error: {e}")
                    time.sleep(1)