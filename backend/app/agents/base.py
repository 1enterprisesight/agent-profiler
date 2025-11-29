"""
Base Agent Framework - Phase D: Self-Describing Agents
Provides abstract base class for all agents with:
- Self-description (get_agent_info, get_capabilities)
- Complete transparency logging (emit_event)
- LLM-driven task interpretation (no hardcoded action routing)
"""

import uuid
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from enum import Enum

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentActivityLog, AgentLLMConversation, TransparencyEvent
from app.config import settings


logger = structlog.get_logger()


class EventType(str, Enum):
    """Transparency event types for agent visibility"""
    RECEIVED = "received"    # Agent received task from orchestrator
    THINKING = "thinking"    # LLM is interpreting/analyzing
    DECISION = "decision"    # Agent chose capability/approach
    ACTION = "action"        # Executing operation
    RESULT = "result"        # Operation completed
    ERROR = "error"          # Something failed


class AgentStatus(str, Enum):
    """Agent execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class AgentMessage:
    """Message passed between agents"""

    def __init__(
        self,
        agent_type: str,
        action: str,
        payload: Dict[str, Any],
        conversation_id: Optional[str] = None,
        parent_message_id: Optional[str] = None,
    ):
        self.id = str(uuid.uuid4())
        self.agent_type = agent_type
        self.action = action
        self.payload = payload
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.parent_message_id = parent_message_id
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            "id": self.id,
            "agent_type": self.agent_type,
            "action": self.action,
            "payload": self.payload,
            "conversation_id": self.conversation_id,
            "parent_message_id": self.parent_message_id,
            "timestamp": self.timestamp.isoformat(),
        }


class AgentResponse:
    """Response from an agent"""

    def __init__(
        self,
        status: AgentStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.status = status
        self.result = result or {}
        self.error = error
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary"""
        return {
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    @property
    def is_success(self) -> bool:
        """Check if response is successful"""
        return self.status == AgentStatus.COMPLETED

    @property
    def is_error(self) -> bool:
        """Check if response is an error"""
        return self.status in [AgentStatus.FAILED, AgentStatus.TIMEOUT]


class BaseAgent(ABC):
    """
    Abstract base class for all agents - Phase D: Self-Describing

    All agents must implement:
    - get_agent_info(): Class method returning agent metadata for orchestrator discovery
    - get_capabilities(): Instance method returning internal routing capabilities
    - _execute_internal(): The actual execution logic

    Provides:
    - emit_event(): Transparency event emission to database
    - log_llm_conversation(): LLM conversation logging
    - call_agent(): Inter-agent communication
    """

    def __init__(self, name: str = None, description: str = None):
        # Allow getting name from get_agent_info() if not provided
        info = self.get_agent_info()
        self.name = name or info.get("name", self.__class__.__name__.lower())
        self.description = description or info.get("purpose", "")
        self.logger = structlog.get_logger().bind(agent=self.name)

    @classmethod
    @abstractmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """
        Agent describes itself for dynamic discovery by orchestrator.

        Returns:
            {
                "name": "segmentation",
                "purpose": "Group clients into meaningful cohorts",
                "when_to_use": [
                    "User wants to group or cluster clients",
                    "User asks about segments, cohorts, or personas",
                ],
                "when_not_to_use": [
                    "User needs numerical calculations",
                    "User is searching for specific text",
                ],
                "example_tasks": [
                    "Segment my clients by engagement level",
                    "Find clients similar to my top performers",
                ],
                "data_source_aware": True,  # Optional: can handle multi-source queries
            }
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """
        Agent's internal capabilities for LLM-driven task routing.

        Returns:
            {
                "cluster_clients": {
                    "description": "Group clients into segments based on attributes",
                    "examples": ["segment by", "group clients", "create clusters"],
                    "method": "_cluster_clients"  # Method name to call
                },
                "find_similar": {
                    "description": "Find clients similar to a reference",
                    "examples": ["find similar", "clients like", "lookalikes"],
                    "method": "_find_similar_clients"
                },
            }
        """
        pass

    async def emit_event(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: str,
        event_type: EventType,
        title: str,
        details: Optional[Dict[str, Any]] = None,
        parent_event_id: Optional[uuid.UUID] = None,
        step_number: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> TransparencyEvent:
        """
        Emit a transparency event - stored in DB for user visibility.

        Args:
            db: Database session
            session_id: Conversation session ID
            user_id: User ID (REQUIRED for isolation)
            event_type: Type of event (received, thinking, decision, action, result, error)
            title: Short summary shown in collapsed UI view
            details: Verbose data shown when user expands the event
            parent_event_id: Optional parent event for hierarchy
            step_number: Order within workflow
            duration_ms: Duration for action/result events

        Returns:
            The created TransparencyEvent
        """
        if not user_id:
            raise ValueError("user_id is required for all transparency events")

        try:
            # Convert string session_id to UUID if needed
            if isinstance(session_id, str):
                session_uuid = uuid.UUID(session_id)
            else:
                session_uuid = session_id

            event = TransparencyEvent(
                session_id=session_uuid,
                user_id=user_id,
                agent_name=self.name,
                event_type=event_type.value if isinstance(event_type, EventType) else event_type,
                title=title,
                details=details or {},
                parent_event_id=parent_event_id,
                step_number=step_number,
                duration_ms=duration_ms,
            )
            db.add(event)
            await db.flush()

            self.logger.info(
                "transparency_event_emitted",
                event_type=event_type.value if isinstance(event_type, EventType) else event_type,
                title=title,
                session_id=str(session_uuid),
                user_id=user_id,
            )

            return event

        except Exception as e:
            self.logger.error(
                "failed_to_emit_transparency_event",
                error=str(e),
                event_type=event_type,
                title=title,
                exc_info=True,
            )
            raise

    async def execute(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """
        Execute agent with complete transparency logging

        Args:
            message: Input message with action and payload
            db: Database session
            user_id: User making the request

        Returns:
            AgentResponse with results or error
        """
        activity_log = None
        start_time = datetime.utcnow()

        try:
            # Log agent start
            self.logger.info(
                "agent_started",
                action=message.action,
                conversation_id=message.conversation_id,
                user_id=user_id,
            )

            # Create activity log entry
            # Truncate activity_type to 100 chars (DB column limit)
            activity_type = (message.action[:97] + "...") if len(message.action) > 100 else message.action
            activity_log = AgentActivityLog(
                session_id=message.conversation_id,  # Use conversation_id as session_id
                user_id=user_id,
                agent_name=self.name,
                activity_type=activity_type,
                input_data=message.payload,
                status=AgentStatus.RUNNING.value,
            )
            db.add(activity_log)
            await db.flush()

            # Execute agent-specific logic with timeout
            try:
                response = await asyncio.wait_for(
                    self._execute_internal(message, db, user_id),
                    timeout=settings.agent_timeout_seconds
                )
            except asyncio.TimeoutError:
                response = AgentResponse(
                    status=AgentStatus.TIMEOUT,
                    error=f"Agent execution exceeded {settings.agent_timeout_seconds}s timeout"
                )

            # Update activity log with results
            end_time = datetime.utcnow()
            activity_log.status = response.status.value
            activity_log.output_data = response.result
            activity_log.meta_data = {"error": response.error} if response.error else None
            activity_log.completed_at = end_time
            activity_log.duration_ms = int((end_time - start_time).total_seconds() * 1000)

            await db.commit()

            # Log completion
            self.logger.info(
                "agent_completed",
                status=response.status.value,
                duration_ms=activity_log.duration_ms,
                conversation_id=message.conversation_id,
            )

            return response

        except Exception as e:
            # Log error
            self.logger.error(
                "agent_failed",
                error=str(e),
                conversation_id=message.conversation_id,
                exc_info=True,
            )

            # Update activity log with error
            if activity_log:
                end_time = datetime.utcnow()
                activity_log.status = AgentStatus.FAILED.value
                activity_log.meta_data = {"error": str(e)}
                activity_log.completed_at = end_time
                activity_log.duration_ms = int((end_time - start_time).total_seconds() * 1000)
                await db.commit()

            return AgentResponse(
                status=AgentStatus.FAILED,
                error=str(e)
            )

    @abstractmethod
    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """
        Internal execution logic to be implemented by each agent

        Args:
            message: Input message with action and payload
            db: Database session
            user_id: User making the request

        Returns:
            AgentResponse with results
        """
        pass

    async def log_llm_conversation(
        self,
        db: AsyncSession,
        conversation_id: str,
        user_id: str,
        model_name: str,
        prompt: str,
        response: str,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
    ):
        """
        Log LLM conversation for transparency

        Args:
            db: Database session
            conversation_id: Conversation ID (used as session_id)
            user_id: User ID
            model_name: LLM model name
            prompt: Input prompt
            response: LLM response
            tokens_used: Optional token count
            latency_ms: Optional latency in milliseconds
        """
        try:
            llm_log = AgentLLMConversation(
                session_id=conversation_id,  # Use conversation_id as session_id
                user_id=user_id,
                agent_name=self.name,
                model_used=model_name,  # Changed from model_name
                prompt=prompt,  # Changed from prompt_text
                response=response,  # Changed from response_text
                token_usage={"total": tokens_used} if tokens_used else None,  # JSONB format
                latency_ms=latency_ms,
            )
            db.add(llm_log)
            await db.flush()

            self.logger.info(
                "llm_conversation_logged",
                model=model_name,
                tokens=tokens_used,
                conversation_id=conversation_id,
            )
        except Exception as e:
            self.logger.error(
                "failed_to_log_llm_conversation",
                error=str(e),
                exc_info=True,
            )

    async def call_agent(
        self,
        target_agent: "BaseAgent",
        action: str,
        payload: Dict[str, Any],
        db: AsyncSession,
        user_id: str,
        conversation_id: str,
        parent_message_id: Optional[str] = None,
    ) -> AgentResponse:
        """
        Call another agent from within this agent

        Args:
            target_agent: Agent to call
            action: Action to perform
            payload: Input data
            db: Database session
            user_id: User ID
            conversation_id: Conversation ID
            parent_message_id: Optional parent message ID

        Returns:
            AgentResponse from target agent
        """
        message = AgentMessage(
            agent_type=target_agent.name,
            action=action,
            payload=payload,
            conversation_id=conversation_id,
            parent_message_id=parent_message_id,
        )

        self.logger.info(
            "calling_agent",
            target_agent=target_agent.name,
            action=action,
            conversation_id=conversation_id,
        )

        return await target_agent.execute(message, db, user_id)
