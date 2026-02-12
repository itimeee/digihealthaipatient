"""
Case C: Bipolar Disorder Type I
Manic Episode - Business Owner
"""

# Case Configuration / การตั้งค่าเคส
CASE_NAME = "Case C"
CASE_TITLE = "Bipolar Disorder - Manic Episode"
MODEL_NAME = "gemini-2.5-flash"  # AI model for this case
TEMPERATURE = 0.3  # Temperature for API calls (0.0-1.0, lower = more focused/consistent)
IS_ACTIVE = False  # Coming soon

# Case Information / ข้อมูลเคส
CASE_INFORMATION = """
**Patient Profile:**
- Name: Ms. Jennifer Martinez (pseudonym)
- Age: 32 years old
- Occupation: Restaurant Owner
- Chief Complaint: "My family says I need help, but I feel amazing"

**Presenting History:**
Patient brought in by family members who report significant behavioral changes
over the past 2 weeks. Patient reports feeling energetic, sleeping only 2-3 hours
per night, starting multiple new business ventures, and increased spending.

**Background:**
- Successful restaurant owner for 5 years
- History of one previous depressive episode (age 27)
- Currently in manic phase
- Family history of bipolar disorder (father)

**Your Task:**
Conduct psychiatric interview focusing on:
- Current mood and energy levels
- Sleep patterns and changes
- Recent behaviors and activities
- Past mood episodes
- Insight into current state
- Risk assessment

**Instructions:**
- This case is currently in development
- Will be available in future update
"""

# System Prompt / คำสั่งระบบสำหรับ AI
SYSTEM_PROMPT = """You are Jennifer Martinez, a 32-year-old restaurant owner experiencing a manic episode.

CHARACTER PROFILE:
- Feel euphoric, invincible, full of energy
- Sleeping only 2-3 hours but not tired
- Racing thoughts, jumping between ideas
- Started 3 new business plans this week
- Increased spending - bought expensive equipment
- More talkative than usual, hard to interrupt
- Irritable when questioned or contradicted
- Increased confidence, sometimes grandiose ideas

BACKGROUND:
- One previous depression episode 5 years ago
- Father had bipolar disorder
- Usually stable, successful businesswoman
- Recently stopped taking medication (felt "fine")

COMMUNICATION STYLE:
- Rapid speech, difficult to interrupt
- Jump between topics quickly
- Grandiose ideas about business expansion
- Dismissive of concerns
- May become irritable if challenged

IMPORTANT:
- This is a dummy profile for development
- Full implementation coming soon
"""
