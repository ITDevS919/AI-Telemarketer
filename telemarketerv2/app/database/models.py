"""
Database models for the AI Telemarketer system

This module defines the database schema and provides functions
for initializing and interacting with the database.

Supports both SQLite and PostgreSQL databases.
"""

import sqlite3
import datetime
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from .connection import DatabaseAdapter, get_database_adapter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database.models")

def init_database(connection_string: str):
    """
    Initialize the database schema.
    
    Args:
        connection_string: Database connection string (SQLite file path or PostgreSQL URL)
    """
    adapter = get_database_adapter(connection_string)
    adapter.connect()
    
    try:
        # Determine column types based on database
        text_type = "TEXT" if adapter.db_type == "sqlite" else "VARCHAR"
        int_type = "INTEGER" if adapter.db_type == "sqlite" else "INTEGER"
        
        # Create call_records table
        call_records_sql = f"""
        CREATE TABLE IF NOT EXISTS call_records (
            call_id {text_type} PRIMARY KEY,
            phone_number {text_type} NOT NULL,
            business_type {text_type} NOT NULL,
            caller_id {text_type} NOT NULL,
            status {text_type} NOT NULL,
            retry_count {int_type} DEFAULT 0,
            created_at {text_type} NOT NULL,
            scheduled_time {text_type} NOT NULL,
            started_at {text_type},
            completed_at {text_type},
            last_error {text_type},
            regulation_violation {text_type},
            call_sid {text_type},
            twilio_call_sid {text_type},
            conversation_history {text_type},
            call_duration {int_type},
            updated_at {text_type} NOT NULL
        )
        """
        adapter.execute(call_records_sql)
        
        # Create lead_records table
        lead_records_sql = f"""
        CREATE TABLE IF NOT EXISTS lead_records (
            lead_id {text_type} PRIMARY KEY,
            call_id {text_type} NOT NULL,
            phone_number {text_type} NOT NULL,
            business_name {text_type},
            business_type {text_type},
            contact_name {text_type},
            contact_email {text_type},
            contact_phone {text_type},
            appointment_time {text_type},
            notes {text_type},
            created_at {text_type} NOT NULL,
            updated_at {text_type} NOT NULL,
            FOREIGN KEY (call_id) REFERENCES call_records (call_id)
        )
        """
        adapter.execute(lead_records_sql)
        
        # Create indices
        adapter.execute("CREATE INDEX IF NOT EXISTS idx_call_records_status ON call_records (status)")
        adapter.execute("CREATE INDEX IF NOT EXISTS idx_call_records_phone ON call_records (phone_number)")
        adapter.execute("CREATE INDEX IF NOT EXISTS idx_call_records_created ON call_records (created_at)")
        adapter.execute("CREATE INDEX IF NOT EXISTS idx_lead_records_call_id ON lead_records (call_id)")
        
        adapter.commit()
        logger.info(f"Database initialized: {connection_string}")
        
    finally:
        adapter.close()

class BaseModel:
    """Base class for database models"""
    
    table_name = ""
    primary_key = ""
    
    def __init__(self, **kwargs):
        """Initialize model with attributes"""
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    @classmethod
    def from_row(cls, row: Any) -> 'BaseModel':
        """
        Create model instance from database row.
        
        Args:
            row: Database row (SQLite Row, PostgreSQL dict-like, or dict)
            
        Returns:
            Model instance
        """
        if hasattr(row, 'keys'):
            return cls(**dict(row))
        return cls(**dict(row))
    
    def to_dict(self) -> Dict:
        """
        Convert model to dictionary.
        
        Returns:
            Dictionary representation of the model
        """
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
    
    @classmethod
    def get_by_id(cls, conn: Union[DatabaseAdapter, sqlite3.Connection], id_value: str) -> Optional['BaseModel']:
        """
        Get record by ID.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            id_value: ID value
            
        Returns:
            Model instance or None if not found
        """
        if isinstance(conn, DatabaseAdapter):
            cursor = conn.execute(f"SELECT * FROM {cls.table_name} WHERE {cls.primary_key} = ?", (id_value,))
            row = cursor.fetchone()
            if row:
                return cls(**conn.row_to_dict(row))
            return None
        else:
            # Backward compatibility
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE {cls.primary_key} = ?", (id_value,))
            row = cursor.fetchone()
            if row:
                return cls.from_row(row)
            return None
    
    @classmethod
    def get_all(cls, conn: Union[DatabaseAdapter, sqlite3.Connection], 
               where_clause: str = "", 
               params: tuple = (), 
               order_by: str = "", 
               limit: int = 0, 
               offset: int = 0) -> List['BaseModel']:
        """
        Get multiple records.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            where_clause: SQL WHERE clause (without 'WHERE')
            params: Parameters for the query
            order_by: SQL ORDER BY clause (without 'ORDER BY')
            limit: Maximum number of records to return
            offset: Offset for pagination
            
        Returns:
            List of model instances
        """
        query = f"SELECT * FROM {cls.table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        if order_by:
            query += f" ORDER BY {order_by}"
        if limit:
            query += f" LIMIT {limit}"
        if offset:
            query += f" OFFSET {offset}"
        
        if isinstance(conn, DatabaseAdapter):
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [cls(**conn.row_to_dict(row)) for row in rows]
        else:
            # Backward compatibility
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [cls.from_row(row) for row in rows]
    
    def save(self, conn: Union[DatabaseAdapter, sqlite3.Connection]) -> bool:
        """
        Save model to database.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            
        Returns:
            True if successful, False otherwise
        """
        data = self.to_dict()
        
        # Set updated_at
        if 'updated_at' in data:
            data['updated_at'] = datetime.datetime.now().isoformat()
        
        try:
            if isinstance(conn, DatabaseAdapter):
                # Check if record exists
                cursor = conn.execute(f"SELECT 1 FROM {self.table_name} WHERE {self.primary_key} = ?", 
                                     (data[self.primary_key],))
                exists = cursor.fetchone() is not None
                
                if exists:
                    # Update
                    set_clause = ', '.join(f"{k} = ?" for k in data.keys() if k != self.primary_key)
                    params = [data[k] for k in data.keys() if k != self.primary_key]
                    params.append(data[self.primary_key])
                    conn.execute(f"UPDATE {self.table_name} SET {set_clause} WHERE {self.primary_key} = ?", tuple(params))
                else:
                    # Insert
                    keys = ', '.join(data.keys())
                    placeholders = ', '.join(['?'] * len(data))
                    params = list(data.values())
                    conn.execute(f"INSERT INTO {self.table_name} ({keys}) VALUES ({placeholders})", tuple(params))
                
                conn.commit()
                return True
            else:
                # Backward compatibility
                cursor = conn.cursor()
                cursor.execute(f"SELECT 1 FROM {self.table_name} WHERE {self.primary_key} = ?", 
                             (data[self.primary_key],))
                exists = cursor.fetchone() is not None
                
                if exists:
                    set_clause = ', '.join(f"{k} = ?" for k in data.keys() if k != self.primary_key)
                    params = [data[k] for k in data.keys() if k != self.primary_key]
                    params.append(data[self.primary_key])
                    cursor.execute(f"UPDATE {self.table_name} SET {set_clause} WHERE {self.primary_key} = ?", params)
                else:
                    keys = ', '.join(data.keys())
                    placeholders = ', '.join(['?'] * len(data))
                    params = list(data.values())
                    cursor.execute(f"INSERT INTO {self.table_name} ({keys}) VALUES ({placeholders})", params)
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error saving {self.table_name}: {e}")
            if isinstance(conn, DatabaseAdapter):
                conn.rollback()
            else:
                conn.rollback()
            return False
    
    @classmethod
    def delete(cls, conn: Union[DatabaseAdapter, sqlite3.Connection], id_value: str) -> bool:
        """
        Delete record from database.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            id_value: ID value
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if isinstance(conn, DatabaseAdapter):
                cursor = conn.execute(f"DELETE FROM {cls.table_name} WHERE {cls.primary_key} = ?", (id_value,))
                conn.commit()
                return cursor.rowcount > 0
            else:
                # Backward compatibility
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {cls.table_name} WHERE {cls.primary_key} = ?", (id_value,))
                conn.commit()
                return cursor.rowcount > 0
            
        except Exception as e:
            logger.error(f"Error deleting {cls.table_name}: {e}")
            if isinstance(conn, DatabaseAdapter):
                conn.rollback()
            else:
                conn.rollback()
            return False

class CallRecord(BaseModel):
    """Model for call records"""
    
    table_name = "call_records"
    primary_key = "call_id"
    
    def __init__(self, 
                call_id: str,
                phone_number: str,
                business_type: str,
                caller_id: str,
                status: str,
                created_at: str = None,
                scheduled_time: str = None,
                retry_count: int = 0,
                started_at: str = None,
                completed_at: str = None,
                last_error: str = None,
                regulation_violation: str = None,
                call_sid: str = None,
                twilio_call_sid: str = None,
                conversation_history: str = None,
                call_duration: int = None,
                updated_at: str = None):
        """
        Initialize call record.
        
        Args:
            call_id: Unique ID for the call
            phone_number: Phone number called
            business_type: Type of business
            caller_id: Caller ID used
            status: Current status of the call
            created_at: Creation timestamp
            scheduled_time: Scheduled time for the call
            retry_count: Number of retry attempts
            started_at: Start timestamp
            completed_at: Completion timestamp
            last_error: Last error message
            regulation_violation: Type of regulation violation if any
            call_sid: Internal call SID
            twilio_call_sid: Twilio call SID
            conversation_history: JSON string of conversation
            call_duration: Call duration in seconds
            updated_at: Last update timestamp
        """
        self.call_id = call_id
        self.phone_number = phone_number
        self.business_type = business_type
        self.caller_id = caller_id
        self.status = status
        self.retry_count = retry_count
        self.created_at = created_at or datetime.datetime.now().isoformat()
        self.scheduled_time = scheduled_time or self.created_at
        self.started_at = started_at
        self.completed_at = completed_at
        self.last_error = last_error
        self.regulation_violation = regulation_violation
        self.call_sid = call_sid
        self.twilio_call_sid = twilio_call_sid
        self.conversation_history = conversation_history
        self.call_duration = call_duration
        self.updated_at = updated_at or self.created_at
    
    def set_conversation_history(self, history: List[Dict]):
        """
        Set conversation history from a list of message dicts.
        
        Args:
            history: List of message dictionaries
        """
        self.conversation_history = json.dumps(history)
    
    def get_conversation_history(self) -> List[Dict]:
        """
        Get conversation history as a list of message dicts.
        
        Returns:
            List of message dictionaries
        """
        if not self.conversation_history:
            return []
        return json.loads(self.conversation_history)
    
    @classmethod
    def get_by_twilio_sid(cls, conn: Union[DatabaseAdapter, sqlite3.Connection], twilio_sid: str) -> Optional['CallRecord']:
        """
        Get call record by Twilio SID.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            twilio_sid: Twilio call SID
            
        Returns:
            CallRecord or None if not found
        """
        if isinstance(conn, DatabaseAdapter):
            cursor = conn.execute(f"SELECT * FROM {cls.table_name} WHERE twilio_call_sid = ?", (twilio_sid,))
            row = cursor.fetchone()
            if row:
                return cls(**conn.row_to_dict(row))
            return None
        else:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE twilio_call_sid = ?", (twilio_sid,))
            row = cursor.fetchone()
            if row:
                return cls.from_row(row)
            return None
    
    @classmethod
    def get_by_phone_number(cls, conn: Union[DatabaseAdapter, sqlite3.Connection], phone_number: str, 
                          limit: int = 10) -> List['CallRecord']:
        """
        Get call records for a specific phone number.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            phone_number: Phone number
            limit: Maximum number of records to return
            
        Returns:
            List of CallRecord instances
        """
        return cls.get_all(
            conn, 
            where_clause="phone_number = ?", 
            params=(phone_number,), 
            order_by="created_at DESC", 
            limit=limit
        )
    
    @classmethod
    def get_recent_calls(cls, conn: Union[DatabaseAdapter, sqlite3.Connection], limit: int = 50, 
                       offset: int = 0) -> List['CallRecord']:
        """
        Get recent calls.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            limit: Maximum number of records to return
            offset: Offset for pagination
            
        Returns:
            List of CallRecord instances
        """
        return cls.get_all(
            conn,
            order_by="created_at DESC",
            limit=limit,
            offset=offset
        )
    
    @classmethod
    def get_pending_calls(cls, conn: Union[DatabaseAdapter, sqlite3.Connection]) -> List['CallRecord']:
        """
        Get pending calls (queued or retry scheduled).
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            
        Returns:
            List of CallRecord instances
        """
        return cls.get_all(
            conn,
            where_clause="status IN ('queued', 'retry_scheduled')",
            order_by="scheduled_time ASC"
        )
    
    @classmethod
    def get_active_calls(cls, conn: Union[DatabaseAdapter, sqlite3.Connection]) -> List['CallRecord']:
        """
        Get active calls.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            
        Returns:
            List of CallRecord instances
        """
        return cls.get_all(
            conn,
            where_clause="status = 'in-progress'"
        )
    
    @classmethod
    def get_call_stats(cls, conn: Union[DatabaseAdapter, sqlite3.Connection]) -> Dict:
        """
        Get call statistics.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            
        Returns:
            Dictionary with call statistics
        """
        if isinstance(conn, DatabaseAdapter):
            # Get counts by status
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM call_records
                GROUP BY status
            """)
            status_counts = {conn.row_to_dict(row)['status']: conn.row_to_dict(row)['count'] for row in cursor.fetchall()}
            
            # Get total duration
            cursor = conn.execute("""
                SELECT SUM(call_duration) as total_duration
                FROM call_records
                WHERE call_duration IS NOT NULL
            """)
            row = cursor.fetchone()
            total_duration = conn.row_to_dict(row)['total_duration'] or 0 if row else 0
            
            # Get counts by day for the last 7 days
            seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
            date_func = conn.get_date_function()
            cursor = conn.execute(f"""
                SELECT {date_func}(created_at) as day, COUNT(*) as count
                FROM call_records
                WHERE created_at >= ?
                GROUP BY day
                ORDER BY day
            """, (seven_days_ago,))
            daily_counts = {conn.row_to_dict(row)['day']: conn.row_to_dict(row)['count'] for row in cursor.fetchall()}
        else:
            # Backward compatibility
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM call_records
                GROUP BY status
            """)
            status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
            
            cursor.execute("""
                SELECT SUM(call_duration) as total_duration
                FROM call_records
                WHERE call_duration IS NOT NULL
            """)
            total_duration = cursor.fetchone()['total_duration'] or 0
            
            seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
            cursor.execute("""
                SELECT date(created_at) as day, COUNT(*) as count
                FROM call_records
                WHERE created_at >= ?
                GROUP BY day
                ORDER BY day
            """, (seven_days_ago,))
            daily_counts = {row['day']: row['count'] for row in cursor.fetchall()}
        
        return {
            'by_status': status_counts,
            'total_duration': total_duration,
            'daily_counts': daily_counts,
            'total_calls': sum(status_counts.values())
        }

class LeadRecord(BaseModel):
    """Model for lead records"""
    
    table_name = "lead_records"
    primary_key = "lead_id"
    
    def __init__(self,
                lead_id: str,
                call_id: str,
                phone_number: str,
                business_name: str = None,
                business_type: str = None,
                contact_name: str = None,
                contact_email: str = None,
                contact_phone: str = None,
                appointment_time: str = None,
                notes: str = None,
                created_at: str = None,
                updated_at: str = None):
        """
        Initialize lead record.
        
        Args:
            lead_id: Unique ID for the lead
            call_id: Associated call ID
            phone_number: Phone number called
            business_name: Name of the business
            business_type: Type of business
            contact_name: Name of the contact person
            contact_email: Email of the contact person
            contact_phone: Phone of the contact person
            appointment_time: Scheduled appointment time
            notes: Additional notes
            created_at: Creation timestamp
            updated_at: Last update timestamp
        """
        self.lead_id = lead_id
        self.call_id = call_id
        self.phone_number = phone_number
        self.business_name = business_name
        self.business_type = business_type
        self.contact_name = contact_name
        self.contact_email = contact_email
        self.contact_phone = contact_phone
        self.appointment_time = appointment_time
        self.notes = notes
        self.created_at = created_at or datetime.datetime.now().isoformat()
        self.updated_at = updated_at or self.created_at
    
    @classmethod
    def get_by_call_id(cls, conn: Union[DatabaseAdapter, sqlite3.Connection], call_id: str) -> Optional['LeadRecord']:
        """
        Get lead record by call ID.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            call_id: Call ID
            
        Returns:
            LeadRecord or None if not found
        """
        if isinstance(conn, DatabaseAdapter):
            cursor = conn.execute(f"SELECT * FROM {cls.table_name} WHERE call_id = ?", (call_id,))
            row = cursor.fetchone()
            if row:
                return cls(**conn.row_to_dict(row))
            return None
        else:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE call_id = ?", (call_id,))
            row = cursor.fetchone()
            if row:
                return cls.from_row(row)
            return None
    
    @classmethod
    def get_recent_leads(cls, conn: Union[DatabaseAdapter, sqlite3.Connection], limit: int = 50, 
                       offset: int = 0) -> List['LeadRecord']:
        """
        Get recent leads.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            limit: Maximum number of records to return
            offset: Offset for pagination
            
        Returns:
            List of LeadRecord instances
        """
        return cls.get_all(
            conn,
            order_by="created_at DESC",
            limit=limit,
            offset=offset
        )
    
    @classmethod
    def get_leads_by_date_range(cls, conn: Union[DatabaseAdapter, sqlite3.Connection], 
                              start_date: str, end_date: str) -> List['LeadRecord']:
        """
        Get leads within a date range.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            start_date: Start date in ISO format
            end_date: End date in ISO format
            
        Returns:
            List of LeadRecord instances
        """
        return cls.get_all(
            conn,
            where_clause="created_at BETWEEN ? AND ?",
            params=(start_date, end_date),
            order_by="created_at DESC"
        )
    
    @classmethod
    def get_lead_stats(cls, conn: Union[DatabaseAdapter, sqlite3.Connection]) -> Dict:
        """
        Get lead statistics.
        
        Args:
            conn: Database connection (DatabaseAdapter or sqlite3.Connection)
            
        Returns:
            Dictionary with lead statistics
        """
        if isinstance(conn, DatabaseAdapter):
            # Get total leads
            cursor = conn.execute("SELECT COUNT(*) as count FROM lead_records")
            row = cursor.fetchone()
            total_leads = conn.row_to_dict(row)['count'] if row else 0
            
            # Get leads by business type
            cursor = conn.execute("""
                SELECT business_type, COUNT(*) as count
                FROM lead_records
                WHERE business_type IS NOT NULL
                GROUP BY business_type
            """)
            by_business_type = {conn.row_to_dict(row)['business_type']: conn.row_to_dict(row)['count'] for row in cursor.fetchall()}
            
            # Get leads by day for the last 7 days
            seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
            date_func = conn.get_date_function()
            cursor = conn.execute(f"""
                SELECT {date_func}(created_at) as day, COUNT(*) as count
                FROM lead_records
                WHERE created_at >= ?
                GROUP BY day
                ORDER BY day
            """, (seven_days_ago,))
            daily_counts = {conn.row_to_dict(row)['day']: conn.row_to_dict(row)['count'] for row in cursor.fetchall()}
            
            # Get appointment conversion rate
            cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM lead_records
                WHERE appointment_time IS NOT NULL
            """)
            row = cursor.fetchone()
            appointments = conn.row_to_dict(row)['count'] if row else 0
        else:
            # Backward compatibility
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM lead_records")
            total_leads = cursor.fetchone()['count']
            
            cursor.execute("""
                SELECT business_type, COUNT(*) as count
                FROM lead_records
                WHERE business_type IS NOT NULL
                GROUP BY business_type
            """)
            by_business_type = {row['business_type']: row['count'] for row in cursor.fetchall()}
            
            seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
            cursor.execute("""
                SELECT date(created_at) as day, COUNT(*) as count
                FROM lead_records
                WHERE created_at >= ?
                GROUP BY day
                ORDER BY day
            """, (seven_days_ago,))
            daily_counts = {row['day']: row['count'] for row in cursor.fetchall()}
            
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM lead_records
                WHERE appointment_time IS NOT NULL
            """)
            appointments = cursor.fetchone()['count']
        
        appointment_rate = (appointments / total_leads) if total_leads > 0 else 0
        
        return {
            'total_leads': total_leads,
            'by_business_type': by_business_type,
            'daily_counts': daily_counts,
            'appointment_count': appointments,
            'appointment_rate': appointment_rate
        } 