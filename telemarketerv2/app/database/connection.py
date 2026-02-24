"""
Database connection adapter for SQLite and PostgreSQL support.

This module provides a unified interface for database operations,
supporting both SQLite (for development) and PostgreSQL (for production).
"""

import os
import logging
from typing import Optional, Union, Any, Dict
from urllib.parse import urlparse

logger = logging.getLogger("database.connection")

# Try to import database drivers
try:
    import sqlite3
    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False
    logger.warning("SQLite not available")

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    logger.warning("PostgreSQL driver (psycopg2) not available")


class DatabaseAdapter:
    """
    Database adapter that supports both SQLite and PostgreSQL.
    
    Automatically detects the database type from the connection string:
    - SQLite: file path (e.g., "telemarketer_calls.db") or "sqlite:///path/to/db.db"
    - PostgreSQL: connection string (e.g., "postgresql://user:pass@host:port/dbname")
    """
    
    def __init__(self, connection_string: str):
        """
        Initialize database adapter.
        
        Args:
            connection_string: Database connection string or file path
        """
        self.connection_string = connection_string
        self.db_type = self._detect_db_type(connection_string)
        self.conn = None
        
        logger.info(f"Database adapter initialized for {self.db_type}")
    
    def _detect_db_type(self, conn_str: str) -> str:
        """Detect database type from connection string"""
        # Check if it's a PostgreSQL connection string
        if conn_str.startswith("postgresql://") or conn_str.startswith("postgres://"):
            if not POSTGRESQL_AVAILABLE:
                raise ImportError("psycopg2 is required for PostgreSQL. Install it with: pip install psycopg2-binary")
            return "postgresql"
        
        # Check if it's a SQLite connection string
        if conn_str.startswith("sqlite:///"):
            if not SQLITE_AVAILABLE:
                raise ImportError("SQLite is not available")
            return "sqlite"
        
        # Default to SQLite for file paths
        if not conn_str.startswith(("http://", "https://", "postgresql://", "postgres://")):
            if not SQLITE_AVAILABLE:
                raise ImportError("SQLite is not available")
            return "sqlite"
        
        raise ValueError(f"Unsupported database connection string format: {conn_str}")
    
    def connect(self):
        """Create and return a database connection"""
        if self.conn:
            return self.conn
        
        if self.db_type == "sqlite":
            # SQLite connection
            db_path = self.connection_string
            if db_path.startswith("sqlite:///"):
                db_path = db_path.replace("sqlite:///", "")
            
            # Create directory if needed
            import os
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
            
            self.conn = sqlite3.connect(db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to SQLite database: {db_path}")
            
        elif self.db_type == "postgresql":
            # PostgreSQL connection
            self.conn = psycopg2.connect(self.connection_string)
            logger.info("Connected to PostgreSQL database")
        
        return self.conn
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")
    
    def cursor(self):
        """
        Return a new cursor. Use this so code can call db_conn.cursor() when
        db_conn is a DatabaseAdapter. For PostgreSQL, uses RealDictCursor so
        rows are dict-like (column names as keys).
        """
        if not self.conn:
            self.connect()
        if self.db_type == "postgresql" and POSTGRESQL_AVAILABLE:
            return self.conn.cursor(cursor_factory=RealDictCursor)
        return self.conn.cursor()

    def get_parameter_placeholder(self) -> str:
        """Get the parameter placeholder for the database type"""
        if self.db_type == "sqlite":
            return "?"
        elif self.db_type == "postgresql":
            return "%s"
        raise ValueError(f"Unknown database type: {self.db_type}")
    
    def format_query(self, query: str) -> str:
        """
        Format a query with parameter placeholders for the current database type.
        
        Args:
            query: SQL query with ? placeholders (SQLite style)
            
        Returns:
            Query with appropriate placeholders for the database type
        """
        if self.db_type == "postgresql":
            # Convert ? placeholders to %s for PostgreSQL
            parts = query.split("?")
            if len(parts) > 1:
                # Replace ? with numbered placeholders %s
                result = parts[0]
                for i in range(1, len(parts)):
                    result += "%s" + parts[i]
                return result
        return query
    
    def execute(self, query: str, params: tuple = ()) -> Any:
        """
        Execute a query and return the cursor.
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            Database cursor
        """
        if not self.conn:
            self.connect()
        
        # Format query for the database type
        formatted_query = self.format_query(query)
        
        cursor = self.conn.cursor()
        cursor.execute(formatted_query, params)
        return cursor
    
    def commit(self):
        """Commit the current transaction"""
        if self.conn:
            self.conn.commit()
    
    def rollback(self):
        """Rollback the current transaction"""
        if self.conn:
            self.conn.rollback()
    
    def row_to_dict(self, row: Any) -> Dict:
        """
        Convert a database row to a dictionary.
        
        Args:
            row: Database row object
            
        Returns:
            Dictionary representation of the row
        """
        if self.db_type == "sqlite":
            # SQLite Row objects can be converted to dict directly
            return dict(row)
        elif self.db_type == "postgresql":
            # PostgreSQL RealDictCursor returns dict-like objects
            if hasattr(row, 'keys'):
                return dict(row)
            return dict(row)
        return dict(row)
    
    def get_date_function(self) -> str:
        """Get the date function name for the database type"""
        if self.db_type == "sqlite":
            return "date"
        elif self.db_type == "postgresql":
            return "DATE"
        return "date"
    
    def create_tables(self, schema_sql: str):
        """
        Execute schema SQL to create tables.
        
        Args:
            schema_sql: SQL schema definition
        """
        if not self.conn:
            self.connect()
        
        cursor = self.conn.cursor()
        
        # PostgreSQL uses different syntax for some things
        if self.db_type == "postgresql":
            # Replace SQLite-specific syntax with PostgreSQL equivalents
            schema_sql = schema_sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            schema_sql = schema_sql.replace("TEXT", "VARCHAR")
            # PostgreSQL doesn't need IF NOT EXISTS in the same way, but we'll keep it
            # Actually, PostgreSQL supports IF NOT EXISTS in CREATE TABLE
        
        # Execute schema
        cursor.execute(schema_sql)
        self.conn.commit()
        cursor.close()
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def get_database_adapter(connection_string: Optional[str] = None) -> DatabaseAdapter:
    """
    Get a database adapter instance.
    
    Args:
        connection_string: Database connection string. If None, reads from environment.
        
    Returns:
        DatabaseAdapter instance
    """
    if connection_string is None:
        # Try to get from environment
        connection_string = os.getenv("DATABASE_URL")
        
        if not connection_string:
            # Fall back to SQLite default
            connection_string = os.getenv("DB_PATH", "telemarketer_calls.db")
    
    return DatabaseAdapter(connection_string)
