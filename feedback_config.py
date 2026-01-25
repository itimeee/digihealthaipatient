"""
Feedback Model Configuration / การตั้งค่าโมเดลสำหรับให้ feedback
=================================================================
This file contains all configurable settings for the feedback generation model.
Edit these values to customize the feedback behavior without modifying app.py.

ไฟล์นี้ประกอบด้วยการตั้งค่าทั้งหมดสำหรับโมเดลที่ใช้ให้ feedback
แก้ไขค่าเหล่านี้เพื่อปรับแต่งพฤติกรรมของ feedback โดยไม่ต้องแก้ไข app.py
"""

# =============================================================================
# MODEL PROVIDER SETTINGS / การตั้งค่าผู้ให้บริการโมเดล
# =============================================================================

# Provider: "gemini" (default) - can extend to "openai", "anthropic" in future
# ผู้ให้บริการ: "gemini" (ค่าเริ่มต้น) - สามารถขยายเป็น "openai", "anthropic" ในอนาคต
FEEDBACK_PROVIDER = "gemini"

# Model name for feedback generation
# ชื่อโมเดลสำหรับสร้าง feedback
FEEDBACK_MODEL_NAME = "gemini-2.0-flash-exp"

# Temperature for response generation (0.0 = deterministic, 1.0 = creative)
# อุณหภูมิสำหรับการสร้างคำตอบ (0.0 = แน่นอน, 1.0 = สร้างสรรค์)
FEEDBACK_TEMPERATURE = 0.3

# =============================================================================
# OUTPUT FORMAT / รูปแบบผลลัพธ์
# =============================================================================

# Output format: "json" (recommended for parsing) or "markdown"
# รูปแบบผลลัพธ์: "json" (แนะนำสำหรับการ parse) หรือ "markdown"
FEEDBACK_OUTPUT_FORMAT = "json"

# =============================================================================
# GOOGLE SHEETS SETTINGS / การตั้งค่า Google Sheets
# =============================================================================

# Sheet ID for storing feedback sessions (append mode)
# ID ของ Sheet สำหรับเก็บข้อมูล feedback sessions (โหมด append)
FEEDBACK_SHEET_ID = "1Nl-Ksqpx_I76wDOWpQmSPw7CPXFdpBL4kZyfXlxApXU"

# Worksheet name for session summaries (1 row per session)
# ชื่อ worksheet สำหรับสรุป session (1 แถวต่อ 1 session)
FEEDBACK_SHEET_WORKSHEET_NAME = "sessions"

# Worksheet name for transcript details (1 row per message)
# ชื่อ worksheet สำหรับรายละเอียด transcript (1 แถวต่อ 1 ข้อความ)
TRANSCRIPT_WORKSHEET_NAME = "transcript"

# =============================================================================
# PSYCHODYNAMIC FRAMEWORKS / กรอบแนวคิด Psychodynamic
# =============================================================================

# Available frameworks for psychodynamic formulation
# กรอบแนวคิดที่มีสำหรับ psychodynamic formulation
PSYCHODYNAMIC_FRAMEWORKS = [
    "4P (Predisposing, Precipitating, Perpetuating, Protective)",
    "Psychosexual Development (Freud)",
    "Ego Psychology",
    "Self Psychology (Kohut)",
    "Object Relations Theory",
    "Attachment Theory"
]

# =============================================================================
# FEEDBACK SYSTEM PROMPT / System Prompt สำหรับ Feedback
# =============================================================================

FEEDBACK_SYSTEM_PROMPT = """คุณเป็นผู้เชี่ยวชาญด้านจิตเวชศาสตร์ มีหน้าที่ประเมินและให้ feedback แก่แพทย์ฝึกหัดที่ทำการสัมภาษณ์ผู้ป่วยจิตเวชจำลอง

## บทบาทของคุณ
- ประเมินทักษะการสัมภาษณ์ทางจิตเวช
- ประเมินความสมเหตุสมผลของการวินิจฉัยและ formulation
- ให้ feedback ที่สร้างสรรค์และเป็นประโยชน์ต่อการเรียนรู้

## หลักการประเมินการสัมภาษณ์
1. **Rapport Building**: การสร้างสัมพันธภาพกับผู้ป่วย ใช้ภาษาที่เหมาะสม เปิดใจรับฟัง
2. **Agenda Setting**: การกำหนดหัวข้อและวัตถุประสงค์การสัมภาษณ์
3. **Chronology**: การซักประวัติตามลำดับเวลา onset, course, duration
4. **Symptom Exploration**: การสำรวจอาการอย่างละเอียด (SIGECAPS, PHQ-9 elements, etc.)
5. **Risk Assessment**: การประเมินความเสี่ยง suicidal ideation, self-harm, harm to others
6. **Clarification**: การขอให้ผู้ป่วยอธิบายเพิ่มเติมเมื่อไม่ชัดเจน
7. **Summarization**: การสรุปเป็นระยะเพื่อยืนยันความเข้าใจ
8. **Empathy**: การแสดงความเข้าใจและใส่ใจต่อความรู้สึกของผู้ป่วย
9. **Open-ended Questions**: การใช้คำถามปลายเปิดเพื่อให้ผู้ป่วยเล่าเรื่องได้อิสระ
10. **Non-judgmental Approach**: การไม่ตัดสินหรือวิพากษ์วิจารณ์ผู้ป่วย

## หลักการประเมิน Clinical Reasoning
1. **Provisional Diagnosis**: ความสอดคล้องกับอาการที่ได้จากการสัมภาษณ์ ตรงตามเกณฑ์วินิจฉัย (DSM-5/ICD-10)
2. **Differential Diagnosis**: ความครอบคลุมและเหตุผลสนับสนุน
3. **Psychodynamic Formulation**: ความเหมาะสมของ framework ที่เลือก และความสมบูรณ์ของการอธิบาย

## รูปแบบผลลัพธ์ (JSON)
คุณต้องตอบในรูปแบบ JSON เท่านั้น โดยมีโครงสร้างดังนี้:

```json
{
  "interview_feedback": {
    "strengths": ["จุดแข็ง 1", "จุดแข็ง 2", "..."],
    "missed_opportunities": ["สิ่งที่พลาดไป 1", "สิ่งที่พลาดไป 2", "..."],
    "suggested_questions": ["คำถามที่ควรถามเพิ่ม 1", "คำถามที่ควรถามเพิ่ม 2", "..."],
    "risk_assessment_notes": "ความคิดเห็นเกี่ยวกับการประเมินความเสี่ยง",
    "overall_comment": "สรุปภาพรวมการสัมภาษณ์"
  },
  "clinical_feedback": {
    "provisional_dx_comment": "ความคิดเห็นต่อ provisional diagnosis",
    "ddx_comment": {
      "ddx1": "ความคิดเห็นต่อ DDx ข้อ 1",
      "ddx2": "ความคิดเห็นต่อ DDx ข้อ 2",
      "ddx3": "ความคิดเห็นต่อ DDx ข้อ 3"
    },
    "psychodynamic_formulation_comment": "ความคิดเห็นต่อ psychodynamic formulation",
    "overall_comment": "สรุปภาพรวม clinical reasoning"
  }
}
```

## ข้อควรระวัง
- ให้ feedback ที่สร้างสรรค์ ไม่ตำหนิรุนแรง
- ชี้ให้เห็นทั้งจุดแข็งและจุดที่ควรพัฒนา
- ให้ตัวอย่างคำถามที่ควรถามเพิ่มอย่างเฉพาะเจาะจง
- พิจารณาบริบทของเคสที่กำลังสัมภาษณ์
- ตอบเป็น JSON ที่ถูกต้องและ parse ได้เท่านั้น"""

# =============================================================================
# FEEDBACK USER PROMPT TEMPLATE / Template สำหรับ User Prompt
# =============================================================================

FEEDBACK_USER_PROMPT_TEMPLATE = """## ข้อมูล Session
- **ผู้สัมภาษณ์**: {user_name} ({user_email})
- **เคส**: {case_name}
- **โหมด**: {selected_mode}
- **ระยะเวลา**: {duration_seconds} วินาที ({duration_minutes} นาที)
- **จำนวนข้อความทั้งหมด**: {total_messages} ข้อความ
- **จำนวนคำถามของแพทย์**: {doctor_turns} คำถาม
- **จำนวนคำตอบของผู้ป่วย**: {patient_turns} คำตอบ

## Transcript การสัมภาษณ์
{transcript_text}

## คำตอบของผู้สัมภาษณ์

### Provisional Diagnosis
{provisional_dx}

### Differential Diagnosis
1. {ddx1}
2. {ddx2}
3. {ddx3}

### Psychodynamic Formulation
**Framework ที่เลือก**: {formulation_framework}
**Formulation**:
{formulation_text}

---

กรุณาประเมินและให้ feedback ตามหลักการที่กำหนดไว้ โดยตอบเป็น JSON format ที่กำหนด"""
