"""
Database Migration Helper

Helper functions for executing SQL migrations directly on Supabase database.
Used for schema changes that need to be executed programmatically.
"""

import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from typing import Optional
from urllib.parse import urlparse

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_postgres_connection_string() -> str:
    """
    Extract PostgreSQL connection string from Supabase URL.
    
    Supabase URL format: https://<project-ref>.supabase.co
    We need to construct: postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
    
    However, we need the database password. For now, we'll use the service role key
    in a different way, or we need to parse the SUPABASE_URL differently.
    
    Actually, Supabase provides a direct connection string. Let's check if we have
    a DATABASE_URL environment variable, or we need to construct it from SUPABASE_URL.
    
    Returns:
        PostgreSQL connection string
    """
    # Try to get DATABASE_URL from environment first
    import os
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        return database_url
    
    # If not available, try to construct from SUPABASE_URL
    # This is a fallback - ideally DATABASE_URL should be set
    supabase_url = settings.SUPABASE_URL
    parsed = urlparse(supabase_url)
    
    # Extract project ref from URL (e.g., "abc123" from "https://abc123.supabase.co")
    project_ref = parsed.netloc.split('.')[0]
    
    # We still need the database password - this should be in DATABASE_URL
    # For now, raise an error if DATABASE_URL is not set
    raise ValueError(
        "DATABASE_URL environment variable not set. "
        "Please set DATABASE_URL with format: "
        "postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres"
    )


def execute_sql(sql: str, params: Optional[tuple] = None) -> None:
    """
    Execute SQL statement directly on Supabase database.
    
    Args:
        sql: SQL statement to execute
        params: Optional parameters for parameterized queries
        
    Raises:
        Exception: If SQL execution fails
    """
    conn = None
    try:
        # Get connection string
        conn_string = get_postgres_connection_string()
        
        # Connect to database
        conn = psycopg2.connect(conn_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        # Execute SQL
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        cursor.close()
        
        logger.info(f"SQL executed successfully: {sql[:100]}...")
        
    except Exception as e:
        logger.error(f"Failed to execute SQL: {str(e)}", exc_info=True)
        raise Exception(f"Failed to execute SQL: {str(e)}")
    finally:
        if conn:
            conn.close()


def execute_sql_query(sql: str, params: Optional[tuple] = None) -> list:
    """
    Execute SQL query and return results.
    
    Args:
        sql: SQL SELECT statement
        params: Optional parameters for parameterized queries
        
    Returns:
        List of query results
        
    Raises:
        Exception: If query execution fails
    """
    conn = None
    try:
        # Get connection string
        conn_string = get_postgres_connection_string()
        
        # Connect to database
        conn = psycopg2.connect(conn_string)
        
        # Execute query
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        # Fetch results
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        # Convert to list of dicts
        result_list = [dict(zip(columns, row)) for row in results]
        
        cursor.close()
        
        return result_list
        
    except Exception as e:
        logger.error(f"Failed to execute SQL query: {str(e)}", exc_info=True)
        raise Exception(f"Failed to execute SQL query: {str(e)}")
    finally:
        if conn:
            conn.close()
