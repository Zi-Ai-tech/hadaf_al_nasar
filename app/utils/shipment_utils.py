import random
from datetime import datetime

def generate_tracking_number():
    """
    Generate automatic tracking number
    Format: HNT-YYYYMMDD-XXXX
    """
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = ''.join([str(random.randint(0, 9)) for _ in range(4)])
    return f"HNT-{date_part}-{random_part}"

def validate_tracking_number(tracking_number):
    """
    Validate tracking number format
    """
    if not tracking_number:
        return False
    parts = tracking_number.split('-')
    return len(parts) == 3 and parts[0] == 'HNT' and len(parts[2]) == 4