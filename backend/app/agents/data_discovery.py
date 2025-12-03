"""
Data Discovery Agent

Analyzes data sources to produce semantic understanding of the data.
Uses LLM to determine entity types, domains, field categories, and relationships.
Stores semantic profile with data source for other agents to reference.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus, EventType, register_agent
from app.config import settings


@register_agent
class DataDiscoveryAgent(BaseAgent):
    """
    Analyzes data sources to produce semantic understanding.
    Uses LLM to determine entity types, domains, field categories,
    and relationships. Stores semantic profile with data source.
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Agent metadata for orchestrator's dynamic routing."""
        return {
            "name": "data_discovery",
            "description": "Analyzes data sources to produce semantic understanding of the data",
            "capabilities": [
                "Identify entity types and domain from schema and sample data",
                "Categorize fields by purpose (identity, metrics, segmentation, etc.)",
                "Infer relationships between fields",
                "Generate suggested analyses based on data nature",
                "Store semantic profile with data source for other agents"
            ],
            "inputs": {
                "data_source_id": "ID of the data source to analyze",
                "schema": "Column names and detected types (optional - loaded from data source)",
                "sample_data": "Sample rows for context (optional - loaded from database)"
            },
            "outputs": {
                "semantic_profile": "Entity type, domain, categories, relationships",
                "stored": "Boolean - whether profile was stored with data source"
            }
        }

    def __init__(self):
        super().__init__()
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )
        self.model = GenerativeModel(settings.gemini_flash_model)

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str
    ) -> AgentResponse:
        """Execute data discovery - analyze and store semantic profile."""

        start_time = datetime.utcnow()
        conversation_id = message.conversation_id
        payload = message.payload
        data_source_id = payload.get("data_source_id")
        skip_events = payload.get("skip_transparency_events", False)

        # Helper for events (no-op if skip_events is True)
        async def emit(event_type: EventType, title: str, details: Dict = None, step: int = 1):
            if skip_events:
                return
            await self.emit_event(
                db=db,
                user_id=user_id,
                session_id=conversation_id,
                event_type=event_type,
                title=title,
                details=details or {},
                step_number=step
            )

        try:
            # Event 1: RECEIVED
            await emit(EventType.RECEIVED, "Received data discovery request",
                      {"data_source_id": data_source_id}, 1)

            # If no data_source_id, try to get the most recent one for the user
            if not data_source_id:
                await emit(EventType.THINKING, "Finding most recent data source", {}, 2)
                result = await db.execute(
                    text("""
                        SELECT id FROM uploaded_files
                        WHERE user_id = :user_id
                        ORDER BY uploaded_at DESC LIMIT 1
                    """),
                    {"user_id": user_id}
                )
                row = result.fetchone()
                if not row:
                    return AgentResponse(
                        status=AgentStatus.FAILED,
                        result={"error": "No data sources found for user"},
                        metadata={}
                    )
                data_source_id = str(row[0])

            # Event 2: THINKING - Loading schema
            await emit(EventType.THINKING, "Loading schema and sample data",
                      {"data_source_id": data_source_id}, 2)

            # Load schema from data source
            schema_result = await db.execute(
                text("""
                    SELECT metadata, file_name
                    FROM uploaded_files
                    WHERE id = :data_source_id
                """),
                {"data_source_id": data_source_id}
            )
            schema_row = schema_result.fetchone()

            if not schema_row:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    result={"error": f"Data source {data_source_id} not found"},
                    metadata={}
                )

            metadata = schema_row[0] if isinstance(schema_row[0], dict) else json.loads(schema_row[0] or "{}")
            file_name = schema_row[1]

            columns = metadata.get("columns", [])
            detected_types = metadata.get("detected_types", {})

            # Load sample data from clients table
            sample_result = await db.execute(
                text("""
                    SELECT core_data, custom_data
                    FROM clients
                    WHERE data_source_id = :data_source_id
                    LIMIT 5
                """),
                {"data_source_id": data_source_id}
            )
            sample_rows = sample_result.fetchall()

            # Combine core_data and custom_data for sample
            sample_data = []
            for row in sample_rows:
                combined = {}
                if row[0]:
                    core = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    combined.update(core)
                if row[1]:
                    custom = row[1] if isinstance(row[1], dict) else json.loads(row[1])
                    combined.update(custom)
                sample_data.append(combined)

            # Event 3: ACTION - LLM analysis
            await emit(EventType.ACTION, "Analyzing data semantics with LLM",
                      {"columns": len(columns), "sample_rows": len(sample_data)}, 3)

            # Build schema context for LLM
            schema_context = {
                "file_name": file_name,
                "columns": columns,
                "detected_types": detected_types
            }

            # Call LLM to analyze semantics
            semantic_profile = await self._analyze_semantics(schema_context, sample_data)

            # Event 4: ACTION - Storing profile
            await emit(EventType.ACTION, "Storing semantic profile",
                      {"entity_type": semantic_profile.get("entity_type", "unknown")}, 4)

            # Store semantic profile with data source
            await self._store_semantic_profile(db, data_source_id, semantic_profile)

            # Calculate duration
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Event 5: RESULT
            await emit(EventType.RESULT,
                      f"Discovered: {semantic_profile.get('entity_name', 'entity')} data in {semantic_profile.get('domain', 'unknown')} domain",
                      {"profile": semantic_profile}, 5)

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "data_source_id": data_source_id,
                    "semantic_profile": semantic_profile,
                    "stored": True,
                    "message": f"Semantic profile created for {file_name}"
                },
                metadata={
                    "duration_ms": duration_ms,
                    "model_used": settings.gemini_flash_model
                }
            )

        except Exception as e:
            # Event: ERROR
            await emit(EventType.ERROR, f"Discovery failed: {str(e)}",
                      {"error": str(e)}, 99)

            return AgentResponse(
                status=AgentStatus.FAILED,
                result={"error": str(e)},
                metadata={}
            )

    async def _analyze_semantics(self, schema: Dict, sample_data: List[Dict]) -> Dict:
        """LLM analyzes schema + sample to produce semantic profile."""

        prompt = f"""Analyze this data schema and sample to understand what this data represents.

FILE NAME: {schema.get('file_name', 'unknown')}

COLUMNS AND TYPES:
{json.dumps(schema.get('detected_types', {}), indent=2)}

SAMPLE DATA (first rows):
{json.dumps(sample_data[:5], indent=2, default=str)}

Analyze and determine:

1. entity_type: What type of entity does each row represent?
   Examples: person, company, transaction, event, product, location, etc.

2. entity_name: Specific name for this entity based on the data
   Examples: doctor, customer, order, employee, patient, etc.

3. domain: What industry or domain is this data from?
   Examples: healthcare, finance, retail, manufacturing, etc.

4. primary_key: Which field(s) uniquely identify each record?

5. data_categories: Group ALL fields by their purpose:
   - identity: Fields that identify the entity (IDs, names)
   - performance_metrics: Numeric KPIs and measures
   - segmentation: Fields used to group/categorize/tier
   - geography: Location-related fields
   - temporal: Date/time fields
   - relationships: Fields linking to other entities (managers, territories)
   - preferences: Settings, opt-ins, flags
   - other: Any fields that don't fit above

6. field_descriptions: For each field, provide a brief description of what it represents

7. relationships: What relationships between entities can be inferred?
   Example: {{"field": "territory_manager", "relationship": "assigned_to", "target_entity": "sales_rep"}}

8. suggested_analyses: What business questions could this data answer? (list 5-7)

Return valid JSON only:
{{
  "entity_type": "...",
  "entity_name": "...",
  "domain": "...",
  "domain_description": "...",
  "primary_key": "...",
  "data_categories": {{
    "identity": ["field1", "field2"],
    "performance_metrics": ["field1"],
    "segmentation": ["field1"],
    "geography": ["field1"],
    "temporal": ["field1"],
    "relationships": ["field1"],
    "preferences": ["field1"],
    "other": ["field1"]
  }},
  "field_descriptions": {{
    "field_name": "description of what this field represents"
  }},
  "relationships": [
    {{"field": "...", "relationship": "...", "target_entity": "..."}}
  ],
  "suggested_analyses": [
    "Question 1",
    "Question 2"
  ]
}}"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.2}
            )
            response_text = response.text.strip()

            # Parse JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            return json.loads(response_text.strip())

        except json.JSONDecodeError as e:
            self.logger.error("llm_response_parse_error", error=str(e))
            # Return minimal profile on parse failure
            return {
                "entity_type": "unknown",
                "entity_name": "record",
                "domain": "unknown",
                "primary_key": None,
                "data_categories": {},
                "field_descriptions": {},
                "relationships": [],
                "suggested_analyses": [],
                "parse_error": str(e)
            }

        except Exception as e:
            self.logger.error("llm_analysis_error", error=str(e))
            raise

    async def _store_semantic_profile(self, db: AsyncSession, data_source_id: str, profile: Dict):
        """Store semantic profile in uploaded_files.metadata."""

        profile["analyzed_at"] = datetime.utcnow().isoformat()

        # Fetch current metadata
        result = await db.execute(
            text("SELECT metadata FROM uploaded_files WHERE id = :data_source_id"),
            {"data_source_id": data_source_id}
        )
        row = result.fetchone()
        current_metadata = row[0] if row and row[0] else {}
        if isinstance(current_metadata, str):
            current_metadata = json.loads(current_metadata)

        # Update with semantic profile
        current_metadata["semantic_profile"] = profile

        # Write back
        await db.execute(
            text("""
                UPDATE uploaded_files
                SET metadata = :metadata
                WHERE id = :data_source_id
            """),
            {"data_source_id": data_source_id, "metadata": json.dumps(current_metadata)}
        )
        await db.commit()

    async def get_semantic_profile(self, db: AsyncSession, data_source_id: str) -> Optional[Dict]:
        """Retrieve semantic profile for a data source. Used by other agents."""

        result = await db.execute(
            text("""
                SELECT metadata->'semantic_profile' as profile
                FROM uploaded_files
                WHERE id = :data_source_id
            """),
            {"data_source_id": data_source_id}
        )
        row = result.fetchone()

        if row and row[0]:
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return None


# Utility function for other modules to get semantic context
async def get_semantic_context(db: AsyncSession, data_source_id: str) -> Dict[str, Any]:
    """
    Helper function to get semantic profile for a data source.
    Can be called by orchestrator or other agents.
    """
    result = await db.execute(
        text("""
            SELECT
                metadata->'semantic_profile' as profile,
                metadata->'detected_types' as types,
                metadata->'columns' as columns,
                file_name
            FROM uploaded_files
            WHERE id = :data_source_id
        """),
        {"data_source_id": data_source_id}
    )
    row = result.fetchone()

    if not row:
        return {"error": "Data source not found"}

    profile = row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}")
    types = row[1] if isinstance(row[1], dict) else json.loads(row[1] or "{}")
    columns = row[2] if isinstance(row[2], list) else json.loads(row[2] or "[]")

    return {
        "file_name": row[3],
        "columns": columns,
        "detected_types": types,
        "semantic_profile": profile,
        "has_profile": bool(profile)
    }
