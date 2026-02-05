from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.case import Case


def generate_case_id(db: Session) -> str:
    """
    Generate a unique case ID in format: CASE-YYYY-XXXX
    
    Example: CASE-2026-0001, CASE-2026-0002
    """
    current_year = datetime.now().year
    prefix = f"CASE-{current_year}-"
    
    # Find the highest case number for this year
    latest_case = db.query(Case).filter(
        Case.case_id.like(f"{prefix}%")
    ).order_by(Case.case_id.desc()).first()
    
    if latest_case:
        # Extract the number part and increment
        try:
            last_number = int(latest_case.case_id.split("-")[-1])
            new_number = last_number + 1
        except ValueError:
            new_number = 1
    else:
        new_number = 1
    
    return f"{prefix}{new_number:04d}"
