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
import time
import streamlit as st
from google.oauth2.service_account import Credentials
from log_utils import log_event, classify_tts_error

from voice_config import (
    STT_LANGUAGE_CODE,
    STT_ENABLE_AUTOMATIC_PUNCTUATION,
    STT_MODEL,
    TTS_LANGUAGE_CODE,
    TTS_VOICE_NAME,
    TTS_SPEAKING_RATE,
    TTS_PITCH,
    TTS_AUDIO_ENCODING,
    TTS_REQUEST_TIMEOUT_SEC,
    TTS_VOLUME_GAIN_DB,
    TTS_MODEL_NAME,
    TTS_STYLE_PROMPT,
    TTS_ALLOWED_MODELS,
    TTS_CLOUD_DEFAULT_VOICE_BY_MODEL,
    TTS_GEMINI_VOICE_NAME,
    VOICE_SAMPLE_RATE,
    ERROR_STT_FAILED,
    ERROR_TTS_FAILED,
    ERROR_NO_AUDIO,
    ERROR_AUDIO_TOO_SHORT,
)

_GENAI_TTS_UNAVAILABLE_MODELS = set()
_GENAI_TTS_DIAGNOSTIC_DONE = False
_GENAI_TTS_AVAILABLE_MODELS = set()
USE_GENAI_TTS_SDK_PATH = False  # Force all Gemini TTS through Cloud Text-to-Speech API


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
        log_event("INFO", "voice_stt", "client_initialized")
        return client

    except ImportError:
        log_event("ERROR", "voice_stt", "client_init_failed", error="google-cloud-speech not installed")
        return None
    except KeyError:
        log_event("ERROR", "voice_stt", "client_init_failed", error="gcp_service_account not found in secrets")
        return None
    except Exception as e:
        log_event("ERROR", "voice_stt", "client_init_failed", error=str(e))
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
        log_event("INFO", "voice_tts", "client_initialized")
        return client

    except ImportError:
        log_event("ERROR", "voice_tts", "client_init_failed", error="google-cloud-texttospeech not installed")
        return None
    except KeyError:
        log_event("ERROR", "voice_tts", "client_init_failed", error="gcp_service_account not found in secrets")
        return None
    except Exception as e:
        log_event("ERROR", "voice_tts", "client_init_failed", error=str(e))
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

                log_event(
                    "DEBUG",
                    "voice_stt",
                    "wav_parsed",
                    sample_rate_hz=sample_rate,
                    channels=channels,
                    sample_width_bytes=sample_width,
                    frames=n_frames,
                )

                # Read all PCM frames / อ่าน PCM frames ทั้งหมด
                pcm_frames = wav_file.readframes(n_frames)

                return pcm_frames, sample_rate, channels

    except wave.Error as e:
        log_event("ERROR", "voice_stt", "wav_invalid", error=str(e))
        return None, None, None
    except Exception as e:
        log_event("ERROR", "voice_stt", "wav_parse_failed", error=str(e))
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

        log_event("DEBUG", "voice_stt", "recognize_request", duration_sec=duration_seconds)

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
                log_event(
                    "INFO",
                    "voice_stt",
                    "transcription_success",
                    transcript_preview=transcript[:50],
                    transcript_chars=len(transcript),
                )
                return transcript, None
            else:
                return None, "ไม่ได้ยินเสียงพูด กรุณาลองใหม่"
        else:
            return None, "ไม่ได้ยินเสียงพูด กรุณาลองใหม่"

    except Exception as e:
        error_msg = str(e)
        log_event("ERROR", "voice_stt", "transcription_failed", error=error_msg)

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


# ============================================================================
# GENAI SDK TTS / สังเคราะห์เสียงผ่าน GenAI SDK
# ============================================================================

def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000,
                channels: int = 1, sample_width: int = 2) -> bytes:
    """Convert raw PCM bytes to WAV format for browser playback.
    แปลง PCM bytes เป็น WAV สำหรับเล่นในเบราว์เซอร์"""
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buffer.getvalue()


def detect_audio_mime(audio_bytes: bytes) -> str:
    """Detect audio MIME type from file header bytes.
    ตรวจจับ MIME type ของเสียงจาก header bytes"""
    if not audio_bytes or len(audio_bytes) < 4:
        return "audio/mpeg"
    if audio_bytes[:4] == b'RIFF':
        return "audio/wav"
    if audio_bytes[:3] == b'ID3' or (audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0):
        return "audio/mpeg"
    if audio_bytes[:4] == b'OggS':
        return "audio/ogg"
    return "audio/mpeg"


def _normalize_tts_model_name(model_name: str) -> str:
    """
    Normalize TTS model aliases to canonical names.
    แปลงชื่อ alias ของโมเดล TTS เป็นชื่อมาตรฐาน
    """
    if not model_name:
        return model_name

    alias_map = {
        "gemini-2.5-flash-tts": "gemini-2.5-flash-preview-tts",
        "gemini-2.5-pro-tts": "gemini-2.5-pro-preview-tts",
    }
    return alias_map.get(model_name, model_name)


def _is_genai_tts_model(model_name: str) -> bool:
    """
    Return True if model is a Gemini TTS model identifier.
    คืนค่า True เมื่อเป็นชื่อโมเดล Gemini TTS
    """
    normalized = _normalize_tts_model_name(model_name)
    return bool(normalized) and normalized.startswith("gemini-") and normalized.endswith("-tts")


def _get_genai_tts_candidates(model_name: str) -> list:
    """
    Build ordered candidate list for GenAI TTS retries.
    สร้างรายการโมเดลสำหรับลองซ้ำเมื่อ GenAI TTS ล้มเหลว
    """
    requested = _normalize_tts_model_name(model_name)
    normalized_allowed = [
        _normalize_tts_model_name(m)
        for m in TTS_ALLOWED_MODELS
        if _is_genai_tts_model(m)
    ]

    candidates = []
    if requested:
        candidates.append(requested)
    for allowed in normalized_allowed:
        if allowed not in candidates:
            candidates.append(allowed)
    return candidates


def _log_genai_tts_models_once():
    """
    Log available GenAI TTS models from ListModels once per process.
    ล็อกโมเดล GenAI TTS ที่ใช้งานได้จาก ListModels ครั้งเดียวต่อโปรเซส
    """
    global _GENAI_TTS_DIAGNOSTIC_DONE
    global _GENAI_TTS_AVAILABLE_MODELS

    if _GENAI_TTS_DIAGNOSTIC_DONE:
        return
    _GENAI_TTS_DIAGNOSTIC_DONE = True

    try:
        from genai_client import get_client

        client = get_client()
        discovered_tts_models = set()

        for model in client.models.list():
            raw_name = getattr(model, "name", "") or ""
            model_name = raw_name.split("/", 1)[1] if raw_name.startswith("models/") else raw_name
            if model_name and model_name.endswith("-tts"):
                discovered_tts_models.add(model_name)

        _GENAI_TTS_AVAILABLE_MODELS = discovered_tts_models

        if discovered_tts_models:
            log_event(
                "INFO",
                "voice_tts",
                "genai_models_discovered",
                models=",".join(sorted(discovered_tts_models)),
            )
        else:
            log_event("WARNING", "voice_tts", "genai_models_not_found")

    except Exception as e:
        log_event("WARNING", "voice_tts", "genai_models_query_failed", error=str(e))


def _synthesize_speech_genai(text: str, model_name: str,
                             style_prompt: str = None) -> tuple:
    """
    Synthesize speech using GenAI SDK (Gemini API) for Gemini TTS models.
    สังเคราะห์เสียงผ่าน GenAI SDK สำหรับโมเดล Gemini TTS

    Args:
        text: Text to synthesize / ข้อความที่จะสังเคราะห์
        model_name: Gemini TTS model name / ชื่อโมเดล Gemini TTS
        style_prompt: Optional style prompt / คำสั่งสไตล์ (ถ้ามี)

    Returns:
        Tuple of (audio_bytes, error_message)
    """
    try:
        from genai_client import get_client
        from google.genai import types
    except ImportError:
        return None, "GenAI SDK not available for TTS"

    try:
        client = get_client()

        # Build strict transcript-only instruction for TTS models.
        # สร้างคำสั่งแบบเคร่งครัดให้โมเดลอ่าน transcript เป็นเสียงเท่านั้น
        if style_prompt:
            contents = (
                "Generate audio only. Do not generate any text response.\n"
                "Read the exact transcript below as-is without adding or changing words.\n"
                f"Speaking style: {style_prompt}\n"
                f"Transcript: {text}"
            )
        else:
            contents = (
                "Generate audio only. Do not generate any text response.\n"
                "Read the exact transcript below as-is without adding or changing words.\n"
                f"Transcript: {text}"
            )

        gemini_voice = TTS_GEMINI_VOICE_NAME

        # Build config for audio generation
        # สร้าง config สำหรับการสร้างเสียง
        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=gemini_voice
                    )
                )
            )
        )

        log_event(
            "DEBUG",
            "voice_tts",
            "genai_synthesize_request",
            model=model_name,
            voice=gemini_voice,
            chars=len(text),
            prompt_used=bool(style_prompt),
        )

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )

        # Extract audio from response / ดึงเสียงจาก response
        if (response.candidates and
                response.candidates[0].content and
                response.candidates[0].content.parts):
            part = response.candidates[0].content.parts[0]
            if hasattr(part, 'inline_data') and part.inline_data:
                audio_data = part.inline_data.data
                mime_type = getattr(part.inline_data, 'mime_type', None) or "audio/wav"

                if not audio_data:
                    return None, "GenAI TTS returned empty audio"

                # Convert raw PCM to WAV if needed
                # แปลง PCM เป็น WAV ถ้าจำเป็น
                if 'pcm' in mime_type.lower() or 'l16' in mime_type.lower():
                    sample_rate = 24000
                    if 'rate=' in mime_type:
                        try:
                            rate_str = mime_type.split('rate=')[1].split(';')[0].split(',')[0]
                            sample_rate = int(rate_str)
                        except (ValueError, IndexError):
                            pass
                    audio_data = _pcm_to_wav(audio_data, sample_rate=sample_rate)

                log_event(
                    "DEBUG",
                    "voice_tts",
                    "genai_synthesize_success",
                    bytes=len(audio_data),
                    mime=mime_type,
                )
                return audio_data, None

        return None, "GenAI TTS returned no audio content"

    except Exception as e:
        error_msg = str(e)
        error_lower = error_msg.lower()
        if "404" in error_lower or "not_found" in error_lower or "not found" in error_lower:
            log_event("WARNING", "voice_tts", "genai_model_unavailable", model=model_name, error=error_msg)
        else:
            cause_code, cause_detail = classify_tts_error(error_msg)
            log_event(
                "ERROR",
                "voice_tts",
                "genai_synthesize_failed",
                cause_code=cause_code,
                cause_detail=cause_detail,
                error=error_msg,
            )
        return None, f"GenAI TTS failed: {error_msg[:100]}"


def synthesize_speech(text: str, model_name: str = None,
                      voice_name: str = None, style_prompt: str = None) -> tuple:
    """
    Synthesize speech from text using Google Cloud Text-to-Speech.
    สร้างเสียงจากข้อความด้วย Google Cloud Text-to-Speech

    Args:
        text: Text to convert to speech / ข้อความที่จะแปลงเป็นเสียง
        model_name: TTS model to use (optional, defaults to TTS_MODEL_NAME from config)
                    โมเดล TTS ที่ใช้ (ถ้าไม่ระบุ จะใช้ค่าจาก config)
        voice_name: Cloud voice name override (optional, defaults by model/config)
                    ชื่อเสียง Cloud ที่ต้องการใช้ (ถ้าไม่ระบุ จะใช้ค่าเริ่มต้นตามโมเดล/คอนฟิก)
        style_prompt: Style prompt for Gemini TTS models (optional, defaults to TTS_STYLE_PROMPT)
                      คำสั่งสไตล์สำหรับโมเดล Gemini TTS (ถ้าไม่ระบุ จะใช้ค่าจาก config)

    Returns:
        Tuple of (audio_bytes: bytes, error_message: str or None)
        - On success: (mp3_bytes, None)
        - On failure: (None, error_message)
    """
    tts_started_at = time.perf_counter()

    # Use config defaults if not provided / ใช้ค่า default จาก config ถ้าไม่ระบุ
    if model_name is None:
        model_name = TTS_MODEL_NAME
    model_name = _normalize_tts_model_name(model_name)
    requested_model_name = model_name or "classic"
    is_genai_requested = _is_genai_tts_model(model_name)
    is_cloud_requested = bool(model_name) and model_name.startswith("google-cloud-")
    if voice_name is None:
        if is_cloud_requested:
            voice_name = TTS_CLOUD_DEFAULT_VOICE_BY_MODEL.get(model_name, TTS_VOICE_NAME)
        elif is_genai_requested:
            voice_name = TTS_GEMINI_VOICE_NAME
        else:
            voice_name = TTS_VOICE_NAME

    # Gemini TTS path uses Gemini voice names (e.g. "Kore"), not Cloud voice IDs.
    # Force an explicit and consistent voice to avoid config mismatch.
    if is_genai_requested and voice_name != TTS_GEMINI_VOICE_NAME:
        log_event(
            "WARNING",
            "voice_tts",
            "voice_overridden_for_gemini_model",
            requested_voice=voice_name,
            enforced_voice=TTS_GEMINI_VOICE_NAME,
            model=model_name,
        )
        voice_name = TTS_GEMINI_VOICE_NAME

    requested_voice_name = voice_name or "default"
    if style_prompt is None:
        style_prompt = TTS_STYLE_PROMPT

    def _log_tts_perf(status: str, provider: str, active_model: str, active_voice: str = None):
        elapsed_sec = time.perf_counter() - tts_started_at
        log_event(
            "PERF",
            "voice_tts",
            "synthesis",
            elapsed_sec=elapsed_sec,
            provider=provider,
            requested_model=requested_model_name,
            requested_voice=requested_voice_name,
            active_model=active_model,
            active_voice=active_voice or "default",
            status=status,
            chars=len(text),
        )

    # Validate input / ตรวจสอบ input
    if not text or not text.strip():
        _log_tts_perf("invalid_input", "none", requested_model_name, requested_voice_name)
        return None, "No text provided for TTS"

    # Validate model name if provided / ตรวจสอบชื่อโมเดลถ้าระบุ
    normalized_allowed_models = [_normalize_tts_model_name(m) for m in TTS_ALLOWED_MODELS]
    if model_name and model_name not in normalized_allowed_models:
        allowed = ", ".join(TTS_ALLOWED_MODELS)
        _log_tts_perf("invalid_model", "none", model_name, requested_voice_name)
        return None, f"Unknown TTS model '{model_name}'. Allowed models: {allowed}"

    # Truncate text if too long (TTS has limits)
    # ตัดข้อความถ้ายาวเกินไป (TTS มี limit)
    max_chars = 5000
    if len(text) > max_chars:
        text = text[:max_chars]
        log_event("WARNING", "voice_tts", "text_truncated", max_chars=max_chars)

    # For Gemini TTS model requests, use GenAI path only when explicitly enabled.
    # สำหรับโมเดล Gemini TTS จะใช้ Cloud API เป็นหลัก (จะใช้ GenAI path ต่อเมื่อเปิดใช้งาน)
    if model_name and is_genai_requested and USE_GENAI_TTS_SDK_PATH:
        _log_genai_tts_models_once()
        if _GENAI_TTS_AVAILABLE_MODELS and model_name not in _GENAI_TTS_AVAILABLE_MODELS:
            log_event(
                "WARNING",
                "voice_tts",
                "genai_model_not_listed",
                model=model_name,
                action="try_fallback_candidates",
            )
        genai_error = None
        for candidate_model in _get_genai_tts_candidates(model_name):
            if candidate_model in _GENAI_TTS_UNAVAILABLE_MODELS:
                log_event("WARNING", "voice_tts", "genai_candidate_skipped_unavailable", model=candidate_model)
                continue

            audio_bytes, genai_error = _synthesize_speech_genai(text, candidate_model, style_prompt)
            if audio_bytes:
                _log_tts_perf("success", "genai", candidate_model, TTS_GEMINI_VOICE_NAME)
                return audio_bytes, None

            # Retry with next candidate only for model availability errors
            # ลองโมเดลถัดไปเฉพาะกรณีโมเดลไม่พร้อมใช้งาน
            error_lower = (genai_error or "").lower()
            if "404" in error_lower or "not_found" in error_lower or "not found" in error_lower:
                _GENAI_TTS_UNAVAILABLE_MODELS.add(candidate_model)
                log_event(
                    "WARNING",
                    "voice_tts",
                    "genai_candidate_unavailable",
                    model=candidate_model,
                    action="try_next_candidate",
                )
                continue
            break

        log_event("WARNING", "voice_tts", "genai_path_failed_fallback_cloud", error=genai_error)

    # Get TTS client / รับ TTS client
    client = get_tts_client()
    if client is None:
        _log_tts_perf("client_unavailable", "cloud_tts", requested_model_name, requested_voice_name)
        return None, "Text-to-Speech service unavailable"

    try:
        from google.cloud import texttospeech

        # Set the text input with optional style prompt / ตั้งค่า text input พร้อม style prompt
        input_params = {"text": text}
        if is_genai_requested and style_prompt:
            # Only include prompt when using a Gemini TTS model and prompt is non-empty
            # ใส่ prompt เฉพาะเมื่อใช้โมเดล Gemini TTS และ prompt ไม่ว่าง
            try:
                input_params["prompt"] = style_prompt
            except TypeError:
                # SynthesisInput may not support 'prompt' in older library versions
                log_event(
                    "WARNING",
                    "voice_tts",
                    "synthesis_input_prompt_unsupported",
                    action="upgrade_google_cloud_texttospeech>=2.29.0",
                )

        try:
            synthesis_input = texttospeech.SynthesisInput(**input_params)
        except (TypeError, ValueError) as te:
            # Graceful fallback if 'prompt' is not supported by installed library version
            # proto-plus raises ValueError for unknown fields, TypeError for wrong types
            if "prompt" in str(te):
                log_event(
                    "WARNING",
                    "voice_tts",
                    "synthesis_input_prompt_unsupported",
                    action="upgrade_google_cloud_texttospeech>=2.29.0",
                )
                synthesis_input = texttospeech.SynthesisInput(text=text)
            else:
                raise

        selected_cloud_voice = voice_name
        if not is_genai_requested:
            default_voice_by_model = TTS_CLOUD_DEFAULT_VOICE_BY_MODEL.get(model_name)
            if not selected_cloud_voice:
                selected_cloud_voice = default_voice_by_model or TTS_VOICE_NAME

            # Keep selected voice family aligned with requested Cloud model
            # ให้ family ของเสียงตรงกับ Cloud model ที่เลือก
            if model_name == "google-cloud-neural2" and "-Neural2-" not in selected_cloud_voice:
                selected_cloud_voice = default_voice_by_model or "th-TH-Neural2-C"
            elif model_name == "google-cloud-standard" and "-Standard-" not in selected_cloud_voice:
                selected_cloud_voice = default_voice_by_model or "th-TH-Standard-A"
            elif model_name == "google-cloud-chirp3-hd" and "-Chirp3-HD-" not in selected_cloud_voice:
                selected_cloud_voice = default_voice_by_model or "th-TH-Chirp3-HD-Kore"

        # Build voice parameters / สร้าง parameters สำหรับเสียง
        voice_params = {
            "language_code": TTS_LANGUAGE_CODE,
        }

        # Add model_name for Gemini TTS models / เพิ่ม model_name สำหรับโมเดล Gemini TTS
        if model_name and is_genai_requested:
            # Gemini TTS uses Gemini voice names (e.g. "Kore"), not classic names
            # Gemini TTS ใช้ชื่อเสียง Gemini (เช่น "Kore") ไม่ใช่ชื่อ classic
            voice_params["name"] = voice_name or TTS_GEMINI_VOICE_NAME
            try:
                voice_params["model_name"] = model_name
                voice = texttospeech.VoiceSelectionParams(**voice_params)
            except (TypeError, ValueError) as te:
                if "model_name" in str(te):
                    log_event(
                        "WARNING",
                        "voice_tts",
                        "voice_selection_model_name_unsupported",
                        action="upgrade_google_cloud_texttospeech>=2.29.0",
                    )
                    del voice_params["model_name"]
                    # Revert to classic voice name for fallback
                    if TTS_VOICE_NAME:
                        voice_params["name"] = TTS_VOICE_NAME
                    else:
                        del voice_params["name"]
                    voice = texttospeech.VoiceSelectionParams(**voice_params)
                else:
                    raise
        else:
            # Classic TTS: use configured voice name
            if selected_cloud_voice:
                voice_params["name"] = selected_cloud_voice
            voice = texttospeech.VoiceSelectionParams(**voice_params)

        # Force MP3 encoding for browser compatibility
        # บังคับใช้ MP3 encoding เพื่อความเข้ากันได้กับ browser
        audio_encoding = texttospeech.AudioEncoding.MP3

        # Set audio config / ตั้งค่า audio config
        if model_name == "google-cloud-chirp3-hd":
            # Chirp3-HD has limited support for speaking-rate/pitch controls.
            # Chirp3-HD รองรับพารามิเตอร์ speaking-rate/pitch จำกัด
            audio_config = texttospeech.AudioConfig(audio_encoding=audio_encoding)
        else:
            audio_config = texttospeech.AudioConfig(
                audio_encoding=audio_encoding,
                speaking_rate=TTS_SPEAKING_RATE,
                pitch=TTS_PITCH,
                volume_gain_db=TTS_VOLUME_GAIN_DB,
            )

        prompt_used = bool(is_genai_requested and style_prompt)
        log_event(
            "DEBUG",
            "voice_tts",
            "cloud_synthesize_request",
            chars=len(text),
            model=model_name or "classic",
            voice=voice_params.get("name", "default"),
            prompt_used=prompt_used,
        )

        # Perform synthesis / ดำเนินการสังเคราะห์เสียง
        try:
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
                timeout=TTS_REQUEST_TIMEOUT_SEC,
            )
        except Exception as synth_error:
            synth_error_msg = str(synth_error)
            synth_error_lower = synth_error_msg.lower()

            # Fallback for unavailable voice name (e.g. outdated config)
            # fallback เมื่อชื่อเสียงที่ตั้งไว้ไม่มีจริง (เช่น config เก่า)
            if "voice" in synth_error_lower and "does not exist" in synth_error_lower and voice_params.get("name"):
                invalid_voice = voice_params["name"]
                log_event(
                    "WARNING",
                    "voice_tts",
                    "cloud_voice_unavailable_retry_fallback_voice",
                    invalid_voice=invalid_voice,
                )

                fallback_voice_params = {"language_code": TTS_LANGUAGE_CODE}
                preferred_fallback_voice = TTS_CLOUD_DEFAULT_VOICE_BY_MODEL.get(model_name)
                if preferred_fallback_voice:
                    fallback_voice_params["name"] = preferred_fallback_voice
                elif TTS_LANGUAGE_CODE == "th-TH":
                    # Last-resort Thai fallback
                    fallback_voice_params["name"] = "th-TH-Neural2-C"

                try:
                    fallback_voice = texttospeech.VoiceSelectionParams(**fallback_voice_params)
                    response = client.synthesize_speech(
                        input=synthesis_input,
                        voice=fallback_voice,
                        audio_config=audio_config,
                        timeout=TTS_REQUEST_TIMEOUT_SEC,
                    )
                    voice_params = fallback_voice_params
                    selected_cloud_voice = fallback_voice_params.get("name", selected_cloud_voice)
                except Exception:
                    # Last fallback: let API choose default voice by language
                    fallback_voice_params = {"language_code": TTS_LANGUAGE_CODE}
                    fallback_voice = texttospeech.VoiceSelectionParams(**fallback_voice_params)
                    response = client.synthesize_speech(
                        input=synthesis_input,
                        voice=fallback_voice,
                        audio_config=audio_config,
                        timeout=TTS_REQUEST_TIMEOUT_SEC,
                    )
                    voice_params = fallback_voice_params
                    selected_cloud_voice = fallback_voice_params.get("name", "default")
            else:
                raise

        # Return audio content / คืนค่าเนื้อหา audio
        if response.audio_content:
            log_event("DEBUG", "voice_tts", "cloud_synthesize_success", bytes=len(response.audio_content))
            _log_tts_perf(
                "success",
                "cloud_tts",
                model_name or "classic",
                voice_params.get("name", selected_cloud_voice or "default")
            )
            return response.audio_content, None
        else:
            log_event("WARNING", "voice_tts", "cloud_empty_audio")
            _log_tts_perf(
                "empty_audio",
                "cloud_tts",
                model_name or "classic",
                voice_params.get("name", selected_cloud_voice or "default")
            )
            return None, ERROR_TTS_FAILED

    except Exception as e:
        error_msg = str(e)
        cause_code, cause_detail = classify_tts_error(error_msg)
        log_event(
            "ERROR",
            "voice_tts",
            "synthesize_failed",
            cause_code=cause_code,
            cause_detail=cause_detail,
            error=error_msg,
            requested_model=requested_model_name,
            requested_voice=requested_voice_name,
        )

        # Provide user-friendly error messages
        if "quota" in error_msg.lower():
            _log_tts_perf("quota_exceeded", "cloud_tts", model_name or "classic", requested_voice_name)
            return None, "TTS API quota exceeded"
        elif "permission" in error_msg.lower() or "403" in error_msg:
            _log_tts_perf("permission_denied", "cloud_tts", model_name or "classic", requested_voice_name)
            return None, "Text-to-Speech API not enabled. กรุณาเปิดใช้งาน API ใน Google Cloud Console"
        elif "model" in error_msg.lower() and "not found" in error_msg.lower():
            _log_tts_perf("model_not_found", "cloud_tts", model_name or "classic", requested_voice_name)
            return None, (f"TTS model '{model_name}' not available. "
                          "Ensure your project has the Text-to-Speech API enabled and "
                          "google-cloud-texttospeech>=2.29.0 is installed.")
        else:
            _log_tts_perf("error", "cloud_tts", model_name or "classic", requested_voice_name)
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
