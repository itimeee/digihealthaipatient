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
# ตรวจสอบว่าไฟล์ cases.py อยู่ในโฟลเดอร์เดียวกัน
try:
    from cases import ALL_CASES, get_case_by_name, get_active_cases, get_inactive_cases
except ImportError:
    # Fallback if cases.py is missing (Prevent crash)
    st.error("ไม่พบไฟล์ cases.py กรุณาตรวจสอบว่ามีไฟล์นี้อยู่ในโฟลเดอร์เดียวกัน")
    ALL_CASES = []

# ============================================================================
# CONFIGURATION / การตั้งค่า
# ============================================================================

# Gemini Model Name / ชื่อโมเดล AI
MODEL_NAME = "gemini-2.0-flash" 

# System Prompt for AI Patient / คำสั่งสำหรับ AI แสดงบทบาทผู้ป่วย
SYSTEM_PROMPT = """You are a patient in a psychiatric clinic. Answer questions naturally and realistically based on the case information provided. Stay in character throughout the conversation. Respond in a conversational manner as a real patient would."""

# Timer Duration (in minutes) / ระยะเวลาจับเวลา (นาที)
TIMER_DURATION_MINUTES = 30

# Google Sheet ID for logging session data / ID ของ Google Sheet สำหรับบันทึกข้อมูล
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
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        # Load credentials from secrets
        credentials_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=scopes
        )
        return credentials
    except Exception as e:
        # Log error quietly strictly to avoid UI clutter unless necessary
        return None


def save_session_to_sheet(user_name, user_email, chat_history):
    """
    Append session data to existing Google Sheet
    เพิ่มข้อมูลเซสชันลงใน Google Sheet ที่มีอยู่
    """
    try:
        credentials = get_google_credentials()
        if credentials is None:
            return False

        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.sheet1

        session_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        existing_data = worksheet.get_all_values()
        if not existing_data or existing_data[0][0] != "Session ID":
            headers = ["Session ID", "Timestamp", "User Name", "User Email", "Speaker", "Message"]
            worksheet.insert_row(headers, 1)

        rows_to_add = []
        separator = [f"=== SESSION START: {session_id} ===", session_time, user_name, user_email, "", ""]
        rows_to_add.append(separator)

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

        end_separator = [f"=== SESSION END: {session_id} ===", session_time, user_name, user_email, "", f"Total messages: {len(chat_history)}"]
        rows_to_add.append(end_separator)
        rows_to_add.append(["", "", "", "", "", ""])

        worksheet.append_rows(rows_to_add)
        st.session_state.sheet_url = spreadsheet.url
        return True

    except Exception as e:
        st.error(f"Error saving to Google Sheet: {e}")
        return False


def save_latest_session(user_name, user_email, chat_history):
    """
    Replace data in latest session sheet
    แทนที่ข้อมูลในชีทเซสชันล่าสุด
    """
    try:
        credentials = get_google_credentials()
        if credentials is None:
            return False

        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_LATEST_ID)
        worksheet = spreadsheet.sheet1

        worksheet.clear()

        session_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        all_rows = []
        headers = ["Session ID", "Timestamp", "User Name", "User Email", "Speaker", "Message"]
        all_rows.append(headers)

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

        worksheet.update('A1', all_rows)
        return True

    except Exception as e:
        st.error(f"Error saving latest session: {e}")
        return False


def get_latest_session_data():
    """
    Get the latest session data from the sheet
    ดึงข้อมูลเซสชันล่าสุดจากชีท
    """
    try:
        credentials = get_google_credentials()
        if credentials is None:
            return []

        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_LATEST_ID)
        worksheet = spreadsheet.sheet1
        data = worksheet.get_all_records()
        return data

    except Exception as e:
        st.error(f"Error reading latest session data: {e}")
        return []


# ============================================================================
# GEMINI AI SETUP / ตั้งค่า Gemini AI
# ============================================================================

@st.cache_resource
def get_gemini_model(model_name=None):
    """
    Initialize and cache Gemini model
    เริ่มต้นและแคช Gemini model
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        selected_model = model_name if model_name else MODEL_NAME
        model = genai.GenerativeModel(selected_model)
        return model
    except Exception as e:
        st.error(f"Error initializing Gemini: {e}")
        return None


def get_ai_response(chat_history, case_context):
    """
    Get response from Gemini AI using case-specific configuration
    รับคำตอบจาก Gemini AI
    """
    try:
        case_model = st.session_state.get('case_model', MODEL_NAME)
        case_prompt = st.session_state.get('case_system_prompt', SYSTEM_PROMPT)
        model = get_gemini_model(case_model)

        if model is None:
            return "AI model is not available. Please check your API configuration."

        full_prompt = f"{case_prompt}\n\nCase Context:\n{case_context}\n\n"

        for message in chat_history:
            if message["role"] == "user":
                full_prompt += f"Doctor: {message['content']}\n"
            else:
                full_prompt += f"Patient: {message['content']}\n"

        full_prompt += "Patient: "

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
    # Flag to help with page transition smoothness
    if 'just_entered_chat' not in st.session_state:
        st.session_state.just_entered_chat = False


# ============================================================================
# PAGE 1: HOMEPAGE / LOGIN
# ============================================================================

def page_login():
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

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        name = st.text_input("👤 Name / ชื่อ", value=st.session_state.user_name,
                            placeholder="Enter your full name")
        email = st.text_input("📧 Email / อีเมล", value=st.session_state.user_email,
                             placeholder="your.email@example.com")

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("Next ➡️", use_container_width=True, type="primary"):
            if name and email:
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
    st.title("Select a Case / เลือกเคสผู้ป่วย")
    st.markdown(f"Welcome, {st.session_state.user_name}!")
    st.markdown("<br>", unsafe_allow_html=True)

    # Helper function to create case cards
    def create_case_card(case, col):
        with col:
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

    # Layout cases in rows of 3
    if ALL_CASES:
        rows = [ALL_CASES[i:i + 3] for i in range(0, len(ALL_CASES), 3)]
        for row_cases in rows:
            cols = st.columns(3)
            for idx, case in enumerate(row_cases):
                create_case_card(case, cols[idx])
            st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.warning("No cases loaded.")

    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("⬅️ Back to Login"):
        st.session_state.page = 'login'
        st.rerun()


# ============================================================================
# PAGE 3: PRE-BRIEF / CASE INFORMATION
# ============================================================================

def page_pre_brief():
    selected_case_name = st.session_state.get('selected_case', 'Case A')
    case_config = get_case_by_name(selected_case_name)

    if case_config is None:
        st.error(f"Case '{selected_case_name}' not found. Redirecting...")
        st.session_state.page = 'case_selection'
        st.rerun()
        return

    st.title(f"Case Information / ข้อมูลเคส - {case_config.CASE_NAME}")
    st.info(case_config.CASE_INFORMATION)

    st.session_state.case_context = case_config.CASE_INFORMATION
    st.session_state.case_system_prompt = case_config.SYSTEM_PROMPT
    st.session_state.case_model = case_config.MODEL_NAME

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Select Interview Mode / เลือกโหมดการสัมภาษณ์")

    if 'selected_mode' not in st.session_state:
        st.session_state.selected_mode = 'Text Mode'

    mode = st.radio(
        "Choose your preferred mode:",
        options=[
            'Text 💬 **Text Mode** - Type your questions and responses',
            'Voice 🎤 **Voice Mode** - Speak with the AI patient (Coming Soon)'
        ],
        index=0,
        horizontal=False,
        key='mode_selector'
    )
    st.session_state.selected_mode = mode

    st.markdown("<br>", unsafe_allow_html=True)

    if 'Voice Mode' in mode:
        st.info("🎤 **Voice Mode** will be available in a future update. Please select Text Mode to continue.")
    else:
        st.success("✅ **Text Mode selected.** Click 'Start Case' when you're ready.")

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Added key to prevent widget ID conflicts
        if st.button("▶️ Start Case", use_container_width=True, type="primary",
                    disabled=('Voice Mode' in st.session_state.selected_mode),
                    key="start_case_btn"):
            
            # Reset chat related states
            st.session_state.chat_history = []
            st.session_state.waiting_for_ai = False
            
            # Set transition flag to prevent freezing
            st.session_state.just_entered_chat = True
            
            st.session_state.page = 'chat'
            st.session_state.start_time = datetime.now()
            st.session_state.timer_active = True
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⬅️ Back to Case Selection"):
        st.session_state.page = 'case_selection'
        st.rerun()


# ============================================================================
# PAGE 4: CHAT INTERFACE / SIMULATION
# ============================================================================

def format_time(seconds):
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"

def page_chat():
    st.title("Interview Simulation / การฝึกซ้อมสัมภาษณ์")

    # ========================================================================
    # TIMER SECTION
    # ========================================================================
    if st.session_state.timer_active and st.session_state.start_time:
        elapsed = datetime.now() - st.session_state.start_time
        total_seconds = TIMER_DURATION_MINUTES * 60
        remaining_seconds = total_seconds - int(elapsed.total_seconds())
        if remaining_seconds <= 0:
            remaining_seconds = 0
            st.session_state.timer_active = False
    else:
        remaining_seconds = 0

    col1, col2, col3 = st.columns([2, 1, 1])
    with col2:
        if remaining_seconds > 300:
            timer_color = "#4a90a4"
        elif remaining_seconds > 60:
            timer_color = "#e67e22"
        else:
            timer_color = "#c0392b"

        st.markdown(
            f"<h2 style='text-align: center; color: {timer_color}; font-weight: 600;'>⏱️ {format_time(remaining_seconds)}</h2>",
            unsafe_allow_html=True
        )

    with col3:
        if st.button("🛑 End Case", type="secondary", use_container_width=True):
            st.session_state.timer_active = False
            with st.spinner("Saving session data..."):
                save_session_to_sheet(
                    st.session_state.user_name,
                    st.session_state.user_email,
                    st.session_state.chat_history
                )
                save_latest_session(
                    st.session_state.user_name,
                    st.session_state.user_email,
                    st.session_state.chat_history
                )
            st.session_state.page = 'end'
            st.rerun()

    st.divider()

    # ========================================================================
    # CHAT HISTORY
    # ========================================================================
    chat_container = st.container(height=400)
    with chat_container:
        if len(st.session_state.chat_history) == 0:
            st.info("👋 Start the conversation by greeting the patient.")

        for message in st.session_state.chat_history:
            if message["role"] == "user":
                st.markdown(
                    f"<div style='text-align: right; background: linear-gradient(135deg, #4a90a4 0%, #5ba3b8 100%); "
                    f"color: white; padding: 12px 16px; border-radius: 18px 18px 4px 18px; "
                    f"margin: 8px 0; box-shadow: 0 2px 4px rgba(74, 144, 164, 0.2); max-width: 80%; "
                    f"margin-left: auto;'>"
                    f"<b style='color: #e3f2fd;'>You:</b> {message['content']}</div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"<div style='text-align: left; background-color: white; padding: 12px 16px; "
                    f"border-radius: 18px 18px 18px 4px; margin: 8px 0; "
                    f"border: 2px solid #e3f2fd; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08); "
                    f"max-width: 80%; color: #37474f;'>"
                    f"<b style='color: #2c5f7d;'>Patient:</b> {message['content']}</div>",
                    unsafe_allow_html=True
                )

    # ========================================================================
    # INPUT AREA
    # ========================================================================
    st.markdown("<br>", unsafe_allow_html=True)
    is_waiting = st.session_state.get('waiting_for_ai', False)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Your message / ข้อความของคุณ:",
            placeholder="Type here..." if not is_waiting else "Waiting for patient...",
            label_visibility="collapsed",
            key="chat_input",
            disabled=is_waiting
        )

        # JS to auto-focus (Keep it simple)
        st.markdown("""
            <script>
            setTimeout(function() {
                const inputs = window.parent.document.querySelectorAll('input[type="text"]');
                if (inputs.length > 0) { inputs[inputs.length - 1].focus(); }
            }, 100);
            </script>
        """, unsafe_allow_html=True)

        submit_button = st.form_submit_button(
            "Send 📤" if not is_waiting else "⏳ Waiting...",
            use_container_width=True,
            disabled=is_waiting
        )

    # Process user input
    if submit_button and user_input and not is_waiting:
        if st.session_state.timer_active:
            st.session_state.chat_history.append({
                "role": "user",
                "content": user_input
            })
            st.session_state.waiting_for_ai = True
            st.rerun()
        else:
            st.warning("⏰ Time's up! Please end the case.")

    # Get AI response
    if is_waiting:
        with st.spinner("Patient is responding..."):
            ai_response = get_ai_response(
                st.session_state.chat_history,
                st.session_state.case_context
            )
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": ai_response
        })
        st.session_state.waiting_for_ai = False
        st.rerun()

    # ========================================================================
    # TIMER LOOP (FIXED)
    # ========================================================================
    # Fix for freezing: Only sleep if we are NOT in the first render frame
    if st.session_state.timer_active and remaining_seconds > 0:
        if st.session_state.get('just_entered_chat', False):
            # First frame: Don't sleep, just clear flag and rerun fast
            # This allows the UI to render completely at least once
            st.session_state.just_entered_chat = False
            st.rerun()
        else:
            # Subsequent frames: sleep to pace the timer
            time.sleep(1)
            st.rerun()


# ============================================================================
# PAGE 5: END / SAVE DATA
# ============================================================================

def page_end():
    st.title("Session Complete / เสร็จสิ้นการฝึกซ้อม")
    st.success(f"✅ Interview completed by {st.session_state.user_name}")
    st.success("💾 Your session data has been automatically saved!")

    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.start_time:
            duration = datetime.now() - st.session_state.start_time
            minutes = int(duration.total_seconds() // 60)
            seconds = int(duration.total_seconds() % 60)
            st.info(f"⏱️ **Session Duration**\n\n{minutes} minutes {seconds} seconds")

    with col2:
        st.info(f"💬 **Total Messages**\n\n{len(st.session_state.chat_history)} messages")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📋 Interview Transcript / บันทึกการสัมภาษณ์")

    with st.spinner("Loading interview data..."):
        session_data = get_latest_session_data()

    if session_data:
        for row in session_data:
            speaker = row.get('Speaker', '')
            message = row.get('Message', '')
            if speaker == 'user':
                st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #4a90a4 0%, #5ba3b8 100%);
                                color: white; padding: 12px 16px; border-radius: 12px;
                                margin: 8px 0;'>
                        <b>👨‍⚕️ You:</b><br>{message}
                    </div>
                """, unsafe_allow_html=True)
            elif speaker == 'assistant':
                st.markdown(f"""
                    <div style='background-color: white; padding: 12px 16px;
                                border-radius: 12px; margin: 8px 0;
                                border: 2px solid #e3f2fd;'>
                        <b style='color: #2c5f7d;'>🧑 Patient:</b><br>{message}
                    </div>
                """, unsafe_allow_html=True)
    else:
        st.warning("No interview data found.")

    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Start New Session", use_container_width=True, type="primary"):
            # Reset specific keys instead of clearing all to keep credentials valid
            keys_to_reset = ['page', 'chat_history', 'start_time', 'timer_active', 'selected_case', 'waiting_for_ai']
            for key in keys_to_reset:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.page = 'case_selection'
            st.rerun()


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    st.set_page_config(
        page_title="DigiHealth AI Patient",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # (CSS Code kept same as original for brevity, but included in logic)
    st.markdown("""
        <style>
        .stApp { background: linear-gradient(135deg, #f8fbff 0%, #e8f4f8 100%); }
        h1, h2, h3 { color: #2c5f7d !important; font-weight: 600 !important; }
        .stButton>button[kind="primary"] { background-color: #4a90a4 !important; color: white !important; border-radius: 12px !important; }
        .stButton>button[kind="secondary"] { background-color: #e3f2fd !important; color: #2c5f7d !important; border: 1px solid #b3d9e8 !important; border-radius: 12px !important; }
        .stTextInput>div>div>input { border-radius: 12px !important; border: 2px solid #b3d9e8 !important; }
        .stTextInput>div>div>input:focus { border-color: #4a90a4 !important; }
        </style>
    """, unsafe_allow_html=True)

    initialize_session_state()

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

if __name__ == "__main__":
    main()
