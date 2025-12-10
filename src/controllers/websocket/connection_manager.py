"""WebSocket connection manager for interview sessions."""

import logging
from uuid import UUID

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections for interviews."""

    def __init__(self):
        # interview_id → websocket
        self.active_connections: dict[UUID, WebSocket] = {}

    async def connect(self, interview_id: UUID, websocket: WebSocket):
        """Accept and register WebSocket connection.

        Args:
            interview_id: Interview UUID
            websocket: WebSocket connection
        """
        await websocket.accept()
        self.active_connections[interview_id] = websocket
        logger.info(f"WebSocket connected for interview {interview_id}")

    def disconnect(self, interview_id: UUID):
        """Remove connection.

        Args:
            interview_id: Interview UUID
        """
        if interview_id in self.active_connections:
            del self.active_connections[interview_id]
            logger.info(f"WebSocket disconnected for interview {interview_id}")

    async def send_message(self, interview_id: UUID, message: dict):
        """Send message to specific interview connection.

        Args:
            interview_id: Interview UUID
            message: Message dictionary to send
        """
        websocket = self.active_connections.get(interview_id)
        if websocket:
            await websocket.send_json(message)

            # Log WebSocket address for interview_complete messages
            if message.get("type") == "interview_complete":
                try:
                    client_host = websocket.client.host if websocket.client else "unknown"
                    client_port = websocket.client.port if websocket.client else "unknown"
                    ws_path = websocket.url.path if hasattr(websocket, "url") and websocket.url else "unknown"
                    ws_url = f"ws://{client_host}:{client_port}{ws_path}"
                    logger.info(
                        f"Sent interview feedback via WebSocket to {ws_url} for interview {interview_id}",
                        extra={
                            "interview_id": str(interview_id),
                            "websocket_url": ws_url,
                            "websocket_host": client_host,
                            "websocket_port": str(client_port),
                            "websocket_path": ws_path,
                            "message_type": "interview_complete",
                            "delivery_method": "websocket",
                        },
                    )
                except Exception as e:
                    # Fallback logging if WebSocket info unavailable
                    logger.info(
                        f"Sent interview feedback via WebSocket for interview {interview_id} (address unavailable: {e})",
                        extra={
                            "interview_id": str(interview_id),
                            "message_type": "interview_complete",
                            "delivery_method": "websocket",
                        },
                    )

    async def broadcast(self, message: dict):
        """Send message to all connections.

        Args:
            message: Message dictionary to broadcast
        """
        for websocket in self.active_connections.values():
            await websocket.send_json(message)


# Global instance
manager = ConnectionManager()
