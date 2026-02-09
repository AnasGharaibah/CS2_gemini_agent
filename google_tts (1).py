"""
Google TTS and STT Implementation
Uses Google Gemini API for Speech-to-Text and gTTS for Text-to-Speech
"""

import os
from pathlib import Path
from typing import Optional
from google import genai
from google.genai import types
from gtts import gTTS
from dotenv import load_dotenv



class GoogleTTS:
    """Text-to-Speech using Google TTS (gTTS)"""
    
    def __init__(self, language: str = 'en', slow: bool = False):
        """
        Initialize TTS
        
        Args:
            language: Language code (e.g., 'en', 'es', 'fr')
            slow: If True, speaks slower
        """
        self.language = language
        self.slow = slow
    
    def speak(self, text: str, output_path: str, language: Optional[str] = None, slow: Optional[bool] = None) -> str:
        """
        Convert text to speech and save to file
        
        Args:
            text: Text to convert to speech
            output_path: Path to save audio file (should end with .mp3)
            language: Override default language
            slow: Override default speed
            
        Returns:
            Path to saved audio file
        """
        if not text:
            raise ValueError("Text cannot be empty")
        
        lang = language or self.language
        is_slow = slow if slow is not None else self.slow
        
        print(f"Generating speech for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        
        # Create TTS object
        tts = gTTS(text=text, lang=lang, slow=is_slow)
        
        # Save to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        tts.save(str(output_path))
        print(f"Audio saved to: {output_path}")
        
        return str(output_path)
    
    def speak_to_bytes(self, text: str, language: Optional[str] = None, slow: Optional[bool] = None) -> bytes:
        """
        Convert text to speech and return as bytes
        
        Args:
            text: Text to convert to speech
            language: Override default language
            slow: Override default speed
            
        Returns:
            Audio data as bytes
        """
        import io
        
        lang = language or self.language
        is_slow = slow if slow is not None else self.slow
        
        tts = gTTS(text=text, lang=lang, slow=is_slow)
        
        # Save to BytesIO
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        
        return audio_bytes.read()


# Convenience functions
def text_to_speech(text: str, output_path: str, language: str = 'en', slow: bool = False) -> str:
    """
    Quick function to convert text to speech
    
    Args:
        text: Text to convert
        output_path: Where to save audio file
        language: Language code
        slow: Speak slowly
        
    Returns:
        Path to saved audio file
    """
    tts = GoogleTTS(language=language, slow=slow)
    return tts.speak(text, output_path)


def speech_to_text(audio_path: str, api_key: Optional[str] = None) -> str:
    """
    Quick function to transcribe audio to text
    
    Args:
        audio_path: Path to audio file
        api_key: Google API key (optional if set in environment)
        
    Returns:
        Transcribed text
    """
    stt = GoogleSTT(api_key=api_key)
    return stt.transcribe(audio_path)


if __name__ == "__main__":
    # Example usage
   tts = GoogleTTS(language='en', slow=False)
   tts.speak("Hello, world!", "output.mp3")