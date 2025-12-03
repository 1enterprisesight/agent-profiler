"""
Base Agent Framework - Self-Describing Agents with Dynamic Registry

Provides:
- AgentRegistry: Singleton for dynamic agent discovery (NO hardcoded routing)
- @register_agent: Decorator for auto-registration
- BaseAgent: Abstract base class with transparency logging
- LLM-driven task interpretation (orchestrator decides routing)
"""

import uuid
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, Type
from datetime import datetime
from enum import Enum
from functools import wraps

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentActivityLog, AgentLLMConversation, TransparencyEvent
from app.config import settings


logger = structlog.get_logger()


# =============================================================================
# AGENT REGISTRY - Dynamic Discovery Pattern
# =============================================================================

class AgentRegistry:
    """
    Singleton registry for dynamic agent discovery.

    Agents register themselves via @register_agent decorator.
    Orchestrator queries registry to get available agents and their capabilities,
    then uses LLM to decide routing (NO keyword matching, NO hardcoded rules).

    Usage:
        # Get all registered agents
        registry = AgentRegistry()
        agents = registry.get_all_agents()

        # Get schema for LLM prompt injection
        schema = registry.get_registry_schema()

        # Get specific agent class
        agent_cls = registry.get_agent("data_ingestion")
    """

    _instance = None
    _registry: Dict[str, Type["BaseAgent"]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, agent_class: Type["BaseAgent"]) -> Type["BaseAgent"]:
        """Register an agent class. Called by @register_agent decorator."""
        info = agent_class.get_agent_info()
        name = info.get("name", agent_class.__name__.lower())
        cls._registry[name] = agent_class
        logger.info("agent_registered", agent_name=name)
        return agent_class

    @classmethod
    def get_agent(cls, name: str) -> Optional[Type["BaseAgent"]]:
        """Get an agent class by name."""
        return cls._registry.get(name)

    @classmethod
    def get_all_agents(cls) -> Dict[str, Type["BaseAgent"]]:
        """Get all registered agent classes."""
        return cls._registry.copy()

    @classmethod
    def get_registry_schema(cls) -> List[Dict[str, Any]]:
        """
        Get schema of all registered agents for LLM prompt injection.

        Returns list of agent metadata that orchestrator injects into
        its system prompt so LLM can semantically route queries.

        NO keywords, NO example phrases - just capability descriptions.
        """
        schema = []
        for name, agent_cls in cls._registry.items():
            info = agent_cls.get_agent_info()
            schema.append({
                "name": name,
                "description": info.get("description", ""),
                "capabilities": info.get("capabilities", []),
                "inputs": info.get("inputs", {}),
                "outputs": info.get("outputs", {}),
            })
        return schema

    @classmethod
    def clear(cls):
        """Clear registry (useful for testing)."""
        cls._registry = {}


def register_agent(cls: Type["BaseAgent"]) -> Type["BaseAgent"]:
    """
    Decorator to register an agent class with the registry.

    Usage:
        @register_agent
        class MyAgent(BaseAgent):
            ...
    """
    return AgentRegistry.register(cls)


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
        self.description = description or info.get("description", "")
        self.logger = structlog.get_logger().bind(agent=self.name)

    @classmethod
    @abstractmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """
        Agent describes itself for dynamic discovery by orchestrator.

        IMPORTANT: NO hardcoded keywords, NO example phrases, NO routing hints.
        The orchestrator's LLM uses these descriptions for semantic routing.

        Returns:
            {
                "name": "agent_name",
                "description": "What this agent does (generic, capability-focused)",
                "capabilities": [
                    "First capability description",
                    "Second capability description",
                ],
                "inputs": {
                    "param_name": "Description of expected input"
                },
                "outputs": {
                    "field_name": "Description of output field"
                }
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

    async def get_data_context(
        self,
        db: AsyncSession,
        data_source_id: Optional[str],
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get complete data context (schema + semantic profile) for a data source.

        Shared method used by all agents to ensure consistent data understanding.

        Args:
            db: Database session
            data_source_id: Specific data source ID, or None to get most recent
            user_id: User ID for filtering

        Returns:
            Complete data context dict or None if not found:
            {
                "data_source_id": "uuid",
                "file_name": "name.csv",
                "row_count": 3480,
                "columns": ["col1", "col2", ...],
                "detected_types": {
                    "col1": {"type": "text", "nullable": false, "sample_values": [...]},
                    ...
                },
                "semantic_profile": {
                    "domain": "healthcare",
                    "domain_description": "...",
                    "entity_name": "doctor",
                    "entity_type": "person",
                    "primary_key": "Doctor ID",
                    "relationships": [...],
                    "data_categories": {...},
                    "field_descriptions": {...},
                    "suggested_analyses": [...]
                }
            }
        """
        from sqlalchemy import text
        import json

        try:
            if data_source_id:
                result = await db.execute(
                    text("""
                        SELECT id, file_name, metadata
                        FROM uploaded_files
                        WHERE id = :data_source_id AND user_id = :user_id
                    """),
                    {"data_source_id": data_source_id, "user_id": user_id}
                )
            else:
                result = await db.execute(
                    text("""
                        SELECT id, file_name, metadata
                        FROM uploaded_files
                        WHERE user_id = :user_id
                        ORDER BY uploaded_at DESC LIMIT 1
                    """),
                    {"user_id": user_id}
                )

            row = result.fetchone()
            if not row:
                return None

            metadata = row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}")

            return {
                "data_source_id": str(row[0]),
                "file_name": row[1],
                "row_count": metadata.get("rows", 0),
                "columns": metadata.get("columns", []),
                "detected_types": metadata.get("detected_types", {}),
                "semantic_profile": metadata.get("semantic_profile", {}),
                "field_mappings": metadata.get("field_mappings", {})
            }

        except Exception as e:
            self.logger.warning("failed_to_get_data_context", error=str(e))
            return None

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
