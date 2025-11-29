"""
Data Discovery Agent - Phase D Self-Describing Agent

Provides metadata and context about a user's data to help other agents
understand the data landscape before executing queries.

Key responsibilities:
- Compute and store statistics about uploaded data
- Provide semantic context (what is "high value" in this dataset?)
- Answer questions about data completeness and quality
- Help the orchestrator make informed routing decisions
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus
from app.agents.schema_utils import get_schema_context
from app.models import DataMetadata, Client
from app.config import settings


class DataDiscoveryAgent(BaseAgent):
    """
    Self-describing agent that provides data context and metadata.

    Capabilities:
    - compute_metadata: Analyze all user data and compute statistics
    - get_context: Return current data context for planning
    - describe_field: Get semantic meaning of a specific field
    - get_thresholds: Get computed thresholds (e.g., what is "high value"?)
    """

    name = "data_discovery"
    description = "Analyzes and provides context about user's data"

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        return {
            "name": cls.name,
            "purpose": "Explore, profile, and describe user's uploaded data - structure, fields, statistics, and semantic context",
            "when_to_use": [
                "User asks 'what is this dataset about' or 'describe my data'",
                "User asks 'what are the key elements/fields in this data'",
                "User wants to understand or explore their data before querying",
                "User asks about data quality, completeness, or structure",
                "When interpreting vague terms like 'high value' or 'recent'",
                "To get field statistics (min, max, average, percentiles)",
                "To profile or explore a new dataset",
            ],
            "when_not_to_use": [
                "For actual data queries with filters (use sql_analytics)",
                "For text search (use semantic_search)",
                "For data upload (use data_ingestion)",
            ],
            "example_tasks": [
                "What is this dataset about?",
                "What are the key elements in my data?",
                "Describe the structure of my uploaded data",
                "What fields have data in my dataset?",
                "What is considered 'high value' in my data?",
                "Get statistics for the AUM field",
                "How complete is my email data?",
                "Profile my client data",
            ],
            "data_source_aware": True,
        }

    def get_capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {
            "compute_metadata": {
                "description": "Analyze all data and compute/update statistics",
                "examples": ["refresh data statistics", "recompute metadata"],
                "method": "_compute_metadata"
            },
            "get_context": {
                "description": "Get current data context for query planning",
                "examples": ["get data context", "what data do I have"],
                "method": "_get_context"
            },
            "get_thresholds": {
                "description": "Get computed thresholds for semantic terms",
                "examples": ["what is high value", "define recent clients"],
                "method": "_get_thresholds"
            },
            "get_field_stats": {
                "description": "Get statistics for a specific field",
                "examples": ["AUM statistics", "email completeness"],
                "method": "_get_field_stats"
            },
        }

    def __init__(self):
        super().__init__()
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )
        self.model = GenerativeModel(settings.gemini_flash_model)

    async def _interpret_task(
        self,
        task: str,
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """Use LLM to interpret what the user wants to know about their data."""

        await self.emit_event(
            db, user_id, None, "thinking",
            "Interpreting data discovery request",
            {"task": task}
        )

        prompt = f"""You are analyzing a request about data discovery/metadata.

Task: "{task}"

Determine the appropriate action:
1. "compute_metadata" - User wants to refresh/compute statistics
2. "get_context" - User wants overview of their data
3. "get_thresholds" - User wants to understand semantic terms (high value, recent, etc.)
4. "get_field_stats" - User wants stats for specific field(s)

Respond with JSON:
{{
    "action": "action_name",
    "fields": ["field1", "field2"],  // if specific fields mentioned
    "terms": ["term1"],  // semantic terms to define (high value, recent, etc.)
    "reasoning": "why this action"
}}"""

        response = await self.model.generate_content_async(prompt)
        response_text = response.text.strip()

        # Parse JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {"action": "get_context", "reasoning": "default fallback"}

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str
    ) -> AgentResponse:
        """Execute data discovery task."""

        task = message.action

        await self.emit_event(
            db, user_id, message.conversation_id, "received",
            f"Data discovery request: {task[:50]}...",
            {"full_task": task}
        )

        # Interpret the task
        interpretation = await self._interpret_task(task, db, user_id)
        action = interpretation.get("action", "get_context")

        await self.emit_event(
            db, user_id, message.conversation_id, "decision",
            f"Action: {action}",
            interpretation
        )

        # Execute appropriate method
        if action == "compute_metadata":
            result = await self._compute_metadata(db, user_id)
        elif action == "get_thresholds":
            terms = interpretation.get("terms", [])
            result = await self._get_thresholds(db, user_id, terms)
        elif action == "get_field_stats":
            fields = interpretation.get("fields", [])
            result = await self._get_field_stats(db, user_id, fields)
        else:
            result = await self._get_context(db, user_id)

        await self.emit_event(
            db, user_id, message.conversation_id, "result",
            "Data discovery complete",
            {"summary": str(result)[:200]}
        )

        return AgentResponse(
            status=AgentStatus.SUCCESS,
            result=result,
            metadata={"action": action, "interpretation": interpretation}
        )

    async def _compute_metadata(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """Compute and store comprehensive metadata about user's data using dynamic schema."""

        await self.emit_event(
            db, user_id, None, "action",
            "Computing data statistics",
            {}
        )

        # Get dynamic schema context - this knows all fields and their types
        schema_context = await get_schema_context(db, user_id)

        # Get total counts by source
        sources_query = text("""
            SELECT source_type, COUNT(*) as count
            FROM clients
            WHERE user_id = :user_id
            GROUP BY source_type
        """)
        sources_result = await db.execute(sources_query, {"user_id": user_id})
        sources_summary = {row[0]: row[1] for row in sources_result.fetchall()}
        total_clients = sum(sources_summary.values())

        # Compute field completeness dynamically for all discovered fields
        field_completeness = {}

        # Always check core columns
        core_columns = [
            ("email", "contact_email IS NOT NULL AND contact_email != ''"),
            ("company", "company_name IS NOT NULL AND company_name != ''"),
            ("client_name", "client_name IS NOT NULL AND client_name != ''"),
        ]

        for field_name, condition in core_columns:
            try:
                query = text(f"""
                    SELECT COUNT(*) FILTER (WHERE {condition}) * 100.0 / NULLIF(COUNT(*), 0)
                    FROM clients WHERE user_id = :user_id
                """)
                result = await db.execute(query, {"user_id": user_id})
                row = result.fetchone()
                field_completeness[field_name] = round(row[0] or 0, 1)
            except Exception:
                pass

        # Check discovered fields from schema
        for field in schema_context.get("all_fields", {}).values():
            if isinstance(field, dict):
                field_name = field.get("name")
                null_pct = field.get("null_pct", 100)
                if field_name:
                    field_completeness[field_name] = round(100 - null_pct, 1)

        # Get numeric stats for all numeric fields
        numeric_stats = {}
        for field in schema_context.get("numeric_fields", []):
            field_name = field.get("name")
            access_path = field.get("access_path", f"custom_data->>'{field_name}'")

            try:
                numeric_query = text(f"""
                    SELECT
                        MIN(({access_path})::numeric) as min_val,
                        MAX(({access_path})::numeric) as max_val,
                        AVG(({access_path})::numeric) as avg_val,
                        PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY ({access_path})::numeric) as p10,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ({access_path})::numeric) as p50,
                        PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY ({access_path})::numeric) as p90
                    FROM clients
                    WHERE user_id = :user_id
                      AND {access_path} IS NOT NULL
                      AND {access_path} ~ '^-?[0-9.,]+$'
                """)
                result = await db.execute(numeric_query, {"user_id": user_id})
                row = result.fetchone()
                if row and row[0] is not None:
                    numeric_stats[field_name] = {
                        "min": float(row[0]) if row[0] else None,
                        "max": float(row[1]) if row[1] else None,
                        "avg": float(row[2]) if row[2] else None,
                        "p10": float(row[3]) if row[3] else None,
                        "p50": float(row[4]) if row[4] else None,
                        "p90": float(row[5]) if row[5] else None,
                    }
            except Exception as e:
                self.logger.debug(f"Could not compute stats for {field_name}: {e}")

        # Get date ranges
        date_query = text("""
            SELECT
                MIN(created_at) as min_created,
                MAX(created_at) as max_created,
                MIN(synced_at) as min_synced,
                MAX(synced_at) as max_synced
            FROM clients
            WHERE user_id = :user_id
        """)
        date_result = await db.execute(date_query, {"user_id": user_id})
        date_row = date_result.fetchone()
        date_ranges = {
            "created_at": {
                "min": date_row[0].isoformat() if date_row[0] else None,
                "max": date_row[1].isoformat() if date_row[1] else None,
            },
            "synced_at": {
                "min": date_row[2].isoformat() if date_row[2] else None,
                "max": date_row[3].isoformat() if date_row[3] else None,
            }
        }

        # Compute thresholds based on percentiles for all numeric fields
        computed_thresholds = {}
        for field_name, stats in numeric_stats.items():
            if stats.get("p90"):
                computed_thresholds[f"high_{field_name}"] = stats["p90"]
            if stats.get("p50"):
                computed_thresholds[f"medium_{field_name}"] = stats["p50"]

        # Keep backwards compatibility for "aum" specifically
        if numeric_stats.get("aum", {}).get("p90"):
            computed_thresholds["high_value_aum"] = numeric_stats["aum"]["p90"]
        if numeric_stats.get("aum", {}).get("p50"):
            computed_thresholds["medium_value_aum"] = numeric_stats["aum"]["p50"]

        # Upsert metadata record
        existing = await db.execute(
            text("SELECT id FROM data_metadata WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        existing_row = existing.fetchone()

        if existing_row:
            await db.execute(
                text("""
                    UPDATE data_metadata SET
                        total_clients = :total_clients,
                        sources_summary = :sources_summary,
                        field_completeness = :field_completeness,
                        numeric_stats = :numeric_stats,
                        date_ranges = :date_ranges,
                        computed_thresholds = :computed_thresholds,
                        last_computed_at = NOW(),
                        updated_at = NOW()
                    WHERE user_id = :user_id
                """),
                {
                    "user_id": user_id,
                    "total_clients": total_clients,
                    "sources_summary": json.dumps(sources_summary),
                    "field_completeness": json.dumps(field_completeness),
                    "numeric_stats": json.dumps(numeric_stats),
                    "date_ranges": json.dumps(date_ranges),
                    "computed_thresholds": json.dumps(computed_thresholds),
                }
            )
        else:
            await db.execute(
                text("""
                    INSERT INTO data_metadata
                    (user_id, total_clients, sources_summary, field_completeness,
                     numeric_stats, date_ranges, computed_thresholds)
                    VALUES (:user_id, :total_clients, :sources_summary, :field_completeness,
                            :numeric_stats, :date_ranges, :computed_thresholds)
                """),
                {
                    "user_id": user_id,
                    "total_clients": total_clients,
                    "sources_summary": json.dumps(sources_summary),
                    "field_completeness": json.dumps(field_completeness),
                    "numeric_stats": json.dumps(numeric_stats),
                    "date_ranges": json.dumps(date_ranges),
                    "computed_thresholds": json.dumps(computed_thresholds),
                }
            )

        await db.commit()

        return {
            "total_clients": total_clients,
            "sources": sources_summary,
            "field_completeness": field_completeness,
            "numeric_stats": numeric_stats,
            "date_ranges": date_ranges,
            "computed_thresholds": computed_thresholds,
            "schema": schema_context,
            "message": f"Computed metadata for {total_clients} clients across {len(sources_summary)} sources"
        }

    async def _get_context(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """Get current data context for query planning, including dynamic schema."""

        # Get dynamic schema context
        schema_context = await get_schema_context(db, user_id)

        # Try to get cached metadata
        result = await db.execute(
            text("""
                SELECT total_clients, sources_summary, field_completeness,
                       numeric_stats, computed_thresholds, last_computed_at
                FROM data_metadata
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )
        row = result.fetchone()

        if not row or not row[0]:
            # No metadata, compute it
            metadata = await self._compute_metadata(db, user_id)
            metadata["schema"] = schema_context
            return metadata

        return {
            "total_clients": row[0],
            "sources": row[1] if isinstance(row[1], dict) else json.loads(row[1] or "{}"),
            "field_completeness": row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}"),
            "numeric_stats": row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
            "computed_thresholds": row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}"),
            "last_computed": row[5].isoformat() if row[5] else None,
            "schema": schema_context,
        }

    async def _get_thresholds(
        self,
        db: AsyncSession,
        user_id: str,
        terms: List[str]
    ) -> Dict[str, Any]:
        """Get computed thresholds for semantic terms."""

        context = await self._get_context(db, user_id)
        thresholds = context.get("computed_thresholds", {})
        numeric_stats = context.get("numeric_stats", {})

        result = {"definitions": {}}

        for term in terms:
            term_lower = term.lower()
            if "high" in term_lower and "value" in term_lower:
                if thresholds.get("high_value_aum"):
                    result["definitions"][term] = {
                        "field": "aum",
                        "operator": ">=",
                        "value": thresholds["high_value_aum"],
                        "description": f"Top 10% of clients by AUM (>= ${thresholds['high_value_aum']:,.0f})"
                    }
            elif "medium" in term_lower or "mid" in term_lower:
                if thresholds.get("medium_value_aum"):
                    result["definitions"][term] = {
                        "field": "aum",
                        "operator": ">=",
                        "value": thresholds["medium_value_aum"],
                        "description": f"Above median AUM (>= ${thresholds['medium_value_aum']:,.0f})"
                    }
            elif "recent" in term_lower:
                result["definitions"][term] = {
                    "field": "created_at",
                    "operator": ">=",
                    "value": "NOW() - INTERVAL '90 days'",
                    "description": "Clients added in the last 90 days"
                }

        result["all_thresholds"] = thresholds
        result["available_stats"] = list(numeric_stats.keys())

        return result

    async def _get_field_stats(
        self,
        db: AsyncSession,
        user_id: str,
        fields: List[str]
    ) -> Dict[str, Any]:
        """Get statistics for specific fields."""

        context = await self._get_context(db, user_id)

        result = {"fields": {}}

        for field in fields:
            field_lower = field.lower()

            # Check completeness
            completeness = context.get("field_completeness", {})
            if field_lower in completeness:
                result["fields"][field] = {
                    "completeness": completeness[field_lower],
                    "description": f"{completeness[field_lower]}% of records have {field} data"
                }

            # Check numeric stats
            numeric = context.get("numeric_stats", {})
            if field_lower in numeric:
                stats = numeric[field_lower]
                result["fields"][field] = {
                    **result["fields"].get(field, {}),
                    "stats": stats,
                    "description": f"Range: {stats.get('min', 'N/A')} to {stats.get('max', 'N/A')}, Avg: {stats.get('avg', 'N/A')}"
                }

        result["total_clients"] = context.get("total_clients", 0)

        return result


# Function to get context for orchestrator
async def get_data_context_for_planning(
    db: AsyncSession,
    user_id: str
) -> Dict[str, Any]:
    """
    Helper function for orchestrator to quickly get data context.
    Returns a summary suitable for including in planning prompts.
    """
    agent = DataDiscoveryAgent()
    context = await agent._get_context(db, user_id)

    # Format for planning prompt
    summary = f"""
DATA CONTEXT FOR USER:
- Total Clients: {context.get('total_clients', 0)}
- Data Sources: {context.get('sources', {})}
- Field Completeness: {context.get('field_completeness', {})}
"""

    # Add schema info
    schema = context.get('schema', {})
    if schema.get('has_schema'):
        summary += "\nDISCOVERED FIELDS:\n"
        numeric = [f["name"] for f in schema.get("numeric_fields", [])]
        text = [f["name"] for f in schema.get("text_fields", [])]
        if numeric:
            summary += f"- Numeric (use SQL Analytics): {', '.join(numeric)}\n"
        if text:
            summary += f"- Text (use Semantic Search): {', '.join(text)}\n"

    thresholds = context.get('computed_thresholds', {})
    if thresholds:
        summary += f"""
SEMANTIC THRESHOLDS (based on user's actual data):
"""
        if thresholds.get('high_value_aum'):
            summary += f"- 'High value' clients = AUM >= ${thresholds['high_value_aum']:,.0f} (top 10%)\n"
        if thresholds.get('medium_value_aum'):
            summary += f"- 'Medium value' clients = AUM >= ${thresholds['medium_value_aum']:,.0f} (top 50%)\n"

    return {
        "summary": summary,
        "context": context
    }
