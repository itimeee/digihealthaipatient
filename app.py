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

# Gemini Model Name / ชื่อโมเดล AI (ใช้เป็นค่าเริ่มต้น)
MODEL_NAME = "gemini-1.5-flash" 

# System Prompt สำหรับ AI
SYSTEM_PROMPT = """You are a patient in a psychiatric clinic. Answer questions naturally and realistically based on the case information provided. Stay in character throughout the conversation. Respond in a conversational manner as a real patient would."""

# Timer Duration (in minutes) / ระยะเวลาจับเวลา (นาที)
TIMER_DURATION_MINUTES = 30

# ID ของ Google Sheet สำหรับบันทึกข้อมูล (ใช้ไฟล์ Master เพื่อแก้ปัญหา Quota เต็ม)
GOOGLE_SHEET_ID = "1motfqsOspQrVkWDtRqUxgfH_-3nDuqYGw9eXwEfQWoo"
GOOGLE_SHEET_LATEST_ID = "1y7mhBgABMNDzRFPDmQa7kQqTE6q4h_Py02IvT2OmUM8"

# ============================================================================
# GEMINI AI SETUP / ตั้งค่า Gemini AI (จุดที่ 2: ปรับปรุงความเสถียร)
# ============================================================================

@st.cache_resource
def get_gemini_model(model_name=None):
    """
    เริ่มต้นและแคช Gemini model เพื่อให้ทำงานเร็วขึ้นและไม่ค้าง
    """
    try:
        if "GEMINI_API_KEY" not in st.secrets:
            st.error("ไม่พบ GEMINI_API_KEY ใน secrets.toml")
            return None
            
        api_key = st.secrets["GEMINI_API_KEY"]
        
        # ตั้งค่า API ครั้งเดียวเพื่อลดภาระของระบบ
        genai.configure(api_key=api_key)
        
        selected_model = model_name if model_name else MODEL_NAME
        model = genai.GenerativeModel(selected_model)
        return model
    except Exception as e:
        st.error(f"Error initializing Gemini: {e}")
        return None

def get_ai_response(chat_history, case_context):
    """
    รับคำตอบจาก AI โดยมีการจัดการ Error เพื่อป้องกันหน้าเว็บค้าง
    """
    try:
        case_model = st.session_state.get('case_model', MODEL_NAME)
        model = get_gemini_model(case_model)

        if model is None:
            return "AI model is not available. Please check your API configuration."

        case_prompt = st.session_state.get('case_system_prompt', SYSTEM_PROMPT)
        
        # สร้างบทสนทนาส่งไปที่ AI
        full_prompt = f"{case_prompt}\n\nCase Context:\n{case_context}\n\n"
        for message in chat_history:
            role = "Doctor" if message["role"] == "user" else "Patient"
            full_prompt += f"{role}: {message['content']}\n"
        
        full_prompt += "Patient: "

        # รับคำตอบจาก AI
        response = model.generate_content(full_prompt)
        return response.text

    except Exception as e:
        st.error(f"AI Connection Error: {e}")
        return "I'm sorry, I'm having trouble responding right now. Please try again."

# ============================================================================
# GOOGLE SHEETS SETUP / ตั้งค่า Google Sheets
# ============================================================================

def get_google_credentials():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        return credentials
    except Exception as e:
        st.error(f"Error loading Google credentials: {e}")
        return None

def save_session_to_sheet(user_name, user_email, chat_history):
    try:
        credentials = get_google_credentials()
        if credentials is None: return False
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.sheet1
        session_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        rows_to_add = []
        for message in chat_history:
            rows_to_add.append([session_id, session_time, user_name, user_email, message["role"], message["content"]])
        
        worksheet.append_rows(rows_to_add)
        st.session_state.sheet_url = spreadsheet.url
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

# ============================================================================
# UI PAGES / หน้าแสดงผล
# ============================================================================

def initialize_session_state():
    if 'page' not in st.session_state: st.session_state.page = 'login'
    if 'user_name' not in st.session_state: st.session_state.user_name = ''
    if 'user_email' not in st.session_state: st.session_state.user_email = ''
    if 'chat_history' not in st.session_state: st.session_state.chat_history = []
    if 'timer_active' not in st.session_state: st.session_state.timer_active = False

def page_login():
    st.markdown("<h1 style='text-align: center; color: #2c5f7d;'>🏥 DigiHealth AI Patient</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        name = st.text_input("👤 Name / ชื่อ")
        email = st.text_input("📧 Email / อีเมล")
        if st.button("Next ➡️", use_container_width=True, type="primary"):
            if name and email:
                st.session_state.user_name, st.session_state.user_email = name, email
                st.session_state.page = 'case_selection'
                st.rerun()
            else: st.error("Please fill in both fields")

def page_case_selection():
    st.title("Select a Case / เลือกเคสผู้ป่วย")
    cols = st.columns(3)
    for idx, case in enumerate(ALL_CASES[:3]):
        with cols[idx]:
            st.info(f"📋 {case.CASE_NAME}\n\n{case.CASE_TITLE if case.IS_ACTIVE else '🔒 Coming Soon'}")
            if st.button(f"Select {case.CASE_NAME}", use_container_width=True, disabled=not case.IS_ACTIVE, key=f"btn_{idx}"):
                st.session_state.selected_case = case.CASE_NAME
                st.session_state.page = 'pre_brief'
                st.rerun()

def page_pre_brief():
    # จุดที่ 1: เพิ่ม Spinner เมื่อกด Start Case
    case_config = get_case_by_name(st.session_state.get('selected_case', 'Case A'))
    st.title(f"Case Information - {case_config.CASE_NAME}")
    st.info(case_config.CASE_INFORMATION)
    
    st.session_state.case_context = case_config.CASE_INFORMATION
    st.session_state.case_system_prompt = case_config.SYSTEM_PROMPT
    st.session_state.case_model = case_config.MODEL_NAME

    if st.button("▶️ Start Case", use_container_width=True, type="primary"):
        with st.spinner("กำลังเตรียมการสนทนา... กรุณารอสักครู่"):
            st.session_state.page = 'chat'
            st.session_state.start_time = datetime.now()
            st.session_state.timer_active = True
            time.sleep(0.5) # หน่วงเวลาเล็กน้อยเพื่อให้ระบบ Render สมบูรณ์
            st.rerun()

def page_chat():
    # จุดที่ 3: ปรับแต่ง Timer เพื่อความเสถียร
    st.title("Interview Simulation")
    
    if st.session_state.timer_active and st.session_state.start_time:
        elapsed = datetime.now() - st.session_state.start_time
        remaining = max(0, (TIMER_DURATION_MINUTES * 60) - int(elapsed.total_seconds()))
        if remaining <= 0:
            st.session_state.timer_active = False
            st.warning("⏰ Time's up! Please end the case.")
    else: remaining = 0

    col1, col2, col3 = st.columns([2, 1, 1])
    with col2: st.markdown(f"<h2 style='text-align: center;'>⏱️ {remaining//60:02d}:{remaining%60:02d}</h2>", unsafe_allow_html=True)
    with col3:
        if st.button("🛑 End Case", use_container_width=True):
            st.session_state.timer_active = False
            with st.spinner("Saving data..."):
                save_session_to_sheet(st.session_state.user_name, st.session_state.user_email, st.session_state.chat_history)
            st.session_state.page = 'end'
            st.rerun()

    # Chat UI
    for msg in st.session_state.chat_history:
        with st.chat_message("user" if msg["role"]=="user" else "assistant"):
            st.write(msg["content"])

    is_waiting = st.session_state.get('waiting_for_ai', False)
    user_input = st.chat_input("Type your message here...", disabled=is_waiting)

    if user_input and not is_waiting:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.session_state.waiting_for_ai = True
        st.rerun()

    if is_waiting:
        with st.spinner("Patient is responding..."):
            response = get_ai_response(st.session_state.chat_history, st.session_state.case_context)
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.session_state.waiting_for_ai = False
            st.rerun()

    # จุดที่ 3: ปรับปรุงการ Refresh Timer
    if st.session_state.timer_active and remaining > 0 and not is_waiting:
        time.sleep(2) # รีเฟรชทุก 2 วินาทีเพื่อลดภาระเครื่อง
        st.rerun()

def page_end():
    st.title("Session Complete")
    st.success(f"✅ Interview completed by {st.session_state.user_name}")
    if st.button("🔄 Start New Session", type="primary"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

def main():
    st.set_page_config(page_title="DigiHealth AI Patient", page_icon="🏥", layout="wide")
    
    # CSS ปรับแต่ง UI (ลบ Icon Link และสีดำเวลา Hover)
    st.markdown("""
        <style>
        .stApp { background: #f8fbff; }
        .element-container:has(h1) a, .element-container:has(h2) a, .element-container:has(h3) a { display: none !important; }
        h1:hover, h2:hover, h3:hover { background: transparent !important; }
        </style>
    """, unsafe_allow_html=True)

    initialize_session_state()
    pages = {'login': page_login, 'case_selection': page_case_selection, 'pre_brief': page_pre_brief, 'chat': page_chat, 'end': page_end}
    pages[st.session_state.page]()

if __name__ == "__main__":
    main()
