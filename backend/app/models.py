"""
SQLAlchemy models for Agent Profiler
JSONB-heavy design for maximum flexibility
"""

from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, Text,
    TIMESTAMP, ForeignKey, DECIMAL, ARRAY, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


# ============================================================================
# CRM CONNECTIONS & INTEGRATION
# ============================================================================

class CRMConnection(Base):
    __tablename__ = "crm_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    crm_type = Column(String(50), nullable=False, index=True)
    connection_name = Column(String(255))
    config = Column(JSONB, nullable=False)
    credentials_secret_name = Column(String(255))
    status = Column(String(50), default="active")
    last_sync_at = Column(TIMESTAMP)
    last_sync_status = Column(String(50))
    error_message = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    schemas = relationship("CRMSchema", back_populates="connection", cascade="all, delete-orphan")
    mappings = relationship("FieldMapping", back_populates="connection", cascade="all, delete-orphan")
    clients = relationship("Client", back_populates="connection")
    sync_jobs = relationship("SyncJob", back_populates="connection", cascade="all, delete-orphan")


class CRMSchema(Base):
    __tablename__ = "crm_schemas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("crm_connections.id", ondelete="CASCADE"), unique=True)
    schema_data = Column(JSONB, nullable=False)
    schema_version = Column(String(50))
    discovered_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    connection = relationship("CRMConnection", back_populates="schemas")


class FieldMapping(Base):
    __tablename__ = "field_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("crm_connections.id", ondelete="CASCADE"), index=True)
    mapping_data = Column(JSONB, nullable=False)
    mapping_version = Column(Integer, default=1)
    confidence_score = Column(DECIMAL(3, 2))
    user_approved = Column(Boolean, default=False)
    user_adjustments = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    connection = relationship("CRMConnection", back_populates="mappings")


# ============================================================================
# CLIENT DATA
# ============================================================================

class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), index=True)  # Added for user tracking
    source_type = Column(String(50), nullable=False, index=True)
    source_id = Column(String(255))
    connection_id = Column(UUID(as_uuid=True), ForeignKey("crm_connections.id", ondelete="SET NULL"))
    data_source_id = Column(UUID(as_uuid=True), ForeignKey("uploaded_files.id", ondelete="CASCADE"), index=True)

    # Minimal structured fields
    client_name = Column(String(500))
    contact_email = Column(String(255), index=True)
    company_name = Column(String(500))

    # JSONB fields for flexibility
    core_data = Column(JSONB)
    custom_data = Column(JSONB)
    computed_metrics = Column(JSONB)

    # Metadata
    synced_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    connection = relationship("CRMConnection", back_populates="clients")

    # Indexes
    __table_args__ = (
        Index("idx_clients_source", "source_type", "source_id"),
        Index("idx_clients_core_data", "core_data", postgresql_using="gin"),
        Index("idx_clients_custom_data", "custom_data", postgresql_using="gin"),
    )


# ============================================================================
# DATA SYNC & JOBS
# ============================================================================

class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("crm_connections.id", ondelete="CASCADE"), index=True)
    sync_type = Column(String(50))
    status = Column(String(50), index=True)
    started_at = Column(TIMESTAMP, server_default=func.now())
    completed_at = Column(TIMESTAMP)
    records_processed = Column(Integer, default=0)
    records_succeeded = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    error_details = Column(JSONB)
    processing_log = Column(JSONB)

    # Relationships
    connection = relationship("CRMConnection", back_populates="sync_jobs")
    transformations = relationship("DataTransformationLog", back_populates="sync_job")


# ============================================================================
# AGENT SYSTEM & OBSERVABILITY
# ============================================================================

class AgentActivityLog(Base):
    __tablename__ = "agent_activity_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(String(255), index=True)  # Added for user tracking
    agent_name = Column(String(100), nullable=False, index=True)
    activity_type = Column(String(100))
    status = Column(String(50))
    input_data = Column(JSONB)
    output_data = Column(JSONB)
    meta_data = Column(JSONB)
    started_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    completed_at = Column(TIMESTAMP)
    duration_ms = Column(Integer)


class AgentLLMConversation(Base):
    __tablename__ = "agent_llm_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(String(255), index=True)  # Added for user tracking
    agent_name = Column(String(100), nullable=False, index=True)
    model_used = Column(String(100))
    prompt = Column(Text, nullable=False)
    system_instruction = Column(Text)
    response = Column(Text)
    token_usage = Column(JSONB)
    latency_ms = Column(Integer)
    error = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())


class SQLQueryLog(Base):
    __tablename__ = "sql_query_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    agent_name = Column(String(100))
    query_text = Column(Text, nullable=False)
    query_params = Column(JSONB)
    result_summary = Column(JSONB)
    execution_time_ms = Column(Integer)
    error = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)


class DataTransformationLog(Base):
    __tablename__ = "data_transformation_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), index=True)
    sync_job_id = Column(UUID(as_uuid=True), ForeignKey("sync_jobs.id", ondelete="SET NULL"), index=True)
    transformation_type = Column(String(100))
    source_data = Column(JSONB)
    transformed_data = Column(JSONB)
    transformation_rules = Column(JSONB)
    status = Column(String(50))
    error_details = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    sync_job = relationship("SyncJob", back_populates="transformations")


# ============================================================================
# BENCHMARK & ANALYSIS
# ============================================================================

class BenchmarkDefinition(Base):
    __tablename__ = "benchmark_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    benchmark_name = Column(String(255), nullable=False)
    benchmark_type = Column(String(100), index=True)
    definition = Column(JSONB, nullable=False)
    criteria = Column(JSONB)
    thresholds = Column(JSONB)
    applies_to_sources = Column(JSONB)
    created_by_agent = Column(String(100))
    user_approved = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    analysis_type = Column(String(100), index=True)
    input_parameters = Column(JSONB)
    results = Column(JSONB, nullable=False)
    confidence_score = Column(DECIMAL(3, 2))
    performed_by_agents = Column(JSONB)
    execution_time_ms = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now())
    expires_at = Column(TIMESTAMP, index=True)


# ============================================================================
# USER SESSIONS & CONVERSATIONS
# ============================================================================

class Conversation(Base):
    __tablename__ = "conversation_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    title = Column(String(500))
    context = Column(JSONB)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_activity_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), index=True)

    # Relationships
    messages = relationship("ConversationMessage", back_populates="session", cascade="all, delete-orphan")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    meta_data = Column(JSONB)
    agent_activities = Column(ARRAY(UUID(as_uuid=True)))
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    session = relationship("Conversation", back_populates="messages")

    # Indexes
    __table_args__ = (
        Index("idx_conversation_messages_session", "session_id", "created_at"),
    )


# ============================================================================
# FILE UPLOADS & DATASETS
# ============================================================================

class DataSource(Base):
    __tablename__ = "uploaded_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    file_name = Column(String(500), nullable=False)
    file_type = Column(String(100))
    gcs_path = Column(String(1000), nullable=False)
    file_size_bytes = Column(BigInteger)
    status = Column(String(50), index=True)
    meta_data = Column(JSONB)
    processing_results = Column(JSONB)
    records_imported = Column(Integer)
    error_details = Column(JSONB)
    uploaded_at = Column(TIMESTAMP, server_default=func.now())
    processed_at = Column(TIMESTAMP)


# ============================================================================
# AUDIT & COMPLIANCE
# ============================================================================

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), index=True)
    action = Column(String(255), nullable=False, index=True)
    resource_type = Column(String(100))
    resource_id = Column(UUID(as_uuid=True))
    details = Column(JSONB)
    ip_address = Column(String(100))
    user_agent = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)


# ============================================================================
# USER SESSIONS
# ============================================================================

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    name = Column(String(255))
    picture_url = Column(Text)
    access_token_hash = Column(String(255))
    refresh_token_encrypted = Column(Text)
    expires_at = Column(TIMESTAMP, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_activity_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True, index=True)
    metadata = Column(JSONB)
