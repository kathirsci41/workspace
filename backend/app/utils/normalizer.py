import re


def normalize_opportunity_id(opp_id: str) -> str:
    """
    Normalize opportunity ID to standard format: SKY-XXX
    
    Examples:
        "443" -> "SKY-443"
        "SKY443" -> "SKY-443"
        "sky-443" -> "SKY-443"
        "SKY-443" -> "SKY-443"
    """
    if not opp_id:
        return opp_id
    
    # Strip whitespace and convert to uppercase
    cleaned = opp_id.strip().upper()
    
    # If it's just a number, prefix with SKY-
    if cleaned.isdigit():
        return f"SKY-{cleaned}"
    
    # If it starts with SKY but no dash
    match = re.match(r'^SKY(\d+)$', cleaned)
    if match:
        return f"SKY-{match.group(1)}"
    
    # If it already has SKY- prefix
    if cleaned.startswith("SKY-"):
        return cleaned
    
    # Return as-is if format is unknown
    return cleaned


def normalize_filename(filename: str) -> str:
    """
    Normalize filename for storage.
    
    Replaces spaces with underscores and removes special characters.
    """
    if not filename:
        return filename
    
    # Replace spaces with underscores
    safe_filename = filename.replace(" ", "_")
    
    # Remove any path components
    safe_filename = safe_filename.split("/")[-1].split("\\")[-1]
    
    return safe_filename
