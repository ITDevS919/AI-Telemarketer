"""
Mock UK Call Regulations for testing

This is a simplified mock version of the UK Call Regulations module
used for testing the dialer system.
"""

import datetime
import logging
import os
import sqlite3
from enum import Enum
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uk_call_regulations")

class ViolationType(str, Enum):
    """Types of regulation violations"""
    TPS_VIOLATION = "TPS_VIOLATION"
    TIME_VIOLATION = "TIME_VIOLATION"
    FREQUENCY_VIOLATION = "FREQUENCY_VIOLATION"
    CALLER_ID_VIOLATION = "CALLER_ID_VIOLATION"
    OTHER = "OTHER"

class UKCallRegulator:
    """
    Mock UK Call Regulator for testing
    
    This is a simplified version with minimal functionality
    for testing the dialer system.
    """
    
    def __init__(self, db_path: str = ":memory:", tps_path: str = None):
        """
        Initialize the UK Call Regulator.
        
        Args:
            db_path: Path to the database file
            tps_path: Path to the TPS registry file
        """
        self.db_path = db_path
        self.tps_path = tps_path
        self.tps_numbers = set()
        self.conn = None
        self.tps_loaded = False
        
        # Load TPS numbers if path provided
        if self.tps_path and os.path.exists(self.tps_path):
            self._load_tps_numbers()
    
    def _load_tps_numbers(self):
        """Load TPS numbers from file"""
        try:
            with open(self.tps_path, 'r') as f:
                # Skip header
                next(f)
                for line in f:
                    parts = line.strip().split(',')
                    if parts and len(parts) >= 1:
                        self.tps_numbers.add(parts[0].strip())
            
            self.tps_loaded = True
            logger.info(f"Loaded {len(self.tps_numbers)} TPS numbers")
            
        except Exception as e:
            logger.error(f"Error loading TPS numbers: {e}")
    
    def ensure_db_ready_and_get_conn(self) -> sqlite3.Connection:
        """Ensure the database is ready and get connection"""
        if self.conn is None:
            if self.db_path == ":memory:":
                self.conn = sqlite3.connect(self.db_path)
            else:
                self.conn = sqlite3.connect(self.db_path)
            
            self._create_tables_if_needed()
        
        return self.conn
    
    def _create_tables_if_needed(self):
        """Create necessary tables if they don't exist"""
        cursor = self.conn.cursor()
        
        # Call history table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS call_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            caller_id TEXT NOT NULL,
            call_id TEXT NOT NULL,
            call_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            permitted INTEGER NOT NULL,
            violation_type TEXT,
            violation_details TEXT
        )
        ''')
        
        # Create index on phone number
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_call_history_phone_number
        ON call_history (phone_number)
        ''')
        
        self.conn.commit()
    
    def can_call_number(self, phone_number: str, caller_id: str = None) -> Dict[str, Any]:
        """
        Check if a number can be called under UK regulations.
        
        Args:
            phone_number: The phone number to check
            caller_id: The caller ID to use
            
        Returns:
            Dict with permission status and reasons
        """
        # Ensure database is ready
        self.ensure_db_ready_and_get_conn()
        
        # Default response
        result = {
            "permitted": True,
            "reason": "Call is permitted",
            "violation_type": None,
            "details": {}
        }
        
        # Check TPS (if loaded)
        if self.tps_loaded and phone_number in self.tps_numbers:
            result["permitted"] = False
            result["reason"] = "Number is registered in TPS"
            result["violation_type"] = ViolationType.TPS_VIOLATION
            return result
        
        # Check calling hours
        if not self.is_within_calling_hours():
            result["permitted"] = False
            result["reason"] = "Outside permitted calling hours"
            result["violation_type"] = ViolationType.TIME_VIOLATION
            return result
        
        # Check caller ID is valid (if provided)
        if caller_id and not self._is_valid_caller_id(caller_id):
            result["permitted"] = False
            result["reason"] = "Invalid caller ID"
            result["violation_type"] = ViolationType.CALLER_ID_VIOLATION
            return result
        
        # Check call frequency (mock implementation)
        recent_calls = self._get_recent_calls_count(phone_number)
        if recent_calls >= 3:  # More than 3 calls in the last 30 days
            result["permitted"] = False
            result["reason"] = f"Too many recent calls ({recent_calls} in last 30 days)"
            result["violation_type"] = ViolationType.FREQUENCY_VIOLATION
            return result
        
        return result
    
    def _is_valid_caller_id(self, caller_id: str) -> bool:
        """Check if caller ID is valid (simple mock check)"""
        # UK numbers should start with +44
        return caller_id.startswith("+44") and len(caller_id) >= 10
    
    def _get_recent_calls_count(self, phone_number: str) -> int:
        """Get count of recent calls to a number (mock implementation)"""
        cursor = self.conn.cursor()
        
        # Get calls in last 30 days
        thirty_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).isoformat()
        
        cursor.execute('''
        SELECT COUNT(*) FROM call_history
        WHERE phone_number = ? AND call_time > ?
        ''', (phone_number, thirty_days_ago))
        
        count = cursor.fetchone()[0]
        return count
    
    def track_call(self, phone_number: str, caller_id: str, call_id: str):
        """
        Track a call for regulatory compliance.
        
        Args:
            phone_number: The phone number called
            caller_id: The caller ID used
            call_id: The call ID
        """
        conn = self.ensure_db_ready_and_get_conn()
        cursor = conn.cursor()
        
        # Check if call is permitted
        result = self.can_call_number(phone_number, caller_id)
        
        # Record the call
        cursor.execute('''
        INSERT INTO call_history (
            phone_number, caller_id, call_id, permitted, 
            violation_type, violation_details
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            phone_number, caller_id, call_id,
            1 if result["permitted"] else 0,
            result.get("violation_type"),
            str(result.get("details", {}))
        ))
        
        conn.commit()
    
    def get_call_history(self, phone_number: str = None, limit: int = 50) -> List[Dict]:
        """
        Get call history for a number or all calls.
        
        Args:
            phone_number: Optional phone number to filter by
            limit: Maximum number of records to return
            
        Returns:
            List of call history records
        """
        conn = self.ensure_db_ready_and_get_conn()
        cursor = conn.cursor()
        
        if phone_number:
            cursor.execute('''
            SELECT id, phone_number, caller_id, call_id, call_time,
                   permitted, violation_type, violation_details
            FROM call_history
            WHERE phone_number = ?
            ORDER BY call_time DESC
            LIMIT ?
            ''', (phone_number, limit))
        else:
            cursor.execute('''
            SELECT id, phone_number, caller_id, call_id, call_time,
                   permitted, violation_type, violation_details
            FROM call_history
            ORDER BY call_time DESC
            LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        
        # Convert to list of dicts
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "phone_number": row[1],
                "caller_id": row[2],
                "call_id": row[3],
                "call_time": row[4],
                "permitted": bool(row[5]),
                "violation_type": row[6],
                "violation_details": row[7]
            })
        
        return result
    
    def is_within_calling_hours(self) -> bool:
        """Check if current time is within permitted calling hours"""
        now = datetime.datetime.now()
        day_of_week = now.strftime("%A")
        hour = now.hour
        
        # Get permitted hours for current day
        hours = self.get_calling_hours().get(day_of_week, {})
        
        # If no hours defined for this day, not permitted
        if not hours:
            return False
        
        # Check if current hour is within permitted range
        start_hour = hours.get("start", 5)  # Default 9 AM
        end_hour = hours.get("end", 19)     # Default 7 PM
        
        return start_hour <= hour < end_hour
    
    def get_calling_hours(self) -> Dict[str, Dict[str, int]]:
        """Get permitted calling hours by day of week"""
        # Default UK calling hours: 9 AM to 7 PM weekdays, 10 AM to 2 PM Saturday, none on Sunday
        return {
            "Monday": {"start": 9, "end": 19},
            "Tuesday": {"start": 9, "end": 19},
            "Wednesday": {"start": 9, "end": 19},
            "Thursday": {"start": 9, "end": 19},
            "Friday": {"start": 2, "end": 19},
            "Saturday": {"start": 10, "end": 14},
            "Sunday": {}  # No calling hours on Sunday
        }
    
    def close_db(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None 