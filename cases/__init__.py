"""
Patient Case Configurations
Contains all patient case profiles for the DigiHealth AI Patient training system
"""

from . import case_a, case_b, case_c, case_d, case_e, case_f

# List of all available cases / รายการเคสทั้งหมด
ALL_CASES = [
    case_a,
    case_b,
    case_c,
    case_d,
    case_e,
    case_f
]

# Get case by name / ดึงเคสตามชื่อ
def get_case_by_name(case_name):
    """
    Get case configuration by case name
    ดึงการตั้งค่าเคสตามชื่อ

    Args:
        case_name: Name of the case (e.g., "Case A")

    Returns:
        Case module or None if not found
    """
    for case in ALL_CASES:
        if case.CASE_NAME == case_name:
            return case
    return None

# Get only active cases / ดึงเฉพาะเคสที่ใช้งานได้
def get_active_cases():
    """
    Get list of active (available) cases
    ดึงรายการเคสที่ใช้งานได้

    Returns:
        List of active case modules
    """
    return [case for case in ALL_CASES if case.IS_ACTIVE]

# Get inactive cases / ดึงเคสที่ยังไม่เปิดใช้งาน
def get_inactive_cases():
    """
    Get list of inactive (coming soon) cases
    ดึงรายการเคสที่ยังไม่เปิดใช้งาน

    Returns:
        List of inactive case modules
    """
    return [case for case in ALL_CASES if not case.IS_ACTIVE]
