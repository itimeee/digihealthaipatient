"""
Voice Service / บริการเสียง
============================
Service functions for Google Cloud Speech-to-Text and Text-to-Speech.
ฟังก์ชันบริการสำหรับ Google Cloud Speech-to-Text และ Text-to-Speech

This module provides:
- transcribe_audio(): Convert speech to text using Google Cloud STT
- synthesize_speech(): Convert text to speech using Google Cloud TTS
- Helper functions for audio processing

โมดูลนี้ให้บริการ:
- transcribe_audio(): แปลงเสียงเป็นข้อความด้วย Google Cloud STT
- synthesize_speech(): แปลงข้อความเป็นเสียงด้วย Google Cloud TTS
- ฟังก์ชันช่วยเหลือสำหรับการประมวลผลเสียง
"""

import wave
import io
import re
import streamlit as st
from google.oauth2.service_account import Credentials

from voice_config import (
    STT_LANGUAGE_CODE,
    STT_ENABLE_AUTOMATIC_PUNCTUATION,
    STT_MODEL,
    TTS_LANGUAGE_CODE,
    TTS_VOICE_NAME,
    TTS_SPEAKING_RATE,
    TTS_PITCH,
    TTS_AUDIO_ENCODING,
    TTS_VOLUME_GAIN_DB,
    TTS_MODEL_NAME,
    TTS_STYLE_PROMPT,
    TTS_ALLOWED_MODELS,
    VOICE_SAMPLE_RATE,
    ERROR_STT_FAILED,
    ERROR_TTS_FAILED,
    ERROR_NO_AUDIO,
    ERROR_AUDIO_TOO_SHORT,
)


# ============================================================================
# CLIENT INITIALIZATION / การเริ่มต้น Client
# ============================================================================

@st.cache_resource
def get_speech_client():
    """
    Get Google Cloud Speech-to-Text client using service account credentials.
    สร้าง client สำหรับ Google Cloud Speech-to-Text จาก service account

    Returns:
        SpeechClient object or None if initialization fails
    """
    try:
        from google.cloud import speech

        # Load credentials from Streamlit secrets with appropriate scopes
        # โหลด credentials จาก secrets พร้อม scopes ที่เหมาะสม
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=scopes
        )

        # Create and return client / สร้างและคืน client
        client = speech.SpeechClient(credentials=credentials)
        print("[INFO] Speech-to-Text client initialized successfully")
        return client

    except ImportError:
        print("[ERROR] google-cloud-speech not installed")
        return None
    except KeyError:
        print("[ERROR] gcp_service_account not found in secrets")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to initialize Speech client: {e}")
        return None


@st.cache_resource
def get_tts_client():
    """
    Get Google Cloud Text-to-Speech client using service account credentials.
    สร้าง client สำหรับ Google Cloud Text-to-Speech จาก service account

    Returns:
        TextToSpeechClient object or None if initialization fails
    """
    try:
        from google.cloud import texttospeech

        # Load credentials from Streamlit secrets with appropriate scopes
        # โหลด credentials จาก secrets พร้อม scopes ที่เหมาะสม
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=scopes
        )

        # Create and return client / สร้างและคืน client
        client = texttospeech.TextToSpeechClient(credentials=credentials)
        print("[INFO] Text-to-Speech client initialized successfully")
        return client

    except ImportError:
        print("[ERROR] google-cloud-texttospeech not installed")
        return None
    except KeyError:
        print("[ERROR] gcp_service_account not found in secrets")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to initialize TTS client: {e}")
        return None


# ============================================================================
# AUDIO PROCESSING / การประมวลผลเสียง
# ============================================================================

def parse_wav_audio(wav_bytes: bytes) -> tuple:
    """
    Parse WAV audio bytes to extract PCM frames and sample rate.
    แยกวิเคราะห์ข้อมูล WAV เพื่อดึง PCM frames และ sample rate

    Args:
        wav_bytes: Raw WAV file bytes

    Returns:
        Tuple of (pcm_frames: bytes, sample_rate: int, channels: int) or (None, None, None) on error
    """
    try:
        # Open WAV data from bytes / เปิดข้อมูล WAV จาก bytes
        with io.BytesIO(wav_bytes) as wav_buffer:
            with wave.open(wav_buffer, 'rb') as wav_file:
                # Get audio properties / ดึงคุณสมบัติเสียง
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                n_frames = wav_file.getnframes()

                print(f"[DEBUG] WAV properties: rate={sample_rate}Hz, channels={channels}, "
                      f"sample_width={sample_width}bytes, frames={n_frames}")

                # Read all PCM frames / อ่าน PCM frames ทั้งหมด
                pcm_frames = wav_file.readframes(n_frames)

                return pcm_frames, sample_rate, channels

    except wave.Error as e:
        print(f"[ERROR] Invalid WAV format: {e}")
        return None, None, None
    except Exception as e:
        print(f"[ERROR] Failed to parse WAV audio: {e}")
        return None, None, None


# ============================================================================
# SPEECH-TO-TEXT / การแปลงเสียงเป็นข้อความ
# ============================================================================

def transcribe_audio(audio_bytes: bytes) -> tuple:
    """
    Transcribe audio bytes to text using Google Cloud Speech-to-Text.
    แปลงเสียงเป็นข้อความด้วย Google Cloud Speech-to-Text

    Args:
        audio_bytes: WAV audio data (bytes) from st.audio_input

    Returns:
        Tuple of (transcribed_text: str, error_message: str or None)
        - On success: (text, None)
        - On failure: (None, error_message)
    """
    # Validate input / ตรวจสอบ input
    if not audio_bytes or len(audio_bytes) < 100:
        return None, ERROR_NO_AUDIO

    # Parse WAV audio / แยกวิเคราะห์ WAV audio
    pcm_frames, sample_rate, channels = parse_wav_audio(audio_bytes)
    if pcm_frames is None:
        return None, ERROR_STT_FAILED

    # Check if audio is too short (less than 0.5 seconds)
    # ตรวจสอบว่าเสียงสั้นเกินไปหรือไม่ (น้อยกว่า 0.5 วินาที)
    duration_seconds = len(pcm_frames) / (sample_rate * 2 * channels)  # 2 bytes per sample for 16-bit
    if duration_seconds < 0.5:
        return None, ERROR_AUDIO_TOO_SHORT

    # Get Speech client / รับ Speech client
    client = get_speech_client()
    if client is None:
        return None, "Speech-to-Text service unavailable. กรุณาพิมพ์ข้อความแทน"

    try:
        from google.cloud import speech

        # Configure audio / ตั้งค่า audio
        audio = speech.RecognitionAudio(content=pcm_frames)

        # Configure recognition / ตั้งค่าการรู้จำ
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate,
            language_code=STT_LANGUAGE_CODE,
            enable_automatic_punctuation=STT_ENABLE_AUTOMATIC_PUNCTUATION,
            model=STT_MODEL,
            audio_channel_count=channels,
        )

        print(f"[DEBUG] Sending {duration_seconds:.2f}s audio to STT API")

        # Perform synchronous speech recognition / ดำเนินการรู้จำเสียงแบบ sync
        response = client.recognize(config=config, audio=audio)

        # Extract transcription / ดึงข้อความที่ถอดเสียง
        if response.results:
            transcript = ""
            for result in response.results:
                # Get the best alternative / รับตัวเลือกที่ดีที่สุด
                if result.alternatives:
                    transcript += result.alternatives[0].transcript + " "

            transcript = transcript.strip()
            if transcript:
                print(f"[DEBUG] Transcription successful: {transcript[:50]}...")
                return transcript, None
            else:
                return None, "ไม่ได้ยินเสียงพูด กรุณาลองใหม่"
        else:
            return None, "ไม่ได้ยินเสียงพูด กรุณาลองใหม่"

    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] STT failed: {error_msg}")

        # Provide user-friendly error messages
        if "quota" in error_msg.lower():
            return None, "API quota exceeded. กรุณาลองใหม่ภายหลังหรือพิมพ์ข้อความแทน"
        elif "permission" in error_msg.lower() or "403" in error_msg:
            return None, "Speech API not enabled. กรุณาเปิดใช้งาน Speech-to-Text API ใน Google Cloud Console"
        else:
            return None, f"{ERROR_STT_FAILED}: {error_msg[:100]}"


# ============================================================================
# TEXT-TO-SPEECH / การแปลงข้อความเป็นเสียง
# ============================================================================

def normalize_for_tts_th(text: str) -> str:
    """
    Normalize Thai text for TTS to fix pronunciation issues.
    ปรับข้อความภาษาไทยสำหรับ TTS เพื่อแก้ปัญหาการออกเสียง

    Fixes the word "หมอ" (doctor) being pronounced as "หอ-มอ-ออ"
    by inserting a zero-width character to change tokenization.

    Only replaces standalone "หมอ", not compound words like "หมอฟัน", "หมอผี".
    แทนเฉพาะคำว่า "หมอ" เดี่ยวๆ ไม่แทนคำประสม เช่น "หมอฟัน", "หมอผี"

    Args:
        text: Original text to normalize

    Returns:
        Normalized text for TTS (original text is preserved in UI/transcript)
    """
    if not text or not TTS_DOCTOR_FIX:
        return text

    mode = TTS_DOCTOR_FIX.lower()

    # Choose zero-width character based on mode
    # เลือก zero-width character ตามโหมด
    if mode == "zwnj":
        zw_char = "\u200C"  # Zero-Width Non-Joiner
    elif mode == "zwsp":
        zw_char = "\u200B"  # Zero-Width Space
    else:
        return text  # Unknown mode, no change

    # Regex: match "หมอ" NOT followed by Thai consonants/vowels (ก-๙)
    # This avoids matching compound words like หมอฟัน, หมอผี, หมอลำ
    # ไม่แทนคำที่มีตัวอักษรไทยติดท้าย เช่น หมอฟัน, หมอผี, หมอลำ
    pattern = r'หมอ(?![ก-๙])'
    replacement = f'ห{zw_char}มอ'

    text = re.sub(pattern, replacement, text)

    return text


def synthesize_speech(text: str, model_name: str = None, style_prompt: str = None) -> tuple:
    """
    Synthesize speech from text using Google Cloud Text-to-Speech.
    สร้างเสียงจากข้อความด้วย Google Cloud Text-to-Speech

    Args:
        text: Text to convert to speech / ข้อความที่จะแปลงเป็นเสียง
        model_name: TTS model to use (optional, defaults to TTS_MODEL_NAME from config)
                    โมเดล TTS ที่ใช้ (ถ้าไม่ระบุ จะใช้ค่าจาก config)
        style_prompt: Style prompt for Gemini TTS models (optional, defaults to TTS_STYLE_PROMPT)
                      คำสั่งสไตล์สำหรับโมเดล Gemini TTS (ถ้าไม่ระบุ จะใช้ค่าจาก config)

    Returns:
        Tuple of (audio_bytes: bytes, error_message: str or None)
        - On success: (mp3_bytes, None)
        - On failure: (None, error_message)
    """
    # Use config defaults if not provided / ใช้ค่า default จาก config ถ้าไม่ระบุ
    if model_name is None:
        model_name = TTS_MODEL_NAME
    if style_prompt is None:
        style_prompt = TTS_STYLE_PROMPT

    # Validate input / ตรวจสอบ input
    if not text or not text.strip():
        return None, "No text provided for TTS"

    # Validate model name if provided / ตรวจสอบชื่อโมเดลถ้าระบุ
    if model_name and model_name not in TTS_ALLOWED_MODELS:
        allowed = ", ".join(TTS_ALLOWED_MODELS)
        return None, f"Unknown TTS model '{model_name}'. Allowed models: {allowed}"

    # Truncate text if too long (TTS has limits)
    # ตัดข้อความถ้ายาวเกินไป (TTS มี limit)
    max_chars = 5000
    if len(text) > max_chars:
        text = text[:max_chars]
        print(f"[WARNING] Text truncated to {max_chars} chars for TTS")

    # Normalize Thai text for TTS (fixes pronunciation issues)
    # ปรับข้อความภาษาไทยสำหรับ TTS (แก้ปัญหาการออกเสียง)
    original_text = text
    text = normalize_for_tts_th(text)
    if text != original_text:
        print(f"[DEBUG] TTS text normalized: '{original_text[:50]}...' -> '{text[:50]}...'")

    # Get TTS client / รับ TTS client
    client = get_tts_client()
    if client is None:
        return None, "Text-to-Speech service unavailable"

    try:
        from google.cloud import texttospeech

        # Set the text input with optional style prompt / ตั้งค่า text input พร้อม style prompt
        input_params = {"text": text}
        if model_name and style_prompt:
            # Only include prompt when using a Gemini TTS model and prompt is non-empty
            # ใส่ prompt เฉพาะเมื่อใช้โมเดล Gemini TTS และ prompt ไม่ว่าง
            try:
                input_params["prompt"] = style_prompt
            except TypeError:
                # SynthesisInput may not support 'prompt' in older library versions
                print("[WARNING] SynthesisInput does not support 'prompt'. "
                      "Upgrade google-cloud-texttospeech>=2.29.0 for Gemini TTS prompt support.")

        try:
            synthesis_input = texttospeech.SynthesisInput(**input_params)
        except TypeError as te:
            # Graceful fallback if 'prompt' is not supported by installed library version
            if "prompt" in str(te):
                print("[WARNING] SynthesisInput does not support 'prompt' parameter. "
                      "Upgrade google-cloud-texttospeech>=2.29.0 for Gemini TTS prompt support.")
                synthesis_input = texttospeech.SynthesisInput(text=text)
            else:
                raise

        # Build voice parameters / สร้าง parameters สำหรับเสียง
        voice_params = {
            "language_code": TTS_LANGUAGE_CODE,
        }

        # Add voice name if specified / เพิ่มชื่อเสียงถ้าระบุไว้
        if TTS_VOICE_NAME:
            voice_params["name"] = TTS_VOICE_NAME

        # Add model_name for Gemini TTS models / เพิ่ม model_name สำหรับโมเดล Gemini TTS
        if model_name:
            try:
                voice_params["model"] = model_name
                voice = texttospeech.VoiceSelectionParams(**voice_params)
            except TypeError as te:
                if "model" in str(te):
                    print("[WARNING] VoiceSelectionParams does not support 'model' parameter. "
                          "Upgrade google-cloud-texttospeech>=2.29.0 for Gemini TTS model selection.")
                    del voice_params["model"]
                    voice = texttospeech.VoiceSelectionParams(**voice_params)
                else:
                    raise
        else:
            voice = texttospeech.VoiceSelectionParams(**voice_params)

        # Force MP3 encoding for browser compatibility
        # บังคับใช้ MP3 encoding เพื่อความเข้ากันได้กับ browser
        audio_encoding = texttospeech.AudioEncoding.MP3

        # Set audio config / ตั้งค่า audio config
        audio_config = texttospeech.AudioConfig(
            audio_encoding=audio_encoding,
            speaking_rate=TTS_SPEAKING_RATE,
            pitch=TTS_PITCH,
            volume_gain_db=TTS_VOLUME_GAIN_DB,
        )

        print(f"[DEBUG] Synthesizing {len(text)} chars to speech "
              f"(model={model_name or 'classic'}, prompt={'yes' if style_prompt else 'no'})")

        # Perform synthesis / ดำเนินการสังเคราะห์เสียง
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # Return audio content / คืนค่าเนื้อหา audio
        if response.audio_content:
            return response.audio_content, None
        else:
            return None, ERROR_TTS_FAILED

    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] TTS failed: {error_msg}")

        # Provide user-friendly error messages
        if "quota" in error_msg.lower():
            return None, "TTS API quota exceeded"
        elif "permission" in error_msg.lower() or "403" in error_msg:
            return None, "Text-to-Speech API not enabled. กรุณาเปิดใช้งาน API ใน Google Cloud Console"
        elif "model" in error_msg.lower() and "not found" in error_msg.lower():
            return None, (f"TTS model '{model_name}' not available. "
                          "Ensure your project has the Text-to-Speech API enabled and "
                          "google-cloud-texttospeech>=2.29.0 is installed.")
        else:
            return None, f"{ERROR_TTS_FAILED}: {error_msg[:100]}"


# ============================================================================
# UTILITY FUNCTIONS / ฟังก์ชันยูทิลิตี้
# ============================================================================

def is_voice_service_available() -> tuple:
    """
    Check if voice services (STT and TTS) are available.
    ตรวจสอบว่าบริการเสียง (STT และ TTS) พร้อมใช้งานหรือไม่

    Returns:
        Tuple of (stt_available: bool, tts_available: bool)
    """
    stt_available = get_speech_client() is not None
    tts_available = get_tts_client() is not None
    return stt_available, tts_available


def get_voice_service_status() -> dict:
    """
    Get detailed status of voice services.
    รับสถานะโดยละเอียดของบริการเสียง

    Returns:
        Dictionary with service status information
    """
    stt_available, tts_available = is_voice_service_available()

    return {
        "stt_available": stt_available,
        "tts_available": tts_available,
        "voice_enabled": stt_available,  # Voice mode requires at least STT
        "full_voice_enabled": stt_available and tts_available,  # Full voice requires both
    }
