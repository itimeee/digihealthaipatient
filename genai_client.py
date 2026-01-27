"""
GenAI Client Module / โมดูลไคลเอนต์ GenAI
==========================================
Centralized client for Google GenAI API (google-genai SDK).
โมดูลศูนย์กลางสำหรับเรียกใช้ Google GenAI API (google-genai SDK)

This module provides:
- Unified client initialization with proper error handling
- Both sync and async generation methods
- Helper functions for config and response extraction
"""

import os
import streamlit as st

# Import google-genai SDK with helpful error message
# นำเข้า google-genai SDK พร้อมข้อความ error ที่ช่วยแก้ปัญหา
try:
    from google import genai
    from google.genai import types
except ImportError as e:
    raise ImportError(
        f"Failed to import google-genai SDK: {e}\n\n"
        "Please install the correct package:\n"
        "  pip uninstall google-generativeai  # Remove old package if installed\n"
        "  pip install google-genai>=1.0.0    # Install new SDK\n\n"
        "Or reinstall all requirements:\n"
        "  pip install -r requirements.txt"
    ) from e


# =============================================================================
# API KEY MANAGEMENT / การจัดการ API Key
# =============================================================================

def get_api_key() -> str:
    """
    Get Gemini API key from Streamlit secrets or environment variable.
    ดึง API key จาก Streamlit secrets หรือ environment variable

    Returns:
        API key string

    Raises:
        ValueError: If API key is not found
    """
    api_key = None

    # Try Streamlit secrets first / ลอง Streamlit secrets ก่อน
    try:
        # Method 1: Direct access (preferred)
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            if api_key and str(api_key).strip():
                return str(api_key).strip()
    except Exception as e:
        print(f"[DEBUG] st.secrets direct access failed: {e}")

    try:
        # Method 2: Using .get()
        api_key = st.secrets.get("GEMINI_API_KEY")
        if api_key and str(api_key).strip():
            return str(api_key).strip()
    except Exception as e:
        print(f"[DEBUG] st.secrets.get() failed: {e}")

    # Fallback to environment variable / ใช้ environment variable แทน
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and str(api_key).strip():
        return str(api_key).strip()

    raise ValueError(
        "GEMINI_API_KEY not found. Please set it in:\n"
        "1. Streamlit secrets (.streamlit/secrets.toml): GEMINI_API_KEY = 'your-key'\n"
        "2. Or environment variable: export GEMINI_API_KEY='your-key'\n"
        "Get your API key at: https://aistudio.google.com/app/apikey"
    )


# =============================================================================
# CLIENT INITIALIZATION / การเริ่มต้นไคลเอนต์
# =============================================================================

_client_instance = None


def get_client() -> genai.Client:
    """
    Get or create GenAI client singleton.
    รับหรือสร้าง GenAI client แบบ singleton

    Note: Does NOT cache errors - will retry on each call if previous attempt failed.
    หมายเหตุ: ไม่เก็บ error ไว้ - จะลองใหม่ทุกครั้งถ้าครั้งก่อนล้มเหลว

    Returns:
        genai.Client instance

    Raises:
        ValueError: If client initialization fails
    """
    global _client_instance

    if _client_instance is not None:
        return _client_instance

    try:
        api_key = get_api_key()
        _client_instance = genai.Client(api_key=api_key)
        print(f"[DEBUG] GenAI client initialized successfully")
        return _client_instance
    except Exception as e:
        print(f"[ERROR] Failed to initialize GenAI client: {e}")
        raise ValueError(f"Failed to initialize GenAI client: {e}")


def reset_client():
    """
    Reset client singleton (useful for testing or re-initialization).
    รีเซ็ต client singleton (ใช้สำหรับทดสอบหรือเริ่มต้นใหม่)
    """
    global _client_instance
    _client_instance = None


# =============================================================================
# CONFIGURATION BUILDERS / ตัวสร้างการตั้งค่า
# =============================================================================

def build_safety_settings(block_none: bool = True) -> list:
    """
    Build safety settings for psychiatric training context.
    สร้างการตั้งค่าความปลอดภัยสำหรับบริบทการฝึกอบรมทางจิตเวช

    Args:
        block_none: If True, set all categories to BLOCK_NONE (for medical training)

    Returns:
        List of SafetySetting objects
    """
    threshold = "BLOCK_NONE" if block_none else "BLOCK_MEDIUM_AND_ABOVE"

    return [
        types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold=threshold
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_HATE_SPEECH",
            threshold=threshold
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
            threshold=threshold
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold=threshold
        ),
    ]


def build_generation_config(
    temperature: float = 0.3,
    max_output_tokens: int = 4096,
    top_p: float = None,
    top_k: int = None,
    stop_sequences: list = None,
    system_instruction: str = None,
) -> types.GenerateContentConfig:
    """
    Build generation configuration.
    สร้างการตั้งค่าการสร้างเนื้อหา

    Args:
        temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
        max_output_tokens: Maximum tokens in response
        top_p: Nucleus sampling parameter
        top_k: Top-k sampling parameter
        stop_sequences: List of stop sequences
        system_instruction: System instruction for the model

    Returns:
        GenerateContentConfig object
    """
    config_dict = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "safety_settings": build_safety_settings(block_none=True),
    }

    if top_p is not None:
        config_dict["top_p"] = top_p

    if top_k is not None:
        config_dict["top_k"] = top_k

    if stop_sequences:
        config_dict["stop_sequences"] = stop_sequences

    if system_instruction:
        config_dict["system_instruction"] = system_instruction

    return types.GenerateContentConfig(**config_dict)


# =============================================================================
# RESPONSE EXTRACTION / การดึงข้อมูลจาก Response
# =============================================================================

def extract_text(response) -> str:
    """
    Extract text from GenAI response robustly.
    ดึงข้อความจาก response อย่างรอบคอบ

    Args:
        response: GenerateContentResponse object

    Returns:
        Extracted text string or empty string if extraction fails
    """
    # Strategy 1: Try the .text property / ลองใช้ .text
    try:
        if hasattr(response, 'text') and response.text:
            return response.text.strip()
    except (ValueError, AttributeError):
        pass

    # Strategy 2: Extract from candidates/parts / ดึงจาก candidates/parts
    try:
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                parts = candidate.content.parts
                text_parts = []
                for part in parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                if text_parts:
                    return "".join(text_parts).strip()
    except (IndexError, AttributeError):
        pass

    return ""


def extract_finish_reason(response) -> str:
    """
    Extract finish reason from response.
    ดึง finish reason จาก response

    Args:
        response: GenerateContentResponse object

    Returns:
        Finish reason string or None
    """
    try:
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason'):
                return str(candidate.finish_reason)
    except (IndexError, AttributeError):
        pass
    return None


def is_response_blocked(response) -> bool:
    """
    Check if response was blocked by safety filters.
    ตรวจสอบว่า response ถูกบล็อกโดย safety filters หรือไม่

    Args:
        response: GenerateContentResponse object

    Returns:
        True if blocked, False otherwise
    """
    finish_reason = extract_finish_reason(response)
    if finish_reason:
        reason_upper = finish_reason.upper()
        if "SAFETY" in reason_upper or "BLOCKED" in reason_upper:
            return True

    # Check prompt feedback / ตรวจสอบ prompt feedback
    try:
        if hasattr(response, 'prompt_feedback'):
            pf = response.prompt_feedback
            if hasattr(pf, 'block_reason') and pf.block_reason:
                block_reason_str = str(pf.block_reason).upper()
                if block_reason_str and "UNSPECIFIED" not in block_reason_str:
                    return True
    except Exception:
        pass

    return False


# =============================================================================
# SYNC GENERATION / การสร้างแบบ Sync
# =============================================================================

def generate_content_sync(
    model: str,
    contents: str,
    temperature: float = 0.3,
    max_output_tokens: int = 4096,
    stop_sequences: list = None,
    system_instruction: str = None,
) -> str:
    """
    Generate content synchronously.
    สร้างเนื้อหาแบบ synchronous

    Args:
        model: Model name (e.g., "gemini-2.0-flash-exp")
        contents: Prompt/contents to send
        temperature: Sampling temperature
        max_output_tokens: Maximum tokens
        stop_sequences: Stop sequences list
        system_instruction: System instruction

    Returns:
        Generated text string

    Raises:
        ValueError: If generation fails
    """
    client = get_client()

    config = build_generation_config(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        stop_sequences=stop_sequences,
        system_instruction=system_instruction,
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        if is_response_blocked(response):
            raise ValueError("Response blocked by safety filters")

        text = extract_text(response)
        if not text:
            raise ValueError("Empty response from model")

        return text

    except Exception as e:
        raise ValueError(f"Generation failed: {e}")


# =============================================================================
# ASYNC GENERATION / การสร้างแบบ Async
# =============================================================================

async def generate_content_async(
    model: str,
    contents: str,
    temperature: float = 0.3,
    max_output_tokens: int = 4096,
    stop_sequences: list = None,
    system_instruction: str = None,
) -> str:
    """
    Generate content asynchronously.
    สร้างเนื้อหาแบบ asynchronous

    Args:
        model: Model name (e.g., "gemini-2.0-flash-exp")
        contents: Prompt/contents to send
        temperature: Sampling temperature
        max_output_tokens: Maximum tokens
        stop_sequences: Stop sequences list
        system_instruction: System instruction

    Returns:
        Generated text string

    Raises:
        ValueError: If generation fails
    """
    client = get_client()

    config = build_generation_config(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        stop_sequences=stop_sequences,
        system_instruction=system_instruction,
    )

    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        if is_response_blocked(response):
            raise ValueError("Response blocked by safety filters")

        text = extract_text(response)
        if not text:
            raise ValueError("Empty response from model")

        return text

    except Exception as e:
        raise ValueError(f"Generation failed: {e}")
