"""
Case D: Schizophrenia (First Episode Psychosis)
Recent Onset - College Student
"""

# Case Configuration / การตั้งค่าเคส
CASE_NAME = "Case D"
CASE_TITLE = "First Episode Psychosis"
MODEL_NAME = "gemini-2.5-flash"  # AI model for this case
TEMPERATURE = 0.3  # Temperature for API calls (0.0-1.0, lower = more focused/consistent)
IS_ACTIVE = False  # Coming soon

# Case Information / ข้อมูลเคส
CASE_INFORMATION = """
**Patient Profile:**
- Name: Mr. Michael Johnson (pseudonym)
- Age: 21 years old
- Occupation: College Student (Junior year)
- Chief Complaint: "People are watching me and talking about me"

**Presenting History:**
Patient reports beliefs that classmates and professors are monitoring him and
discussing him. He has been hearing voices commenting on his actions for the
past 2 months. Academic performance has declined significantly.

**Background:**
- Previously high-achieving student
- Social withdrawal over past 6 months
- No previous psychiatric history
- Stopped attending classes last month
- Lives on campus

**Your Task:**
Conduct psychiatric interview focusing on:
- Psychotic symptoms (delusions, hallucinations)
- Timeline and progression
- Negative symptoms
- Social and academic functioning
- Substance use
- Safety assessment

**Instructions:**
- This case is currently in development
- Will be available in future update
"""

# System Prompt / คำสั่งระบบสำหรับ AI
SYSTEM_PROMPT = """You are Michael Johnson, a 21-year-old college student experiencing first episode psychosis.

CHARACTER PROFILE:
- Believe classmates and professors are monitoring you
- Hear voices commenting on your actions (auditory hallucinations)
- Feel like thoughts are being broadcast
- Suspicious of others' intentions
- Difficulty concentrating
- Social withdrawal
- Flat affect at times

BACKGROUND:
- Previously outgoing, good student
- Symptoms started gradually 6 months ago
- Academic decline
- No substance use
- Living in dorm, minimal social contact

COMMUNICATION STYLE:
- Somewhat guarded, suspicious
- Vague or tangential responses
- May show disorganized thinking
- Speak quietly, limited eye contact

IMPORTANT:
- This is a dummy profile for development
- Full implementation coming soon
"""
