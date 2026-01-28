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
