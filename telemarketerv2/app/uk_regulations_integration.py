"""
UK Call Regulations Integration

This module integrates the UK call regulations into the telemarketer system,
providing a unified interface for checking call permissions and tracking calls.
"""

import asyncio
import datetime
import logging
import os
from typing import Dict, List, Optional, Tuple, Any

from .uk_call_regulations import UKCallRegulator, ViolationType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uk_regulations_integration")

class UKRegulationsManager:
    """
    Manager for UK call regulations integration
    
    Handles the integration between the telemarketer system and the
    UK call regulations enforcement.
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls, db_path: str = None, tps_path: str = None) -> 'UKRegulationsManager':
        """
        Get singleton instance of the regulations manager.
        
        Args:
            db_path: Path to the database file
            tps_path: Path to the TPS registry file
            
        Returns:
            UKRegulationsManager instance
        """
        if cls._instance is None:
            cls._instance = UKRegulationsManager(db_path, tps_path)
        return cls._instance
    
    def __init__(self, db_path: str = None, tps_path: str = None):
        """
        Initialize the regulations manager.
        
        Args:
            db_path: Path to the database file
            tps_path: Path to the TPS registry file
        """
        self.db_path = db_path or os.environ.get(
            "UK_REGULATIONS_DB_PATH", 
            "uk_call_regulations.db"
        )
        
        self.tps_path = tps_path or os.environ.get(
            "TPS_REGISTRY_PATH", 
            os.path.join(os.path.dirname(__file__), "data", "tps_numbers.txt")
        )
        
        self.regulator = None
        self.initialized = False
        self.initialization_lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize the regulations manager and underlying components"""
        async with self.initialization_lock:
            if self.initialized:
                return
                
            logger.info("Initializing UK regulations manager...")
            
            # Create regulator
            self.regulator = UKCallRegulator(
                db_path=self.db_path,
                tps_path=self.tps_path
            )
            
            # Initialize database
            self.regulator.ensure_db_ready_and_get_conn()
            
            self.initialized = True
            logger.info("UK regulations manager initialized successfully")
    
    async def check_call_permitted(self, phone_number: str, caller_id: str) -> Tuple[bool, str, str]:
        """
        Check if a call is permitted under UK regulations.
        
        Args:
            phone_number: The phone number to call
            caller_id: The caller ID to use
            
        Returns:
            Tuple of (permitted, reason, violation_type)
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            result = self.regulator.can_call_number(phone_number, caller_id)
            
            permitted = result["permitted"]
            reason = result.get("reason", "")
            violation_type = result.get("violation_type", "")
            
            if not permitted:
                logger.info(f"Call to {phone_number} not permitted: {reason}")
                
            return permitted, reason, violation_type
            
        except Exception as e:
            logger.error(f"Error checking call permission: {e}")
            return False, f"Regulation check error: {str(e)}", "ERROR"
    
    async def track_call(self, phone_number: str, caller_id: str, call_id: str):
        """
        Track a call for regulatory compliance.
        
        Args:
            phone_number: The phone number called
            caller_id: The caller ID used
            call_id: The call ID
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            self.regulator.track_call(phone_number, caller_id, call_id)
            logger.info(f"Tracked call {call_id} to {phone_number}")
            
        except Exception as e:
            logger.error(f"Error tracking call: {e}")
    
    async def get_call_history(self, phone_number: str = None, 
                            limit: int = 50) -> List[Dict]:
        """
        Get call history for regulatory tracking.
        
        Args:
            phone_number: Optional phone number to filter by
            limit: Maximum number of records to return
            
        Returns:
            List of call history records
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            return self.regulator.get_call_history(phone_number, limit)
            
        except Exception as e:
            logger.error(f"Error getting call history: {e}")
            return []
    
    async def get_regulation_status(self) -> Dict:
        """
        Get current status of the regulation system.
        
        Returns:
            Dictionary with regulation status information
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            status = {
                "initialized": self.initialized,
                "db_path": self.db_path,
                "tps_path": self.tps_path,
                "tps_loaded": self.regulator.tps_loaded if self.regulator else False,
                "tps_count": len(self.regulator.tps_numbers) if self.regulator and hasattr(self.regulator, "tps_numbers") else 0,
                "current_time": datetime.datetime.now().isoformat(),
                "current_day": datetime.datetime.now().strftime("%A"),
                "current_hour": datetime.datetime.now().hour
            }
            
            # Add calling hours status
            status["calling_hours"] = self.regulator.get_calling_hours() if self.regulator else {}
            status["within_calling_hours"] = self.regulator.is_within_calling_hours() if self.regulator else False
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting regulation status: {e}")
            return {
                "initialized": self.initialized,
                "error": str(e)
            }
    
    async def cleanup(self):
        """Clean up resources used by the regulations manager"""
        if self.regulator:
            self.regulator.close_db()
            self.regulator = None
            
        self.initialized = False
        logger.info("UK regulations manager cleaned up")

def get_regulations_manager(db_path: str = None, tps_path: str = None) -> UKRegulationsManager:
    """
    Get the regulations manager instance.
    
    Args:
        db_path: Path to the database file
        tps_path: Path to the TPS registry file
        
    Returns:
        UKRegulationsManager instance
    """
    return UKRegulationsManager.get_instance(db_path, tps_path)

# Example of how to use this in the telemarketer system
async def example_usage():
    """Example of how to use the UK regulations integration"""
    
    # Get the regulations manager
    regulations = get_regulations_manager()
    
    # Initialize it
    await regulations.initialize()
    
    # Check if a call is permitted
    phone_number = "+447123456789"
    caller_id = "+441234567890"
    permitted, reason, violation = await regulations.check_call_permitted(phone_number, caller_id)
    
    if permitted:
        print(f"Call to {phone_number} is permitted: {reason}")
        
        # Record the call attempt
        call_sid = "CA123456789"
        await regulations.track_call(phone_number, caller_id, call_sid)
        
        # Get call history
        history = await regulations.get_call_history(phone_number)
        print(f"Call history: {history}")
    else:
        print(f"Call to {phone_number} is NOT permitted: {reason} (violation: {violation})")
        
    # Clean up
    await regulations.cleanup()

if __name__ == "__main__":
    # Run the example
    asyncio.run(example_usage()) 