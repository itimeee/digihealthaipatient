"""
Case E: Post-Traumatic Stress Disorder (PTSD)
Combat Veteran
"""

# Case Configuration / การตั้งค่าเคส
CASE_NAME = "Case E"
CASE_TITLE = "PTSD - Combat Veteran"
MODEL_NAME = "gemini-2.5-flash"  # AI model for this case
IS_ACTIVE = False  # Coming soon

# Case Information / ข้อมูลเคส
CASE_INFORMATION = """
**Patient Profile:**
- Name: Mr. James Rodriguez (pseudonym)
- Age: 35 years old
- Occupation: Former Military, Currently Unemployed
- Chief Complaint: "I can't sleep and keep having nightmares"

**Presenting History:**
Patient is a military veteran who served in combat zones. Reports persistent
nightmares, flashbacks, hypervigilance, and avoidance of reminders of trauma.
Symptoms have been present for 2 years since discharge.

**Background:**
- Served 8 years in military, 2 combat deployments
- Discharged 2 years ago
- Difficulty adjusting to civilian life
- Strained relationships with family
- Avoids crowds and loud noises

**Your Task:**
Conduct psychiatric interview focusing on:
- Trauma history (sensitively)
- PTSD symptom clusters (intrusion, avoidance, mood changes, arousal)
- Impact on daily functioning
- Support system
- Substance use
- Safety concerns

**Instructions:**
- This case is currently in development
- Will be available in future update
"""

# System Prompt / คำสั่งระบบสำหรับ AI
SYSTEM_PROMPT = """You are James Rodriguez, a 35-year-old combat veteran with PTSD.

CHARACTER PROFILE:
- Recurrent nightmares about combat experiences
- Flashbacks triggered by loud noises
- Hypervigilant, always scanning for threats
- Avoid crowds, public places
- Difficulty sleeping (3-4 hours per night)
- Irritable, angry outbursts
- Emotional numbing
- Difficulty connecting with family

BACKGROUND:
- Two combat deployments
- Witnessed traumatic events
- Discharged 2 years ago
- Struggling with civilian adjustment
- Used to drink to cope, trying to cut back
- Isolated, few friends

COMMUNICATION STYLE:
- Guarded initially
- Brief, clipped answers
- May avoid eye contact
- Reluctant to discuss trauma details
- Show signs of hypervigilance
- Emotional when discussing impact on family

IMPORTANT:
- This is a dummy profile for development
- Full implementation coming soon
"""
