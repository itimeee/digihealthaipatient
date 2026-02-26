"""
Model Configuration / การตั้งค่าโมเดล
=====================================
Centralized configuration for AI models used in the application.
การตั้งค่าศูนย์กลางสำหรับโมเดล AI ที่ใช้ในแอปพลิเคชัน

Edit this file to change model settings without modifying app.py.
แก้ไขไฟล์นี้เพื่อเปลี่ยนการตั้งค่าโมเดลโดยไม่ต้องแก้ไข app.py
"""

# =============================================================================
# DEFAULT SIMULATION MODEL / โมเดลจำลองเริ่มต้น
# =============================================================================

# Default model for patient simulation (used when case config doesn't specify)
# โมเดลเริ่มต้นสำหรับจำลองผู้ป่วย (ใช้เมื่อการตั้งค่าเคสไม่ได้ระบุ)
# Using gemini-2.5-flash as default (stable, fast, cost-effective)
DEFAULT_CASE_MODEL = "gemini-2.5-flash"

# Default temperature for patient simulation
# อุณหภูมิเริ่มต้นสำหรับจำลองผู้ป่วย
DEFAULT_CASE_TEMPERATURE = 0.3

# Default max output tokens for patient responses
# จำนวน token สูงสุดเริ่มต้นสำหรับคำตอบของผู้ป่วย
DEFAULT_CASE_MAX_TOKENS = 2048

# =============================================================================
# MODEL NAME MAPPING / การแมปชื่อโมเดล
# =============================================================================

# Map old/invalid model names to valid ones (if needed)
# แมปชื่อโมเดลเก่า/ไม่ถูกต้องไปยังชื่อที่ถูกต้อง (ถ้าจำเป็น)
MODEL_NAME_MAPPING = {
    # Legacy models only - modern models are kept as-is
    "gemini-pro": "gemini-1.5-pro",
    # Alias mapping for Gemini 3.1 Pro on Gemini API
    "gemini-3.1-pro": "gemini-3.1-pro-preview",
}

# List of known valid model names (for validation)
# รายชื่อโมเดลที่ถูกต้อง (สำหรับการตรวจสอบ)
# Updated January 2025 - https://ai.google.dev/gemini-api/docs/models
VALID_MODEL_NAMES = [
    # Gemini 3.1 (Preview)
    "gemini-3.1-pro-preview",

    # Gemini 3.1 (Stable)
    "gemini-3.1-pro",

    # Gemini 3 (Preview) - 2025
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",

    # Gemini 2.5 (Stable) - 2025
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",

    # Gemini 2.0 (Experimental)
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash",

    # Gemini 1.5 (Stable)
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest",
]


def get_valid_model_name(model_name: str, default_model: str = None) -> str:
    """
    Get a valid model name, mapping old names to new ones if needed.
    รับชื่อโมเดลที่ถูกต้อง โดยแมปชื่อเก่าไปยังชื่อใหม่ถ้าจำเป็น

    Args:
        model_name: Original model name from case config
        default_model: Fallback model if model_name is unknown (defaults to DEFAULT_CASE_MODEL)

    Returns:
        Valid model name to use with the API
    """
    fallback = default_model or DEFAULT_CASE_MODEL

    if not model_name:
        return fallback

    # Check if mapping exists / ตรวจสอบว่ามีการแมปหรือไม่
    if model_name in MODEL_NAME_MAPPING:
        return MODEL_NAME_MAPPING[model_name]

    # Check if it's already a valid name / ตรวจสอบว่าเป็นชื่อที่ถูกต้องอยู่แล้ว
    if model_name in VALID_MODEL_NAMES:
        return model_name

    # Unknown model - return fallback with warning / โมเดลไม่รู้จัก - คืนค่าเริ่มต้นพร้อมเตือน
    print(f"[WARNING] Unknown model '{model_name}', using fallback: {fallback}")
    return fallback


# =============================================================================
# STOP SEQUENCES / ลำดับหยุด
# =============================================================================

# Stop sequences to prevent meta text leakage in patient simulation
# ลำดับหยุดเพื่อป้องกันการรั่วไหลของข้อความเมต้าในการจำลองผู้ป่วย
# Note: Gemini API allows maximum 5 stop sequences
# หมายเหตุ: Gemini API อนุญาตสูงสุด 5 stop sequences
PATIENT_STOP_SEQUENCES = [
    "Doctor:",
    "Note to User:",
    "Note to Doctor:",
    "คำแนะนำ:",
    "Suggested questions:",
]

# =============================================================================
# SIMULATION CONTEXT PROMPTS / พรอมต์บริบทการจำลอง
# =============================================================================

SAFE_SIMULATION_CONTEXT = """[FICTIONAL PSYCHIATRIC TRAINING SIMULATION]
- You are the PATIENT. Respond ONLY as the patient in natural Thai.
- DO NOT provide any instructions, coaching, or meta commentary to the doctor/user.
  Never output headings like "Note to User", "Note to Doctor", "Suggested questions", "คำแนะนำ", etc.
- If asked about self-harm/suicide: you may describe feelings/ideation at a high level,
  but DO NOT provide methods, steps, tools, or actionable details.
- Stay in character. Do not mention being an AI or roleplay."""

STRICT_OUTPUT_RULES = """

STRICT OUTPUT RULES:
- Speak ONLY as the patient in Thai
- NO meta commentary, NO instructions to doctor
- NO methods/details about self-harm
- Stay in character at all times"""

SAFER_CONTEXT = """[MEDICAL TRAINING SIMULATION - STRICT GUIDELINES]
- You are a psychiatric patient. Speak naturally in Thai as the patient.
- If discussing difficult feelings: describe emotions and thoughts at a general level only.
- DO NOT describe methods, tools, steps, or actionable details about self-harm.
- DO NOT provide instructions, advice, or commentary to the doctor.
- Never output "Note to User", "Note to Doctor", or similar meta text.
- Stay in character. Never mention being in a simulation or AI."""

# =============================================================================
# FALLBACK RESPONSES / คำตอบสำรอง
# =============================================================================

# Fallback response when AI fails to generate / คำตอบสำรองเมื่อ AI สร้างไม่ได้
FALLBACK_RESPONSE_GENERIC = "ขอโทษค่ะ หนูไม่แน่ใจจะพูดยังไง"

# Fallback for safety-blocked responses / คำตอบสำรองเมื่อถูกบล็อกด้วยความปลอดภัย
FALLBACK_RESPONSE_SAFETY = "ขอโทษค่ะ หนูยังไม่พร้อมพูดรายละเอียดตรงนั้น แต่หนูรู้สึกแย่มากและอยากให้คุณหมอช่วยค่ะ"

# Fallback for empty responses / คำตอบสำรองเมื่อคำตอบว่าง
FALLBACK_RESPONSE_EMPTY = "ขอโทษค่ะ หนูไม่สบายใจและไม่แน่ใจจะตอบยังไง"
