"""
Base Agent Framework
Provides abstract base class for all agents with built-in transparency logging
"""

import uuid
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentActivityLog, AgentLLMConversation
from app.config import settings


logger = structlog.get_logger()


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
    Abstract base class for all agents
    Provides common functionality for agent execution and logging
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = structlog.get_logger().bind(agent=name)

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
            activity_log = AgentActivityLog(
                conversation_id=message.conversation_id,
                user_id=user_id,
                agent_name=self.name,
                action=message.action,
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
            activity_log.error_message = response.error
            activity_log.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            await db.commit()

            # Log completion
            self.logger.info(
                "agent_completed",
                status=response.status.value,
                execution_time_ms=activity_log.execution_time_ms,
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
                activity_log.error_message = str(e)
                activity_log.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
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
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Log LLM conversation for transparency

        Args:
            db: Database session
            conversation_id: Conversation ID
            user_id: User ID
            model_name: LLM model name
            prompt: Input prompt
            response: LLM response
            tokens_used: Optional token count
            metadata: Optional metadata
        """
        try:
            llm_log = AgentLLMConversation(
                conversation_id=conversation_id,
                user_id=user_id,
                agent_name=self.name,
                model_name=model_name,
                prompt_text=prompt,
                response_text=response,
                tokens_used=tokens_used,
                metadata=metadata or {},
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
