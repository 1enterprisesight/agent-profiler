"""
Agent Framework Package - Self-Describing Agents with Dynamic Registry

Agents auto-register via @register_agent decorator when imported.
Orchestrator uses AgentRegistry.get_registry_schema() for LLM-driven routing.
"""

from app.agents.base import (
    BaseAgent,
    AgentMessage,
    AgentResponse,
    AgentStatus,
    EventType,
    AgentRegistry,
    register_agent,
)

# Import agents to trigger registration
# Each @register_agent decorated class registers itself on import
from app.agents.data_ingestion import DataIngestionAgent
from app.agents.data_discovery import DataDiscoveryAgent

__all__ = [
    # Base classes
    "BaseAgent",
    "AgentMessage",
    "AgentResponse",
    "AgentStatus",
    "EventType",
    # Registry
    "AgentRegistry",
    "register_agent",
    # Agents
    "DataIngestionAgent",
    "DataDiscoveryAgent",
]
