"""
Script selector module for choosing appropriate telemarketing scripts based on business type.
"""

import os
import logging
from pathlib import Path
from typing import Tuple, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Define scripts directory
SCRIPTS_DIR = Path(__file__).parent.parent / "data" / "scripts"

# Mapping of business types to script files
BUSINESS_SCRIPTS = {
    "making_money": ("making_money_script.md", "money_making"),
    "saving_money": ("saving_money_script.md", "money_saving"),
    "plumbing": ("plumbing_script.md", "service"),
    "hvac": ("hvac_script.md", "service"),
    "roofing": ("roofing_script.md", "service"),
    "solar": ("solar_script.md", "service"),
    "insurance": ("insurance_script.md", "service"),
    "home_security": ("home_security_script.md", "service"),
    "default": ("making_money_script.md", "money_making")  # Default script
}

def get_script_for_business_type(business_type: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Get the appropriate script file path for a business type.
    
    Args:
        business_type: The type of business (e.g., plumbing, hvac)
        
    Returns:
        Tuple of (script_path, script_type) or (None, None) if not found
    """
    # Handle special case for saving_money script
    if business_type.lower() == "(s)" or business_type.lower() == "saving_money":
        script_filename, script_type = BUSINESS_SCRIPTS["saving_money"]
    else:
        # Get script info or use default if not found
        script_info = BUSINESS_SCRIPTS.get(business_type.lower(), BUSINESS_SCRIPTS["default"])
        script_filename, script_type = script_info
    
    # Construct full path to script file
    script_path = SCRIPTS_DIR / script_filename
    
    # Check if script file exists
    if not script_path.exists():
        logger.warning(f"Script file not found: {script_path}")
        return None, None
        
    return str(script_path), script_type 