"""
Feedback Logger / ระบบบันทึก Feedback ลง Google Sheet
======================================================
This module handles appending session data and transcripts to Google Sheets.
Uses a separate sheet from the main session logging for feedback data.

โมดูลนี้จัดการการเพิ่มข้อมูล session และ transcripts ลง Google Sheets
ใช้ sheet แยกต่างหากจาก session logging หลักสำหรับข้อมูล feedback
"""

import json
import gspread
from datetime import datetime

from feedback_config import (
    FEEDBACK_SHEET_ID,
    FEEDBACK_SHEET_WORKSHEET_NAME,
    TRANSCRIPT_WORKSHEET_NAME,
)


# Column headers for sessions worksheet / หัวคอลัมน์สำหรับ worksheet sessions
SESSION_HEADERS = [
    "session_id",
    "timestamp",
    "user_name",
    "user_email",
    "case_name",
    "selected_mode",
    "duration_seconds",
    "total_messages",
    "doctor_turns",
    "patient_turns",
    "provisional_dx",
    "ddx1",
    "ddx2",
    "ddx3",
    "formulation_framework",
    "formulation_text",
    "feedback_interview_summary",
    "feedback_clinical_summary",
    "feedback_raw",
    "is_fallback",
]

# Column headers for transcript worksheet / หัวคอลัมน์สำหรับ worksheet transcript
TRANSCRIPT_HEADERS = [
    "session_id",
    "timestamp",
    "speaker",
    "message",
    "turn_index",
    "selected_mode",
]


def get_or_create_worksheet(spreadsheet, worksheet_name: str, headers: list):
    """
    Get existing worksheet or create new one with headers.
    Implements safe header migration - updates header row if missing columns.
    ดึง worksheet ที่มีอยู่หรือสร้างใหม่พร้อมหัวคอลัมน์
    รองรับการเพิ่ม column ใหม่อย่างปลอดภัย

    Args:
        spreadsheet: gspread Spreadsheet object
        worksheet_name: Name of the worksheet
        headers: List of column header names

    Returns:
        Tuple of (gspread Worksheet object, list of final headers)
    """
    try:
        # Try to get existing worksheet / ลองดึง worksheet ที่มีอยู่
        worksheet = spreadsheet.worksheet(worksheet_name)

        # Check if headers exist / ตรวจสอบว่ามีหัวคอลัมน์หรือไม่
        try:
            first_row = worksheet.row_values(1)
            if not first_row or first_row[0] == "":
                # Empty worksheet, add headers / worksheet ว่าง เพิ่มหัวคอลัมน์
                worksheet.update('A1', [headers])
                print(f"[INFO] Added headers to existing worksheet: {worksheet_name}")
                return worksheet, headers
            else:
                # Check if any new headers need to be added / ตรวจสอบว่าต้องเพิ่ม header ใหม่หรือไม่
                existing_headers = first_row
                missing_headers = [h for h in headers if h not in existing_headers]

                if missing_headers:
                    # Append missing headers to the end / เพิ่ม header ที่ขาดไปต่อท้าย
                    new_headers = existing_headers + missing_headers
                    worksheet.update('A1', [new_headers])
                    print(f"[INFO] Updated headers in {worksheet_name}, added: {missing_headers}")
                    return worksheet, new_headers

                return worksheet, existing_headers

        except Exception:
            # Worksheet exists but empty, add headers / worksheet มีอยู่แต่ว่าง เพิ่มหัวคอลัมน์
            worksheet.update('A1', [headers])
            return worksheet, headers

    except gspread.WorksheetNotFound:
        # Create new worksheet / สร้าง worksheet ใหม่
        print(f"[INFO] Creating new worksheet: {worksheet_name}")
        worksheet = spreadsheet.add_worksheet(
            title=worksheet_name,
            rows=1000,
            cols=len(headers)
        )
        # Add headers / เพิ่มหัวคอลัมน์
        worksheet.update('A1', [headers])
        return worksheet, headers


def truncate_text(text: str, max_length: int = 40000) -> str:
    """
    Truncate text to avoid Google Sheets cell character limit (50,000).
    ตัดข้อความเพื่อหลีกเลี่ยง limit ตัวอักษรของ cell ใน Google Sheets (50,000)

    Args:
        text: Text to truncate
        max_length: Maximum allowed length (default 40000 for safety margin)

    Returns:
        Truncated text with ellipsis if needed
    """
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 20] + "... [TRUNCATED]"


def extract_feedback_summary(feedback_result: dict, feedback_type: str) -> str:
    """
    Extract summary from feedback result for storage.
    ดึงสรุปจากผลลัพธ์ feedback เพื่อเก็บลง sheet

    Args:
        feedback_result: Full feedback dictionary
        feedback_type: "interview" or "clinical"

    Returns:
        Summary string
    """
    try:
        if feedback_type == "interview":
            fb = feedback_result.get("interview_feedback", {})
            parts = []
            if fb.get("overall_comment"):
                parts.append(f"สรุป: {fb['overall_comment']}")
            if fb.get("strengths"):
                parts.append(f"จุดแข็ง: {', '.join(fb['strengths'][:3])}")
            if fb.get("missed_opportunities"):
                parts.append(f"สิ่งที่พลาด: {', '.join(fb['missed_opportunities'][:3])}")
            return " | ".join(parts) if parts else "No summary available"

        elif feedback_type == "clinical":
            fb = feedback_result.get("clinical_feedback", {})
            parts = []
            if fb.get("overall_comment"):
                parts.append(f"สรุป: {fb['overall_comment']}")
            if fb.get("provisional_dx_comment"):
                parts.append(f"Dx: {fb['provisional_dx_comment'][:100]}")
            return " | ".join(parts) if parts else "No summary available"

        return "Unknown type"

    except Exception as e:
        return f"Error extracting summary: {e}"


def append_session_to_feedback_sheet(
    credentials,
    session_row: dict,
    transcript_rows: list = None
) -> bool:
    """
    Append session data and transcript to feedback Google Sheet.
    Implements safe header migration and row padding.
    เพิ่มข้อมูล session และ transcript ลง feedback Google Sheet
    รองรับการเพิ่ม column และการ pad row

    Args:
        credentials: Google credentials object (from get_google_credentials())
        session_row: Dictionary containing session data with keys matching SESSION_HEADERS
        transcript_rows: List of dictionaries for transcript data (optional)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Authorize and open spreadsheet / ยืนยันตัวตนและเปิด spreadsheet
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(FEEDBACK_SHEET_ID)

        # === SESSIONS WORKSHEET ===
        sessions_ws, final_session_headers = get_or_create_worksheet(
            spreadsheet,
            FEEDBACK_SHEET_WORKSHEET_NAME,
            SESSION_HEADERS
        )

        # Prepare session row data using final headers / เตรียมข้อมูลแถว session ตาม headers สุดท้าย
        row_data = []
        for header in final_session_headers:
            value = session_row.get(header, "")

            # Handle special cases / จัดการกรณีพิเศษ
            if header == "feedback_raw":
                # Convert dict to JSON string and truncate / แปลง dict เป็น JSON string และตัด
                if isinstance(value, dict):
                    value = truncate_text(json.dumps(value, ensure_ascii=False))
                else:
                    value = truncate_text(str(value))
            elif header in ["feedback_interview_summary", "feedback_clinical_summary"]:
                value = truncate_text(str(value), max_length=5000)
            elif header == "formulation_text":
                value = truncate_text(str(value), max_length=10000)
            else:
                value = str(value) if value is not None else ""

            row_data.append(value)

        # Append session row / เพิ่มแถว session
        sessions_ws.append_row(row_data, value_input_option='USER_ENTERED')
        print(f"[INFO] Appended session {session_row.get('session_id')} to sessions worksheet")

        # === TRANSCRIPT WORKSHEET ===
        if transcript_rows:
            transcript_ws, final_transcript_headers = get_or_create_worksheet(
                spreadsheet,
                TRANSCRIPT_WORKSHEET_NAME,
                TRANSCRIPT_HEADERS
            )

            # Prepare transcript rows data using final headers / เตรียมข้อมูลแถว transcript ตาม headers สุดท้าย
            rows_to_add = []
            for tr in transcript_rows:
                row = []
                for header in final_transcript_headers:
                    value = tr.get(header, "")
                    # Truncate message content / ตัดเนื้อหาข้อความ
                    if header == "message":
                        value = truncate_text(str(value), max_length=10000)
                    else:
                        value = str(value) if value is not None else ""
                    row.append(value)
                rows_to_add.append(row)

            # Batch append transcript rows / เพิ่มแถว transcript แบบ batch
            if rows_to_add:
                transcript_ws.append_rows(rows_to_add, value_input_option='USER_ENTERED')
                print(f"[INFO] Appended {len(rows_to_add)} transcript rows for session {session_row.get('session_id')}")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to append to feedback sheet: {e}")
        return False


def prepare_session_row(
    session_id: str,
    timestamp: str,
    user_name: str,
    user_email: str,
    case_name: str,
    selected_mode: str,
    stats: dict,
    answers: dict,
    feedback_result: dict
) -> dict:
    """
    Prepare session row dictionary for appending to sheet.
    เตรียม dictionary แถว session สำหรับเพิ่มลง sheet

    Args:
        session_id: Unique session identifier
        timestamp: Session timestamp
        user_name: User's name
        user_email: User's email
        case_name: Case name
        selected_mode: Selected mode (text/voice)
        stats: Session statistics dictionary
        answers: User's answers dictionary
        feedback_result: Generated feedback dictionary

    Returns:
        Dictionary with keys matching SESSION_HEADERS
    """
    return {
        "session_id": session_id,
        "timestamp": timestamp,
        "user_name": user_name,
        "user_email": user_email,
        "case_name": case_name,
        "selected_mode": selected_mode,
        "duration_seconds": stats.get("duration_seconds", 0),
        "total_messages": stats.get("total_messages", 0),
        "doctor_turns": stats.get("doctor_turns", 0),
        "patient_turns": stats.get("patient_turns", 0),
        "provisional_dx": answers.get("provisional_dx", ""),
        "ddx1": answers.get("ddx1", ""),
        "ddx2": answers.get("ddx2", ""),
        "ddx3": answers.get("ddx3", ""),
        "formulation_framework": answers.get("formulation_framework", ""),
        "formulation_text": answers.get("formulation_text", ""),
        "feedback_interview_summary": extract_feedback_summary(feedback_result, "interview"),
        "feedback_clinical_summary": extract_feedback_summary(feedback_result, "clinical"),
        "feedback_raw": feedback_result,
        "is_fallback": str(feedback_result.get("is_fallback", False)),
    }
