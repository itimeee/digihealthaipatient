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
import json
import streamlit as st
from google.oauth2.service_account import Credentials

from voice_config import (
    STT_LANGUAGE_CODE,
    STT_ALTERNATIVE_LANGUAGE_CODES,
    STT_ENABLE_AUTOMATIC_PUNCTUATION,
    STT_MODEL,
    TTS_LANGUAGE_CODE,
    TTS_VOICE_NAME,
    TTS_SPEAKING_RATE,
    TTS_PITCH,
    TTS_AUDIO_ENCODING,
    TTS_VOLUME_GAIN_DB,
    TTS_DOCTOR_FIX,
    VOICE_SAMPLE_RATE,
    ERROR_STT_FAILED,
    ERROR_TTS_FAILED,
    ERROR_NO_AUDIO,
    ERROR_AUDIO_TOO_SHORT,
    get_tts_voice_name,
)


# ============================================================================
# CREDENTIAL LOADING / การโหลด Credentials
# ============================================================================

# Track if we've already logged the credential error (to avoid spam)
_credential_error_logged = False


def load_gcp_credentials() -> tuple:
    """
    Load GCP service account credentials from Streamlit secrets robustly.
    โหลด GCP service account credentials จาก Streamlit secrets อย่าง robust

    Supports:
    - Dict-like TOML table format: st.secrets["gcp_service_account"] as mapping
    - JSON string format: st.secrets["gcp_service_account"] as JSON string
    - Normalizes private_key newlines (\\n -> \n)

    Returns:
        Tuple of (credentials_dict: dict, error_message: str or None)
        - On success: (dict, None)
        - On failure: (None, error_message)
    """
    global _credential_error_logged

    try:
        # Check if gcp_service_account exists in secrets
        if "gcp_service_account" not in st.secrets:
            error_msg = "gcp_service_account not found in secrets"
            if not _credential_error_logged:
                print(f"[VOICE][ERROR] {error_msg}")
                _credential_error_logged = True
            return None, error_msg

        raw_creds = st.secrets["gcp_service_account"]

        # Handle different formats
        if isinstance(raw_creds, str):
            # It's a JSON string, parse it
            try:
                credentials_dict = json.loads(raw_creds)
                print("[VOICE][DEBUG] Parsed gcp_service_account from JSON string")
            except json.JSONDecodeError as e:
                error_msg = f"gcp_service_account is string but not valid JSON: {type(e).__name__}"
                if not _credential_error_logged:
                    print(f"[VOICE][ERROR] {error_msg}")
                    _credential_error_logged = True
                return None, error_msg
        else:
            # It's dict-like (TOML table), convert to dict
            try:
                credentials_dict = dict(raw_creds)
                print("[VOICE][DEBUG] Loaded gcp_service_account from TOML table")
            except Exception as e:
                error_msg = f"Failed to convert gcp_service_account to dict: {type(e).__name__}"
                if not _credential_error_logged:
                    print(f"[VOICE][ERROR] {error_msg}")
                    _credential_error_logged = True
                return None, error_msg

        # Normalize private_key newlines
        # Some environments store literal "\\n" instead of actual newlines
        if "private_key" in credentials_dict:
            pk = credentials_dict["private_key"]
            if isinstance(pk, str):
                # Check if it has literal \n but no actual newlines
                if "\\n" in pk and "\n" not in pk.replace("\\n", ""):
                    credentials_dict["private_key"] = pk.replace("\\n", "\n")
                    print("[VOICE][DEBUG] Normalized private_key newlines (\\\\n -> \\n)")

        # Validate required fields
        required_fields = ["type", "project_id", "private_key", "client_email"]
        missing = [f for f in required_fields if f not in credentials_dict]
        if missing:
            error_msg = f"Missing required fields in gcp_service_account: {missing}"
            if not _credential_error_logged:
                print(f"[VOICE][ERROR] {error_msg}")
                _credential_error_logged = True
            return None, error_msg

        # Log success (without exposing secrets)
        project_id = credentials_dict.get("project_id", "unknown")
        # Only show first few chars of project_id for debugging
        project_hint = project_id[:8] + "..." if len(project_id) > 8 else project_id
        print(f"[VOICE][DEBUG] Credentials loaded successfully (project: {project_hint})")

        return credentials_dict, None

    except Exception as e:
        error_msg = f"Unexpected error loading credentials: {type(e).__name__}"
        if not _credential_error_logged:
            print(f"[VOICE][ERROR] {error_msg}: {str(e)[:100]}")
            _credential_error_logged = True
        return None, error_msg


def get_credential_debug_info() -> dict:
    """
    Get safe debug information about credential status (no secrets exposed).
    รับข้อมูล debug เกี่ยวกับสถานะ credentials อย่างปลอดภัย (ไม่เปิดเผย secrets)

    Returns:
        Dictionary with debug information safe to display
    """
    info = {
        "has_gcp_service_account": False,
        "gcp_service_account_type": "none",
        "has_private_key": False,
        "has_client_email": False,
        "project_id_hint": None,
        "error": None,
    }

    try:
        if "gcp_service_account" not in st.secrets:
            info["error"] = "gcp_service_account not in secrets"
            return info

        info["has_gcp_service_account"] = True
        raw_creds = st.secrets["gcp_service_account"]

        if isinstance(raw_creds, str):
            info["gcp_service_account_type"] = "string"
            try:
                creds_dict = json.loads(raw_creds)
            except json.JSONDecodeError:
                info["error"] = "JSON parse failed"
                return info
        else:
            info["gcp_service_account_type"] = "mapping"
            creds_dict = dict(raw_creds)

        info["has_private_key"] = "private_key" in creds_dict and bool(creds_dict.get("private_key"))
        info["has_client_email"] = "client_email" in creds_dict and bool(creds_dict.get("client_email"))

        if "project_id" in creds_dict:
            pid = creds_dict["project_id"]
            info["project_id_hint"] = pid[:8] + "..." if len(pid) > 8 else pid

    except Exception as e:
        info["error"] = f"{type(e).__name__}: {str(e)[:50]}"

    return info


# ============================================================================
# CLIENT INITIALIZATION / การเริ่มต้น Client
# ============================================================================

# Store clients in module-level variables (not cached, re-created on each run)
# This prevents caching None values
_speech_client = None
_tts_client = None
_clients_initialized = False


def get_speech_client():
    """
    Get Google Cloud Speech-to-Text client using service account credentials.
    สร้าง client สำหรับ Google Cloud Speech-to-Text จาก service account

    Note: Removed @st.cache_resource to avoid caching None values.
    Client is created once per module load.

    Returns:
        SpeechClient object or None if initialization fails
    """
    global _speech_client, _clients_initialized

    # Return cached client if available
    if _speech_client is not None:
        return _speech_client

    # If already tried and failed, don't retry
    if _clients_initialized and _speech_client is None:
        return None

    try:
        from google.cloud import speech

        # Load credentials using robust helper
        credentials_dict, error = load_gcp_credentials()
        if credentials_dict is None:
            print(f"[VOICE][ERROR] Cannot create Speech client: {error}")
            return None

        # Create credentials object
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        try:
            credentials = Credentials.from_service_account_info(
                credentials_dict,
                scopes=scopes
            )
        except Exception as e:
            print(f"[VOICE][ERROR] Failed to create Credentials: {type(e).__name__}: {str(e)[:100]}")
            return None

        # Create and store client
        try:
            _speech_client = speech.SpeechClient(credentials=credentials)
            print("[VOICE][INFO] Speech-to-Text client initialized successfully")
            return _speech_client
        except Exception as e:
            print(f"[VOICE][ERROR] Failed to init SpeechClient: {type(e).__name__}: {str(e)[:100]}")
            return None

    except ImportError:
        print("[VOICE][ERROR] google-cloud-speech not installed")
        return None
    except Exception as e:
        print(f"[VOICE][ERROR] Unexpected error in get_speech_client: {type(e).__name__}: {str(e)[:100]}")
        return None
    finally:
        _clients_initialized = True


def get_tts_client():
    """
    Get Google Cloud Text-to-Speech client using service account credentials.
    สร้าง client สำหรับ Google Cloud Text-to-Speech จาก service account

    Note: Removed @st.cache_resource to avoid caching None values.
    Client is created once per module load.

    Returns:
        TextToSpeechClient object or None if initialization fails
    """
    global _tts_client, _clients_initialized

    # Return cached client if available
    if _tts_client is not None:
        return _tts_client

    # If already tried and failed for speech, credentials are likely bad
    # But still try TTS as it might have different requirements

    try:
        from google.cloud import texttospeech

        # Load credentials using robust helper
        credentials_dict, error = load_gcp_credentials()
        if credentials_dict is None:
            print(f"[VOICE][ERROR] Cannot create TTS client: {error}")
            return None

        # Create credentials object
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        try:
            credentials = Credentials.from_service_account_info(
                credentials_dict,
                scopes=scopes
            )
        except Exception as e:
            print(f"[VOICE][ERROR] Failed to create Credentials for TTS: {type(e).__name__}: {str(e)[:100]}")
            return None

        # Create and store client
        try:
            _tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
            print("[VOICE][INFO] Text-to-Speech client initialized successfully")
            return _tts_client
        except Exception as e:
            print(f"[VOICE][ERROR] Failed to init TTSClient: {type(e).__name__}: {str(e)[:100]}")
            return None

    except ImportError:
        print("[VOICE][ERROR] google-cloud-texttospeech not installed")
        return None
    except Exception as e:
        print(f"[VOICE][ERROR] Unexpected error in get_tts_client: {type(e).__name__}: {str(e)[:100]}")
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

        # Build recognition config / สร้างการตั้งค่าการรู้จำ
        config_kwargs = {
            "encoding": speech.RecognitionConfig.AudioEncoding.LINEAR16,
            "sample_rate_hertz": sample_rate,
            "language_code": STT_LANGUAGE_CODE,
            "enable_automatic_punctuation": STT_ENABLE_AUTOMATIC_PUNCTUATION,
            "model": STT_MODEL,
            "audio_channel_count": channels,
        }

        # Add alternative language codes if configured
        # เพิ่มรหัสภาษาทางเลือกถ้ามีการตั้งค่า
        if STT_ALTERNATIVE_LANGUAGE_CODES:
            try:
                config_kwargs["alternative_language_codes"] = STT_ALTERNATIVE_LANGUAGE_CODES
            except Exception:
                # Field may not be supported in some API versions
                # field อาจไม่รองรับใน API บางเวอร์ชัน
                print("[WARNING] alternative_language_codes not supported, skipping")

        config = speech.RecognitionConfig(**config_kwargs)

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


def synthesize_speech(text: str) -> tuple:
    """
    Synthesize speech from text using Google Cloud Text-to-Speech.
    สร้างเสียงจากข้อความด้วย Google Cloud Text-to-Speech

    Args:
        text: Text to convert to speech / ข้อความที่จะแปลงเป็นเสียง

    Returns:
        Tuple of (audio_bytes: bytes, error_message: str or None)
        - On success: (mp3_bytes, None)
        - On failure: (None, error_message)
    """
    # Validate input / ตรวจสอบ input
    if not text or not text.strip():
        return None, "No text provided for TTS"

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

        # Set the text input / ตั้งค่า text input
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Build voice parameters / สร้าง parameters สำหรับเสียง
        voice_params = {
            "language_code": TTS_LANGUAGE_CODE,
        }

        # Add voice name if specified (with secrets override support)
        # เพิ่มชื่อเสียงถ้าระบุไว้ (รองรับ override จาก secrets)
        tts_voice = get_tts_voice_name()
        if tts_voice:
            voice_params["name"] = tts_voice

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

        print(f"[DEBUG] Synthesizing {len(text)} chars to speech")

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


def get_voice_service_status(include_debug: bool = False) -> dict:
    """
    Get detailed status of voice services.
    รับสถานะโดยละเอียดของบริการเสียง

    Args:
        include_debug: If True, include safe debug info about credentials

    Returns:
        Dictionary with service status information
    """
    stt_available, tts_available = is_voice_service_available()

    status = {
        "stt_available": stt_available,
        "tts_available": tts_available,
        "voice_enabled": stt_available,  # Voice mode requires at least STT
        "full_voice_enabled": stt_available and tts_available,  # Full voice requires both
    }

    if include_debug:
        status["debug"] = get_credential_debug_info()

    return status
