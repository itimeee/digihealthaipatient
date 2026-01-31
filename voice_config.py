"""
Voice Configuration / การตั้งค่าเสียง
======================================
Configuration settings for Google Cloud Speech-to-Text and Text-to-Speech.
การตั้งค่าสำหรับ Google Cloud Speech-to-Text และ Text-to-Speech

This module contains all voice-related settings used by voice_service.py
โมดูลนี้เก็บการตั้งค่าเสียงทั้งหมดที่ใช้โดย voice_service.py
"""

# ============================================================================
# SPEECH-TO-TEXT (STT) SETTINGS / การตั้งค่าการแปลงเสียงเป็นข้อความ
# ============================================================================

# Language code for speech recognition / รหัสภาษาสำหรับการรู้จำเสียง
# Thai language / ภาษาไทย
STT_LANGUAGE_CODE = "th-TH"

# Alternative language codes for multi-language support (optional)
# รหัสภาษาทางเลือกสำหรับรองรับหลายภาษา (ถ้าต้องการ)
STT_ALTERNATIVE_LANGUAGE_CODES = ["en-US"]

# Audio encoding expected from input / รูปแบบเสียงที่คาดหวังจาก input
# LINEAR16 is standard for WAV files from st.audio_input
STT_AUDIO_ENCODING = "LINEAR16"

# Enable automatic punctuation / เปิดใช้การเติมเครื่องหมายวรรคตอนอัตโนมัติ
STT_ENABLE_AUTOMATIC_PUNCTUATION = True

# Model selection for STT / เลือกโมเดลสำหรับ STT
# Options: "default", "latest_long", "latest_short", "command_and_search", "phone_call"
# For short recordings like in interview, "default" or "latest_short" works well
STT_MODEL = "default"


# ============================================================================
# TEXT-TO-SPEECH (TTS) SETTINGS / การตั้งค่าการแปลงข้อความเป็นเสียง
# ============================================================================

# Language code for speech synthesis / รหัสภาษาสำหรับการสังเคราะห์เสียง
TTS_LANGUAGE_CODE = "th-TH"

# Voice name for TTS (optional - if None, uses default for language)
# ชื่อเสียงสำหรับ TTS (ถ้าไม่กำหนด จะใช้ค่าเริ่มต้นของภาษา)
# Thai voices: "th-TH-Standard-A" (female), "th-TH-Wavenet-A" (female, higher quality)
# Set to None to use the default voice for the language
TTS_VOICE_NAME = "th-TH-Standard-A"

# Speaking rate (speed) - 0.25 to 4.0, where 1.0 is normal
# อัตราการพูด (ความเร็ว) - 0.25 ถึง 4.0, โดย 1.0 คือปกติ
TTS_SPEAKING_RATE = 1.0

# Pitch adjustment - -20.0 to 20.0 semitones
# การปรับระดับเสียง - -20.0 ถึง 20.0 semitones
TTS_PITCH = 0.0

# Audio encoding for TTS output / รูปแบบเสียงสำหรับ TTS output
# Options: "MP3", "LINEAR16", "OGG_OPUS"
TTS_AUDIO_ENCODING = "MP3"

# Volume gain in dB (-96.0 to 16.0)
# การเพิ่มเสียง (dB) (-96.0 ถึง 16.0)
TTS_VOLUME_GAIN_DB = 0.0

# TTS Text Normalization for Thai / การ normalize ข้อความภาษาไทยสำหรับ TTS
# Fixes pronunciation issues like "หมอ" being spelled out as "หอ-มอ-ออ"
# แก้ปัญหาการออกเสียงเช่น "หมอ" ถูกสะกดเป็น "หอ-มอ-ออ"
#
# Uses zero-width characters to change tokenization without changing visible text
# ใช้ zero-width character เพื่อเปลี่ยน tokenization โดยไม่เปลี่ยนข้อความที่เห็น
#
# Options / ตัวเลือก:
#   - None or "": Disabled, no normalization
#   - "zwnj": Replace "หมอ" -> "ห\u200Cมอ" (Zero-Width Non-Joiner) [default]
#   - "zwsp": Replace "หมอ" -> "ห\u200Bมอ" (Zero-Width Space)
#
# Only replaces standalone "หมอ", not compound words like "หมอฟัน", "หมอผี"
# แทนเฉพาะคำว่า "หมอ" เดี่ยวๆ ไม่แทนคำประสม เช่น "หมอฟัน", "หมอผี"
TTS_DOCTOR_FIX = "zwnj"


# ============================================================================
# GENERAL VOICE SETTINGS / การตั้งค่าเสียงทั่วไป
# ============================================================================

# Sample rate for microphone input (Hz) / อัตราสุ่มสำหรับไมโครโฟน (Hz)
# st.audio_input default is 16000 Hz
VOICE_SAMPLE_RATE = 16000

# Whether to auto-play TTS audio in chat / เล่น TTS อัตโนมัติในแชทหรือไม่
TTS_AUTO_PLAY = True

# Maximum audio recording duration in seconds (for chunking if needed)
# ความยาวสูงสุดของการบันทึกเสียง (วินาที)
MAX_RECORDING_DURATION_SECONDS = 60


# ============================================================================
# UI CONFIGURATION / การตั้งค่า UI
# ============================================================================

# Voice Mode minimal UI flag / ธง UI แบบน้อยสุดสำหรับ Voice Mode
# When True: Shows only mic button, no transcript displayed
# When False: Shows both transcript and mic input (current default)
# เมื่อ True: แสดงเฉพาะปุ่มไมค์ ไม่แสดง transcript
# เมื่อ False: แสดงทั้ง transcript และ mic input (ค่าเริ่มต้นปัจจุบัน)
VOICE_MINIMAL_UI = False

# Status messages in Thai / ข้อความสถานะภาษาไทย
STATUS_TRANSCRIBING = "กำลังถอดเสียง…"
STATUS_AI_RESPONDING = "กำลังรอคำตอบจาก AI…"
STATUS_GENERATING_TTS = "กำลังสร้างเสียงตอบกลับ…"
STATUS_RECORDING = "กำลังบันทึกเสียง…"
STATUS_READY = "พร้อมบันทึกเสียง"

# Error messages in Thai / ข้อความผิดพลาดภาษาไทย
ERROR_STT_FAILED = "ไม่สามารถถอดเสียงได้ กรุณาลองใหม่หรือพิมพ์ข้อความแทน"
ERROR_TTS_FAILED = "ไม่สามารถสร้างเสียงตอบกลับได้"
ERROR_NO_AUDIO = "ไม่พบข้อมูลเสียง กรุณาลองบันทึกใหม่"
ERROR_AUDIO_TOO_SHORT = "เสียงสั้นเกินไป กรุณาลองบันทึกใหม่"


# ============================================================================
# SECRETS OVERRIDE / การ override จาก secrets
# ============================================================================

def get_voice_config(key: str, default=None):
    """
    Get voice config value from secrets with fallback to module defaults.
    ดึงค่า config จาก secrets โดย fallback ไปค่าเริ่มต้นของโมดูล

    Usage:
        # In secrets.toml:
        # [voice]
        # tts_voice_name = "th-TH-Wavenet-A"
        # tts_auto_play = false
        # voice_minimal_ui = true

    Args:
        key: Config key name (e.g., "tts_voice_name", "tts_auto_play")
        default: Default value if not found anywhere

    Returns:
        Config value from secrets, or module default, or provided default
    """
    try:
        import streamlit as st
        voice_secrets = st.secrets.get("voice", {})
        if key in voice_secrets:
            return voice_secrets[key]
    except Exception:
        pass

    # Fall back to module-level default
    module_defaults = {
        "tts_voice_name": TTS_VOICE_NAME,
        "tts_auto_play": TTS_AUTO_PLAY,
        "voice_minimal_ui": VOICE_MINIMAL_UI,
        "tts_speaking_rate": TTS_SPEAKING_RATE,
        "tts_pitch": TTS_PITCH,
        "tts_volume_gain_db": TTS_VOLUME_GAIN_DB,
        "stt_language_code": STT_LANGUAGE_CODE,
        "stt_alternative_language_codes": STT_ALTERNATIVE_LANGUAGE_CODES,
    }

    return module_defaults.get(key, default)


def get_tts_voice_name() -> str:
    """Get TTS voice name from secrets or default."""
    return get_voice_config("tts_voice_name", TTS_VOICE_NAME)


def get_tts_auto_play() -> bool:
    """Get TTS auto-play setting from secrets or default."""
    return get_voice_config("tts_auto_play", TTS_AUTO_PLAY)


def get_voice_minimal_ui() -> bool:
    """Get voice minimal UI setting from secrets or default."""
    return get_voice_config("voice_minimal_ui", VOICE_MINIMAL_UI)
