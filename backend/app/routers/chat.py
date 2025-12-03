"""
Chat API & WebSocket Endpoints

Handles:
- Chat session management (create, list, delete)
- Message history
- WebSocket for real-time agent communication
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import json
import uuid

import structlog

from app.database import get_db_session
from app.auth import get_current_user, User
from app.agents.base import AgentMessage
from app.agents.orchestrator import OrchestratorAgent


logger = structlog.get_logger()
router = APIRouter(prefix="/api/chat", tags=["chat"])

# Initialize orchestrator
orchestrator = OrchestratorAgent()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""
    message: str
    session_id: Optional[str] = None
    data_source_id: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """Response from chat."""
    session_id: str
    response: str
    needs_clarification: bool = False
    data: Optional[dict] = None
    visualization: Optional[dict] = None
    agent_activities: Optional[List[dict]] = None


class SessionInfo(BaseModel):
    """Session information."""
    id: str
    title: Optional[str]
    created_at: str
    last_activity_at: str
    message_count: int


class MessageInfo(BaseModel):
    """Message information."""
    id: str
    role: str
    content: str
    created_at: str
    metadata: Optional[dict] = None


# =============================================================================
# REST ENDPOINTS
# =============================================================================

@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Send a message and get an AI response.

    The orchestrator will:
    1. Interpret the message in context
    2. Ask for clarification if needed
    3. Route to appropriate agents
    4. Return synthesized insights
    """
    user_id = current_user.user_id
    session_id = request.session_id or str(uuid.uuid4())

    try:
        logger.info(
            "chat_message_received",
            user_id=user_id,
            session_id=session_id,
            message_length=len(request.message),
        )

        # Create orchestrator message
        agent_message = AgentMessage(
            agent_type="orchestrator",
            action="chat",
            payload={
                "message": request.message,
                "data_source_id": request.data_source_id,
            },
            conversation_id=session_id,
        )

        # Execute orchestrator
        response = await orchestrator.execute(agent_message, db, user_id)

        if not response.is_success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Chat processing failed: {response.error}"
            )

        result = response.result

        logger.info(
            "chat_message_processed",
            session_id=session_id,
            needs_clarification=result.get("needs_clarification", False),
        )

        return ChatMessageResponse(
            session_id=session_id,
            response=result.get("response", ""),
            needs_clarification=result.get("needs_clarification", False),
            data=result.get("data"),
            visualization=result.get("visualization"),
            agent_activities=result.get("agent_activities"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("chat_message_error", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat error: {str(e)}"
        )


@router.get("/sessions", response_model=List[SessionInfo])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List all chat sessions for the current user."""
    user_id = current_user.user_id

    try:
        result = await db.execute(
            text("""
                SELECT
                    s.id,
                    s.title,
                    s.created_at,
                    s.last_activity_at,
                    COUNT(m.id) as message_count
                FROM conversation_sessions s
                LEFT JOIN conversation_messages m ON m.session_id = s.id
                WHERE s.user_id = :user_id AND s.is_active = true
                GROUP BY s.id
                ORDER BY s.last_activity_at DESC
                LIMIT 50
            """),
            {"user_id": user_id}
        )
        rows = result.fetchall()

        return [
            SessionInfo(
                id=str(row[0]),
                title=row[1] or "Untitled",
                created_at=row[2].isoformat() if row[2] else "",
                last_activity_at=row[3].isoformat() if row[3] else "",
                message_count=row[4] or 0,
            )
            for row in rows
        ]

    except Exception as e:
        logger.error("list_sessions_error", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}"
        )


@router.get("/sessions/{session_id}/messages", response_model=List[MessageInfo])
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get all messages for a session."""
    user_id = current_user.user_id

    try:
        # Verify session belongs to user
        session_check = await db.execute(
            text("""
                SELECT id FROM conversation_sessions
                WHERE id = :session_id AND user_id = :user_id
            """),
            {"session_id": session_id, "user_id": user_id}
        )
        if not session_check.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        result = await db.execute(
            text("""
                SELECT id, role, content, created_at, meta_data
                FROM conversation_messages
                WHERE session_id = :session_id
                ORDER BY created_at ASC
            """),
            {"session_id": session_id}
        )
        rows = result.fetchall()

        return [
            MessageInfo(
                id=str(row[0]),
                role=row[1],
                content=row[2],
                created_at=row[3].isoformat() if row[3] else "",
                metadata=row[4] if isinstance(row[4], dict) else json.loads(row[4]) if row[4] else None,
            )
            for row in rows
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_messages_error", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get messages: {str(e)}"
        )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete a chat session (soft delete - marks inactive)."""
    user_id = current_user.user_id

    try:
        result = await db.execute(
            text("""
                UPDATE conversation_sessions
                SET is_active = false
                WHERE id = :session_id AND user_id = :user_id
                RETURNING id
            """),
            {"session_id": session_id, "user_id": user_id}
        )
        row = result.fetchone()
        await db.commit()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        return {"status": "success", "message": "Session deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_session_error", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )


@router.post("/sessions/{session_id}/clear")
async def clear_session_context(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Clear all messages in a session (keeps session, clears history)."""
    user_id = current_user.user_id

    try:
        # Verify session belongs to user
        session_check = await db.execute(
            text("""
                SELECT id FROM conversation_sessions
                WHERE id = :session_id AND user_id = :user_id
            """),
            {"session_id": session_id, "user_id": user_id}
        )
        if not session_check.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        # Delete messages
        await db.execute(
            text("""
                DELETE FROM conversation_messages
                WHERE session_id = :session_id
            """),
            {"session_id": session_id}
        )
        await db.commit()

        return {"status": "success", "message": "Session context cleared"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("clear_session_error", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear session: {str(e)}"
        )


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_event(self, session_id: str, event: dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(event)
            except Exception as e:
                logger.warning("websocket_send_error", error=str(e), session_id=session_id)


manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
):
    """
    WebSocket endpoint for real-time chat.

    Events sent to client:
    - {"type": "connected", "session_id": "..."}
    - {"type": "agent_start", "agent": "...", "task": "..."}
    - {"type": "agent_thought", "agent": "...", "content": "..."}
    - {"type": "agent_action", "agent": "...", "action": "..."}
    - {"type": "agent_result", "agent": "...", "result": {...}}
    - {"type": "response", "content": "...", "data": {...}}
    - {"type": "error", "message": "..."}
    """
    await manager.connect(websocket, session_id)

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Get database session
        from app.database import async_session_factory
        async with async_session_factory() as db:
            while True:
                # Wait for message from client
                data = await websocket.receive_json()

                message_type = data.get("type")

                if message_type == "message":
                    user_message = data.get("content", "")
                    user_id = data.get("user_id", "anonymous")
                    data_source_id = data.get("data_source_id")

                    # Send acknowledgment
                    await websocket.send_json({
                        "type": "processing",
                        "message": "Analyzing your request..."
                    })

                    try:
                        # Create orchestrator message
                        agent_message = AgentMessage(
                            agent_type="orchestrator",
                            action="chat",
                            payload={
                                "message": user_message,
                                "data_source_id": data_source_id,
                            },
                            conversation_id=session_id,
                        )

                        # Execute orchestrator
                        response = await orchestrator.execute(agent_message, db, user_id)

                        if response.is_success:
                            result = response.result
                            await websocket.send_json({
                                "type": "response",
                                "content": result.get("response", ""),
                                "needs_clarification": result.get("needs_clarification", False),
                                "data": result.get("data"),
                                "visualization": result.get("visualization"),
                                "agent_activities": result.get("agent_activities"),
                            })
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "message": response.error or "Processing failed"
                            })

                    except Exception as e:
                        logger.error("websocket_processing_error", error=str(e))
                        await websocket.send_json({
                            "type": "error",
                            "message": str(e)
                        })

                elif message_type == "ping":
                    await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        logger.info("websocket_disconnected", session_id=session_id)
    except Exception as e:
        logger.error("websocket_error", error=str(e), session_id=session_id)
        manager.disconnect(session_id)
