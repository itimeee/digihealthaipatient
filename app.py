"""
DigiHealth AI Patient - Psychiatric Training Application
แอปพลิเคชันฝึกซ้อมการซักประวัติผู้ป่วยทางจิตเวช
"""

import html
import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import threading
import time
import re
from streamlit.runtime.scriptrunner import add_script_run_ctx

# Import case configurations / นำเข้าการตั้งค่าเคส
from cases import ALL_CASES, get_case_by_name

# Import GenAI client and model config / นำเข้า GenAI client และการตั้งค่าโมเดล
from genai_client import (
    get_client,
    generate_content_sync,
)
from model_config import (
    DEFAULT_CASE_MODEL,
    DEFAULT_CASE_TEMPERATURE,
    get_valid_model_name,
    PATIENT_STOP_SEQUENCES,
    SAFE_SIMULATION_CONTEXT,
    STRICT_OUTPUT_RULES,
    SAFER_CONTEXT,
    FALLBACK_RESPONSE_GENERIC,
    FALLBACK_RESPONSE_SAFETY,
    FALLBACK_RESPONSE_EMPTY,
)

# Import feedback modules / นำเข้าโมดูล feedback
from feedback_config import PSYCHODYNAMIC_FRAMEWORKS
from feedback_service import (
    generate_feedback,
    format_transcript_for_display,
    prepare_transcript_rows,
)
from feedback_logger import (
    append_session_to_feedback_sheet,
    prepare_session_row,
)

# Import voice modules / นำเข้าโมดูลเสียง
from voice_config import (
    STATUS_TRANSCRIBING,
    STATUS_GENERATING_TTS,
    TTS_AUTO_PLAY,
    VOICE_MINIMAL_UI,
    get_tts_auto_play,
    get_voice_minimal_ui,
)
from voice_service import (
    transcribe_audio,
    synthesize_speech,
    is_voice_service_available,
    get_voice_service_status,
)

# ============================================================================
# PAGE CONFIGURATION (Must be first Streamlit command)
# การตั้งค่าหน้าเว็บ (ต้องเป็นคำสั่ง Streamlit แรก)
# ============================================================================

st.set_page_config(
    page_title="DigiHealth AI Patient",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================================
# CONFIGURATION / การตั้งค่า
# ============================================================================
# You can easily change these values / คุณสามารถแก้ไขค่าเหล่านี้ได้ง่าย ๆ

# Timer Duration (in minutes) / ระยะเวลาจับเวลา (นาที)
TIMER_DURATION_MINUTES = 30

# Google Sheet ID for logging session data / ID ของ Google Sheet สำหรับบันทึกข้อมูล
# Get sheet ID from the URL: https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit
# Can be overridden via st.secrets["logging"]["sheet_id"]
_DEFAULT_GOOGLE_SHEET_ID = "1motfqsOspQrVkWDtRqUxgfH_-3nDuqYGw9eXwEfQWoo"

# Google Sheet ID for latest session data (overwrites each time) / ID ของ Google Sheet สำหรับข้อมูลเซสชันล่าสุด
# Can be overridden via st.secrets["logging"]["sheet_latest_id"]
_DEFAULT_GOOGLE_SHEET_LATEST_ID = "1y7mhBgABMNDzRFPDmQa7kQqTE6q4h_Py02IvT2OmUM8"


def get_sheet_id() -> str:
    """
    Get Google Sheet ID from secrets or use default.
    ดึง Google Sheet ID จาก secrets หรือใช้ค่าเริ่มต้น
    """
    try:
        logging_config = st.secrets.get("logging", {})
        return logging_config.get("sheet_id", _DEFAULT_GOOGLE_SHEET_ID)
    except Exception:
        return _DEFAULT_GOOGLE_SHEET_ID


def get_sheet_latest_id() -> str:
    """
    Get Google Sheet Latest ID from secrets or use default.
    ดึง Google Sheet Latest ID จาก secrets หรือใช้ค่าเริ่มต้น
    """
    try:
        logging_config = st.secrets.get("logging", {})
        return logging_config.get("sheet_latest_id", _DEFAULT_GOOGLE_SHEET_LATEST_ID)
    except Exception:
        return _DEFAULT_GOOGLE_SHEET_LATEST_ID


# ============================================================================
# HTML ESCAPING HELPERS / ฟังก์ชันช่วย escape HTML
# ============================================================================

def escape_html(text: str) -> str:
    """
    Escape HTML characters to prevent injection.
    แปลง HTML characters เพื่อป้องกัน injection

    Args:
        text: Raw text that may contain HTML

    Returns:
        Escaped text safe for HTML rendering
    """
    if not text:
        return ""
    return html.escape(str(text))


def render_doctor_bubble(content: str) -> str:
    """
    Render doctor's chat bubble HTML with escaped content.
    สร้าง HTML สำหรับ chat bubble ของแพทย์พร้อม escape content

    Args:
        content: Message content (will be escaped)

    Returns:
        HTML string for doctor's message bubble
    """
    safe_content = escape_html(content)
    return (
        f"<div style='text-align: right; background: linear-gradient(135deg, #4a90a4 0%, #5ba3b8 100%); "
        f"color: white; padding: 12px 16px; border-radius: 18px 18px 4px 18px; "
        f"margin: 8px 0; box-shadow: 0 2px 4px rgba(74, 144, 164, 0.2); max-width: 80%; "
        f"margin-left: auto;'>"
        f"<b style='color: #e3f2fd;'>You:</b> {safe_content}</div>"
    )


def render_patient_bubble(content: str) -> str:
    """
    Render patient's chat bubble HTML with escaped content.
    สร้าง HTML สำหรับ chat bubble ของผู้ป่วยพร้อม escape content

    Args:
        content: Message content (will be escaped)

    Returns:
        HTML string for patient's message bubble
    """
    safe_content = escape_html(content)
    return (
        f"<div style='text-align: left; background-color: white; padding: 12px 16px; "
        f"border-radius: 18px 18px 18px 4px; margin: 8px 0; "
        f"border: 2px solid #e3f2fd; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08); "
        f"max-width: 80%; color: #37474f;'>"
        f"<b style='color: #2c5f7d;'>Patient:</b> {safe_content}</div>"
    )


def render_patient_bubble_with_audio(content: str, audio_b64: str, iframe_height: int) -> str:
    """
    Render patient's chat bubble with audio replay button using components.html.
    สร้าง HTML สำหรับ chat bubble ของผู้ป่วยพร้อมปุ่มเล่นเสียง

    Args:
        content: Message content (will be escaped)
        audio_b64: Base64 encoded audio data
        iframe_height: Height for iframe component

    Returns:
        HTML string for patient's message bubble with audio
    """
    safe_content = escape_html(content)
    return f"""
    <div style='display: flex; align-items: flex-start; gap: 6px; font-family: "Source Sans Pro", sans-serif;'>
        <div style='text-align: left; background-color: white; padding: 10px 14px;
            border-radius: 18px 18px 18px 4px;
            border: 2px solid #e3f2fd; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
            flex: 1; color: #37474f; font-size: 14px; line-height: 1.4; max-width: calc(100% - 40px);'>
            <b style='color: #2c5f7d;'>Patient:</b> {safe_content}
        </div>
        <button onclick="new Audio('data:audio/mpeg;base64,{audio_b64}').play()"
            style='background: #4a90a4; color: white; border: none; border-radius: 50%;
            width: 28px; height: 28px; cursor: pointer; font-size: 12px; margin-top: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2); flex-shrink: 0;'
            title='Replay audio'>🔊</button>
    </div>
    """


# ============================================================================
# GOOGLE SHEETS SETUP / ตั้งค่า Google Sheets
# ============================================================================

def get_google_credentials():
    """
    Load Google credentials from Streamlit secrets
    โหลดข้อมูลรับรองจาก Streamlit secrets
    """
    try:
        # Define the scopes needed for Google Drive and Sheets
        # กำหนด permissions ที่ต้องการสำหรับ Drive และ Sheets
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        # Load credentials from secrets
        # โหลดข้อมูลรับรองจาก secrets
        credentials_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=scopes
        )
        return credentials
    except Exception as e:
        st.error(f"Error loading Google credentials: {e}")
        st.error("Please check your secrets.toml file configuration.")
        return None


def save_session_to_sheet(user_name, user_email, chat_history, case_name=None, mode=None):
    """
    Append session data to existing Google Sheet
    เพิ่มข้อมูลเซสชันลงใน Google Sheet ที่มีอยู่

    Args:
        user_name: Name of the user / ชื่อผู้ใช้
        user_email: Email of the user / อีเมลผู้ใช้
        chat_history: List of chat messages / ประวัติการสนทนา
        case_name: Name of the case (e.g., "Case A") / ชื่อเคส
        mode: Interview mode (text/voice) / โหมดการสัมภาษณ์
    """
    try:
        # Get credentials / รับข้อมูลรับรอง
        credentials = get_google_credentials()
        if credentials is None:
            return False

        # Connect to Google Sheets / เชื่อมต่อ Google Sheets
        gc = gspread.authorize(credentials)

        # Open the existing spreadsheet / เปิดสเปรดชีทที่มีอยู่
        spreadsheet = gc.open_by_key(get_sheet_id())
        worksheet = spreadsheet.sheet1

        # Get current timestamp / รับเวลาปัจจุบัน
        session_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Get mode from session state if not provided / ดึง mode จาก session state ถ้าไม่ได้ระบุ
        if mode is None:
            mode = st.session_state.get('selected_mode', 'text')

        # Define expected headers including Mode / กำหนด headers ที่คาดหวังรวม Mode
        expected_headers = ["Session ID", "Timestamp", "User Name", "User Email", "Case Name", "Mode", "Speaker", "Message"]

        # Check and update headers if needed (optimized: only read row 1)
        # ตรวจสอบและอัพเดท headers ถ้าจำเป็น (ปรับปรุง: อ่านแค่แถว 1)
        try:
            current_headers = worksheet.row_values(1)
        except Exception:
            current_headers = []

        if not current_headers or (current_headers and current_headers[0] != "Session ID"):
            # Add headers if sheet is empty / เพิ่ม header ถ้าชีทว่าง
            worksheet.insert_row(expected_headers, 1)
        elif "Mode" not in current_headers:
            # Update header row to include Mode / อัพเดท header row ให้มี Mode
            # Insert Mode column after Case Name (position 5, 0-indexed)
            if len(current_headers) >= 5:
                # Find position after "Case Name"
                try:
                    case_idx = current_headers.index("Case Name")
                    new_headers = current_headers[:case_idx+1] + ["Mode"] + current_headers[case_idx+1:]
                    worksheet.update('A1', [new_headers])
                except ValueError:
                    # Case Name not found, append Mode at end
                    new_headers = current_headers + ["Mode"]
                    worksheet.update('A1', [new_headers])

        # Prepare rows to append / เตรียมแถวที่จะเพิ่ม
        rows_to_add = []

        # Add session separator row / เพิ่มแถวแบ่งเซสชัน
        separator = [f"=== SESSION START: {session_id} ===", session_time, user_name, user_email, case_name or "", mode, "", ""]
        rows_to_add.append(separator)

        # Add all chat messages / เพิ่มข้อความสนทนาทั้งหมด
        for message in chat_history:
            row = [
                session_id,
                session_time,
                user_name,
                user_email,
                case_name or "",
                mode,
                message["role"],
                message["content"]
            ]
            rows_to_add.append(row)

        # Add session end separator / เพิ่มแถวปิดเซสชัน
        end_separator = [f"=== SESSION END: {session_id} ===", session_time, user_name, user_email, case_name or "", mode, "", f"Total messages: {len(chat_history)}"]
        rows_to_add.append(end_separator)

        # Add empty row for spacing / เพิ่มแถวว่างเพื่อเว้นระยะ
        rows_to_add.append(["", "", "", "", "", "", "", ""])

        # Append all rows at once (more efficient) / เพิ่มทุกแถวพร้อมกัน (เร็วกว่า)
        worksheet.append_rows(rows_to_add)

        return True

    except Exception as e:
        st.error(f"Error saving to Google Sheet: {e}")
        return False


def save_latest_session(user_name, user_email, chat_history, case_name=None, mode=None):
    """
    Replace data in latest session sheet (for displaying most recent interview)
    แทนที่ข้อมูลในชีทเซสชันล่าสุด (สำหรับแสดงการสัมภาษณ์ล่าสุด)

    Args:
        user_name: Name of the user / ชื่อผู้ใช้
        user_email: Email of the user / อีเมลผู้ใช้
        chat_history: List of chat messages / ประวัติการสนทนา
        case_name: Name of the case (e.g., "Case A") / ชื่อเคส
        mode: Interview mode (text/voice) / โหมดการสัมภาษณ์
    """
    try:
        # Get credentials / รับข้อมูลรับรอง
        credentials = get_google_credentials()
        if credentials is None:
            return False

        # Connect to Google Sheets / เชื่อมต่อ Google Sheets
        gc = gspread.authorize(credentials)

        # Open the latest session spreadsheet / เปิดสเปรดชีทเซสชันล่าสุด
        spreadsheet = gc.open_by_key(get_sheet_latest_id())
        worksheet = spreadsheet.sheet1

        # Clear all existing data / ลบข้อมูลเก่าทั้งหมด
        worksheet.clear()

        # Get current timestamp / รับเวลาปัจจุบัน
        session_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Get mode from session state if not provided / ดึง mode จาก session state ถ้าไม่ได้ระบุ
        if mode is None:
            mode = st.session_state.get('selected_mode', 'text')

        # Prepare all rows including headers / เตรียมแถวทั้งหมดรวมหัวตาราง
        all_rows = []

        # Add headers including Mode / เพิ่มหัวตารางรวม Mode
        headers = ["Session ID", "Timestamp", "User Name", "User Email", "Case Name", "Mode", "Speaker", "Message"]
        all_rows.append(headers)

        # Add all chat messages / เพิ่มข้อความสนทนาทั้งหมด
        for message in chat_history:
            row = [
                session_id,
                session_time,
                user_name,
                user_email,
                case_name or "",
                mode,
                message["role"],
                message["content"]
            ]
            all_rows.append(row)

        # Write all rows at once / เขียนทุกแถวพร้อมกัน
        worksheet.update('A1', all_rows)

        return True

    except Exception as e:
        st.error(f"Error saving latest session: {e}")
        return False


def get_latest_session_data():
    """
    Get the latest session data from the sheet
    ดึงข้อมูลเซสชันล่าสุดจากชีท

    Returns:
        List of dictionaries with session data / รายการข้อมูลเซสชัน
    """
    try:
        # Get credentials / รับข้อมูลรับรอง
        credentials = get_google_credentials()
        if credentials is None:
            return []

        # Connect to Google Sheets / เชื่อมต่อ Google Sheets
        gc = gspread.authorize(credentials)

        # Open the latest session spreadsheet / เปิดสเปรดชีทเซสชันล่าสุด
        spreadsheet = gc.open_by_key(get_sheet_latest_id())
        worksheet = spreadsheet.sheet1

        # Get all data / ดึงข้อมูลทั้งหมด
        data = worksheet.get_all_records()

        return data

    except Exception as e:
        st.error(f"Error reading latest session data: {e}")
        return []


# ============================================================================
# GEMINI AI SETUP / ตั้งค่า Gemini AI
# ============================================================================

def validate_genai_client() -> tuple:
    """
    Validate GenAI client is available and return status.
    ตรวจสอบว่า GenAI client พร้อมใช้งานและคืนสถานะ

    Returns:
        Tuple of (is_valid: bool, error_message: str or None)
    """
    try:
        client = get_client()
        return (True, None)
    except ValueError as e:
        error_msg = str(e)
        # Store error for UI display / เก็บ error สำหรับแสดงใน UI
        if 'last_model_error' not in st.session_state:
            st.session_state.last_model_error = error_msg
        return (False, error_msg)
    except Exception as e:
        error_msg = f"Unexpected error initializing AI: {e}"
        if 'last_model_error' not in st.session_state:
            st.session_state.last_model_error = error_msg
        return (False, error_msg)


def sanitize_patient_output(text: str) -> str:
    """
    Remove meta commentary, instructions, and out-of-character text from AI output
    ลบข้อความที่เป็นคำอธิบาย คำแนะนำ และข้อความที่ออกจากบทบาทผู้ป่วย

    Args:
        text: Raw output from AI / ข้อความดิบจาก AI

    Returns:
        Sanitized text with meta content removed / ข้อความที่ลบเนื้อหาเมต้าออกแล้ว
    """
    if not text:
        return "ขอโทษค่ะ หนูไม่แน่ใจจะพูดยังไง"

    # Define patterns to remove meta commentary / กำหนดแพทเทิร์นเพื่อลบคำอธิบาย
    meta_patterns = [
        r'\*\*Note to User:\*\*.*?(?=\n\n|\Z)',  # **Note to User:** blocks
        r'Note to User:.*?(?=\n\n|\Z)',           # Note to User: blocks
        r'\*\*Note to Doctor:\*\*.*?(?=\n\n|\Z)', # **Note to Doctor:** blocks
        r'Note to Doctor:.*?(?=\n\n|\Z)',         # Note to Doctor: blocks
        r'Suggested questions:.*?(?=\n\n|\Z)',    # Suggested questions: blocks
        r'คำแนะนำ:.*?(?=\n\n|\Z)',                # Thai "recommendations"
        r'ข้อเสนอแนะ:.*?(?=\n\n|\Z)',             # Thai "suggestions"
        r'As an AI.*?(?=\n\n|\Z)',                # "As an AI..." disclaimers
        r'I am an AI.*?(?=\n\n|\Z)',              # "I am an AI..." disclaimers
        r'\(Note:.*?\)',                          # (Note: ...) inline
        r'\[Note:.*?\]',                          # [Note: ...] inline
    ]

    # Apply all patterns / ใช้แพทเทิร์นทั้งหมด
    cleaned_text = text
    for pattern in meta_patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.DOTALL)

    # Clean up excessive whitespace / ลบช่องว่างเกิน
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)  # Max 2 newlines
    cleaned_text = cleaned_text.strip()

    # If sanitization resulted in empty text, return fallback / ถ้าข้อความว่างหลังทำความสะอาด ให้คืนข้อความสำรอง
    if not cleaned_text:
        return "ขอโทษค่ะ หนูไม่แน่ใจจะพูดยังไง"

    return cleaned_text


def get_ai_response_sync(chat_history, case_context):
    """
    Get response from Gemini AI using case-specific configuration (sync).
    รับคำตอบจาก Gemini AI โดยใช้การตั้งค่าเฉพาะของเคส (แบบ sync)

    Uses synchronous generation to avoid asyncio event loop issues.
    ใช้การสร้างแบบ synchronous เพื่อหลีกเลี่ยงปัญหา asyncio event loop

    Args:
        chat_history: List of previous messages / ประวัติการสนทนา
        case_context: Case information for context / ข้อมูลเคสสำหรับบริบท

    Returns:
        AI response text or fallback message
    """
    try:
        # Validate client first / ตรวจสอบ client ก่อน
        is_valid, error_msg = validate_genai_client()
        if not is_valid:
            st.session_state.last_model_error = error_msg
            return f"AI model is not available: {error_msg}"

        # Get case-specific model, prompt, and temperature from session state
        # ดึงโมเดล prompt และ temperature เฉพาะของเคส
        raw_model = st.session_state.get('case_model', DEFAULT_CASE_MODEL)
        case_model = get_valid_model_name(raw_model)  # Map to valid model name
        case_prompt = st.session_state.get('case_system_prompt', 'You are a patient in a psychiatric clinic.')
        case_temperature = st.session_state.get('case_temperature', DEFAULT_CASE_TEMPERATURE)

        print(f"[DEBUG] Using model: {case_model} (original: {raw_model})")

        # Build the conversation prompt / สร้าง prompt การสนทนา
        full_prompt = f"{SAFE_SIMULATION_CONTEXT}\n\n{case_prompt}{STRICT_OUTPUT_RULES}\n\nCase Context:\n{case_context}\n\n"

        # Add chat history / เพิ่มประวัติการสนทนา
        for message in chat_history:
            if message["role"] == "user":
                full_prompt += f"Doctor: {message['content']}\n"
            else:
                full_prompt += f"Patient: {message['content']}\n"

        full_prompt += "Patient: "

        # Attempt 1: Try with current prompt / พยายามครั้งที่ 1
        try:
            response_text = generate_content_sync(
                model=case_model,
                contents=full_prompt,
                temperature=case_temperature,
                max_output_tokens=2048,
                stop_sequences=PATIENT_STOP_SEQUENCES,
            )

            if response_text and response_text.strip():
                return sanitize_patient_output(response_text.strip())

        except ValueError as e:
            error_str = str(e)
            print(f"[DEBUG] First attempt failed: {error_str}")

            # If blocked by safety, try safer prompt / ถ้าถูกบล็อก ลองใช้ prompt ที่ปลอดภัยกว่า
            if "blocked" in error_str.lower() or "safety" in error_str.lower():
                print("[DEBUG] Trying safer prompt...")

                # Attempt 2: Retry with safer context / พยายามครั้งที่ 2
                safer_prompt = f"{SAFER_CONTEXT}\n\n{case_prompt}{STRICT_OUTPUT_RULES}\n\nCase Context:\n{case_context}\n\n"
                for message in chat_history:
                    if message["role"] == "user":
                        safer_prompt += f"Doctor: {message['content']}\n"
                    else:
                        safer_prompt += f"Patient: {message['content']}\n"
                safer_prompt += "Patient: "

                try:
                    response_text = generate_content_sync(
                        model=case_model,
                        contents=safer_prompt,
                        temperature=case_temperature,
                        max_output_tokens=2048,
                        stop_sequences=PATIENT_STOP_SEQUENCES,
                    )

                    if response_text and response_text.strip():
                        return sanitize_patient_output(response_text.strip())

                except ValueError:
                    print("[DEBUG] Second attempt also failed. Returning fallback.")
                    return FALLBACK_RESPONSE_SAFETY

            # Store error for debugging / เก็บ error สำหรับ debug
            st.session_state.last_model_error = error_str

            # Check if it's a model name issue / ตรวจสอบว่าเป็นปัญหาชื่อโมเดลหรือไม่
            if "not found" in error_str.lower() or "invalid" in error_str.lower():
                return f"โมเดล AI ไม่พร้อมใช้งาน: {case_model} อาจไม่รองรับ กรุณาตรวจสอบการตั้งค่า"

            return FALLBACK_RESPONSE_GENERIC

        # If we get here with empty response / ถ้ามาถึงตรงนี้พร้อมคำตอบว่าง
        return FALLBACK_RESPONSE_EMPTY

    except Exception as e:
        error_msg = str(e)
        st.session_state.last_model_error = error_msg
        print(f"[ERROR] get_ai_response_sync failed: {error_msg}")
        return FALLBACK_RESPONSE_GENERIC


def get_ai_response_threaded(chat_history, case_context):
    """
    Wrapper function to run AI response in a background thread.
    ฟังก์ชันห่อหุ้มเพื่อเรียก AI ในเธรดพื้นหลัง

    Uses synchronous generation (no asyncio) to avoid event loop issues.
    ใช้การสร้างแบบ synchronous (ไม่ใช้ asyncio) เพื่อหลีกเลี่ยงปัญหา event loop

    This allows the timer fragment to continue updating while waiting for AI response.
    ทำให้ตัวจับเวลายังคงอัพเดทต่อได้ขณะรอคำตอบจาก AI
    """
    try:
        # Call sync function directly - no asyncio event loop needed
        # เรียกฟังก์ชัน sync โดยตรง - ไม่ต้องใช้ asyncio event loop
        return get_ai_response_sync(chat_history, case_context)
    except Exception as e:
        error_msg = str(e)
        st.session_state.last_model_error = error_msg
        print(f"[ERROR] get_ai_response_threaded failed: {error_msg}")
        return FALLBACK_RESPONSE_GENERIC


# ============================================================================
# SESSION STATE INITIALIZATION / เริ่มต้น Session State
# ============================================================================

def initialize_session_state():
    """
    Initialize all session state variables
    เริ่มต้นตัวแปร session state ทั้งหมด
    """
    if 'page' not in st.session_state:
        st.session_state.page = 'login'

    if 'user_name' not in st.session_state:
        st.session_state.user_name = ''

    if 'user_email' not in st.session_state:
        st.session_state.user_email = ''

    if 'selected_case' not in st.session_state:
        st.session_state.selected_case = None

    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    if 'start_time' not in st.session_state:
        st.session_state.start_time = None

    if 'timer_active' not in st.session_state:
        st.session_state.timer_active = False

    if 'ai_responding' not in st.session_state:
        st.session_state.ai_responding = False

    if 'ai_response_ready' not in st.session_state:
        st.session_state.ai_response_ready = False

    if 'pending_ai_response' not in st.session_state:
        st.session_state.pending_ai_response = None

    # Feedback form state / สถานะฟอร์ม feedback
    if 'provisional_dx' not in st.session_state:
        st.session_state.provisional_dx = ''

    if 'ddx1' not in st.session_state:
        st.session_state.ddx1 = ''

    if 'ddx2' not in st.session_state:
        st.session_state.ddx2 = ''

    if 'ddx3' not in st.session_state:
        st.session_state.ddx3 = ''

    if 'formulation_framework' not in st.session_state:
        st.session_state.formulation_framework = PSYCHODYNAMIC_FRAMEWORKS[0]

    if 'formulation_text' not in st.session_state:
        st.session_state.formulation_text = ''

    if 'feedback_result' not in st.session_state:
        st.session_state.feedback_result = None

    if 'feedback_generated' not in st.session_state:
        st.session_state.feedback_generated = False

    if 'feedback_error' not in st.session_state:
        st.session_state.feedback_error = None

    if 'feedback_session_id' not in st.session_state:
        st.session_state.feedback_session_id = None

    # Voice mode session state / สถานะ session สำหรับ voice mode
    if 'voice_input_key' not in st.session_state:
        st.session_state.voice_input_key = 0

    if 'pending_ai_audio' not in st.session_state:
        st.session_state.pending_ai_audio = None

    # Base64 encoded TTS audio for HTML playback
    if 'tts_audio_b64_by_msg' not in st.session_state:
        st.session_state.tts_audio_b64_by_msg = {}

    # One-shot autoplay flag: set when new audio arrives, cleared after render
    if 'autoplay_tts_msg_idx' not in st.session_state:
        st.session_state.autoplay_tts_msg_idx = None

    if 'voice_transcribing' not in st.session_state:
        st.session_state.voice_transcribing = False

    if 'voice_generating_tts' not in st.session_state:
        st.session_state.voice_generating_tts = False

    if 'formulation_mic_key' not in st.session_state:
        st.session_state.formulation_mic_key = 0

    if 'last_processed_audio_key' not in st.session_state:
        st.session_state.last_processed_audio_key = -1

    if 'last_processed_audio_id' not in st.session_state:
        st.session_state.last_processed_audio_id = None

    # STT retry: track attempted vs successfully processed
    if 'last_attempted_audio_id' not in st.session_state:
        st.session_state.last_attempted_audio_id = None

    if 'stt_error_audio_id' not in st.session_state:
        st.session_state.stt_error_audio_id = None

    if 'stt_error_message' not in st.session_state:
        st.session_state.stt_error_message = None

    # Formulation STT retry
    if 'last_attempted_formulation_id' not in st.session_state:
        st.session_state.last_attempted_formulation_id = None

    if 'formulation_stt_error' not in st.session_state:
        st.session_state.formulation_stt_error = None

    if 'voice_send_pending' not in st.session_state:
        st.session_state.voice_send_pending = False

    if 'voice_clear_pending' not in st.session_state:
        st.session_state.voice_clear_pending = False

    if 'voice_message_to_send' not in st.session_state:
        st.session_state.voice_message_to_send = None

    # Widget key rotation pattern for voice textbox
    # Rotating the key creates a fresh widget, allowing programmatic value updates
    if 'voice_widget_version' not in st.session_state:
        st.session_state.voice_widget_version = 0

    if 'voice_text_pending' not in st.session_state:
        st.session_state.voice_text_pending = None

    if 'voice_text_value' not in st.session_state:
        st.session_state.voice_text_value = ""

    # Widget key rotation pattern for formulation textbox
    if 'formulation_widget_version' not in st.session_state:
        st.session_state.formulation_widget_version = 0

    if 'formulation_text_pending' not in st.session_state:
        st.session_state.formulation_text_pending = None

    if 'formulation_text_value' not in st.session_state:
        st.session_state.formulation_text_value = ""

    if 'formulation_clear_pending' not in st.session_state:
        st.session_state.formulation_clear_pending = False


# ============================================================================
# PAGE 1: HOMEPAGE / LOGIN
# ============================================================================

def page_login():
    """
    Homepage with login form
    หน้าแรก - ใส่ชื่อและอีเมล
    """
    # Center the title with medical styling / จัดหัวข้อกลางพร้อมสไตล์ทางการแพทย์
    st.markdown("""
        <div style='text-align: center; padding: 30px 0;'>
            <h1 style='color: #2c5f7d; font-size: 3.5em; font-weight: 700; margin: 0;'>
                🏥 DigiHealth AI Patient
            </h1>
        </div>
    """, unsafe_allow_html=True)

    # Add some spacing / เพิ่มช่องว่าง
    st.markdown("<br>", unsafe_allow_html=True)

    # Create centered form / สร้างฟอร์มกลางหน้า
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # Input fields / ช่องกรอกข้อมูล
        name = st.text_input("👤 Name / ชื่อ", value=st.session_state.user_name,
                            placeholder="Enter your full name")
        email = st.text_input("📧 Email / อีเมล", value=st.session_state.user_email,
                             placeholder="your.email@example.com")

        st.markdown("<br>", unsafe_allow_html=True)

        # Next button / ปุ่มถัดไป
        if st.button("Next ➡️", use_container_width=True, type="primary"):
            if name and email:
                # Save to session state / บันทึกใน session state
                st.session_state.user_name = name
                st.session_state.user_email = email
                st.session_state.page = 'case_selection'
                st.rerun()
            else:
                st.error("Please fill in both fields / กรุณากรอกข้อมูลให้ครบ")


# ============================================================================
# PAGE 2: CASE SELECTION / HELPER FUNCTIONS
# ============================================================================

def render_case_card(case, col, index):
    """
    Render a case selection card with styling and button
    แสดงการ์ดเลือกเคสพร้อมสไตล์และปุ่ม

    Args:
        case: Case configuration object / ข้อมูลเคส
        col: Streamlit column object / คอลัมน์สำหรับแสดงผล
        index: Unique index for the case / ดัชนีไม่ซ้ำสำหรับเคส
    """
    with col:
        # Determine card style based on active status / กำหนดสไตล์ตามสถานะ
        if case.IS_ACTIVE:
            card_bg = "white"
            border_color = "#4a90a4"
            shadow = "0 4px 12px rgba(74, 144, 164, 0.15)"
            title_color = "#2c5f7d"
            text_color = "#5a7a8a"
            status_text = f"✅ {case.CASE_TITLE}"
        else:
            card_bg = "#f8f9fa"
            border_color = "#e0e0e0"
            shadow = "0 2px 8px rgba(0, 0, 0, 0.08)"
            title_color = "#9e9e9e"
            text_color = "#9e9e9e"
            status_text = "🔒 Coming Soon"

        st.markdown(f"""
            <div style='background: {card_bg}; padding: 25px; border-radius: 16px;
                        border: 2px solid {border_color}; box-shadow: {shadow};'>
                <h3 style='color: {title_color}; margin-top: 0;'>📋 {case.CASE_NAME}</h3>
                <p style='color: {text_color}; margin-bottom: 0; font-size: 0.9em;'>{status_text}</p>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button(
            f"Select {case.CASE_NAME}" if case.IS_ACTIVE else f"{case.CASE_NAME} (Coming Soon)",
            use_container_width=True,
            type="primary" if case.IS_ACTIVE else "secondary",
            disabled=not case.IS_ACTIVE,
            key=f"case_button_{case.CASE_NAME}_{index}"
        ):
            st.session_state.selected_case = case.CASE_NAME
            st.session_state.page = 'pre_brief'
            st.rerun()


def page_case_selection():
    """
    Case selection page
    หน้าเลือกเคสผู้ป่วย
    """
    st.title("Select a Case / เลือกเคสผู้ป่วย")
    st.markdown(f"Welcome, {st.session_state.user_name}!")

    st.markdown("<br>", unsafe_allow_html=True)

    # Create rows of case cards / สร้างแถวของการ์ดเคส
    # First row: Cases A, B, C
    col1, col2, col3 = st.columns(3)

    for idx, col in enumerate([col1, col2, col3]):
        if idx < len(ALL_CASES):
            render_case_card(ALL_CASES[idx], col, idx)

    st.markdown("<br>", unsafe_allow_html=True)

    # Second row: Cases D, E, F
    col4, col5, col6 = st.columns(3)

    for idx, col in enumerate([col4, col5, col6]):
        case_idx = idx + 3
        if case_idx < len(ALL_CASES):
            render_case_card(ALL_CASES[case_idx], col, case_idx)

    # Back button / ปุ่มย้อนกลับ
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("⬅️ Back to Login"):
        st.session_state.page = 'login'
        st.rerun()


# ============================================================================
# PAGE 3: PRE-BRIEF / CASE INFORMATION
# ============================================================================

def page_pre_brief():
    """
    Pre-brief page with case information
    หน้าแสดงข้อมูลเคสก่อนเริ่มฝึกซ้อม
    """
    # Load selected case configuration / โหลดการตั้งค่าเคสที่เลือก
    selected_case_name = st.session_state.get('selected_case', 'Case A')
    case_config = get_case_by_name(selected_case_name)

    if case_config is None:
        st.error(f"Case '{selected_case_name}' not found. Redirecting...")
        st.session_state.page = 'case_selection'
        st.rerun()
        return

    st.title(f"Case Information / ข้อมูลเคส - {case_config.CASE_NAME}")

    # Display case information from configuration / แสดงข้อมูลเคสจากการตั้งค่า
    st.info(case_config.CASE_INFORMATION)

    # Store case configuration in session state ONLY if not already set or if case changed
    # บันทึกการตั้งค่าเคสใน session state เฉพาะครั้งแรกหรือเมื่อเปลี่ยนเคส
    if ('case_context' not in st.session_state or
        st.session_state.get('current_case_name') != case_config.CASE_NAME):
        st.session_state.case_context = case_config.CASE_INFORMATION
        st.session_state.case_system_prompt = case_config.SYSTEM_PROMPT
        st.session_state.case_model = case_config.MODEL_NAME
        st.session_state.case_temperature = case_config.TEMPERATURE
        st.session_state.current_case_name = case_config.CASE_NAME

    st.markdown("<br>", unsafe_allow_html=True)

    # Mode selection / เลือกโหมด
    st.subheader("Select Interview Mode / เลือกโหมดการสัมภาษณ์")

    import streamlit as st

    sa = st.secrets.get("gcp_service_account", None)
    st.write("DEBUG voice:")
    st.write("has gcp_service_account:", sa is not None)
    st.write("type:", type(sa).__name__)
    if isinstance(sa, dict):
    st.write("keys:", list(sa.keys()))
    elif isinstance(sa, str):
    st.write("first 50 chars:", sa[:50])

    # Initialize selected mode in session state / เริ่มต้นโหมดที่เลือกใน session state
    if 'selected_mode' not in st.session_state:
        st.session_state.selected_mode = 'text'

    # Callback functions for mode selection / ฟังก์ชันสำหรับเลือกโหมด
    def select_text_mode():
        """Select text mode / เลือกโหมดข้อความ"""
        st.session_state.selected_mode = 'text'

    def select_voice_mode():
        """Select voice mode / เลือกโหมดเสียง"""
        st.session_state.selected_mode = 'voice'

    # Create 2 columns for mode buttons / สร้าง 2 คอลัมน์สำหรับปุ่มโหมด
    col1, col2 = st.columns(2)

    # Text Mode card button / ปุ่มโหมดข้อความแบบการ์ด
    with col1:
        # Apply conditional CSS class based on selection
        css_class = "mode-card-button-selected" if st.session_state.selected_mode == 'text' else "mode-card-button"

        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
        st.button(
            "💬\n\nText Mode",
            key="btn_text_mode",
            use_container_width=True,
            on_click=select_text_mode
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # Voice Mode card button / ปุ่มโหมดเสียงแบบการ์ด
    with col2:
        # Apply conditional CSS class based on selection
        css_class = "mode-card-button-selected" if st.session_state.selected_mode == 'voice' else "mode-card-button"

        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
        st.button(
            "🎤\n\nVoice Mode",
            key="btn_voice_mode",
            use_container_width=True,
            on_click=select_voice_mode
        )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Show info about selected mode / แสดงข้อมูลเกี่ยวกับโหมดที่เลือก
    if st.session_state.selected_mode == 'voice':
        # Check voice service availability / ตรวจสอบความพร้อมของบริการเสียง
        stt_available, tts_available = is_voice_service_available()
        if stt_available:
            st.success("🎤 **Voice Mode selected.** คุณสามารถพูดกับผู้ป่วย AI ได้โดยตรง ระบบจะถอดเสียงและแปลงคำตอบเป็นเสียง Click 'Start Case' when you're ready to begin the interview.")
            if not tts_available:
                st.warning("⚠️ Text-to-Speech ไม่พร้อมใช้งาน คำตอบจะแสดงเป็นข้อความเท่านั้น")
        else:
            st.warning("⚠️ **Voice Mode** is not available. Speech-to-Text API is not configured. Please check your Google Cloud setup or use Text Mode.")

        # Optional debug widget (only shown if debug.voice_status is true in secrets)
        # Debug widget ทางเลือก (แสดงเฉพาะเมื่อ debug.voice_status เป็น true ใน secrets)
        try:
            show_voice_debug = st.secrets.get("debug", {}).get("voice_status", False)
        except Exception:
            show_voice_debug = False

        if show_voice_debug:
            with st.expander("🔧 Voice Service Debug Info (for troubleshooting)"):
                status = get_voice_service_status(include_debug=True)
                debug_info = status.get("debug", {})

                st.markdown("**Service Status:**")
                st.write(f"- STT Available: {'✅' if status['stt_available'] else '❌'}")
                st.write(f"- TTS Available: {'✅' if status['tts_available'] else '❌'}")

                st.markdown("**Credential Status:**")
                st.write(f"- Has gcp_service_account: {'✅' if debug_info.get('has_gcp_service_account') else '❌'}")
                st.write(f"- Format type: `{debug_info.get('gcp_service_account_type', 'unknown')}`")
                st.write(f"- Has private_key: {'✅' if debug_info.get('has_private_key') else '❌'}")
                st.write(f"- Has client_email: {'✅' if debug_info.get('has_client_email') else '❌'}")

                if debug_info.get("project_id_hint"):
                    st.write(f"- Project ID hint: `{debug_info['project_id_hint']}`")

                if debug_info.get("error"):
                    st.error(f"Error: {debug_info['error']}")

                st.caption("Check app logs for more details. Look for lines starting with [VOICE]")
    else:
        st.success("✅ **Text Mode selected.** You will type your questions and the AI patient will respond in text. Click 'Start Case' when you're ready to begin the interview.")

    st.markdown("<br>", unsafe_allow_html=True)

    # Callback function for Start Case button / ฟังก์ชันสำหรับปุ่มเริ่มเคส
    def start_case_callback():
        """Callback to start the case interview / เริ่มการสัมภาษณ์"""
        st.session_state.page = 'chat'
        st.session_state.start_time = datetime.now()
        st.session_state.timer_active = True

    # Start Case button / ปุ่มเริ่มเคส
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Disable only if voice mode is selected AND STT is not available
        # ปิดการใช้งานเฉพาะเมื่อเลือก voice mode และ STT ไม่พร้อมใช้งาน
        stt_avail, _ = is_voice_service_available()
        start_disabled = (st.session_state.selected_mode == 'voice' and not stt_avail)
        st.button(
            "▶️ Start Case",
            use_container_width=True,
            type="primary",
            disabled=start_disabled,
            on_click=start_case_callback
        )

    # Back button / ปุ่มย้อนกลับ
    st.markdown("<br>", unsafe_allow_html=True)
    st.button(
        "⬅️ Back to Case Selection",
        on_click=lambda: st.session_state.update({'page': 'case_selection'})
    )


# ============================================================================
# PAGE 4: CHAT INTERFACE / SIMULATION
# ============================================================================

def format_time(seconds):
    """
    Format seconds to MM:SS
    แปลงวินาทีเป็นรูปแบบ นาที:วินาที
    """
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"




def page_chat():
    """
    Main chat interface with timer and end button at bottom
    หน้าสนทนากับ AI พร้อมตัวจับเวลาและปุ่มจบด้านล่าง
    """
    # ========================================================================
    # INJECT CSS FOR LIGHT MODE ENFORCEMENT / บังคับโหมดสว่าง
    # ========================================================================

    st.markdown("""
        <style>
        /* Force Light Mode Overrides - Prevent dark mode flash */
        :root {
            --primary-color: #4a90a4;
            --background-color: #f8fbff;
            --secondary-background-color: #e8f4f8;
            --text-color: #2c3e50;
            --font: sans-serif;
        }

        /* Force background on the main app container to prevent dark mode leak */
        .stApp {
            background: linear-gradient(135deg, #f8fbff 0%, #e8f4f8 100%) !important;
            color: #2c3e50 !important;
        }

        /* Ensure all text is dark (to be visible on light background) */
        p, h1, h2, h3, h4, h5, h6, span, div {
            color: #2c3e50 !important;
        }

        /* Fix specific components that might revert to dark mode */
        .stMarkdown, .stButton, .stSpinner {
            color-scheme: light !important;
        }

        /* Ensure spinner background stays light */
        .stSpinner > div {
            background-color: transparent !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # ========================================================================
    # TITLE SECTION / ส่วนหัวเรื่อง
    # ========================================================================

    st.title("Interview Simulation / การฝึกซ้อมสัมภาษณ์")

    # ========================================================================
    # AI RESPONSE PROCESSING - Must be BEFORE fragment to prevent infinite rerun
    # การประมวลผลคำตอบจาก AI - ต้องอยู่ก่อน fragment เพื่อป้องกันการรีรันไม่รู้จบ
    # ========================================================================
    # Check if AI response is ready and process it immediately
    # ตรวจสอบว่า AI ตอบเสร็จแล้วและประมวลผลทันที
    if st.session_state.ai_response_ready and st.session_state.pending_ai_response:
        # Sanitize and append AI response to history / ทำความสะอาดและเพิ่มคำตอบ AI ในประวัติ
        # Double-layer protection: sanitize again before saving to chat history
        # การป้องกันสองชั้น: ทำความสะอาดอีกครั้งก่อนบันทึกในประวัติแชท
        sanitized_response = sanitize_patient_output(st.session_state.pending_ai_response)
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": sanitized_response
        })

        # Store TTS audio by message index for persistence across reruns
        # เก็บ TTS audio ตาม index ข้อความเพื่อคงอยู่ระหว่าง reruns
        if st.session_state.pending_ai_audio:
            import base64
            msg_index = len(st.session_state.chat_history) - 1

            # Store base64 encoded for HTML playback
            audio_b64 = base64.b64encode(st.session_state.pending_ai_audio).decode('utf-8')
            st.session_state.tts_audio_b64_by_msg[msg_index] = audio_b64

            # Set one-shot autoplay flag
            st.session_state.autoplay_tts_msg_idx = msg_index

            st.session_state.pending_ai_audio = None

        # Reset flags BEFORE rerun / รีเซ็ตสถานะก่อนรีรัน
        st.session_state.ai_responding = False
        st.session_state.ai_response_ready = False
        st.session_state.pending_ai_response = None
        # Now trigger rerun to show the response / รีรันเพื่อแสดงคำตอบ
        st.rerun()

    # ========================================================================
    # STABLE POLLING FRAGMENT - Check for AI response completion
    # Fragment แบบเสถียรสำหรับตรวจสอบ - ตรวจสอบการเสร็จสิ้นของ AI
    # ========================================================================
    # CRITICAL: This fragment is placed AFTER response processing
    # สำคัญ: Fragment นี้วางไว้หลังการประมวลผลคำตอบ
    @st.fragment(run_every=0.5)
    def polling_fragment():
        """
        Hidden polling fragment that checks if AI response is ready
        Fragment ที่ซ่อนไว้สำหรับตรวจสอบว่า AI ตอบเสร็จหรือยัง
        """
        # Only trigger rerun if AI is responding and response is ready
        # รีรันเฉพาะเมื่อ AI กำลังตอบและคำตอบพร้อมแล้ว
        if st.session_state.ai_responding and st.session_state.ai_response_ready:
            st.rerun()
        # If not ready, this fragment just re-runs itself silently
        # ถ้ายังไม่พร้อม fragment นี้จะรันตัวเองเงียบๆ

    # Call the polling fragment / เรียกใช้ polling fragment
    polling_fragment()

    # ========================================================================
    # CHAT HISTORY / ประวัติการสนทนา
    # ========================================================================

    # Display chat history in natural flow / แสดงประวัติการสนทนาแบบธรรมชาติ
    if len(st.session_state.chat_history) == 0:
        st.info("👋 Start the conversation by greeting the patient.")

    current_mode = st.session_state.get('selected_mode', 'text')

    for idx, message in enumerate(st.session_state.chat_history):
        if message["role"] == "user":
            # Doctor's message (right side) with HTML escaping / ข้อความของแพทย์ (ขวา) พร้อม escape HTML
            st.markdown(render_doctor_bubble(message['content']), unsafe_allow_html=True)
        else:
            # AI Patient's message (left side) / ข้อความของผู้ป่วย AI (ซ้าย)
            # Check if we have TTS audio for this message (voice mode only)
            has_audio = (current_mode == 'voice' and idx in st.session_state.tts_audio_b64_by_msg)

            if has_audio:
                # Message with speaker icon for replay using components.html for JavaScript
                audio_b64 = st.session_state.tts_audio_b64_by_msg[idx]
                msg_content = message['content']
                # Calculate height: base 50px + ~18px per 100 chars
                estimated_lines = max(1, len(msg_content) // 100 + 1)
                iframe_height = min(50 + estimated_lines * 18, 250)

                # Use helper with HTML escaping
                components.html(
                    render_patient_bubble_with_audio(msg_content, audio_b64, iframe_height),
                    height=iframe_height
                )
            else:
                # Standard message without audio (with HTML escaping)
                st.markdown(render_patient_bubble(message['content']), unsafe_allow_html=True)

    # ========================================================================
    # LOADING INDICATOR (Stable placeholder) / ตัวบอกสถานะโหลด (ตัวยึดตำแหน่งเสถียร)
    # ========================================================================

    # Create a permanent placeholder for the loading indicator
    # This ensures the element tree structure never changes, preventing Fragment crashes.
    # สร้างตัวยึดตำแหน่งถาวรสำหรับตัวบอกสถานะโหลด
    # เพื่อให้โครงสร้างต้นไม้ของ element ไม่เปลี่ยนแปลง ป้องกันการ crash ของ Fragment
    thinking_placeholder = st.empty()

    if st.session_state.ai_responding:
        # Render the content inside the placeholder / แสดงเนื้อหาภายในตัวยึดตำแหน่ง
        with thinking_placeholder.container():
            st.markdown("""
                <div style='text-align: center; padding: 20px;'>
                    <div style='display: inline-block; padding: 15px 30px; background: linear-gradient(135deg, #e3f2fd 0%, #f0f8fb 100%);
                                border-radius: 12px; border: 2px solid #4a90a4;'>
                        <span style='color: #2c5f7d; font-weight: 600; font-size: 1.1em;'>
                            🤔 Patient is thinking and responding...
                        </span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        # IMPORTANT: Clear it but keep the placeholder alive / เคลียร์แต่เก็บตัวยึดตำแหน่งไว้
        thinking_placeholder.empty()

    # ========================================================================
    # DYNAMIC SPACER (Stable DOM for fragment) / ส่วนเว้นระยะแบบไดนามิก (DOM เสถียรสำหรับ fragment)
    # ========================================================================

    # Calculate spacer height: 30vh if empty, 0px if chatting
    # คำนวณความสูงช่องว่าง: 30vh ถ้าว่าง, 0px ถ้ามีข้อความ
    spacer_height = "30vh" if len(st.session_state.chat_history) == 0 else "0px"

    # Always render this div so the DOM structure remains stable for the fragment
    # แสดง div นี้เสมอเพื่อให้โครงสร้าง DOM คงที่สำหรับ fragment
    st.markdown(
        f'<div style="height: {spacer_height}; transition: height 0.3s ease;"></div>',
        unsafe_allow_html=True
    )

    # ========================================================================
    # FOOTER: TIMER & END BUTTON (BOTTOM) / ส่วนท้าย: ตัวจับเวลาและปุ่มจบ (ด้านล่าง)
    # ========================================================================

    st.divider()

    # Display timer and end button at bottom / แสดงตัวจับเวลาและปุ่มจบด้านล่าง
    col1, col2 = st.columns([1, 1])

    with col1:
        # Calculate remaining time once in Python / คำนวณเวลาที่เหลือครั้งเดียวใน Python
        if st.session_state.timer_active and st.session_state.start_time:
            elapsed = datetime.now() - st.session_state.start_time
            total_seconds = TIMER_DURATION_MINUTES * 60
            remaining_seconds = total_seconds - int(elapsed.total_seconds())

            if remaining_seconds <= 0:
                remaining_seconds = 0
                st.session_state.timer_active = False
        else:
            remaining_seconds = 0

        # Determine color based on time remaining / กำหนดสีตามเวลาที่เหลือ
        if remaining_seconds > 300:  # More than 5 minutes
            timer_color = "#4a90a4"  # Medical blue
        elif remaining_seconds > 60:  # More than 1 minute
            timer_color = "#e67e22"  # Warm orange for caution
        else:
            timer_color = "#c0392b"  # Deep red for urgency

        # Display timer div that will be updated by JavaScript / แสดง div ตัวจับเวลาที่จะอัพเดทด้วย JavaScript
        st.markdown(
            f'<div id="countdown-timer" style="text-align: center; color: {timer_color}; font-weight: 600; font-size: 2em;">⏱️ {format_time(remaining_seconds)}</div>',
            unsafe_allow_html=True
        )

        # Inject JavaScript to update timer every second / แทรก JavaScript เพื่ออัพเดทตัวจับเวลาทุกวินาที
        components.html(
            f"""
            <script>
            (function() {{
                let remainingSeconds = {remaining_seconds};

                function formatTime(seconds) {{
                    const minutes = Math.floor(seconds / 60);
                    const secs = seconds % 60;
                    return minutes.toString().padStart(2, '0') + ':' + secs.toString().padStart(2, '0');
                }}

                function updateTimer() {{
                    const timerElement = window.parent.document.getElementById('countdown-timer');
                    if (timerElement && remainingSeconds > 0) {{
                        remainingSeconds--;

                        // Update color based on time remaining
                        let color = '#4a90a4';  // Medical blue
                        if (remainingSeconds <= 60) {{
                            color = '#c0392b';  // Deep red for urgency
                        }} else if (remainingSeconds <= 300) {{
                            color = '#e67e22';  // Warm orange for caution
                        }}

                        timerElement.style.color = color;
                        timerElement.innerHTML = '⏱️ ' + formatTime(remainingSeconds);
                    }} else if (remainingSeconds <= 0) {{
                        clearInterval(timerInterval);
                    }}
                }}

                const timerInterval = setInterval(updateTimer, 1000);
            }})();
            </script>
            """,
            height=0
        )

    with col2:
        if st.button("🛑 End Case", type="secondary", use_container_width=True, key="end_case_button"):
            st.session_state.timer_active = False
            # Auto-save to both sheets / บันทึกอัตโนมัติไปทั้งสองชีท
            with st.spinner("Saving session data... / กำลังบันทึกข้อมูล..."):
                current_mode = st.session_state.get('selected_mode', 'text')
                # Save to main log sheet / บันทึกไปชีทบันทึกหลัก
                save_session_to_sheet(
                    st.session_state.user_name,
                    st.session_state.user_email,
                    st.session_state.chat_history,
                    st.session_state.get('current_case_name', None),
                    mode=current_mode
                )
                # Save to latest session sheet / บันทึกไปชีทเซสชันล่าสุด
                save_latest_session(
                    st.session_state.user_name,
                    st.session_state.user_email,
                    st.session_state.chat_history,
                    st.session_state.get('current_case_name', None),
                    mode=current_mode
                )
            st.session_state.page = 'end'
            st.rerun()

    # ========================================================================
    # CHAT INPUT - Mode-aware input / ช่องป้อนข้อมูลตามโหมด
    # ========================================================================

    # Get current mode / ดึงโหมดปัจจุบัน
    current_mode = st.session_state.get('selected_mode', 'text')

    # Check if timer is still active / ตรวจสอบว่าตัวจับเวลายังทำงานอยู่หรือไม่
    if st.session_state.timer_active:

        if current_mode == 'voice':
            # ================================================================
            # VOICE MODE INPUT / ช่องป้อนข้อมูลโหมดเสียง
            # ================================================================

            # Build dynamic widget key using version for key rotation
            # สร้าง widget key แบบ dynamic โดยใช้ version สำหรับการหมุนเวียน key
            voice_widget_key = f"voice_text_widget_{st.session_state.voice_widget_version}"

            # Handle pending text BEFORE widget is rendered (key rotation pattern)
            # จัดการ pending text ก่อน widget ถูกสร้าง (รูปแบบหมุนเวียน key)
            if st.session_state.voice_text_pending is not None:
                st.session_state[voice_widget_key] = st.session_state.voice_text_pending
                st.session_state.voice_text_value = st.session_state.voice_text_pending
                st.session_state.voice_text_pending = None

            # Handle pending clear BEFORE widget is rendered
            if st.session_state.voice_clear_pending:
                st.session_state[voice_widget_key] = ""
                st.session_state.voice_text_value = ""
                st.session_state.voice_clear_pending = False

            if st.session_state.voice_send_pending and st.session_state.voice_message_to_send:
                # Clear the textbox (message already captured in voice_message_to_send)
                st.session_state[voice_widget_key] = ""
                st.session_state.voice_text_value = ""
                st.session_state.voice_send_pending = False

                # Start AI response thread
                def ai_response_callback_voice():
                    """Background thread function to get AI response with TTS"""
                    response = get_ai_response_threaded(
                        st.session_state.chat_history,
                        st.session_state.case_context
                    )
                    st.session_state.pending_ai_response = response

                    # Generate TTS for voice mode
                    if response and get_tts_auto_play():
                        st.session_state.voice_generating_tts = True
                        audio_bytes_tts, tts_error = synthesize_speech(response)
                        st.session_state.voice_generating_tts = False
                        if audio_bytes_tts:
                            st.session_state.pending_ai_audio = audio_bytes_tts
                        else:
                            print(f"[WARNING] TTS failed: {tts_error}")

                    st.session_state.ai_response_ready = True

                thread = threading.Thread(target=ai_response_callback_voice, daemon=True)
                add_script_run_ctx(thread)
                thread.start()
                st.session_state.voice_message_to_send = None

            st.markdown("---")
            st.markdown("### 🎤 Voice Input / ป้อนข้อมูลด้วยเสียง")

            # Show status indicators / แสดงสถานะ
            if st.session_state.voice_transcribing:
                st.info(f"🎙️ {STATUS_TRANSCRIBING}")
            elif st.session_state.voice_generating_tts:
                st.info(f"🔊 {STATUS_GENERATING_TTS}")

            # Voice input section / ส่วนป้อนเสียง
            voice_col1, voice_col2 = st.columns([1, 2])

            with voice_col1:
                # Microphone input with unique key
                # ช่อง mic input พร้อม key ที่ไม่ซ้ำ
                current_audio_key = st.session_state.voice_input_key
                audio_data = st.audio_input(
                    "🎤 Record your message",
                    key=f"voice_input_{current_audio_key}",
                    disabled=st.session_state.ai_responding
                )

                # Process recorded audio (only if not already successfully transcribed)
                # ประมวลผลเสียงที่บันทึก (เฉพาะเมื่อยังไม่ได้ถอดเสียงสำเร็จ)
                if audio_data is not None and not st.session_state.ai_responding:
                    # Read audio bytes using getvalue() if available, else fallback to seek+read
                    # อ่าน bytes ของเสียงด้วย getvalue() ถ้ามี ไม่งั้น fallback เป็น seek+read
                    import hashlib
                    try:
                        audio_bytes = audio_data.getvalue()
                    except AttributeError:
                        try:
                            audio_data.seek(0)
                        except Exception:
                            pass
                        audio_bytes = audio_data.read()

                    # Create a hash of audio content to detect new recordings
                    if audio_bytes and len(audio_bytes) > 100:
                        audio_hash = hashlib.md5(audio_bytes[:1000]).hexdigest()[:8]
                        audio_id = f"{current_audio_key}_{audio_hash}"

                        # Check if this audio was already successfully processed
                        # Only skip if successfully transcribed before (not just attempted)
                        if st.session_state.get('last_processed_audio_id') != audio_id:
                            # Check if we already attempted this audio and it failed
                            # Allow retry if error occurred
                            already_attempted = (st.session_state.get('last_attempted_audio_id') == audio_id)
                            has_error = (st.session_state.get('stt_error_audio_id') == audio_id)

                            if not already_attempted or has_error:
                                # Mark as attempted
                                st.session_state.last_attempted_audio_id = audio_id
                                st.session_state.last_processed_audio_key = current_audio_key

                                # Clear previous error for this audio
                                st.session_state.stt_error_audio_id = None
                                st.session_state.stt_error_message = None

                                # Transcribe audio / ถอดเสียง
                                with st.spinner(STATUS_TRANSCRIBING):
                                    st.session_state.voice_transcribing = True
                                    transcript, error = transcribe_audio(audio_bytes)
                                    st.session_state.voice_transcribing = False

                                if transcript:
                                    # Mark as successfully processed
                                    st.session_state.last_processed_audio_id = audio_id
                                    # Widget key rotation: set pending, bump version, rerun
                                    st.session_state.voice_text_pending = transcript
                                    st.session_state.voice_widget_version += 1
                                    # Reset mic to allow next recording / รีเซ็ตไมค์เพื่อบันทึกรอบถัดไป
                                    st.session_state.voice_input_key += 1
                                    st.rerun()
                                elif error:
                                    # Store error for retry UI
                                    st.session_state.stt_error_audio_id = audio_id
                                    st.session_state.stt_error_message = error

            with voice_col2:
                # Show STT error with retry button if applicable
                if st.session_state.stt_error_message:
                    st.error(f"❌ {st.session_state.stt_error_message}")
                    if st.button("🔄 Retry STT", key="retry_stt_btn"):
                        # Clear the error to allow retry
                        st.session_state.stt_error_audio_id = None
                        st.session_state.stt_error_message = None
                        st.session_state.last_attempted_audio_id = None
                        st.rerun()

                # Editable text area for transcribed text (using dynamic key for rotation)
                # ช่อง text area สำหรับแก้ไขข้อความที่ถอดเสียง (ใช้ key แบบ dynamic)
                st.text_area(
                    "📝 ข้อความ (แก้ไขได้):",
                    height=100,
                    placeholder="บันทึกเสียงหรือพิมพ์ข้อความที่นี่...",
                    disabled=st.session_state.ai_responding,
                    key=voice_widget_key
                )

                # Sync widget -> value immediately after rendering
                st.session_state.voice_text_value = st.session_state.get(voice_widget_key, "")

                # Get current text from value key for button logic
                current_text = st.session_state.voice_text_value.strip()

                # Send button / ปุ่มส่ง
                send_col1, send_col2 = st.columns([1, 1])
                with send_col1:
                    send_disabled = st.session_state.ai_responding or (current_text == "")
                    if st.button(
                        "📤 Send / ส่ง",
                        use_container_width=True,
                        type="primary",
                        disabled=send_disabled,
                        key="voice_send_btn"
                    ):
                        if current_text:
                            # 1. Append user message to history
                            st.session_state.chat_history.append({
                                "role": "user",
                                "content": current_text
                            })

                            # 2. Set flags for pending actions (will be processed on next rerun BEFORE widget)
                            st.session_state.voice_send_pending = True
                            st.session_state.voice_message_to_send = current_text
                            st.session_state.ai_responding = True

                            # 3. Rotate widget key to clear textbox on next render
                            # หมุนเวียน widget key เพื่อล้าง textbox ในการ render ถัดไป
                            st.session_state.voice_text_pending = ""
                            st.session_state.voice_widget_version += 1
                            st.session_state.voice_input_key += 1
                            st.session_state.last_processed_audio_key = -1
                            st.session_state.last_processed_audio_id = None

                            # 4. Rerun to process pending send and show loading state
                            st.rerun()

                with send_col2:
                    if st.button(
                        "🗑️ Clear / ล้าง",
                        use_container_width=True,
                        disabled=st.session_state.ai_responding,
                        key="voice_clear_btn"
                    ):
                        # Rotate widget key to clear textbox on next render
                        # หมุนเวียน widget key เพื่อล้าง textbox ในการ render ถัดไป
                        st.session_state.voice_text_pending = ""
                        st.session_state.voice_widget_version += 1
                        st.session_state.voice_input_key += 1
                        st.session_state.last_processed_audio_key = -1
                        st.session_state.last_processed_audio_id = None
                        st.rerun()

            # One-shot TTS autoplay via hidden audio element
            # เล่น TTS อัตโนมัติครั้งเดียวผ่าน hidden audio element
            if st.session_state.autoplay_tts_msg_idx is not None:
                msg_idx = st.session_state.autoplay_tts_msg_idx
                if msg_idx in st.session_state.tts_audio_b64_by_msg:
                    audio_b64 = st.session_state.tts_audio_b64_by_msg[msg_idx]
                    # Render hidden autoplay audio via components.html
                    # This plays once and doesn't show any UI
                    components.html(
                        f'<audio autoplay style="display:none"><source src="data:audio/mpeg;base64,{audio_b64}" type="audio/mpeg"></audio>',
                        height=0
                    )
                # Clear the flag immediately after rendering to prevent replay on rerun
                st.session_state.autoplay_tts_msg_idx = None

        else:
            # ================================================================
            # TEXT MODE INPUT / ช่องป้อนข้อมูลโหมดข้อความ
            # ================================================================
            # Use st.chat_input for a pinned chat bar at the bottom
            # ใช้ st.chat_input เพื่อสร้างแถบแชทที่ปักหมุดไว้ด้านล่าง
            if prompt := st.chat_input(
                placeholder="Type your question or response here..." if not st.session_state.ai_responding else "Please wait for patient's response...",
                key="chat_input"
            ):
                # 1. Append user message to history immediately
                # เพิ่มข้อความผู้ใช้ในประวัติทันที
                st.session_state.chat_history.append({
                    "role": "user",
                    "content": prompt
                })

                # 2. Set AI responding flag / ตั้งสถานะว่า AI กำลังตอบ
                st.session_state.ai_responding = True

                # 3. Define callback function for thread / กำหนดฟังก์ชันสำหรับเธรด
                def ai_response_callback():
                    """Background thread function to get AI response"""
                    response = get_ai_response_threaded(
                        st.session_state.chat_history,
                        st.session_state.case_context
                    )
                    # Store response and set ready flag / เก็บคำตอบและตั้งสถานะพร้อม
                    st.session_state.pending_ai_response = response
                    st.session_state.ai_response_ready = True

                # 4. Start background thread with Streamlit context / เริ่มเธรดพื้นหลังพร้อม Streamlit context
                thread = threading.Thread(target=ai_response_callback, daemon=True)
                add_script_run_ctx(thread)  # Attach Streamlit context to thread
                thread.start()

                # 5. Rerun to show loading state / รีรันเพื่อแสดงสถานะโหลด
                st.rerun()
    else:
        # Timer ended, disable input / หมดเวลาแล้ว ปิดการพิมพ์
        st.warning("⏰ Time's up! Please end the case.")

    # ========================================================================
    # AUTO-FOCUS CHAT INPUT / โฟกัสช่องแชทอัตโนมัติ
    # ========================================================================

    # Inject JavaScript to auto-focus the chat input after each rerun
    # เพิ่ม JavaScript เพื่อโฟกัสช่องแชทหลังจากทุกครั้งที่รีรัน
    components.html(
        """
        <script>
        // Function to focus chat input / ฟังก์ชันโฟกัสช่องแชท
        function focusChatInput() {
            try {
                // Access parent document (Streamlit iframe container)
                const parentDoc = window.parent.document;

                // Find the chat input textarea
                // Try multiple selectors to ensure compatibility
                let chatInput = parentDoc.querySelector('textarea[aria-label="Chat input"]') ||
                               parentDoc.querySelector('textarea[data-testid="stChatInput"]') ||
                               parentDoc.querySelector('textarea[placeholder*="Type your question"]') ||
                               parentDoc.querySelector('.stChatInput textarea');

                if (chatInput) {
                    // Focus the input with a slight delay to ensure DOM is ready
                    setTimeout(() => {
                        chatInput.focus();
                        // Also scroll to bottom if needed
                        chatInput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }, 100);
                }
            } catch (error) {
                console.log('Could not auto-focus chat input:', error);
            }
        }

        // Execute on load / รันเมื่อโหลด
        if (document.readyState === 'complete') {
            focusChatInput();
        } else {
            window.addEventListener('load', focusChatInput);
        }

        // Also try after a short delay to catch late renders
        setTimeout(focusChatInput, 200);
        setTimeout(focusChatInput, 500);
        </script>
        """,
        height=0,  # Hidden component / ซ่อนคอมโพเนนต์
    )


# ============================================================================
# PAGE 5: END / SAVE DATA
# ============================================================================

def display_feedback_results(feedback_result: dict):
    """
    Display feedback results in formatted sections.
    แสดงผล feedback ในรูปแบบที่จัดหมวดหมู่
    """
    if not feedback_result:
        st.warning("ไม่พบข้อมูล feedback")
        return

    # Check if fallback / ตรวจสอบว่าเป็น fallback หรือไม่
    if feedback_result.get("is_fallback"):
        st.warning("⚠️ ไม่สามารถสร้าง feedback จาก AI ได้ แสดงผลลัพธ์เริ่มต้น")

    # Show model used / แสดงโมเดลที่ใช้
    if feedback_result.get("model_used"):
        st.caption(f"🤖 Model: {feedback_result.get('model_used')}")

    # Check for parse failure / ตรวจสอบการ parse ล้มเหลว
    if feedback_result.get("parse_failed"):
        st.warning("⚠️ ไม่สามารถ parse JSON ได้ แสดงผลลัพธ์ดิบ")
        with st.expander("Raw Response"):
            st.text(feedback_result.get("raw_text", ""))

    st.markdown("---")

    # ========== SECTION 1: Interview Feedback ==========
    st.subheader("📋 1) Feedback: การสัมภาษณ์ (Interview)")

    interview_fb = feedback_result.get("interview_feedback", {})

    # Strengths / จุดแข็ง
    strengths = interview_fb.get("strengths", [])
    if strengths:
        st.markdown("**✅ จุดแข็ง (Strengths):**")
        for s in strengths:
            st.markdown(f"- {s}")

    # Missed opportunities / สิ่งที่พลาดไป
    missed = interview_fb.get("missed_opportunities", [])
    if missed:
        st.markdown("**⚠️ สิ่งที่พลาดไป (Missed Opportunities):**")
        for m in missed:
            st.markdown(f"- {m}")

    # Suggested questions / คำถามที่ควรถาม
    suggestions = interview_fb.get("suggested_questions", [])
    if suggestions:
        st.markdown("**💡 คำถามที่ควรถามเพิ่ม (Suggested Questions):**")
        for sq in suggestions:
            st.markdown(f"- {sq}")

    # Risk assessment notes / หมายเหตุการประเมินความเสี่ยง
    risk_notes = interview_fb.get("risk_assessment_notes", "")
    if risk_notes:
        st.markdown(f"**🚨 ความคิดเห็นเรื่อง Risk Assessment:**\n\n{risk_notes}")

    # Overall comment / ความคิดเห็นโดยรวม
    overall_interview = interview_fb.get("overall_comment", "")
    if overall_interview:
        st.info(f"**สรุปภาพรวมการสัมภาษณ์:**\n\n{overall_interview}")

    st.markdown("---")

    # ========== SECTION 2: Clinical Feedback ==========
    st.subheader("🩺 2) Feedback: Dx/DDx/Psychodynamic (Clinical Reasoning)")

    clinical_fb = feedback_result.get("clinical_feedback", {})

    # Provisional Dx comment / ความคิดเห็นต่อ Provisional Dx
    prov_dx_comment = clinical_fb.get("provisional_dx_comment", "")
    if prov_dx_comment:
        st.markdown(f"**📌 Provisional Diagnosis:**\n\n{prov_dx_comment}")

    # DDx comments / ความคิดเห็นต่อ DDx
    ddx_comment = clinical_fb.get("ddx_comment", {})
    if ddx_comment:
        st.markdown("**📋 Differential Diagnosis:**")
        for key, value in ddx_comment.items():
            if value:
                st.markdown(f"- **{key.upper()}:** {value}")

    # Psychodynamic formulation comment / ความคิดเห็นต่อ Psychodynamic
    psycho_comment = clinical_fb.get("psychodynamic_formulation_comment", "")
    if psycho_comment:
        st.markdown(f"**🧠 Psychodynamic Formulation:**\n\n{psycho_comment}")

    # Overall clinical comment / ความคิดเห็นโดยรวม clinical
    overall_clinical = clinical_fb.get("overall_comment", "")
    if overall_clinical:
        st.info(f"**สรุปภาพรวม Clinical Reasoning:**\n\n{overall_clinical}")


def page_end():
    """
    End page - display session results, feedback form, and AI feedback.
    หน้าจบการฝึกซ้อม - แสดงผล, ฟอร์มตอบคำถาม, และ AI feedback
    """
    # Inject CSS for styled expander headers
    # ใส่ CSS สำหรับ expander headers ที่ดูเป็นปุ่มกดได้
    st.markdown("""
        <style>
        /* Make expander headers look clickable */
        div[data-testid="stExpander"] details summary {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border: 2px solid #dee2e6;
            border-radius: 8px;
            padding: 12px 16px;
            font-weight: 600;
            color: #2c5f7d;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        div[data-testid="stExpander"] details summary:hover {
            background: linear-gradient(135deg, #e9ecef 0%, #dee2e6 100%);
            border-color: #4a90a4;
            box-shadow: 0 2px 8px rgba(74, 144, 164, 0.2);
        }
        div[data-testid="stExpander"] details[open] summary {
            background: linear-gradient(135deg, #4a90a4 0%, #5ba3b8 100%);
            color: white;
            border-color: #4a90a4;
        }
        div[data-testid="stExpander"] details {
            border: none;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("Session Complete / เสร็จสิ้นการฝึกซ้อม")

    # Show summary / แสดงสรุป
    st.success(f"✅ Interview completed by {st.session_state.user_name}")
    st.success("💾 Your session data has been automatically saved!")

    # Calculate session duration / คำนวณระยะเวลา
    duration_seconds = 0
    if st.session_state.start_time:
        duration = datetime.now() - st.session_state.start_time
        duration_seconds = int(duration.total_seconds())

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.session_state.start_time:
            minutes = duration_seconds // 60
            seconds = duration_seconds % 60
            st.info(f"⏱️ **Session Duration**\n\n{minutes} min {seconds} sec")

    with col2:
        # Total message count / จำนวนข้อความทั้งหมด
        total_msgs = len(st.session_state.chat_history)
        st.info(f"💬 **Total Messages**\n\n{total_msgs} messages")

    with col3:
        # Doctor turns / จำนวนคำถามของแพทย์
        doctor_turns = sum(1 for m in st.session_state.chat_history if m.get("role") == "user")
        st.info(f"👨‍⚕️ **Doctor Turns**\n\n{doctor_turns} questions")

    with col4:
        # Patient turns / จำนวนคำตอบของผู้ป่วย
        patient_turns = sum(1 for m in st.session_state.chat_history if m.get("role") == "assistant")
        st.info(f"🧑 **Patient Turns**\n\n{patient_turns} responses")

    st.markdown("<br>", unsafe_allow_html=True)

    # Display interview transcript / แสดงบันทึกการสัมภาษณ์
    with st.expander("📋 Interview Transcript / บันทึกการสัมภาษณ์", expanded=False):
        # Get latest session data from sheet / ดึงข้อมูลเซสชันล่าสุดจากชีท
        with st.spinner("Loading interview data... / กำลังโหลดข้อมูล..."):
            session_data = get_latest_session_data()

        if session_data:
            # Display in a nice format with HTML escaping / แสดงในรูปแบบที่สวยงามพร้อม escape HTML
            for idx, row in enumerate(session_data):
                speaker = row.get('Speaker', '')
                message = row.get('Message', '')
                safe_message = escape_html(message)

                if speaker == 'user':
                    # Doctor's message / ข้อความของแพทย์
                    st.markdown(f"""
                        <div style='background: linear-gradient(135deg, #4a90a4 0%, #5ba3b8 100%);
                                    color: white; padding: 12px 16px; border-radius: 12px;
                                    margin: 8px 0;'>
                            <b>👨‍⚕️ You:</b><br>{safe_message}
                        </div>
                    """, unsafe_allow_html=True)
                elif speaker == 'assistant':
                    # Patient's message / ข้อความของผู้ป่วย
                    st.markdown(f"""
                        <div style='background-color: white; padding: 12px 16px;
                                    border-radius: 12px; margin: 8px 0;
                                    border: 2px solid #e3f2fd;'>
                            <b style='color: #2c5f7d;'>🧑 Patient:</b><br>{safe_message}
                        </div>
                    """, unsafe_allow_html=True)

            st.success(f"✅ Displayed {len(session_data)} interview exchanges")
        else:
            st.warning("No interview data found. The session may not have been saved properly.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ========================================================================
    # FEEDBACK FORM SECTION / ส่วนฟอร์มตอบคำถาม
    # ========================================================================

    st.subheader("📝 Post-Case Evaluation / แบบประเมินหลังเคส")

    # If feedback already generated, show results / ถ้าสร้าง feedback แล้ว แสดงผล
    if st.session_state.feedback_generated and st.session_state.feedback_result:
        st.success("✅ Feedback generated successfully! / สร้าง feedback สำเร็จแล้ว!")

        # Show submitted answers / แสดงคำตอบที่ส่งไปแล้ว
        with st.expander("📋 Your Submitted Answers / คำตอบที่ส่งไป", expanded=False):
            st.markdown(f"**Provisional Diagnosis:** {st.session_state.provisional_dx}")
            st.markdown(f"**DDx 1:** {st.session_state.ddx1}")
            st.markdown(f"**DDx 2:** {st.session_state.ddx2}")
            st.markdown(f"**DDx 3:** {st.session_state.ddx3}")
            st.markdown(f"**Framework:** {st.session_state.formulation_framework}")
            st.markdown(f"**Formulation:**\n\n{st.session_state.formulation_text}")

        # Display feedback / แสดง feedback
        st.markdown("---")
        st.subheader("🎓 AI Feedback / ผลการประเมินจาก AI")
        display_feedback_results(st.session_state.feedback_result)

        st.markdown("---")

        # Re-evaluate button / ปุ่มประเมินใหม่
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Re-evaluate / ประเมินใหม่", use_container_width=True):
                st.session_state.feedback_generated = False
                st.session_state.feedback_result = None
                st.session_state.feedback_session_id = None
                st.rerun()

    else:
        # Show the form (refactored without st.form for audio_input compatibility)
        # แสดงฟอร์ม (ปรับโครงสร้างโดยไม่ใช้ st.form เพื่อให้ audio_input ทำงานได้)
        st.markdown("""
        กรุณาตอบคำถามด้านล่างเพื่อรับ feedback จาก AI:

        Please answer the questions below to receive AI feedback:
        """)

        # Build dynamic widget key for formulation textbox (key rotation pattern)
        formulation_widget_key = f"formulation_text_widget_{st.session_state.formulation_widget_version}"

        # Handle pending text BEFORE widget is rendered
        if st.session_state.formulation_text_pending is not None:
            st.session_state[formulation_widget_key] = st.session_state.formulation_text_pending
            st.session_state.formulation_text_value = st.session_state.formulation_text_pending
            st.session_state.formulation_text = st.session_state.formulation_text_pending
            st.session_state.formulation_text_pending = None

        # Handle pending clear
        if st.session_state.formulation_clear_pending:
            st.session_state[formulation_widget_key] = ""
            st.session_state.formulation_text_value = ""
            st.session_state.formulation_text = ""
            st.session_state.formulation_clear_pending = False

        # 1. Provisional Diagnosis
        st.markdown("#### 1️⃣ Provisional Diagnosis")
        provisional_dx = st.text_area(
            "ระบุการวินิจฉัยเบื้องต้นของคุณ / Enter your provisional diagnosis:",
            value=st.session_state.provisional_dx,
            height=100,
            placeholder="เช่น Major Depressive Disorder, single episode, moderate severity",
            key="form_provisional_dx"
        )
        st.session_state.provisional_dx = provisional_dx

        st.markdown("---")

        # 2. Differential Diagnosis (3 items)
        st.markdown("#### 2️⃣ Differential Diagnosis (3 ข้อ)")

        ddx1 = st.text_area(
            "DDx 1:",
            value=st.session_state.ddx1,
            height=60,
            placeholder="เช่น Adjustment Disorder with Depressed Mood",
            key="form_ddx1"
        )
        st.session_state.ddx1 = ddx1

        ddx2 = st.text_area(
            "DDx 2:",
            value=st.session_state.ddx2,
            height=60,
            placeholder="เช่น Bipolar II Disorder",
            key="form_ddx2"
        )
        st.session_state.ddx2 = ddx2

        ddx3 = st.text_area(
            "DDx 3:",
            value=st.session_state.ddx3,
            height=60,
            placeholder="เช่น Persistent Depressive Disorder (Dysthymia)",
            key="form_ddx3"
        )
        st.session_state.ddx3 = ddx3

        st.markdown("---")

        # 3. Psychodynamic Formulation
        st.markdown("#### 3️⃣ Psychodynamic Formulation")

        formulation_framework = st.selectbox(
            "เลือกทฤษฎี / Select Theory:",
            options=PSYCHODYNAMIC_FRAMEWORKS,
            index=PSYCHODYNAMIC_FRAMEWORKS.index(st.session_state.formulation_framework)
                  if st.session_state.formulation_framework in PSYCHODYNAMIC_FRAMEWORKS else 0,
            key="form_framework"
        )
        st.session_state.formulation_framework = formulation_framework

        # Dynamic placeholder based on framework
        framework_placeholders = {
            "4P (Predisposing, Precipitating, Perpetuating, Protective)":
                "Predisposing: ...\nPrecipitating: ...\nPerpetuat...\nProtective: ...",
            "Psychosexual Development (Freud)":
                "ระบุ stage ที่มี fixation และอธิบายความสัมพันธ์กับอาการปัจจุบัน...",
            "Ego Psychology":
                "อธิบาย ego functions, defense mechanisms, และ conflict...",
            "Self Psychology (Kohut)":
                "อธิบาย self-object needs, narcissistic injury, และ mirroring...",
            "Object Relations Theory":
                "อธิบาย internal objects, splitting, และ projective identification...",
            "Attachment Theory":
                "อธิบาย attachment style, early attachment experiences, และ current relationships..."
        }

        placeholder = framework_placeholders.get(formulation_framework, "อธิบาย formulation ตาม framework ที่เลือก...")

        # Formulation textbox (using key rotation for dictation support)
        formulation_text = st.text_area(
            f"Formulation ตาม {formulation_framework.split('(')[0].strip()}:",
            height=200,
            placeholder=placeholder,
            key=formulation_widget_key
        )
        # Sync widget -> session state
        st.session_state.formulation_text_value = st.session_state.get(formulation_widget_key, "")
        st.session_state.formulation_text = st.session_state.formulation_text_value

        # ================================================================
        # COMPACT VOICE DICTATION FOR FORMULATION (below formulation textbox)
        # ================================================================
        st.markdown("##### 🎤 Dictate / พูดเพิ่ม")
        mic_col1, mic_col2, mic_col3 = st.columns([2, 1, 1])

        with mic_col1:
            current_formulation_key = st.session_state.formulation_mic_key
            formulation_audio = st.audio_input(
                "Record",
                key=f"formulation_mic_{current_formulation_key}",
                label_visibility="collapsed"
            )

            # Process recorded audio
            if formulation_audio is not None:
                import hashlib
                try:
                    audio_bytes = formulation_audio.getvalue()
                except AttributeError:
                    try:
                        formulation_audio.seek(0)
                    except Exception:
                        pass
                    audio_bytes = formulation_audio.read()

                if audio_bytes and len(audio_bytes) > 100:
                    audio_hash = hashlib.md5(audio_bytes[:1000]).hexdigest()[:8]
                    formulation_audio_id = f"{current_formulation_key}_{audio_hash}"

                    # Check if already processed successfully
                    if st.session_state.get('last_processed_formulation_id') != formulation_audio_id:
                        # Check if already attempted
                        already_attempted = (st.session_state.get('last_attempted_formulation_id') == formulation_audio_id)
                        has_error = (st.session_state.get('formulation_stt_error') is not None and
                                    st.session_state.get('formulation_stt_error_id') == formulation_audio_id)

                        if not already_attempted or has_error:
                            st.session_state.last_attempted_formulation_id = formulation_audio_id
                            st.session_state.formulation_stt_error = None

                            with st.spinner(STATUS_TRANSCRIBING):
                                transcript, error = transcribe_audio(audio_bytes)

                            if transcript:
                                # Mark as successfully processed
                                st.session_state.last_processed_formulation_id = formulation_audio_id
                                # Append to existing text
                                if st.session_state.formulation_text_value:
                                    new_text = st.session_state.formulation_text_value + "\n" + transcript
                                else:
                                    new_text = transcript
                                st.session_state.formulation_text_pending = new_text
                                st.session_state.formulation_widget_version += 1
                                # Reset mic to allow next recording / รีเซ็ตไมค์เพื่อบันทึกรอบถัดไป
                                st.session_state.formulation_mic_key += 1
                                st.rerun()
                            elif error:
                                st.session_state.formulation_stt_error = error
                                st.session_state.formulation_stt_error_id = formulation_audio_id

        with mic_col2:
            if st.session_state.get('formulation_stt_error'):
                if st.button("🔄 Retry", key="retry_formulation_stt"):
                    st.session_state.formulation_stt_error = None
                    st.session_state.last_attempted_formulation_id = None
                    st.rerun()

        with mic_col3:
            if st.button("🗑️ Clear", key="clear_formulation"):
                st.session_state.formulation_text_pending = ""
                st.session_state.formulation_widget_version += 1
                st.session_state.formulation_mic_key += 1
                st.session_state.last_processed_formulation_id = None
                st.session_state.last_attempted_formulation_id = None
                st.rerun()

        # Show STT error if any
        if st.session_state.get('formulation_stt_error'):
            st.error(f"❌ {st.session_state.formulation_stt_error}")

        st.markdown("---")

        # Submit button (outside st.form, using regular button)
        submitted = st.button(
            "📤 Submit & Get Feedback",
            use_container_width=True,
            type="primary",
            key="submit_feedback_btn"
        )

        if submitted:
                # Validate required fields / ตรวจสอบฟิลด์ที่จำเป็น
                if not provisional_dx.strip():
                    st.error("⚠️ กรุณาระบุ Provisional Diagnosis")
                elif not formulation_text.strip():
                    st.error("⚠️ กรุณาระบุ Psychodynamic Formulation")
                else:
                    # Save to session state / บันทึกลง session state
                    st.session_state.provisional_dx = provisional_dx
                    st.session_state.ddx1 = ddx1
                    st.session_state.ddx2 = ddx2
                    st.session_state.ddx3 = ddx3
                    st.session_state.formulation_framework = formulation_framework
                    st.session_state.formulation_text = formulation_text

                    # Generate session ID / สร้าง session ID
                    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.session_state.feedback_session_id = session_id

                    # Prepare stats / เตรียมสถิติ
                    stats = {
                        "duration_seconds": duration_seconds,
                        "total_messages": len(st.session_state.chat_history),
                        "doctor_turns": sum(1 for m in st.session_state.chat_history if m.get("role") == "user"),
                        "patient_turns": sum(1 for m in st.session_state.chat_history if m.get("role") == "assistant"),
                    }

                    # Prepare answers / เตรียมคำตอบ
                    answers = {
                        "provisional_dx": provisional_dx,
                        "ddx1": ddx1,
                        "ddx2": ddx2,
                        "ddx3": ddx3,
                        "formulation_framework": formulation_framework,
                        "formulation_text": formulation_text,
                    }

                    # Prepare transcript text / เตรียมข้อความ transcript
                    transcript_text = format_transcript_for_display(st.session_state.chat_history)

                    # Prepare payload for feedback / เตรียม payload สำหรับ feedback
                    payload = {
                        "user": {
                            "name": st.session_state.user_name,
                            "email": st.session_state.user_email,
                        },
                        "case": st.session_state.get("current_case_name", "Unknown"),
                        "mode": st.session_state.get("selected_mode", "text"),
                        "stats": stats,
                        "transcript_text": transcript_text,
                        "transcript_messages": st.session_state.chat_history,
                        "answers": answers,
                    }

                    # Generate feedback with status indicator / สร้าง feedback พร้อมแสดงสถานะ
                    with st.status("🧠 กำลังวิเคราะห์การสัมภาษณ์และคำตอบของคุณ…", expanded=True) as status:
                        st.write("Analyzing your interview and clinical reasoning...")
                        st.write("โปรดรอสักครู่ ระบบกำลังประเมินทักษะการสัมภาษณ์และการวินิจฉัย")
                        feedback_result = generate_feedback(payload)
                        status.update(label="✅ วิเคราะห์เสร็จแล้ว / Analysis Complete", state="complete", expanded=False)

                    # Store result / เก็บผลลัพธ์
                    st.session_state.feedback_result = feedback_result
                    st.session_state.feedback_generated = True

                    # Log to Google Sheet / บันทึกลง Google Sheet
                    try:
                        credentials = get_google_credentials()
                        if credentials:
                            # Prepare session row / เตรียมแถว session
                            session_row = prepare_session_row(
                                session_id=session_id,
                                timestamp=timestamp,
                                user_name=st.session_state.user_name,
                                user_email=st.session_state.user_email,
                                case_name=st.session_state.get("current_case_name", "Unknown"),
                                selected_mode=st.session_state.get("selected_mode", "text"),
                                stats=stats,
                                answers=answers,
                                feedback_result=feedback_result,
                            )

                            # Prepare transcript rows / เตรียมแถว transcript
                            transcript_rows = prepare_transcript_rows(
                                session_id=session_id,
                                chat_history=st.session_state.chat_history,
                                timestamp=timestamp,
                                selected_mode=st.session_state.get("selected_mode", "text"),
                            )

                            # Append to sheet / เพิ่มลง sheet
                            success = append_session_to_feedback_sheet(
                                credentials=credentials,
                                session_row=session_row,
                                transcript_rows=transcript_rows,
                            )

                            if success:
                                st.success("✅ Session data saved to feedback sheet!")
                            else:
                                st.warning("⚠️ Could not save to feedback sheet (check logs)")
                        else:
                            st.warning("⚠️ Google credentials not available")
                    except Exception as e:
                        st.error(f"Error saving to sheet: {e}")

                    # Rerun to show results / rerun เพื่อแสดงผลลัพธ์
                    st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)

    # Start new session button / ปุ่มเริ่มใหม่
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Start New Session / เริ่มเซสชันใหม่", use_container_width=True, type="primary"):
            # Clear all session state / ล้าง session state ทั้งหมด
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ============================================================================
# MAIN APPLICATION / แอปพลิเคชันหลัก
# ============================================================================

def main():
    """
    Main application function - controls page flow
    ฟังก์ชันหลักของแอป - ควบคุมการเปลี่ยนหน้า
    """
    # Custom CSS for medical/psychiatric theme / CSS ธีมทางการแพทย์
    st.markdown("""
        <style>
        /* Medical/Psychiatric Theme - Soft Blue & White */
        /* ธีมทางการแพทย์ - สีฟ้าอ่อนและขาว */

        /* Main app background */
        .stApp {
            background: linear-gradient(135deg, #f8fbff 0%, #e8f4f8 100%);
        }

        /* Headers with medical blue */
        h1, h2, h3 {
            color: #2c5f7d !important;
            font-weight: 600 !important;
        }

        /* Hide header anchor links and hover effects */
        h1:hover, h2:hover, h3:hover {
            background-color: transparent !important;
        }

        /* Hide the anchor link icon */
        .stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a {
            display: none !important;
        }

        /* Remove header hover background */
        [data-testid="stMarkdownContainer"] h1:hover,
        [data-testid="stMarkdownContainer"] h2:hover,
        [data-testid="stMarkdownContainer"] h3:hover {
            background-color: transparent !important;
        }

        /* Primary buttons - Medical blue */
        .stButton>button[kind="primary"] {
            background-color: #4a90a4 !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            height: 3.5em !important;
            font-weight: 500 !important;
            box-shadow: 0 2px 8px rgba(74, 144, 164, 0.25) !important;
            transition: all 0.3s ease !important;
        }

        .stButton>button[kind="primary"]:hover {
            background-color: #3a7a8a !important;
            box-shadow: 0 4px 12px rgba(74, 144, 164, 0.35) !important;
            transform: translateY(-1px) !important;
        }

        /* Secondary buttons - Light blue */
        .stButton>button[kind="secondary"] {
            background-color: #e3f2fd !important;
            color: #2c5f7d !important;
            border: 1px solid #b3d9e8 !important;
            border-radius: 12px !important;
            height: 3.5em !important;
            font-weight: 500 !important;
            transition: all 0.3s ease !important;
        }

        .stButton>button[kind="secondary"]:hover {
            background-color: #d0e9f7 !important;
            border-color: #4a90a4 !important;
        }

        /* All other buttons */
        .stButton>button {
            border-radius: 12px !important;
            height: 3em !important;
            font-weight: 500 !important;
            transition: all 0.3s ease !important;
        }

        /* Disabled buttons */
        .stButton>button:disabled {
            background-color: #e0e0e0 !important;
            color: #9e9e9e !important;
            opacity: 0.6 !important;
        }

        /* Text inputs with medical theme */
        .stTextInput>div>div>input {
            border-radius: 12px !important;
            border: 2px solid #b3d9e8 !important;
            background-color: white !important;
            padding: 12px !important;
            transition: border-color 0.3s ease !important;
            color: #2c3e50 !important;
            caret-color: black !important; /* Text cursor color */
        }

        .stTextInput>div>div>input:focus {
            border-color: #4a90a4 !important;
            box-shadow: 0 0 0 3px rgba(74, 144, 164, 0.1) !important;
        }

        /* Text input labels */
        .stTextInput>label {
            color: #2c5f7d !important;
            font-weight: 500 !important;
        }

        /* Info boxes - Calming blue */
        .stAlert {
            border-radius: 12px !important;
            border-left: 4px solid #4a90a4 !important;
            background-color: #f0f8fb !important;
            color: #2c3e50 !important;
        }

        .stAlert p, .stAlert div, .stAlert span {
            color: #2c3e50 !important;
        }

        /* Success messages */
        .stSuccess {
            background-color: #e8f5e9 !important;
            border-left: 4px solid #66bb6a !important;
            border-radius: 12px !important;
        }

        /* Warning messages */
        .stWarning {
            background-color: #fff8e1 !important;
            border-left: 4px solid #ffa726 !important;
            border-radius: 12px !important;
        }

        /* Error messages */
        .stError {
            background-color: #ffebee !important;
            border-left: 4px solid #ef5350 !important;
            border-radius: 12px !important;
        }

        /* Divider */
        hr {
            border-color: #b3d9e8 !important;
            opacity: 0.5 !important;
        }

        /* Markdown text */
        .stMarkdown {
            color: #37474f !important;
        }

        /* Cards/Containers */
        .element-container {
            transition: all 0.3s ease !important;
        }

        /* Chat container styling */
        [data-testid="stVerticalBlock"] {
            gap: 0.5rem !important;
        }

        /* Form styling */
        .stForm {
            border: 2px solid #b3d9e8 !important;
            border-radius: 12px !important;
            padding: 1rem !important;
            background-color: white !important;
        }

        /* ============================================ */
        /* TEXT AREA STYLING / สไตล์ Text Area */
        /* ============================================ */

        /* Text area container and textarea */
        .stTextArea textarea {
            border-radius: 12px !important;
            border: 2px solid #b3d9e8 !important;
            background-color: white !important;
            padding: 12px !important;
            transition: border-color 0.3s ease !important;
            color: #2c3e50 !important;
            caret-color: #2c3e50 !important;
            font-size: 1rem !important;
        }

        .stTextArea textarea:focus {
            border-color: #4a90a4 !important;
            box-shadow: 0 0 0 3px rgba(74, 144, 164, 0.1) !important;
        }

        /* Text area labels */
        .stTextArea label {
            color: #2c5f7d !important;
            font-weight: 500 !important;
        }

        .stTextArea label p {
            color: #2c5f7d !important;
        }

        /* ============================================ */
        /* SELECTBOX STYLING / สไตล์ SelectBox */
        /* ============================================ */

        /* Selectbox container */
        .stSelectbox > div > div {
            border-radius: 12px !important;
            border: 2px solid #b3d9e8 !important;
            background-color: white !important;
            background: white !important;
        }

        /* Selectbox focus state */
        .stSelectbox > div > div:focus-within {
            border-color: #4a90a4 !important;
            box-shadow: 0 0 0 3px rgba(74, 144, 164, 0.2) !important;
        }

        .stSelectbox label {
            color: #2c5f7d !important;
            font-weight: 500 !important;
        }

        .stSelectbox label p {
            color: #2c5f7d !important;
        }

        /* Selectbox selected value text - high contrast */
        .stSelectbox [data-baseweb="select"] span,
        .stSelectbox [data-baseweb="select"] > div,
        .stSelectbox [data-baseweb="select"] div[aria-selected="true"] {
            color: #1a1a1a !important;
            font-weight: 500 !important;
        }

        /* Selectbox input/control area */
        .stSelectbox [data-baseweb="select"] > div {
            background-color: white !important;
            background: white !important;
        }

        /* Selectbox placeholder text */
        .stSelectbox [data-baseweb="select"] [data-baseweb="icon"],
        .stSelectbox [data-baseweb="select"] svg {
            color: #4a90a4 !important;
            fill: #4a90a4 !important;
        }

        /* Selectbox dropdown menu options - comprehensive fix */
        [data-baseweb="menu"],
        [data-baseweb="popover"] > div,
        [data-baseweb="popover"] [data-baseweb="menu"],
        div[data-baseweb="popover"] {
            background-color: white !important;
            background: white !important;
        }

        [data-baseweb="menu"] li,
        [data-baseweb="menu"] ul li,
        [role="listbox"] li,
        [role="option"] {
            color: #2c3e50 !important;
            background-color: white !important;
            background: white !important;
        }

        [data-baseweb="menu"] li:hover,
        [role="option"]:hover,
        [role="option"][aria-selected="true"] {
            background-color: #e3f2fd !important;
            background: #e3f2fd !important;
            color: #2c5f7d !important;
        }

        /* Selectbox listbox container */
        [role="listbox"],
        ul[role="listbox"] {
            background-color: white !important;
            background: white !important;
        }

        /* Override any dark theme popover */
        .stSelectbox div[data-baseweb="popover"] > div {
            background-color: white !important;
        }

        /* ============================================ */
        /* EXPANDER STYLING / สไตล์ Expander */
        /* ============================================ */

        /* Expander header */
        .streamlit-expanderHeader {
            background-color: #f0f8fb !important;
            border-radius: 12px !important;
            color: #2c5f7d !important;
            font-weight: 500 !important;
        }

        .streamlit-expanderHeader p {
            color: #2c5f7d !important;
        }

        /* Expander content */
        .streamlit-expanderContent {
            background-color: white !important;
            border: 1px solid #b3d9e8 !important;
            border-top: none !important;
            border-radius: 0 0 12px 12px !important;
            padding: 1rem !important;
        }

        .streamlit-expanderContent p,
        .streamlit-expanderContent span,
        .streamlit-expanderContent div {
            color: #2c3e50 !important;
        }

        /* ============================================ */
        /* FORM LABELS & TEXT / ป้ายและข้อความในฟอร์ม */
        /* ============================================ */

        /* All form labels */
        label, .stMarkdown label {
            color: #2c5f7d !important;
        }

        /* Markdown headers in forms */
        .stMarkdown h4 {
            color: #2c5f7d !important;
            font-weight: 600 !important;
        }

        /* General paragraph text */
        .stMarkdown p {
            color: #37474f !important;
        }

        /* Bold text */
        .stMarkdown strong, .stMarkdown b {
            color: #2c5f7d !important;
        }

        /* List items */
        .stMarkdown li {
            color: #37474f !important;
        }

        /* Horizontal rules in forms */
        .stMarkdown hr {
            border-color: #b3d9e8 !important;
            opacity: 0.5 !important;
        }

        /* Caption text */
        .stCaption, .stCaption p {
            color: #5a7a8a !important;
        }

        /* ============================================ */
        /* FEEDBACK RESULTS STYLING / สไตล์ผลลัพธ์ Feedback */
        /* ============================================ */

        /* Ensure all text in main content area is visible */
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] span {
            color: #37474f !important;
        }

        [data-testid="stMarkdownContainer"] strong,
        [data-testid="stMarkdownContainer"] b {
            color: #2c5f7d !important;
        }

        [data-testid="stMarkdownContainer"] h4 {
            color: #2c5f7d !important;
        }

        /* Spinner */
        .stSpinner > div {
            border-top-color: #4a90a4 !important;
        }

        /* Professional medical look */
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif !important;
        }

        /* Mode selection card-style buttons */
        .mode-card-button button {
            height: 180px !important;
            padding: 25px !important;
            border-radius: 16px !important;
            font-size: 1.1em !important;
            white-space: pre-line !important;
            background-color: white !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
            border: 2px solid #d0d0d0 !important;
            color: #6b7280 !important;
            transition: all 0.3s ease !important;
        }

        .mode-card-button button:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12) !important;
            transform: translateY(-2px) !important;
        }

        /* Selected mode card button */
        .mode-card-button-selected button {
            height: 180px !important;
            padding: 25px !important;
            border-radius: 16px !important;
            font-size: 1.1em !important;
            white-space: pre-line !important;
            background: linear-gradient(135deg, #e3f2fd 0%, #f0f8fb 100%) !important;
            box-shadow: 0 6px 20px rgba(74, 144, 164, 0.3) !important;
            border: 4px solid #4a90a4 !important;
            color: #1a4d5f !important;
            font-weight: 700 !important;
            transition: all 0.3s ease !important;
            transform: scale(1.02) !important;
        }

        .mode-card-button-selected button:hover {
            box-shadow: 0 8px 24px rgba(74, 144, 164, 0.4) !important;
            transform: scale(1.02) translateY(-2px) !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Initialize session state / เริ่มต้น session state
    initialize_session_state()

    # Route to appropriate page / นำทางไปหน้าที่เหมาะสม
    if st.session_state.page == 'login':
        page_login()
    elif st.session_state.page == 'case_selection':
        page_case_selection()
    elif st.session_state.page == 'pre_brief':
        page_pre_brief()
    elif st.session_state.page == 'chat':
        page_chat()
    elif st.session_state.page == 'end':
        page_end()


# ============================================================================
# RUN APPLICATION / รันแอปพลิเคชัน
# ============================================================================

if __name__ == "__main__":
    main()
