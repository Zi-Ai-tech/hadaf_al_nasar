from datetime import datetime

def generate_driver_id():
    """Generate unique driver employee ID"""
    from app.models.logistics.driver import Driver
    
    # Format: DRV-YYYY-XXXX
    base_ref = f"DRV-{datetime.now().strftime('%Y')}"
    
    # Find the maximum sequence number for this year
    # Get all employee_ids for this year and find the max sequence
    existing_drivers = Driver.query.filter(
        Driver.employee_id.like(f"{base_ref}-%")
    ).all()
    
    # Extract sequence numbers
    sequences = []
    for driver in existing_drivers:
        if driver.employee_id and driver.employee_id.startswith(base_ref):
            try:
                # Extract the 4-digit sequence
                seq_part = driver.employee_id.split('-')[-1]
                sequences.append(int(seq_part))
            except (IndexError, ValueError):
                continue
    
    next_sequence = max(sequences) + 1 if sequences else 1
    return f"{base_ref}-{next_sequence:04d}"