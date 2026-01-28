"""
Feedback Service / บริการสร้าง Feedback
========================================
This module handles the generation of feedback using Gemini AI models.
Uses Gemini 3 Pro (primary) with deep thinking for comprehensive evaluation.

โมดูลนี้จัดการการสร้าง feedback โดยใช้โมเดล Gemini AI
ใช้ Gemini 3 Pro (หลัก) พร้อมการคิดวิเคราะห์เชิงลึกสำหรับการประเมินอย่างครอบคลุม
"""

import json
import re
import streamlit as st

# Import GenAI client and types / นำเข้า GenAI client และ types
from genai_client import (
    get_client,
    generate_content_sync,
    types,
)
from model_config import get_valid_model_name

from feedback_config import (
    FEEDBACK_MODEL_NAME,
    FEEDBACK_FALLBACK_MODEL,
    FEEDBACK_TEMPERATURE,
    FEEDBACK_OUTPUT_FORMAT,
    FEEDBACK_SYSTEM_PROMPT,
    FEEDBACK_USER_PROMPT_TEMPLATE,
    FEEDBACK_MAX_TOKENS,
    FEEDBACK_THINKING_LEVEL,
    FEEDBACK_FALLBACK_THINKING_BUDGET,
    FEEDBACK_RESPONSE_MIME_TYPE,
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


def _get_thinking_config_for_model(model_name: str):
    """
    Get appropriate ThinkingConfig based on model family.
    รับ ThinkingConfig ที่เหมาะสมตามตระกูลโมเดล

    Args:
        model_name: Name of the model

    Returns:
        ThinkingConfig object or None
    """
    if model_name.startswith("gemini-3"):
        # Gemini 3 models use thinking_level
        print(f"[INFO] Using thinking_level='{FEEDBACK_THINKING_LEVEL}' for {model_name}")
        return types.ThinkingConfig(thinking_level=FEEDBACK_THINKING_LEVEL)
    elif model_name == "gemini-2.5-pro":
        # Gemini 2.5 Pro uses thinking_budget
        print(f"[INFO] Using thinking_budget={FEEDBACK_FALLBACK_THINKING_BUDGET} for {model_name}")
        return types.ThinkingConfig(thinking_budget=FEEDBACK_FALLBACK_THINKING_BUDGET)
    else:
        # Other models don't support thinking config
        return None


def generate_feedback_gemini(payload: dict, model_name: str = None) -> dict:
    """
    Generate feedback using Google Gemini API with thinking support.
    สร้าง feedback โดยใช้ Google Gemini API พร้อมการคิดวิเคราะห์เชิงลึก

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
            return None

        # Use provided model name or default, with validation
        # ใช้ชื่อโมเดลที่ให้มาหรือค่าเริ่มต้น พร้อมการตรวจสอบ
        raw_model = model_name or FEEDBACK_MODEL_NAME
        use_model = get_valid_model_name(raw_model, default_model=FEEDBACK_MODEL_NAME)

        print(f"[INFO] Generating feedback with model: {use_model}")

        # Build prompt / สร้าง prompt
        user_prompt = build_feedback_prompt(payload)

        # Combine system and user prompts / รวม system และ user prompts
        full_prompt = f"{FEEDBACK_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"

        # Get thinking config for model / รับ thinking config สำหรับโมเดล
        thinking_config = _get_thinking_config_for_model(use_model)

        # Determine response_mime_type (only for JSON output)
        # กำหนด response_mime_type (เฉพาะสำหรับ JSON output)
        response_mime_type = FEEDBACK_RESPONSE_MIME_TYPE if FEEDBACK_OUTPUT_FORMAT == "json" else None

        # Generate response / สร้างคำตอบ
        try:
            response_text = generate_content_sync(
                model=use_model,
                contents=full_prompt,
                temperature=FEEDBACK_TEMPERATURE,
                max_output_tokens=FEEDBACK_MAX_TOKENS,
                thinking_config=thinking_config,
                response_mime_type=response_mime_type,
            )
        except ValueError as e:
            print(f"[ERROR] Generation failed: {e}")
            return None

        if not response_text or not response_text.strip():
            print("[ERROR] Empty response from Gemini")
            return None

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
        if thinking_config:
            result["thinking_enabled"] = True

        return result

    except Exception as e:
        print(f"[ERROR] Gemini API error: {e}")
        return None


def generate_feedback(payload: dict) -> dict:
    """
    Main function to generate feedback using Gemini models.
    ฟังก์ชันหลักสำหรับสร้าง feedback โดยใช้โมเดล Gemini

    Uses Gemini 3 Pro as primary with fallback to Gemini 2.5 Pro.
    Both models use deep thinking for comprehensive analysis.

    ใช้ Gemini 3 Pro เป็นหลักพร้อม fallback ไปยัง Gemini 2.5 Pro
    ทั้งสองโมเดลใช้การคิดวิเคราะห์เชิงลึกสำหรับการวิเคราะห์อย่างครอบคลุม

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
    # Try primary model (Gemini 3 Pro) / ลองโมเดลหลัก (Gemini 3 Pro)
    print(f"[INFO] Trying primary model: {FEEDBACK_MODEL_NAME}")
    result = generate_feedback_gemini(payload, model_name=FEEDBACK_MODEL_NAME)

    # Check if primary succeeded / ตรวจสอบว่าโมเดลหลักสำเร็จหรือไม่
    if result and not result.get("is_fallback") and not result.get("parse_failed"):
        return result

    # Try fallback model (Gemini 2.5 Pro) / ลองโมเดลสำรอง (Gemini 2.5 Pro)
    print(f"[INFO] Primary model failed, trying fallback: {FEEDBACK_FALLBACK_MODEL}")
    fallback_result = generate_feedback_gemini(payload, model_name=FEEDBACK_FALLBACK_MODEL)

    if fallback_result and not fallback_result.get("is_fallback"):
        fallback_result["used_fallback"] = True
        fallback_result["original_model"] = FEEDBACK_MODEL_NAME
        return fallback_result

    # If primary had partial result, return it / ถ้าโมเดลหลักมีผลลัพธ์บางส่วน ให้คืนค่า
    if result:
        return result

    # All models failed / โมเดลทั้งหมดล้มเหลว
    return get_fallback_feedback("All models failed to generate feedback")


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


def prepare_transcript_rows(session_id: str, chat_history: list, timestamp: str, selected_mode: str = "text") -> list:
    """
    Prepare transcript data as rows for Google Sheet.
    เตรียมข้อมูล transcript เป็นแถวสำหรับ Google Sheet

    Args:
        session_id: Unique session identifier
        chat_history: List of message dictionaries
        timestamp: Session timestamp string
        selected_mode: Interview mode (text/voice) / โหมดการสัมภาษณ์

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
            "turn_index": idx + 1,
            "selected_mode": selected_mode,
        })

    return rows
