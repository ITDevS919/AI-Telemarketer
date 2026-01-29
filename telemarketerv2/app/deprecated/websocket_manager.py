# This file has been moved from telemarketerv2/app/websocket_manager.py
# Its functionality is superseded by main.py's WebSocket endpoint and ConversationManager.

"""
WebSocket Manager for handling WebSocket connections in the telemarketer application.
"""

import logging
from typing import Dict, Optional, Any
# from fastapi import WebSocket # Commented out

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connections for the telemarketer application."""
    
    def __init__(self):
        """Initialize the WebSocket manager."""
        self.active_connections: Dict[str, Any] = {}
        
    async def connect(self, call_sid: str, websocket: Any) -> None:
        """Connect a new WebSocket for a call."""
        # await websocket.accept() # This is handled by FastAPI endpoint directly
        self.active_connections[call_sid] = websocket
        logger.info(f"WebSocket connected for call {call_sid} (logic moved)")
        
    async def disconnect(self, call_sid: str) -> None:
        """Disconnect a WebSocket for a call."""
        if call_sid in self.active_connections:
            try:
                # await self.active_connections[call_sid].close() # This is handled by FastAPI endpoint directly
                logger.info(f"WebSocket close attempt for call {call_sid} (logic moved)")
            except Exception as e:
                logger.error(f"Error closing WebSocket for call {call_sid} (logic moved): {e}")
            finally:
                del self.active_connections[call_sid]
                logger.info(f"WebSocket disconnected for call {call_sid} (logic moved)")
                
    def get_connection(self, call_sid: str) -> Optional[Any]:
        """Get the WebSocket connection for a call."""
        return self.active_connections.get(call_sid)
        
    async def send_message(self, call_sid: str, message: str) -> bool:
        """Send a message through a WebSocket connection."""
        websocket = self.get_connection(call_sid)
        if websocket and hasattr(websocket, 'send_text'):
            try:
                await websocket.send_text(message)
                return True
            except Exception as e:
                logger.error(f"Error sending message to call {call_sid}: {e}")
                return False
        elif websocket:
            logger.error(f"WebSocket object for call {call_sid} does not have send_text method.")
            return False
        return False 