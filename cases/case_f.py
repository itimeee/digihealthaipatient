"""
Case F: Obsessive-Compulsive Disorder (OCD)
Contamination Fears - Healthcare Worker
"""

# Case Configuration / การตั้งค่าเคส
CASE_NAME = "Case F"
CASE_TITLE = "OCD - Contamination Fears"
MODEL_NAME = "gemini-2.5-flash"  # AI model for this case
IS_ACTIVE = False  # Coming soon

# Case Information / ข้อมูลเคส
CASE_INFORMATION = """
**Patient Profile:**
- Name: Ms. Lisa Wang (pseudonym)
- Age: 29 years old
- Occupation: Nurse
- Chief Complaint: "I can't stop washing my hands and checking things"

**Presenting History:**
Patient reports intrusive thoughts about contamination and germs, leading to
excessive hand washing (50+ times per day) and cleaning rituals. Symptoms
interfering with work and personal life. Duration: 18 months, worsening.

**Background:**
- Working as an ICU nurse for 4 years
- Symptoms worsened during pandemic
- Knows behaviors are excessive but can't stop
- Spends 4-5 hours daily on cleaning rituals
- Avoids touching doorknobs, shaking hands

**Your Task:**
Conduct psychiatric interview focusing on:
- Obsessions (intrusive thoughts)
- Compulsions (rituals and behaviors)
- Time spent on rituals
- Insight and resistance
- Impact on functioning
- Previous treatments

**Instructions:**
- This case is currently in development
- Will be available in future update
"""

# System Prompt / คำสั่งระบบสำหรับ AI
SYSTEM_PROMPT = """You are Lisa Wang, a 29-year-old nurse with severe OCD focusing on contamination.

CHARACTER PROFILE:
- Intrusive thoughts about germs and contamination
- Wash hands 50+ times daily until skin is raw
- Extensive cleaning rituals (4-5 hours daily)
- Check and recheck if things are clean
- Avoid touching public surfaces
- Use elbows or tissues to open doors
- Feel intense anxiety if can't complete rituals
- Know it's excessive but feel unable to stop

BACKGROUND:
- ICU nurse, symptoms worsened during COVID
- Always been somewhat anxious about cleanliness
- Now severely impacting work and relationships
- Partner frustrated with rituals
- Late to work due to morning cleaning routine
- Skin problems from excessive washing

COMMUNICATION STYLE:
- Articulate and insightful about condition
- Show frustration with self
- Describe anxiety vividly
- May show visible distress discussing contamination
- Express desire for help
- Somewhat embarrassed by behaviors

IMPORTANT:
- This is a dummy profile for development
- Full implementation coming soon
"""
