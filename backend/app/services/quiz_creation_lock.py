"""
Quiz Creation Lock Service

Manages locks for active quiz creation to prevent race conditions
when page changes occur during quiz generation.
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)


class QuizCreationLock:
    """
    Thread-safe lock service for tracking active quiz creation operations.
    
    This prevents race conditions when:
    - User changes page while quiz is being created
    - Multiple quiz creation requests for the same material
    - State updates during quiz generation
    """
    
    def __init__(self):
        """Initialize the lock service."""
        self._locks: Dict[str, Dict[str, any]] = {}  # material_id -> lock info
        self._lock = threading.Lock()  # Thread lock for thread-safety
        self._default_timeout = timedelta(minutes=5)  # Default lock timeout
    
    def acquire_lock(
        self,
        material_id: str,
        user_id: str,
        start_page: int,
        end_page: int,
        timeout: Optional[timedelta] = None
    ) -> bool:
        """
        Acquire a lock for quiz creation.
        
        Args:
            material_id: Course material ID
            user_id: User ID
            start_page: Starting page number
            end_page: Ending page number
            timeout: Optional lock timeout (default: 5 minutes)
            
        Returns:
            True if lock was acquired, False if already locked
        """
        lock_key = f"{material_id}:{user_id}"
        timeout = timeout or self._default_timeout
        
        with self._lock:
            # Check if lock exists and is still valid
            if lock_key in self._locks:
                lock_info = self._locks[lock_key]
                expires_at = lock_info.get("expires_at")
                
                # Check if lock has expired
                if expires_at and datetime.now() > expires_at:
                    logger.debug(f"Lock expired for {lock_key}, removing")
                    del self._locks[lock_key]
                else:
                    # Lock is still active
                    logger.debug(f"Lock already exists for {lock_key}")
                    return False
            
            # Acquire new lock
            self._locks[lock_key] = {
                "material_id": material_id,
                "user_id": user_id,
                "start_page": start_page,
                "end_page": end_page,
                "created_at": datetime.now(),
                "expires_at": datetime.now() + timeout
            }
            
            logger.info(
                f"Lock acquired for quiz creation: {lock_key} "
                f"(pages {start_page}-{end_page}, expires in {timeout})"
            )
            return True
    
    def release_lock(self, material_id: str, user_id: str) -> bool:
        """
        Release a lock for quiz creation.
        
        Args:
            material_id: Course material ID
            user_id: User ID
            
        Returns:
            True if lock was released, False if not found
        """
        lock_key = f"{material_id}:{user_id}"
        
        with self._lock:
            if lock_key in self._locks:
                del self._locks[lock_key]
                logger.info(f"Lock released for {lock_key}")
                return True
            
            logger.debug(f"Lock not found for {lock_key}")
            return False
    
    def is_locked(self, material_id: str, user_id: str) -> bool:
        """
        Check if a lock exists for quiz creation.
        
        Args:
            material_id: Course material ID
            user_id: User ID
            
        Returns:
            True if lock exists and is valid, False otherwise
        """
        lock_key = f"{material_id}:{user_id}"
        
        with self._lock:
            if lock_key not in self._locks:
                return False
            
            lock_info = self._locks[lock_key]
            expires_at = lock_info.get("expires_at")
            
            # Check if lock has expired
            if expires_at and datetime.now() > expires_at:
                logger.debug(f"Lock expired for {lock_key}, removing")
                del self._locks[lock_key]
                return False
            
            return True
    
    def get_lock_info(self, material_id: str, user_id: str) -> Optional[Dict[str, any]]:
        """
        Get information about an active lock.
        
        Args:
            material_id: Course material ID
            user_id: User ID
            
        Returns:
            Lock information dict or None if no lock exists
        """
        lock_key = f"{material_id}:{user_id}"
        
        with self._lock:
            if lock_key not in self._locks:
                return None
            
            lock_info = self._locks[lock_key]
            expires_at = lock_info.get("expires_at")
            
            # Check if lock has expired
            if expires_at and datetime.now() > expires_at:
                logger.debug(f"Lock expired for {lock_key}, removing")
                del self._locks[lock_key]
                return None
            
            # Return copy of lock info
            return {
                "material_id": lock_info["material_id"],
                "user_id": lock_info["user_id"],
                "start_page": lock_info["start_page"],
                "end_page": lock_info["end_page"],
                "created_at": lock_info["created_at"],
                "expires_at": lock_info["expires_at"]
            }
    
    def cleanup_expired_locks(self) -> int:
        """
        Clean up expired locks.
        
        Returns:
            Number of locks removed
        """
        removed = 0
        
        with self._lock:
            now = datetime.now()
            expired_keys = [
                key for key, info in self._locks.items()
                if info.get("expires_at") and now > info["expires_at"]
            ]
            
            for key in expired_keys:
                del self._locks[key]
                removed += 1
            
            if removed > 0:
                logger.debug(f"Cleaned up {removed} expired locks")
        
        return removed


# Global singleton instance
_quiz_creation_lock: Optional[QuizCreationLock] = None


def get_quiz_creation_lock() -> QuizCreationLock:
    """
    Get the global QuizCreationLock instance.
    
    Returns:
        QuizCreationLock singleton instance
    """
    global _quiz_creation_lock
    
    if _quiz_creation_lock is None:
        _quiz_creation_lock = QuizCreationLock()
    
    return _quiz_creation_lock
