# app/utils/sequence_generator.py (PostgreSQL version)
from app import db
from sqlalchemy import text
from datetime import datetime

def generate_next_sequence(key: str) -> int:
    """
    Generate next sequence number for a given key with thread safety
    PostgreSQL version
    
    Args:
        key: Sequence key (e.g., 'income_2024-01')
        
    Returns:
        int: Next sequence number
    """
    try:
        # PostgreSQL UPSERT with RETURNING
        result = db.session.execute(
            text("""
                INSERT INTO sequence_counters (key_name, last_value, created_at, updated_at)
                VALUES (:key, 1, NOW(), NOW())
                ON CONFLICT (key_name) 
                DO UPDATE SET last_value = sequence_counters.last_value + 1,
                             updated_at = NOW()
                RETURNING last_value
            """),
            {'key': key}
        ).fetchone()
        
        db.session.commit()
        return result[0] if result else 1
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in sequence generation: {e}")
        # Fallback: timestamp-based sequence
        return int(datetime.now().timestamp() % 1000000)

def get_sequence_info(key: str):
    """
    Get information about a sequence
    
    Args:
        key: Sequence key
        
    Returns:
        dict or None: Sequence information
    """
    try:
        result = db.session.execute(
            text("""
                SELECT key_name, last_value, created_at, updated_at
                FROM sequence_counters
                WHERE key_name = :key
            """),
            {'key': key}
        ).fetchone()
        
        if result:
            return {
                'key': result[0],
                'last_value': result[1],
                'created_at': result[2],
                'updated_at': result[3]
            }
        return None
    except Exception as e:
        print(f"Error getting sequence info: {e}")
        return None