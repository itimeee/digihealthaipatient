"""
Feedback Service / บริการสร้าง Feedback
========================================
This module handles the generation of feedback using the configured model.
Separated from app.py for easier maintenance and configuration.

โมดูลนี้จัดการการสร้าง feedback โดยใช้โมเดลที่กำหนดไว้
แยกออกจาก app.py เพื่อให้ดูแลและปรับแต่งได้ง่ายขึ้น
"""

import json
import re
import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from feedback_config import (
    FEEDBACK_PROVIDER,
    FEEDBACK_MODEL_NAME,
    FEEDBACK_TEMPERATURE,
    FEEDBACK_OUTPUT_FORMAT,
    FEEDBACK_SYSTEM_PROMPT,
    FEEDBACK_USER_PROMPT_TEMPLATE,
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


def get_fallback_feedback() -> dict:
    """
    Return fallback feedback when API call fails.
    คืนค่า fallback feedback เมื่อเรียก API ไม่สำเร็จ

    Returns:
        Dictionary with is_fallback=True flag
    """
    return {
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


def generate_feedback_gemini(payload: dict) -> dict:
    """
    Generate feedback using Google Gemini API.
    สร้าง feedback โดยใช้ Google Gemini API

    Args:
        payload: Session data dictionary

    Returns:
        Feedback dictionary with interview_feedback and clinical_feedback
    """
    try:
        # Get API key from secrets / ดึง API key จาก secrets
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key:
            print("[ERROR] GEMINI_API_KEY not found in secrets")
            return get_fallback_feedback()

        # Configure Gemini / ตั้งค่า Gemini
        genai.configure(api_key=api_key)

        # Create model instance / สร้าง instance ของโมเดล
        model = genai.GenerativeModel(FEEDBACK_MODEL_NAME)

        # Build prompt / สร้าง prompt
        user_prompt = build_feedback_prompt(payload)

        # Combine system and user prompts / รวม system และ user prompts
        full_prompt = f"{FEEDBACK_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"

        # Generation config / ตั้งค่าการสร้าง
        generation_config = {
            "temperature": FEEDBACK_TEMPERATURE,
            "max_output_tokens": 4096,
        }

        # Safety settings - allow psychiatric content / ตั้งค่าความปลอดภัย - อนุญาตเนื้อหาจิตเวช
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        # Generate response / สร้างคำตอบ
        response = model.generate_content(
            full_prompt,
            generation_config=generation_config,
            safety_settings=safety_settings,
        )

        # Extract text from response / ดึงข้อความจากคำตอบ
        try:
            response_text = response.text
        except (ValueError, AttributeError) as e:
            print(f"[ERROR] Failed to get response.text: {e}")
            # Try to extract from parts / ลองดึงจาก parts
            try:
                response_text = ""
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text
            except Exception as inner_e:
                print(f"[ERROR] Failed to extract from parts: {inner_e}")
                return get_fallback_feedback()

        if not response_text or not response_text.strip():
            print("[ERROR] Empty response from Gemini")
            return get_fallback_feedback()

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
        result["model_used"] = FEEDBACK_MODEL_NAME

        return result

    except Exception as e:
        print(f"[ERROR] Gemini API error: {e}")
        fallback = get_fallback_feedback()
        fallback["error_message"] = str(e)
        return fallback


def generate_feedback(payload: dict) -> dict:
    """
    Main function to generate feedback using configured provider.
    ฟังก์ชันหลักสำหรับสร้าง feedback โดยใช้ provider ที่กำหนดไว้

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
            "error_message": str (optional)
        }
    """
    if FEEDBACK_PROVIDER == "gemini":
        return generate_feedback_gemini(payload)
    else:
        # Future: Add support for other providers / อนาคต: เพิ่มการรองรับ provider อื่น
        print(f"[WARNING] Unknown provider: {FEEDBACK_PROVIDER}, using fallback")
        return get_fallback_feedback()


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
