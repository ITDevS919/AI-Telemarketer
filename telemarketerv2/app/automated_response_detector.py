"""
Automated Response Detector for AI Telemarketer

This module provides functionality to detect automated responses from voicemail
systems, answering machines, and other automated call handling systems.
"""

import logging
import re
from typing import Dict, Tuple, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("automated_response_detector")

class AutomatedResponseDetector:
    """
    Detector for automated responses during outbound calls.
    
    This class analyzes text responses to determine if they are from
    automated systems like voicemail, IVR, or call screening systems.
    """
    
    def __init__(self):
        """Initialize the automated response detector."""
        # Common voicemail message patterns
        self.voicemail_patterns = [
            r"(?i)voicemail",
            r"(?i)leave a message",
            r"(?i)after the tone",
            r"(?i)leave your message",
            r"(?i)not available",
            r"(?i)unavailable",
            r"(?i)beep",
            r"(?i)can't come to the phone",
            r"(?i)please record your message",
            r"(?i)at the tone"
        ]
        
        # IVR/Auto-attendant patterns
        self.ivr_patterns = [
            r"(?i)press \d",
            r"(?i)dial \d",
            r"(?i)for \w+, press \d",
            r"(?i)main menu",
            r"(?i)options",
            r"(?i)automated",
            r"(?i)connecting you",
            r"(?i)if you know your party's extension",
            r"(?i)please hold",
            r"(?i)following options"
        ]
        
        # Call screening patterns
        self.screening_patterns = [
            r"(?i)who's calling",
            r"(?i)purpose of your call",
            r"(?i)calling regarding",
            r"(?i)calling about",
            r"(?i)calling from",
            r"(?i)before connecting",
            r"(?i)can I ask who's calling",
            r"(?i)may I tell them who's calling",
            r"(?i)who shall I say is calling"
        ]
        
        # Non-interactive response patterns
        self.non_interactive_patterns = [
            r"(?i)thank you for calling",
            r"(?i)business hours",
            r"(?i)we are open",
            r"(?i)we are closed",
            r"(?i)our office is",
            r"(?i)call back",
            r"(?i)we're currently",
            r"(?i)try again later",
            r"(?i)temporarily unavailable"
        ]
    
    def analyze_response(self, response_text: str) -> Dict[str, Any]:
        """
        Analyze a text response to determine if it is automated.
        
        Args:
            response_text: The text response to analyze
            
        Returns:
            Dictionary with analysis results including:
            - is_automated: Boolean indicating if response is automated
            - response_type: Type of response (voicemail, ivr, screening, human)
            - confidence: Confidence level from 0.0 to 1.0
            - detected_patterns: List of detected patterns
        """
        logger.info(f"Analyzing response: {response_text[:50]}...")
        
        # Check for voicemail patterns
        voicemail_matches = self._check_patterns(response_text, self.voicemail_patterns)
        
        # Check for IVR patterns
        ivr_matches = self._check_patterns(response_text, self.ivr_patterns)
        
        # Check for screening patterns
        screening_matches = self._check_patterns(response_text, self.screening_patterns)
        
        # Check for non-interactive patterns
        non_interactive_matches = self._check_patterns(response_text, self.non_interactive_patterns)
        
        # Determine total matches and confidence
        total_matches = len(voicemail_matches) + len(ivr_matches) + len(screening_matches) + len(non_interactive_matches)
        
        # Calculate confidence (0.0 to 1.0)
        # More matches = higher confidence, max out at 5 matches
        confidence = min(total_matches / 5.0, 1.0)
        
        # Determine if this is an automated response (confidence > 0.3)
        is_automated = confidence > 0.3
        
        # Determine response type based on which category has most matches
        response_type = "human"
        if is_automated:
            pattern_counts = {
                "voicemail": len(voicemail_matches),
                "ivr": len(ivr_matches),
                "screening": len(screening_matches),
                "non_interactive": len(non_interactive_matches)
            }
            response_type = max(pattern_counts, key=pattern_counts.get)
        
        # Compile all detected patterns
        detected_patterns = voicemail_matches + ivr_matches + screening_matches + non_interactive_matches
        
        # Log results
        logger.info(f"Response analysis: is_automated={is_automated}, type={response_type}, confidence={confidence:.2f}")
        
        return {
            "is_automated": is_automated,
            "response_type": response_type,
            "confidence": confidence,
            "detected_patterns": detected_patterns,
            "voicemail_detected": len(voicemail_matches) > 0,
            "ivr_detected": len(ivr_matches) > 0,
            "screening_detected": len(screening_matches) > 0,
            "non_interactive_detected": len(non_interactive_matches) > 0
        }
    
    def should_hang_up(self, response_text: str) -> Tuple[bool, str]:
        """
        Determine if a call should be hung up based on the response.
        
        Args:
            response_text: The text response to analyze
            
        Returns:
            Tuple of (should_hang_up, reason)
        """
        analysis = self.analyze_response(response_text)
        
        # Hang up if it's a voicemail
        if analysis["voicemail_detected"] and analysis["confidence"] > 0.5:
            return True, "Voicemail detected"
        
        # Hang up if it's a non-interactive message with high confidence
        if analysis["non_interactive_detected"] and analysis["confidence"] > 0.7:
            return True, "Non-interactive message detected"
        
        # Hang up if it's an IVR with high confidence
        if analysis["ivr_detected"] and analysis["confidence"] > 0.8:
            return True, "IVR system detected"
        
        # Don't hang up on screening systems - we want to get through
        if analysis["screening_detected"] and not analysis["voicemail_detected"]:
            return False, "Call screening detected - continuing call"
        
        # Default: don't hang up
        return False, "No automatic hang up criteria met"
    
    def is_human_response(self, response_text: str) -> bool:
        """
        Determine if a response is likely from a human.
        
        Args:
            response_text: The text response to analyze
            
        Returns:
            Boolean indicating if response is likely human
        """
        analysis = self.analyze_response(response_text)
        return not analysis["is_automated"]
    
    def get_response_type(self, response_text: str) -> str:
        """
        Get the type of response.
        
        Args:
            response_text: The text response to analyze
            
        Returns:
            Response type: 'human', 'voicemail', 'ivr', 'screening', or 'non_interactive'
        """
        analysis = self.analyze_response(response_text)
        return analysis["response_type"]
    
    def analyze_conversation_history(self, conversation_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Analyze an entire conversation history for patterns indicating automated responses.
        
        Args:
            conversation_history: List of conversation entries, each with 'speaker' and 'text'
            
        Returns:
            Dictionary with analysis results and recommendations
        """
        # Get customer responses
        customer_responses = [
            entry["text"] for entry in conversation_history 
            if entry.get("speaker", "").lower() in ["customer", "user", "prospect"]
        ]
        
        if not customer_responses:
            return {
                "is_automated": False,
                "confidence": 0.0,
                "recommendation": "Continue call - no customer responses yet"
            }
        
        # Analyze each response
        analyses = [self.analyze_response(response) for response in customer_responses]
        
        # Calculate average confidence
        avg_confidence = sum(a["confidence"] for a in analyses) / len(analyses)
        
        # Count automated responses
        automated_count = sum(1 for a in analyses if a["is_automated"])
        
        # Determine if conversation is with an automated system
        is_automated = automated_count > 0 and avg_confidence > 0.4
        
        # Generate recommendation
        recommendation = "Continue call - likely human conversation"
        if is_automated:
            if any(a["voicemail_detected"] for a in analyses):
                recommendation = "Terminate call - voicemail detected"
            elif any(a["ivr_detected"] for a in analyses):
                recommendation = "Consider terminating call - IVR system detected"
            elif any(a["non_interactive_detected"] for a in analyses):
                recommendation = "Consider terminating call - non-interactive system detected"
        
        return {
            "is_automated": is_automated,
            "confidence": avg_confidence,
            "automated_responses": automated_count,
            "total_responses": len(customer_responses),
            "recommendation": recommendation
        }
    
    def _check_patterns(self, text: str, patterns: List[str]) -> List[str]:
        """
        Check if text matches any of the provided patterns.
        
        Args:
            text: The text to check
            patterns: List of regex patterns to check against
            
        Returns:
            List of matched patterns
        """
        matches = []
        for pattern in patterns:
            if re.search(pattern, text):
                matches.append(pattern)
        return matches 