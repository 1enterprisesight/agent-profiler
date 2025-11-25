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

from app.database import get_db_session
from app.auth import get_current_user
from app.models import Conversation, ConversationMessage
from app.agents.base import AgentMessage, AgentStatus
from app.agents.orchestrator import OrchestratorAgent
from app.agents.data_ingestion import DataIngestionAgent
from app.agents.sql_analytics import SQLAnalyticsAgent
from app.agents.semantic_search import SemanticSearchAgent
from app.agents.pattern_recognition import PatternRecognitionAgent
from app.agents.segmentation import SegmentationAgent
from app.agents.benchmark import BenchmarkAgent
from app.agents.recommendation import RecommendationAgent


logger = structlog.get_logger()
router = APIRouter(prefix="/api/conversations", tags=["conversations"])

# Initialize all agents
data_ingestion = DataIngestionAgent()
sql_analytics = SQLAnalyticsAgent()
semantic_search = SemanticSearchAgent()
pattern_recognition = PatternRecognitionAgent()
segmentation = SegmentationAgent()
benchmark = BenchmarkAgent()
recommendation = RecommendationAgent()

# Build agent registry
agent_registry = {
    "data_ingestion": data_ingestion,
    "sql_analytics": sql_analytics,
    "semantic_search": semantic_search,
    "pattern_recognition": pattern_recognition,
    "segmentation": segmentation,
    "benchmark": benchmark,
    "recommendation": recommendation,
}

# Initialize orchestrator with complete agent registry
orchestrator = OrchestratorAgent(agent_registry=agent_registry)


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
    db: AsyncSession = Depends(get_db_session),
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
            session_id=conversation.id,  # Changed from conversation_id
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

        # Orchestrate multi-agent workflow
        orchestrator_message = AgentMessage(
            agent_type="orchestrator",
            action="orchestrate",
            payload={
                "user_query": request.message,
                "context": request.context or {},
            },
            conversation_id=conversation_id,
        )

        orchestration_response = await orchestrator.execute(
            orchestrator_message,
            db,
            user_id
        )

        if not orchestration_response.is_success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Orchestration failed: {orchestration_response.error}"
            )

        # Extract workflow results
        result = orchestration_response.result
        answer = result.get("answer", "Workflow completed.")
        agents_used = result.get("agents_used", [])
        execution_plan = result.get("execution_plan", {})
        workflow_results = result.get("workflow_results", [])

        logger.info(
            "workflow_completed",
            agents_used=agents_used,
            total_steps=len(workflow_results),
            successful_steps=sum(1 for r in workflow_results if r.get("success"))
        )

        # Format response text
        response_text = answer

        # Save assistant message
        assistant_message = ConversationMessage(
            session_id=conversation.id,  # Changed from conversation_id
            role="assistant",
            content=response_text,
            meta_data={
                "agents_used": agents_used,
                "execution_plan": execution_plan,
                "workflow_results": workflow_results,
                "orchestration_metadata": orchestration_response.metadata,
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
                "agents_used": agents_used,
                "execution_plan": execution_plan,
                "workflow_summary": {
                    "total_steps": len(workflow_results),
                    "successful_steps": sum(1 for r in workflow_results if r.get("success"))
                }
            },
            agent_used="orchestrator",
            status=orchestration_response.status.value,
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
    db: AsyncSession = Depends(get_db_session),
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
    db: AsyncSession = Depends(get_db_session),
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
            .where(ConversationMessage.session_id == conversation.id)
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
                    "metadata": msg.meta_data,
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
