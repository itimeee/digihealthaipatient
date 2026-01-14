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

# ============================================================================
# CONFIGURATION / การตั้งค่า
# ============================================================================
# You can easily change these values / คุณสามารถแก้ไขค่าเหล่านี้ได้ง่าย ๆ

# Gemini Model Name / ชื่อโมเดล AI
MODEL_NAME = "gemini-2.0-flash-exp"

# System Prompt for AI Patient / คำสั่งสำหรับ AI แสดงบทบาทผู้ป่วย
SYSTEM_PROMPT = """You are a patient in a psychiatric clinic. Answer questions naturally and realistically based on the case information provided. Stay in character throughout the conversation. Respond in a conversational manner as a real patient would."""

# Timer Duration (in minutes) / ระยะเวลาจับเวลา (นาที)
TIMER_DURATION_MINUTES = 30

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


def create_new_sheet(user_name, user_email, chat_history):
    """
    Create a NEW Google Sheet and save session data
    สร้าง Google Sheet ใหม่และบันทึกข้อมูลการฝึกซ้อม

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

        # Create filename with timestamp / สร้างชื่อไฟล์พร้อมเวลา
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sheet_name = f"DigiHealth_{user_name.replace(' ', '_')}_{timestamp}"

        # Create new spreadsheet / สร้างสเปรดชีทใหม่
        spreadsheet = gc.create(sheet_name)
        worksheet = spreadsheet.sheet1

        # Prepare header row / เตรียมหัวตาราง
        headers = ["Timestamp", "User Name", "User Email", "Speaker", "Message"]
        worksheet.append_row(headers)

        # Add session info row / เพิ่มข้อมูลเซสชัน
        session_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Add all chat messages / เพิ่มข้อความสนทนาทั้งหมด
        for message in chat_history:
            row = [
                session_time,
                user_name,
                user_email,
                message["role"],
                message["content"]
            ]
            worksheet.append_row(row)

        # Make the spreadsheet shareable / ทำให้สเปรดชีทแชร์ได้
        spreadsheet.share('', perm_type='anyone', role='reader')

        # Save the URL in session state / บันทึก URL ใน session state
        st.session_state.sheet_url = spreadsheet.url

        return True

    except Exception as e:
        st.error(f"Error creating Google Sheet: {e}")
        return False


# ============================================================================
# GEMINI AI SETUP / ตั้งค่า Gemini AI
# ============================================================================

def initialize_gemini():
    """
    Initialize Gemini AI with API key from secrets
    เริ่มต้น Gemini AI ด้วย API key จาก secrets
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        st.error(f"Error initializing Gemini: {e}")
        st.error("Please add your GEMINI_API_KEY to secrets.toml")
        return False


def get_ai_response(chat_history, case_context):
    """
    Get response from Gemini AI
    รับคำตอบจาก Gemini AI

    Args:
        chat_history: List of previous messages / ประวัติการสนทนา
        case_context: Case information for context / ข้อมูลเคสสำหรับบริบท
    """
    try:
        # Initialize the model / เริ่มต้นโมเดล
        model = genai.GenerativeModel(MODEL_NAME)

        # Build the conversation / สร้างการสนทนา
        # Start with system prompt and case context / เริ่มด้วยคำสั่งระบบและข้อมูลเคส
        full_prompt = f"{SYSTEM_PROMPT}\n\nCase Context:\n{case_context}\n\n"

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
            <div style='background: linear-gradient(135deg, #4a90a4 0%, #5ba3b8 100%);
                        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                        background-clip: text;'>
                <h1 style='font-size: 3.5em; font-weight: 700; margin: 0; padding: 0;'>
                    🏥 DigiHealth AI Patient
                </h1>
            </div>
            <p style='color: #5a7a8a; font-size: 1.3em; margin-top: 10px; font-weight: 400;'>
                Psychiatric Training Simulator
            </p>
            <p style='color: #7a9aa8; font-size: 0.95em; margin-top: 5px;'>
                Advanced Clinical Skills Development Platform
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Add some spacing / เพิ่มช่องว่าง
    st.markdown("<br>", unsafe_allow_html=True)

    # Create centered form / สร้างฟอร์มกลางหน้า
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # Card container for inputs / กล่องสำหรับฟอร์ม
        st.markdown("""
            <div style='background: white; padding: 35px; border-radius: 20px;
                        box-shadow: 0 8px 24px rgba(74, 144, 164, 0.12);
                        border: 1px solid #e3f2fd;'>
            </div>
        """, unsafe_allow_html=True)

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

    # Create 3 columns for case cards / สร้าง 3 คอลัมน์สำหรับการ์ดเคส
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
            <div style='background: white; padding: 25px; border-radius: 16px;
                        border: 2px solid #4a90a4; box-shadow: 0 4px 12px rgba(74, 144, 164, 0.15);'>
                <h3 style='color: #2c5f7d; margin-top: 0;'>🧠 Case A: Depression</h3>
                <p style='color: #5a7a8a; margin-bottom: 0;'>✅ Active case for practice</p>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Select Case A", use_container_width=True, type="primary"):
            st.session_state.selected_case = "Case A"
            st.session_state.page = 'pre_brief'
            st.rerun()

    with col2:
        st.markdown("""
            <div style='background: #f8f9fa; padding: 25px; border-radius: 16px;
                        border: 2px solid #e0e0e0; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);'>
                <h3 style='color: #9e9e9e; margin-top: 0;'>😰 Case B: Anxiety</h3>
                <p style='color: #9e9e9e; margin-bottom: 0;'>🔒 Coming Soon</p>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("Case B (Disabled)", use_container_width=True, disabled=True)

    with col3:
        st.markdown("""
            <div style='background: #f8f9fa; padding: 25px; border-radius: 16px;
                        border: 2px solid #e0e0e0; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);'>
                <h3 style='color: #9e9e9e; margin-top: 0;'>🌀 Case C: Psychosis</h3>
                <p style='color: #9e9e9e; margin-bottom: 0;'>🔒 Coming Soon</p>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("Case C (Disabled)", use_container_width=True, disabled=True)

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
    st.title("Case Information / ข้อมูลเคส")

    # ========================================================================
    # CASE HISTORY - YOU CAN EDIT THIS TEXT EASILY
    # ข้อมูลเคส - คุณสามารถแก้ไขข้อความนี้ได้ง่าย ๆ
    # ========================================================================
    case_history = """
    **Patient Profile:**
    - Name: Ms. Sarah Thompson (pseudonym)
    - Age: 28 years old
    - Occupation: Software Developer
    - Chief Complaint: "I've been feeling very sad and tired for the past 3 months"

    **Presenting History:**
    The patient reports experiencing persistent low mood, loss of interest in activities
    she used to enjoy, difficulty sleeping, and decreased energy levels. She mentions
    that these symptoms started after a significant work project ended.

    **Your Task:**
    Conduct a comprehensive psychiatric history interview. Focus on:
    - Present illness details
    - Past psychiatric history
    - Family history
    - Social history
    - Risk assessment (suicide, self-harm)

    **Instructions:**
    - Be professional and empathetic
    - Use open-ended questions
    - Listen actively to the patient's responses
    - You have 30 minutes for this interview
    """

    # Display case information / แสดงข้อมูลเคส
    st.info(case_history)

    # Store case context in session state / บันทึกข้อมูลเคสใน session state
    st.session_state.case_context = case_history

    st.markdown("<br>", unsafe_allow_html=True)

    # Mode selection / เลือกโหมด
    st.subheader("Select Interview Mode / เลือกโหมดการสัมภาษณ์")

    col1, col2 = st.columns(2)

    with col1:
        st.button("🎤 Voice Mode (Coming Soon)", use_container_width=True, disabled=True)

    with col2:
        if st.button("💬 Text Mode", use_container_width=True, type="primary"):
            # Initialize Gemini / เริ่มต้น Gemini
            if initialize_gemini():
                st.session_state.page = 'chat'
                st.session_state.start_time = datetime.now()
                st.session_state.timer_active = True
                st.rerun()

    # Back button / ปุ่มย้อนกลับ
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⬅️ Back to Case Selection"):
        st.session_state.page = 'case_selection'
        st.rerun()


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
    Main chat interface with timer
    หน้าสนทนากับ AI พร้อมตัวจับเวลา
    """
    st.title("Interview Simulation / การฝึกซ้อมสัมภาษณ์")

    # ========================================================================
    # TIMER SECTION / ส่วนตัวจับเวลา
    # ========================================================================

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

    # Display timer / แสดงตัวจับเวลา
    col1, col2, col3 = st.columns([2, 1, 1])

    with col2:
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

    with col3:
        if st.button("🛑 End Case", type="secondary", use_container_width=True):
            st.session_state.timer_active = False
            st.session_state.page = 'end'
            st.rerun()

    st.divider()

    # ========================================================================
    # CHAT INTERFACE / ส่วนการสนทนา
    # ========================================================================

    # Display chat history / แสดงประวัติการสนทนา
    chat_container = st.container(height=400)

    with chat_container:
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

    # Chat input / ช่องพิมพ์ข้อความ
    st.markdown("<br>", unsafe_allow_html=True)

    # Use a form for better UX / ใช้ฟอร์มเพื่อ UX ที่ดีขึ้น
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Your message / ข้อความของคุณ:",
            placeholder="Type your question or response here...",
            label_visibility="collapsed"
        )
        submit_button = st.form_submit_button("Send 📤", use_container_width=True)

    # Process user input / ประมวลผลข้อความ
    if submit_button and user_input:
        if st.session_state.timer_active:
            # Add user message to history / เพิ่มข้อความผู้ใช้ในประวัติ
            st.session_state.chat_history.append({
                "role": "user",
                "content": user_input
            })

            # Get AI response / รับคำตอบจาก AI
            with st.spinner("Patient is responding... / ผู้ป่วยกำลังตอบ..."):
                ai_response = get_ai_response(
                    st.session_state.chat_history,
                    st.session_state.case_context
                )

            # Add AI response to history / เพิ่มคำตอบ AI ในประวัติ
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": ai_response
            })

            st.rerun()
        else:
            st.warning("⏰ Time's up! Please end the case.")

    # Auto-refresh for timer / รีเฟรชอัตโนมัติสำหรับตัวจับเวลา
    if st.session_state.timer_active and remaining_seconds > 0:
        time.sleep(1)
        st.rerun()


# ============================================================================
# PAGE 5: END / SAVE DATA
# ============================================================================

def page_end():
    """
    End page - save data and show results
    หน้าจบการฝึกซ้อม - บันทึกข้อมูลและแสดงผล
    """
    st.title("Session Complete / เสร็จสิ้นการฝึกซ้อม")

    # Show summary / แสดงสรุป
    st.success(f"✅ Interview completed by {st.session_state.user_name}")

    # Calculate session duration / คำนวณระยะเวลา
    if st.session_state.start_time:
        duration = datetime.now() - st.session_state.start_time
        minutes = int(duration.total_seconds() // 60)
        seconds = int(duration.total_seconds() % 60)
        st.info(f"⏱️ Session Duration: {minutes} minutes {seconds} seconds")

    # Show message count / แสดงจำนวนข้อความ
    st.info(f"💬 Total Messages: {len(st.session_state.chat_history)}")

    st.markdown("<br>", unsafe_allow_html=True)

    # Save data button / ปุ่มบันทึกข้อมูล
    if st.session_state.sheet_url is None:
        if st.button("💾 Save Session Data", type="primary", use_container_width=True):
            with st.spinner("Saving data to Google Sheets... / กำลังบันทึกข้อมูล..."):
                success = create_new_sheet(
                    st.session_state.user_name,
                    st.session_state.user_email,
                    st.session_state.chat_history
                )

                if success:
                    st.success("✅ Data saved successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to save data. Please check your Google Sheets configuration.")
    else:
        st.success("✅ Data has been saved!")
        st.markdown(f"📊 [View Your Session Data]({st.session_state.sheet_url})")

    st.markdown("<br><br>", unsafe_allow_html=True)

    # Start new session button / ปุ่มเริ่มใหม่
    if st.button("🔄 Start New Session", use_container_width=True):
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
        }

        .stTextInput>div>div>input:focus {
            border-color: #4a90a4 !important;
            box-shadow: 0 0 0 3px rgba(74, 144, 164, 0.1) !important;
        }

        /* Info boxes - Calming blue */
        .stAlert {
            border-radius: 12px !important;
            border-left: 4px solid #4a90a4 !important;
            background-color: #f0f8fb !important;
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
