"""
Conversation API Endpoints
Handles chat interface and agent interactions
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import uuid

import structlog

from app.database import get_db
from app.auth import get_current_user
from app.models import Conversation, ConversationMessage
from app.agents.base import AgentMessage, AgentStatus
from app.agents.orchestrator import OrchestratorAgent
from app.agents.data_ingestion import DataIngestionAgent


logger = structlog.get_logger()
router = APIRouter(prefix="/api/conversations", tags=["conversations"])

# Initialize agents
orchestrator = OrchestratorAgent()
data_ingestion = DataIngestionAgent()


class ChatRequest(BaseModel):
    """Request to send a message in a conversation"""
    message: str
    conversation_id: Optional[str] = None
    context: Optional[dict] = None


class ChatResponse(BaseModel):
    """Response from chat"""
    conversation_id: str
    message_id: str
    response: dict
    agent_used: str
    status: str
    timestamp: str


class ConversationSummary(BaseModel):
    """Summary of a conversation"""
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and get agent response

    The orchestrator will route the request to the appropriate specialized agent
    """
    try:
        conversation_id = request.conversation_id or str(uuid.uuid4())

        # Get or create conversation
        if request.conversation_id:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == uuid.UUID(conversation_id),
                    Conversation.user_id == user_id
                )
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
        else:
            # Create new conversation
            conversation = Conversation(
                id=uuid.UUID(conversation_id),
                user_id=user_id,
                title=request.message[:100],  # Use first message as title
            )
            db.add(conversation)

        # Save user message
        user_message = ConversationMessage(
            conversation_id=conversation.id,
            user_id=user_id,
            role="user",
            content=request.message,
        )
        db.add(user_message)
        await db.flush()

        logger.info(
            "chat_request_received",
            conversation_id=conversation_id,
            user_id=user_id,
            message=request.message[:100],
        )

        # Route request through orchestrator
        orchestrator_message = AgentMessage(
            agent_type="orchestrator",
            action="route",
            payload={
                "user_query": request.message,
                "context": request.context or {},
            },
            conversation_id=conversation_id,
        )

        routing_response = await orchestrator.execute(
            orchestrator_message,
            db,
            user_id
        )

        if not routing_response.is_success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Orchestrator failed: {routing_response.error}"
            )

        # Get routing decision
        target_agent_name = routing_response.result.get("target_agent")
        action = routing_response.result.get("action")
        parameters = routing_response.result.get("parameters", {})
        reasoning = routing_response.result.get("reasoning")

        logger.info(
            "request_routed",
            target_agent=target_agent_name,
            action=action,
            reasoning=reasoning,
        )

        # Execute target agent
        target_agent = _get_agent_instance(target_agent_name)

        if not target_agent:
            # Agent not yet implemented
            agent_response_text = f"I understand you want to {reasoning}. The {target_agent_name} agent will be available in an upcoming phase."

            # Save assistant message
            assistant_message = ConversationMessage(
                conversation_id=conversation.id,
                user_id=user_id,
                role="assistant",
                content=agent_response_text,
                metadata={
                    "target_agent": target_agent_name,
                    "action": action,
                    "status": "pending_implementation"
                }
            )
            db.add(assistant_message)
            await db.commit()

            return ChatResponse(
                conversation_id=conversation_id,
                message_id=str(assistant_message.id),
                response={
                    "text": agent_response_text,
                    "target_agent": target_agent_name,
                    "action": action,
                    "reasoning": reasoning,
                },
                agent_used=target_agent_name,
                status="pending_implementation",
                timestamp=datetime.utcnow().isoformat(),
            )

        # Execute the target agent
        agent_message = AgentMessage(
            agent_type=target_agent_name,
            action=action,
            payload=parameters,
            conversation_id=conversation_id,
        )

        agent_response = await target_agent.execute(agent_message, db, user_id)

        # Format response text
        if agent_response.is_success:
            response_text = _format_agent_response(
                target_agent_name,
                action,
                agent_response.result
            )
        else:
            response_text = f"Sorry, I encountered an error: {agent_response.error}"

        # Save assistant message
        assistant_message = ConversationMessage(
            conversation_id=conversation.id,
            user_id=user_id,
            role="assistant",
            content=response_text,
            metadata={
                "target_agent": target_agent_name,
                "action": action,
                "agent_response": agent_response.to_dict(),
            }
        )
        db.add(assistant_message)

        # Update conversation
        conversation.updated_at = datetime.utcnow()
        await db.commit()

        return ChatResponse(
            conversation_id=conversation_id,
            message_id=str(assistant_message.id),
            response={
                "text": response_text,
                "details": agent_response.result,
                "reasoning": reasoning,
            },
            agent_used=target_agent_name,
            status=agent_response.status.value,
            timestamp=datetime.utcnow().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "chat_failed",
            error=str(e),
            user_id=user_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {str(e)}"
        )


@router.get("/", response_model=List[ConversationSummary])
async def list_conversations(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all conversations for the current user
    """
    try:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        conversations = result.scalars().all()

        return [
            ConversationSummary(
                id=str(conv.id),
                title=conv.title,
                created_at=conv.created_at.isoformat(),
                updated_at=conv.updated_at.isoformat(),
                message_count=len(conv.messages) if conv.messages else 0,
            )
            for conv in conversations
        ]

    except Exception as e:
        logger.error(
            "list_conversations_failed",
            error=str(e),
            user_id=user_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list conversations: {str(e)}"
        )


@router.get("/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all messages in a conversation
    """
    try:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == uuid.UUID(conversation_id),
                Conversation.user_id == user_id
            )
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.created_at.asc())
        )
        messages = result.scalars().all()

        return {
            "conversation_id": conversation_id,
            "title": conversation.title,
            "messages": [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "metadata": msg.metadata,
                    "created_at": msg.created_at.isoformat(),
                }
                for msg in messages
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_messages_failed",
            error=str(e),
            conversation_id=conversation_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get messages: {str(e)}"
        )


def _get_agent_instance(agent_name: str):
    """Get agent instance by name"""
    agents = {
        "data_ingestion": data_ingestion,
        # Will add more agents in later phases
    }
    return agents.get(agent_name)


def _format_agent_response(agent_name: str, action: str, result: dict) -> str:
    """Format agent response into human-readable text"""

    if agent_name == "data_ingestion" and action == "upload_csv":
        ingested = result.get("records_ingested", 0)
        failed = result.get("records_failed", 0)
        total = result.get("total_rows", 0)

        return f"Successfully processed CSV file! Ingested {ingested} out of {total} records. {failed} records failed validation."

    # Default formatting
    return f"Action '{action}' completed successfully. {result.get('message', '')}"
