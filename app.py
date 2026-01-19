"""
DigiHealth AI Patient - Psychiatric Training Application
แอปพลิเคชันฝึกซ้อมการซักประวัติผู้ป่วยทางจิตเวช
"""

import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import time

# Import case configurations / นำเข้าการตั้งค่าเคส
from cases import ALL_CASES, get_case_by_name, get_active_cases, get_inactive_cases

# ============================================================================
# CONFIGURATION / การตั้งค่า
# ============================================================================
# You can easily change these values / คุณสามารถแก้ไขค่าเหล่านี้ได้ง่าย ๆ

# Gemini Model Name / ชื่อโมเดล AI
MODEL_NAME = "gemini-2.5-flash"

# System Prompt for AI Patient / คำสั่งสำหรับ AI แสดงบทบาทผู้ป่วย
SYSTEM_PROMPT = """You are a patient in a psychiatric clinic. Answer questions naturally and realistically based on the case information provided. Stay in character throughout the conversation. Respond in a conversational manner as a real patient would."""

# Timer Duration (in minutes) / ระยะเวลาจับเวลา (นาที)
TIMER_DURATION_MINUTES = 30

# Google Sheet ID for logging session data / ID ของ Google Sheet สำหรับบันทึกข้อมูล
# Get sheet ID from the URL: https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit
GOOGLE_SHEET_ID = "1motfqsOspQrVkWDtRqUxgfH_-3nDuqYGw9eXwEfQWoo"

# Google Sheet ID for latest session data (overwrites each time) / ID ของ Google Sheet สำหรับข้อมูลเซสชันล่าสุด
GOOGLE_SHEET_LATEST_ID = "1y7mhBgABMNDzRFPDmQa7kQqTE6q4h_Py02IvT2OmUM8"

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


def save_session_to_sheet(user_name, user_email, chat_history):
    """
    Append session data to existing Google Sheet
    เพิ่มข้อมูลเซสชันลงใน Google Sheet ที่มีอยู่

    Args:
        user_name: Name of the user / ชื่อผู้ใช้
        user_email: Email of the user / อีเมลผู้ใช้
        chat_history: List of chat messages / ประวัติการสนทนา
    """
    try:
        # Get credentials / รับข้อมูลรับรอง
        credentials = get_google_credentials()
        if credentials is None:
            return False

        # Connect to Google Sheets / เชื่อมต่อ Google Sheets
        gc = gspread.authorize(credentials)

        # Open the existing spreadsheet / เปิดสเปรดชีทที่มีอยู่
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.sheet1

        # Get current timestamp / รับเวลาปัจจุบัน
        session_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Check if sheet has headers, if not add them / ตรวจสอบว่ามี header หรือยัง
        existing_data = worksheet.get_all_values()
        if not existing_data or existing_data[0][0] != "Session ID":
            # Add headers if sheet is empty / เพิ่ม header ถ้าชีทว่าง
            headers = ["Session ID", "Timestamp", "User Name", "User Email", "Speaker", "Message"]
            worksheet.insert_row(headers, 1)

        # Prepare rows to append / เตรียมแถวที่จะเพิ่ม
        rows_to_add = []

        # Add session separator row / เพิ่มแถวแบ่งเซสชัน
        separator = [f"=== SESSION START: {session_id} ===", session_time, user_name, user_email, "", ""]
        rows_to_add.append(separator)

        # Add all chat messages / เพิ่มข้อความสนทนาทั้งหมด
        for message in chat_history:
            row = [
                session_id,
                session_time,
                user_name,
                user_email,
                message["role"],
                message["content"]
            ]
            rows_to_add.append(row)

        # Add session end separator / เพิ่มแถวปิดเซสชัน
        end_separator = [f"=== SESSION END: {session_id} ===", session_time, user_name, user_email, "", f"Total messages: {len(chat_history)}"]
        rows_to_add.append(end_separator)

        # Add empty row for spacing / เพิ่มแถวว่างเพื่อเว้นระยะ
        rows_to_add.append(["", "", "", "", "", ""])

        # Append all rows at once (more efficient) / เพิ่มทุกแถวพร้อมกัน (เร็วกว่า)
        worksheet.append_rows(rows_to_add)

        # Save the sheet URL in session state / บันทึก URL ใน session state
        st.session_state.sheet_url = spreadsheet.url

        return True

    except Exception as e:
        st.error(f"Error saving to Google Sheet: {e}")
        return False


def save_latest_session(user_name, user_email, chat_history):
    """
    Replace data in latest session sheet (for displaying most recent interview)
    แทนที่ข้อมูลในชีทเซสชันล่าสุด (สำหรับแสดงการสัมภาษณ์ล่าสุด)

    Args:
        user_name: Name of the user / ชื่อผู้ใช้
        user_email: Email of the user / อีเมลผู้ใช้
        chat_history: List of chat messages / ประวัติการสนทนา
    """
    try:
        # Get credentials / รับข้อมูลรับรอง
        credentials = get_google_credentials()
        if credentials is None:
            return False

        # Connect to Google Sheets / เชื่อมต่อ Google Sheets
        gc = gspread.authorize(credentials)

        # Open the latest session spreadsheet / เปิดสเปรดชีทเซสชันล่าสุด
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_LATEST_ID)
        worksheet = spreadsheet.sheet1

        # Clear all existing data / ลบข้อมูลเก่าทั้งหมด
        worksheet.clear()

        # Get current timestamp / รับเวลาปัจจุบัน
        session_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Prepare all rows including headers / เตรียมแถวทั้งหมดรวมหัวตาราง
        all_rows = []

        # Add headers / เพิ่มหัวตาราง
        headers = ["Session ID", "Timestamp", "User Name", "User Email", "Speaker", "Message"]
        all_rows.append(headers)

        # Add all chat messages / เพิ่มข้อความสนทนาทั้งหมด
        for message in chat_history:
            row = [
                session_id,
                session_time,
                user_name,
                user_email,
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
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_LATEST_ID)
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

def get_gemini_model(model_name=None):
    """
    Get Gemini model instance - initializes API and creates model
    สร้าง Gemini model พร้อมตั้งค่า API

    This function does NOT use caching to avoid SessionInfo initialization errors.
    It's designed to be called only when needed (during chat).

    Args:
        model_name: Name of the model to use (optional, defaults to MODEL_NAME)

    Returns:
        GenerativeModel instance or None if configuration fails
    """
    try:
        # Configure API with key from secrets
        # ตั้งค่า API ด้วย key จาก secrets
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key:
            st.error("GEMINI_API_KEY not found in secrets")
            return None

        genai.configure(api_key=api_key)

        # Create model instance
        # สร้าง model instance
        selected_model = model_name if model_name else MODEL_NAME
        model = genai.GenerativeModel(selected_model)
        return model

    except Exception as e:
        st.error(f"Error initializing Gemini model: {e}")
        return None


def get_ai_response(chat_history, case_context):
    """
    Get response from Gemini AI using case-specific configuration
    รับคำตอบจาก Gemini AI โดยใช้การตั้งค่าเฉพาะของเคส

    Args:
        chat_history: List of previous messages / ประวัติการสนทนา
        case_context: Case information for context / ข้อมูลเคสสำหรับบริบท
    """
    try:
        # Get case-specific model and prompt from session state / ดึงโมเดลและ prompt เฉพาะของเคส
        case_model = st.session_state.get('case_model', MODEL_NAME)
        case_prompt = st.session_state.get('case_system_prompt', SYSTEM_PROMPT)

        # Get cached model with case-specific model name / ดึงโมเดลที่แคชไว้ตามชื่อของเคส
        model = get_gemini_model(case_model)

        if model is None:
            return "AI model is not available. Please check your API configuration."

        # Build the conversation using case-specific system prompt / สร้างการสนทนาโดยใช้ prompt เฉพาะของเคส
        # Start with case-specific system prompt and case context / เริ่มด้วย prompt และข้อมูลเคสเฉพาะ
        full_prompt = f"{case_prompt}\n\nCase Context:\n{case_context}\n\n"

        # Add chat history / เพิ่มประวัติการสนทนา
        for message in chat_history:
            if message["role"] == "user":
                full_prompt += f"Doctor: {message['content']}\n"
            else:
                full_prompt += f"Patient: {message['content']}\n"

        full_prompt += "Patient: "

        # Get response / รับคำตอบ
        response = model.generate_content(full_prompt)
        return response.text

    except Exception as e:
        st.error(f"Error getting AI response: {e}")
        return "I'm sorry, I'm having trouble responding right now."


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

    if 'sheet_url' not in st.session_state:
        st.session_state.sheet_url = None


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
            <p style='color: #4a90a4; font-size: 1.3em; margin-top: 10px; font-weight: 400;'>
                Psychiatric Training Simulator
            </p>
            <p style='color: #5a7a8a; font-size: 0.95em; margin-top: 5px;'>
                Advanced Clinical Skills Development Platform
            </p>
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
# PAGE 2: CASE SELECTION
# ============================================================================

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
            case = ALL_CASES[idx]
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
                    key=f"case_button_{case.CASE_NAME}"
                ):
                    st.session_state.selected_case = case.CASE_NAME
                    st.session_state.page = 'pre_brief'
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Second row: Cases D, E, F
    col4, col5, col6 = st.columns(3)

    for idx, col in enumerate([col4, col5, col6]):
        case_idx = idx + 3
        if case_idx < len(ALL_CASES):
            case = ALL_CASES[case_idx]
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
                    key=f"case_button_{case.CASE_NAME}"
                ):
                    st.session_state.selected_case = case.CASE_NAME
                    st.session_state.page = 'pre_brief'
                    st.rerun()

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
        st.session_state.current_case_name = case_config.CASE_NAME

    st.markdown("<br>", unsafe_allow_html=True)

    # Mode selection / เลือกโหมด
    st.subheader("Select Interview Mode / เลือกโหมดการสัมภาษณ์")

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

    # Text Mode button / ปุ่มโหมดข้อความ
    with col1:
        # Determine styling based on selection / กำหนดสไตล์ตามการเลือก
        if st.session_state.selected_mode == 'text':
            card_bg = "white"
            border_color = "#4a90a4"
            shadow = "0 4px 12px rgba(74, 144, 164, 0.15)"
            title_color = "#2c5f7d"
            text_color = "#5a7a8a"
            border_width = "3px"
        else:
            card_bg = "white"
            border_color = "#d0d0d0"
            shadow = "0 2px 8px rgba(0, 0, 0, 0.08)"
            title_color = "#6b7280"
            text_color = "#9ca3af"
            border_width = "2px"

        st.markdown(f"""
            <div style='background: {card_bg}; padding: 25px; border-radius: 16px;
                        border: {border_width} solid {border_color}; box-shadow: {shadow};
                        text-align: center;'>
                <h2 style='color: {title_color}; margin: 0; font-size: 2em;'>💬</h2>
                <h3 style='color: {title_color}; margin: 10px 0;'>Text Mode</h3>
            </div>
        """, unsafe_allow_html=True)

    # Voice Mode button / ปุ่มโหมดเสียง
    with col2:
        # Voice mode is always disabled (coming soon) / โหมดเสียงยังไม่พร้อมใช้งาน
        card_bg = "#f8f9fa"
        border_color = "#e0e0e0"
        shadow = "0 2px 8px rgba(0, 0, 0, 0.08)"
        title_color = "#9e9e9e"
        text_color = "#9e9e9e"

        st.markdown(f"""
            <div style='background: {card_bg}; padding: 25px; border-radius: 16px;
                        border: 2px solid {border_color}; box-shadow: {shadow};
                        text-align: center;'>
                <h2 style='color: {title_color}; margin: 0; font-size: 2em;'>🎤</h2>
                <h3 style='color: {title_color}; margin: 10px 0;'>Voice Mode</h3>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Show info about selected mode / แสดงข้อมูลเกี่ยวกับโหมดที่เลือก
    if st.session_state.selected_mode == 'voice':
        st.info("🎤 **Voice Mode** will be available in a future update. This mode will allow you to speak naturally with the AI patient using voice recognition. Please select Text Mode to continue.")
    else:
        st.success("✅ **Text Mode selected.** You will type your questions and the AI patient will respond in text. Click 'Start Case' when you're ready to begin the interview.")

    st.markdown("<br>", unsafe_allow_html=True)

    # Callback function for Start Case button / ฟังก์ชันสำหรับปุ่มเริ่มเคส
    def start_case_callback():
        """Callback to start the case interview / เริ่มการสัมภาษณ์"""
        st.session_state.page = 'chat'
        st.session_state.start_time = datetime.now()
        st.session_state.timer_active = True

    # Callback function for Back button / ฟังก์ชันสำหรับปุ่มย้อนกลับ
    def back_to_case_selection_callback():
        """Callback to return to case selection / กลับไปหน้าเลือกเคส"""
        st.session_state.page = 'case_selection'

    # Start Case button / ปุ่มเริ่มเคส
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.button(
            "▶️ Start Case",
            use_container_width=True,
            type="primary",
            disabled=(st.session_state.selected_mode == 'voice'),
            on_click=start_case_callback
        )

    # Back button / ปุ่มย้อนกลับ
    st.markdown("<br>", unsafe_allow_html=True)
    st.button(
        "⬅️ Back to Case Selection",
        on_click=back_to_case_selection_callback
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


@st.fragment(run_every=1)
def display_timer():
    """
    Timer fragment that updates independently without reloading the page
    ส่วนแสดงตัวจับเวลาที่อัพเดทอิสระโดยไม่โหลดหน้าใหม่
    """
    # Calculate remaining time / คำนวณเวลาที่เหลือ
    if st.session_state.timer_active and st.session_state.start_time:
        elapsed = datetime.now() - st.session_state.start_time
        total_seconds = TIMER_DURATION_MINUTES * 60
        remaining_seconds = total_seconds - int(elapsed.total_seconds())

        if remaining_seconds <= 0:
            remaining_seconds = 0
            st.session_state.timer_active = False
    else:
        remaining_seconds = 0

    # Change color based on time remaining / เปลี่ยนสีตามเวลาที่เหลือ
    if remaining_seconds > 300:  # More than 5 minutes
        timer_color = "#4a90a4"  # Medical blue
    elif remaining_seconds > 60:  # More than 1 minute
        timer_color = "#e67e22"  # Warm orange for caution
    else:
        timer_color = "#c0392b"  # Deep red for urgency

    st.markdown(
        f"<h2 style='text-align: center; color: {timer_color}; font-weight: 600;'>⏱️ {format_time(remaining_seconds)}</h2>",
        unsafe_allow_html=True
    )


def page_chat():
    """
    Main chat interface with timer
    หน้าสนทนากับ AI พร้อมตัวจับเวลา
    """
    st.title("Interview Simulation / การฝึกซ้อมสัมภาษณ์")

    # ========================================================================
    # TIMER SECTION / ส่วนตัวจับเวลา
    # ========================================================================

    # Display timer using fragment (updates independently) / แสดงตัวจับเวลาด้วย fragment (อัพเดทอิสระ)
    col1, col2, col3 = st.columns([2, 1, 1])

    with col2:
        # Use the fragment timer that updates every second without reloading the page
        # ใช้ fragment timer ที่อัพเดททุกวินาทีโดยไม่โหลดหน้าใหม่
        display_timer()

    with col3:
        if st.button("🛑 End Case", type="secondary", use_container_width=True):
            st.session_state.timer_active = False
            # Auto-save to both sheets / บันทึกอัตโนมัติไปทั้งสองชีท
            with st.spinner("Saving session data... / กำลังบันทึกข้อมูล..."):
                # Save to main log sheet / บันทึกไปชีทบันทึกหลัก
                save_session_to_sheet(
                    st.session_state.user_name,
                    st.session_state.user_email,
                    st.session_state.chat_history
                )
                # Save to latest session sheet / บันทึกไปชีทเซสชันล่าสุด
                save_latest_session(
                    st.session_state.user_name,
                    st.session_state.user_email,
                    st.session_state.chat_history
                )
            st.session_state.page = 'end'
            st.rerun()

    st.divider()

    # ========================================================================
    # CHAT INTERFACE / ส่วนการสนทนา
    # ========================================================================

    # Display chat history / แสดงประวัติการสนทนา
    if len(st.session_state.chat_history) == 0:
        st.info("👋 Start the conversation by greeting the patient.")

    for message in st.session_state.chat_history:
        if message["role"] == "user":
            # Doctor's message (right side) / ข้อความของแพทย์ (ขวา)
            st.markdown(
                f"<div style='text-align: right; background: linear-gradient(135deg, #4a90a4 0%, #5ba3b8 100%); "
                f"color: white; padding: 12px 16px; border-radius: 18px 18px 4px 18px; "
                f"margin: 8px 0; box-shadow: 0 2px 4px rgba(74, 144, 164, 0.2); max-width: 80%; "
                f"margin-left: auto;'>"
                f"<b style='color: #e3f2fd;'>You:</b> {message['content']}</div>",
                unsafe_allow_html=True
            )
        else:
            # AI Patient's message (left side) / ข้อความของผู้ป่วย AI (ซ้าย)
            st.markdown(
                f"<div style='text-align: left; background-color: white; padding: 12px 16px; "
                f"border-radius: 18px 18px 18px 4px; margin: 8px 0; "
                f"border: 2px solid #e3f2fd; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08); "
                f"max-width: 80%; color: #37474f;'>"
                f"<b style='color: #2c5f7d;'>Patient:</b> {message['content']}</div>",
                unsafe_allow_html=True
            )

    # ========================================================================
    # CHAT INPUT - Using native st.chat_input / ใช้ st.chat_input แบบ native
    # ========================================================================

    # Check if timer is still active / ตรวจสอบว่าตัวจับเวลายังทำงานอยู่หรือไม่
    if st.session_state.timer_active:
        # Use st.chat_input for a pinned chat bar at the bottom
        # ใช้ st.chat_input เพื่อสร้างแถบแชทที่ปักหมุดไว้ด้านล่าง
        if prompt := st.chat_input(
            placeholder="Type your question or response here...",
            key="chat_input"
        ):
            # 1. Append user message to history immediately
            # เพิ่มข้อความผู้ใช้ในประวัติทันที
            st.session_state.chat_history.append({
                "role": "user",
                "content": prompt
            })

            # 2. IMMEDIATELY render the user's message bubble (before rerun)
            # แสดงข้อความผู้ใช้ทันที (ก่อน rerun)
            st.markdown(
                f"<div style='text-align: right; background: linear-gradient(135deg, #4a90a4 0%, #5ba3b8 100%); "
                f"color: white; padding: 12px 16px; border-radius: 18px 18px 4px 18px; "
                f"margin: 8px 0; box-shadow: 0 2px 4px rgba(74, 144, 164, 0.2); max-width: 80%; "
                f"margin-left: auto;'>"
                f"<b style='color: #e3f2fd;'>You:</b> {prompt}</div>",
                unsafe_allow_html=True
            )

            # 3. Show spinner and get AI response
            # แสดง spinner และรับคำตอบจาก AI
            with st.spinner("Patient is responding... / ผู้ป่วยกำลังตอบ..."):
                ai_response = get_ai_response(
                    st.session_state.chat_history,
                    st.session_state.case_context
                )

            # 4. Append AI response to history
            # เพิ่มคำตอบ AI ในประวัติ
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": ai_response
            })

            # 5. Rerun to refresh the full view
            # รีรันเพื่อรีเฟรชทั้งหมด
            st.rerun()
    else:
        # Timer ended, disable input / หมดเวลาแล้ว ปิดการพิมพ์
        st.warning("⏰ Time's up! Please end the case.")


# ============================================================================
# PAGE 5: END / SAVE DATA
# ============================================================================

def page_end():
    """
    End page - display session results and interview log
    หน้าจบการฝึกซ้อม - แสดงผลและบันทึกการสัมภาษณ์
    """
    st.title("Session Complete / เสร็จสิ้นการฝึกซ้อม")

    # Show summary / แสดงสรุป
    st.success(f"✅ Interview completed by {st.session_state.user_name}")
    st.success("💾 Your session data has been automatically saved!")

    # Calculate session duration / คำนวณระยะเวลา
    col1, col2 = st.columns(2)

    with col1:
        if st.session_state.start_time:
            duration = datetime.now() - st.session_state.start_time
            minutes = int(duration.total_seconds() // 60)
            seconds = int(duration.total_seconds() % 60)
            st.info(f"⏱️ **Session Duration**\n\n{minutes} minutes {seconds} seconds")

    with col2:
        # Show message count / แสดงจำนวนข้อความ
        st.info(f"💬 **Total Messages**\n\n{len(st.session_state.chat_history)} messages")

    st.markdown("<br>", unsafe_allow_html=True)

    # Display interview transcript / แสดงบันทึกการสัมภาษณ์
    st.subheader("📋 Interview Transcript / บันทึกการสัมภาษณ์")

    # Get latest session data from sheet / ดึงข้อมูลเซสชันล่าสุดจากชีท
    with st.spinner("Loading interview data... / กำลังโหลดข้อมูล..."):
        session_data = get_latest_session_data()

    if session_data:
        # Display in a nice format / แสดงในรูปแบบที่สวยงาม
        for idx, row in enumerate(session_data):
            speaker = row.get('Speaker', '')
            message = row.get('Message', '')

            if speaker == 'user':
                # Doctor's message / ข้อความของแพทย์
                st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #4a90a4 0%, #5ba3b8 100%);
                                color: white; padding: 12px 16px; border-radius: 12px;
                                margin: 8px 0;'>
                        <b>👨‍⚕️ You:</b><br>{message}
                    </div>
                """, unsafe_allow_html=True)
            elif speaker == 'assistant':
                # Patient's message / ข้อความของผู้ป่วย
                st.markdown(f"""
                    <div style='background-color: white; padding: 12px 16px;
                                border-radius: 12px; margin: 8px 0;
                                border: 2px solid #e3f2fd;'>
                        <b style='color: #2c5f7d;'>🧑 Patient:</b><br>{message}
                    </div>
                """, unsafe_allow_html=True)

        st.success(f"✅ Displayed {len(session_data)} interview exchanges")
    else:
        st.warning("No interview data found. The session may not have been saved properly.")

    st.markdown("<br><br>", unsafe_allow_html=True)

    # Start new session button / ปุ่มเริ่มใหม่
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Start New Session", use_container_width=True, type="primary"):
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
    # Page configuration / ตั้งค่าหน้าเว็บ
    st.set_page_config(
        page_title="DigiHealth AI Patient",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

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

        /* Spinner */
        .stSpinner > div {
            border-top-color: #4a90a4 !important;
        }

        /* Professional medical look */
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif !important;
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
