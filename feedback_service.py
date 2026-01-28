"""
Feedback Service / บริการสร้าง Feedback
========================================
This module handles the generation of feedback using the configured model.
Supports multiple providers: Gemini, MedGemma (via Hugging Face), and generic Hugging Face models.

โมดูลนี้จัดการการสร้าง feedback โดยใช้โมเดลที่กำหนดไว้
รองรับหลาย providers: Gemini, MedGemma (ผ่าน Hugging Face), และโมเดล Hugging Face ทั่วไป
"""

import json
import re
import time
import requests
import streamlit as st

# Import GenAI client for Gemini / นำเข้า GenAI client สำหรับ Gemini
from genai_client import (
    get_client,
    generate_content_sync,
    extract_text,
)
from model_config import get_valid_model_name

from feedback_config import (
    FEEDBACK_PROVIDER,
    FEEDBACK_MODEL_NAME,
    FEEDBACK_TEMPERATURE,
    FEEDBACK_OUTPUT_FORMAT,
    FEEDBACK_SYSTEM_PROMPT,
    FEEDBACK_USER_PROMPT_TEMPLATE,
    FEEDBACK_FALLBACK_PROVIDER,
    FEEDBACK_FALLBACK_MODEL,
    FEEDBACK_MAX_TOKENS,
    HF_ENDPOINT_TYPE,
    HF_ROUTER_BASE_URL,
    HF_DEDICATED_ENDPOINT_URL,
    HF_API_TIMEOUT,
    HF_MAX_RETRIES,
    HF_RETRY_DELAY,
)


def build_feedback_prompt(payload: dict) -> str:
    """
    Build the user prompt for feedback generation from payload data.
    สร้าง user prompt สำหรับการสร้าง feedback จากข้อมูล payload

    Args:
        payload: Dictionary containing session data:
            - user: {name, email}
            - case: case name
            - mode: selected mode
            - stats: {duration_seconds, total_messages, doctor_turns, patient_turns}
            - transcript_text: formatted transcript string
            - answers: {provisional_dx, ddx1, ddx2, ddx3, formulation_framework, formulation_text}

    Returns:
        Formatted prompt string
    """
    # Extract data from payload / ดึงข้อมูลจาก payload
    user = payload.get("user", {})
    stats = payload.get("stats", {})
    answers = payload.get("answers", {})

    duration_seconds = stats.get("duration_seconds", 0)
    duration_minutes = duration_seconds // 60

    # Format the prompt using template / จัดรูปแบบ prompt โดยใช้ template
    prompt = FEEDBACK_USER_PROMPT_TEMPLATE.format(
        user_name=user.get("name", "Unknown"),
        user_email=user.get("email", "Unknown"),
        case_name=payload.get("case", "Unknown"),
        selected_mode=payload.get("mode", "Unknown"),
        duration_seconds=duration_seconds,
        duration_minutes=duration_minutes,
        total_messages=stats.get("total_messages", 0),
        doctor_turns=stats.get("doctor_turns", 0),
        patient_turns=stats.get("patient_turns", 0),
        transcript_text=payload.get("transcript_text", "No transcript available"),
        provisional_dx=answers.get("provisional_dx", "Not provided"),
        ddx1=answers.get("ddx1", "Not provided"),
        ddx2=answers.get("ddx2", "Not provided"),
        ddx3=answers.get("ddx3", "Not provided"),
        formulation_framework=answers.get("formulation_framework", "Not selected"),
        formulation_text=answers.get("formulation_text", "Not provided"),
    )

    return prompt


def parse_json_response(text: str) -> dict:
    """
    Attempt to parse JSON from model response.
    พยายาม parse JSON จากคำตอบของโมเดล

    Args:
        text: Raw text response from model

    Returns:
        Parsed dictionary or fallback structure with raw text
    """
    # Try direct JSON parse first / ลองแปลง JSON โดยตรงก่อน
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block / ลองดึง JSON จาก code block
    json_pattern = r'```(?:json)?\s*\n?([\s\S]*?)\n?```'
    matches = re.findall(json_pattern, text, re.IGNORECASE)

    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try to find JSON object pattern in text / ลองหา pattern ของ JSON object ในข้อความ
    brace_pattern = r'\{[\s\S]*\}'
    brace_matches = re.findall(brace_pattern, text)

    for match in brace_matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    # Return fallback with raw text / คืนค่า fallback พร้อม raw text
    return {
        "parse_failed": True,
        "raw_text": text,
        "interview_feedback": {
            "strengths": [],
            "missed_opportunities": [],
            "suggested_questions": [],
            "risk_assessment_notes": "Unable to parse structured feedback",
            "overall_comment": text[:500] if text else "No feedback available"
        },
        "clinical_feedback": {
            "provisional_dx_comment": "Unable to parse structured feedback",
            "ddx_comment": {
                "ddx1": "",
                "ddx2": "",
                "ddx3": ""
            },
            "psychodynamic_formulation_comment": "",
            "overall_comment": ""
        }
    }


def get_fallback_feedback(error_message: str = None) -> dict:
    """
    Return fallback feedback when API call fails.
    คืนค่า fallback feedback เมื่อเรียก API ไม่สำเร็จ

    Args:
        error_message: Optional error message to include

    Returns:
        Dictionary with is_fallback=True flag
    """
    result = {
        "is_fallback": True,
        "interview_feedback": {
            "strengths": ["ไม่สามารถประเมินได้ในขณะนี้"],
            "missed_opportunities": ["กรุณาลองใหม่อีกครั้ง"],
            "suggested_questions": [],
            "risk_assessment_notes": "ไม่สามารถประเมินได้",
            "overall_comment": "ระบบไม่สามารถสร้าง feedback ได้ในขณะนี้ กรุณาลองใหม่อีกครั้งหรือติดต่อผู้ดูแลระบบ"
        },
        "clinical_feedback": {
            "provisional_dx_comment": "ไม่สามารถประเมินได้ในขณะนี้",
            "ddx_comment": {
                "ddx1": "",
                "ddx2": "",
                "ddx3": ""
            },
            "psychodynamic_formulation_comment": "ไม่สามารถประเมินได้ในขณะนี้",
            "overall_comment": "กรุณาลองใหม่อีกครั้ง"
        }
    }
    if error_message:
        result["error_message"] = error_message
    return result


def generate_feedback_gemini(payload: dict, model_name: str = None) -> dict:
    """
    Generate feedback using Google Gemini API (new google-genai SDK).
    สร้าง feedback โดยใช้ Google Gemini API (google-genai SDK ใหม่)

    Args:
        payload: Session data dictionary
        model_name: Override model name (for fallback scenarios)

    Returns:
        Feedback dictionary with interview_feedback and clinical_feedback
    """
    try:
        # Validate client / ตรวจสอบ client
        try:
            get_client()
        except ValueError as e:
            print(f"[ERROR] GenAI client error: {e}")
            return get_fallback_feedback(str(e))

        # Use provided model name or default, with validation
        # ใช้ชื่อโมเดลที่ให้มาหรือค่าเริ่มต้น พร้อมการตรวจสอบ
        raw_model = model_name or FEEDBACK_MODEL_NAME
        use_model = get_valid_model_name(raw_model)

        print(f"[INFO] Generating feedback with model: {use_model}")

        # Build prompt / สร้าง prompt
        user_prompt = build_feedback_prompt(payload)

        # Combine system and user prompts / รวม system และ user prompts
        full_prompt = f"{FEEDBACK_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"

        # Generate response using new SDK / สร้างคำตอบโดยใช้ SDK ใหม่
        try:
            response_text = generate_content_sync(
                model=use_model,
                contents=full_prompt,
                temperature=FEEDBACK_TEMPERATURE,
                max_output_tokens=FEEDBACK_MAX_TOKENS,
            )
        except ValueError as e:
            print(f"[ERROR] Generation failed: {e}")
            return get_fallback_feedback(str(e))

        if not response_text or not response_text.strip():
            print("[ERROR] Empty response from Gemini")
            return get_fallback_feedback("Empty response from Gemini")

        # Parse JSON response / แปลง JSON จากคำตอบ
        if FEEDBACK_OUTPUT_FORMAT == "json":
            result = parse_json_response(response_text)
        else:
            # For markdown format, wrap in a structure / สำหรับ markdown format ห่อในโครงสร้าง
            result = {
                "raw_text": response_text,
                "format": "markdown"
            }

        # Add metadata / เพิ่ม metadata
        result["is_fallback"] = False
        result["model_used"] = use_model
        result["provider"] = "gemini"

        return result

    except Exception as e:
        print(f"[ERROR] Gemini API error: {e}")
        return get_fallback_feedback(str(e))


def generate_feedback_huggingface(payload: dict, model_id: str = None) -> dict:
    """
    Generate feedback using Hugging Face Inference API.
    สร้าง feedback โดยใช้ Hugging Face Inference API

    Supports both Serverless Inference API (via HF Router) and Dedicated Inference Endpoints.
    รองรับทั้ง Serverless Inference API (ผ่าน HF Router) และ Dedicated Inference Endpoints

    Args:
        payload: Session data dictionary
        model_id: Override model ID (default uses FEEDBACK_MODEL_NAME)

    Returns:
        Feedback dictionary with interview_feedback and clinical_feedback
    """
    try:
        # Get API token from secrets / ดึง API token จาก secrets
        api_token = st.secrets.get("HF_API_TOKEN")
        if not api_token:
            print("[ERROR] HF_API_TOKEN not found in secrets")
            return None  # Return None to trigger fallback

        # Use provided model ID or default / ใช้ model ID ที่ให้มาหรือค่าเริ่มต้น
        use_model = model_id or FEEDBACK_MODEL_NAME

        # Determine API URL / กำหนด API URL
        if HF_ENDPOINT_TYPE == "dedicated" and HF_DEDICATED_ENDPOINT_URL:
            api_url = HF_DEDICATED_ENDPOINT_URL
            print(f"[INFO] Using dedicated endpoint: {api_url}")
        else:
            # Serverless Inference API via HF Router (new recommended endpoint)
            # ใช้ HF Router แทน api-inference.huggingface.co ที่เลิกใช้แล้ว
            api_url = f"{HF_ROUTER_BASE_URL}/{use_model}"
            print(f"[INFO] Using HF Router: {api_url}")

        # Build prompt / สร้าง prompt
        user_prompt = build_feedback_prompt(payload)
        full_prompt = f"{FEEDBACK_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"

        # Prepare headers / เตรียม headers
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        # Prepare payload for chat completion / เตรียม payload สำหรับ chat completion
        # MedGemma uses chat format / MedGemma ใช้รูปแบบ chat
        request_payload = {
            "inputs": full_prompt,
            "parameters": {
                "max_new_tokens": FEEDBACK_MAX_TOKENS,
                "temperature": FEEDBACK_TEMPERATURE,
                "return_full_text": False,
                "do_sample": True if FEEDBACK_TEMPERATURE > 0 else False,
            }
        }

        # Make request with retry logic / ส่ง request พร้อม retry logic
        response_text = None
        last_error = None

        for attempt in range(HF_MAX_RETRIES):
            try:
                print(f"[INFO] HuggingFace API attempt {attempt + 1}/{HF_MAX_RETRIES}")

                response = requests.post(
                    api_url,
                    headers=headers,
                    json=request_payload,
                    timeout=HF_API_TIMEOUT
                )

                # Handle specific error codes with helpful messages
                # จัดการ error codes เฉพาะพร้อมข้อความที่เป็นประโยชน์

                # 401/403 - Authentication/Authorization error
                if response.status_code in (401, 403):
                    error_msg = f"HTTP {response.status_code}: Authentication failed"
                    print(f"[ERROR] {error_msg}")
                    print("[ERROR] Your HF_API_TOKEN likely lacks 'Inference Providers' permission.")
                    print("[ERROR] Go to https://huggingface.co/settings/tokens and ensure your token has the required permissions.")
                    last_error = error_msg
                    return None  # Don't retry auth errors

                # 404 - Model not found
                if response.status_code == 404:
                    error_msg = f"HTTP 404: Model '{use_model}' not found"
                    print(f"[ERROR] {error_msg}")
                    print(f"[ERROR] The model '{use_model}' may not be available on hf-inference.")
                    print("[ERROR] Consider switching to a different model or using a dedicated endpoint.")
                    last_error = error_msg
                    return None  # Don't retry 404 errors

                # 503 - Model loading / จัดการ 503 - โมเดลกำลังโหลด
                if response.status_code == 503:
                    try:
                        error_data = response.json()
                        estimated_time = error_data.get("estimated_time", HF_RETRY_DELAY)
                    except Exception:
                        estimated_time = HF_RETRY_DELAY
                    print(f"[INFO] Model loading, waiting {estimated_time}s...")
                    time.sleep(min(estimated_time, HF_RETRY_DELAY * 2))
                    continue

                # Handle other errors / จัดการ error อื่นๆ
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    print(f"[ERROR] HuggingFace API error: {last_error}")
                    if attempt < HF_MAX_RETRIES - 1:
                        time.sleep(HF_RETRY_DELAY)
                    continue

                # Parse response / แปลง response
                result_data = response.json()

                # Extract generated text / ดึงข้อความที่สร้าง
                if isinstance(result_data, list) and len(result_data) > 0:
                    # Standard format: [{"generated_text": "..."}]
                    response_text = result_data[0].get("generated_text", "")
                elif isinstance(result_data, dict):
                    # Alternative format: {"generated_text": "..."}
                    response_text = result_data.get("generated_text", "")

                if response_text:
                    break

            except requests.exceptions.Timeout:
                last_error = f"Request timeout after {HF_API_TIMEOUT}s"
                print(f"[ERROR] {last_error}")
                if attempt < HF_MAX_RETRIES - 1:
                    time.sleep(HF_RETRY_DELAY)

            except requests.exceptions.RequestException as e:
                last_error = str(e)
                print(f"[ERROR] Request error: {last_error}")
                if attempt < HF_MAX_RETRIES - 1:
                    time.sleep(HF_RETRY_DELAY)

        # Check if we got a response / ตรวจสอบว่าได้ response หรือไม่
        if not response_text:
            print(f"[ERROR] No response after {HF_MAX_RETRIES} attempts. Last error: {last_error}")
            return None  # Return None to trigger fallback

        # Parse JSON response / แปลง JSON จากคำตอบ
        if FEEDBACK_OUTPUT_FORMAT == "json":
            result = parse_json_response(response_text)
        else:
            result = {
                "raw_text": response_text,
                "format": "markdown"
            }

        # Add metadata / เพิ่ม metadata
        result["is_fallback"] = False
        result["model_used"] = use_model
        result["provider"] = "huggingface"

        return result

    except Exception as e:
        print(f"[ERROR] HuggingFace API error: {e}")
        return None  # Return None to trigger fallback


def generate_feedback_medgemma(payload: dict) -> dict:
    """
    Generate feedback using MedGemma via Hugging Face.
    สร้าง feedback โดยใช้ MedGemma ผ่าน Hugging Face

    This is a wrapper that uses the HuggingFace function with MedGemma-specific settings.
    นี่คือ wrapper ที่ใช้ฟังก์ชัน HuggingFace กับการตั้งค่าเฉพาะ MedGemma

    Args:
        payload: Session data dictionary

    Returns:
        Feedback dictionary or None if failed (triggers fallback)
    """
    return generate_feedback_huggingface(payload, model_id=FEEDBACK_MODEL_NAME)


def generate_feedback(payload: dict) -> dict:
    """
    Main function to generate feedback using configured provider.
    ฟังก์ชันหลักสำหรับสร้าง feedback โดยใช้ provider ที่กำหนดไว้

    Supports automatic fallback to Gemini if primary provider fails.
    รองรับ fallback อัตโนมัติไปยัง Gemini หากผู้ให้บริการหลักล้มเหลว

    Args:
        payload: Session data dictionary containing:
            - user: {name, email}
            - case: case name
            - mode: selected mode
            - stats: {duration_seconds, total_messages, doctor_turns, patient_turns}
            - transcript_text: formatted transcript string
            - transcript_messages: list of message dicts
            - answers: {provisional_dx, ddx1, ddx2, ddx3, formulation_framework, formulation_text}

    Returns:
        Feedback dictionary with structure:
        {
            "is_fallback": bool,
            "interview_feedback": {...},
            "clinical_feedback": {...},
            "model_used": str (optional),
            "provider": str (optional),
            "error_message": str (optional)
        }
    """
    result = None

    # Try primary provider / ลองผู้ให้บริการหลัก
    if FEEDBACK_PROVIDER == "gemini":
        result = generate_feedback_gemini(payload)

    elif FEEDBACK_PROVIDER == "medgemma":
        print(f"[INFO] Using MedGemma provider: {FEEDBACK_MODEL_NAME}")
        result = generate_feedback_medgemma(payload)

    elif FEEDBACK_PROVIDER == "huggingface":
        print(f"[INFO] Using HuggingFace provider: {FEEDBACK_MODEL_NAME}")
        result = generate_feedback_huggingface(payload)

    else:
        print(f"[WARNING] Unknown provider: {FEEDBACK_PROVIDER}")

    # Check if primary succeeded / ตรวจสอบว่าผู้ให้บริการหลักสำเร็จหรือไม่
    if result and not result.get("is_fallback"):
        return result

    # Try fallback provider if configured / ลอง fallback provider หากกำหนดไว้
    if FEEDBACK_FALLBACK_PROVIDER and FEEDBACK_FALLBACK_PROVIDER != FEEDBACK_PROVIDER:
        print(f"[INFO] Primary provider failed, trying fallback: {FEEDBACK_FALLBACK_PROVIDER}")

        if FEEDBACK_FALLBACK_PROVIDER == "gemini":
            fallback_result = generate_feedback_gemini(payload, model_name=FEEDBACK_FALLBACK_MODEL)
            if fallback_result and not fallback_result.get("is_fallback"):
                fallback_result["used_fallback"] = True
                fallback_result["original_provider"] = FEEDBACK_PROVIDER
                return fallback_result

    # Return the result or fallback / คืนค่าผลลัพธ์หรือ fallback
    if result:
        return result

    return get_fallback_feedback("All providers failed")


def format_transcript_for_display(chat_history: list) -> str:
    """
    Format chat history into readable transcript text.
    จัดรูปแบบ chat history เป็นข้อความ transcript ที่อ่านได้

    Args:
        chat_history: List of message dictionaries with 'role' and 'content'

    Returns:
        Formatted transcript string
    """
    lines = []
    for idx, msg in enumerate(chat_history, 1):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if role == "user":
            speaker = "👨‍⚕️ Doctor"
        elif role == "assistant":
            speaker = "🧑 Patient"
        else:
            speaker = role.capitalize()

        lines.append(f"[{idx}] {speaker}: {content}")

    return "\n\n".join(lines)


def prepare_transcript_rows(session_id: str, chat_history: list, timestamp: str) -> list:
    """
    Prepare transcript data as rows for Google Sheet.
    เตรียมข้อมูล transcript เป็นแถวสำหรับ Google Sheet

    Args:
        session_id: Unique session identifier
        chat_history: List of message dictionaries
        timestamp: Session timestamp string

    Returns:
        List of row dictionaries
    """
    rows = []
    for idx, msg in enumerate(chat_history):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        speaker = "Doctor" if role == "user" else "Patient" if role == "assistant" else role

        rows.append({
            "session_id": session_id,
            "timestamp": timestamp,
            "speaker": speaker,
            "message": content,
            "turn_index": idx + 1
        })

    return rows
