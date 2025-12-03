"""
SQL Analytics Agent

LLM-powered agent that analyzes structured data using SQL.
Uses Gemini to understand requests, schema, and semantic context
to generate comprehensive queries and insights.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus, EventType, register_agent
from app.config import settings


@register_agent
class SQLAnalyticsAgent(BaseAgent):
    """
    Analyzes structured data using SQL queries.
    LLM interprets requests and generates queries based on
    schema and semantic understanding of the data.
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Agent metadata for orchestrator's dynamic routing."""
        return {
            "name": "sql_analytics",
            "description": "Analyzes structured data using SQL queries to answer quantitative questions",
            "capabilities": [
                "Execute analytical queries against structured client data",
                "Aggregate, filter, group, and compare data",
                "Calculate statistics and distributions",
                "Provide data-backed insights and supporting evidence",
                "Return results suitable for visualization"
            ],
            "inputs": {
                "request": "The analytical question or task from orchestrator",
                "data_source_id": "ID of the data source to analyze",
                "context": "Additional context from conversation (optional)"
            },
            "outputs": {
                "results": "Query results as structured data",
                "insights": "LLM-generated interpretation of findings",
                "queries_executed": "SQL queries that were run",
                "visualization_hint": "Suggested visualization type"
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
        """Execute SQL analytics - LLM-driven query generation and insight."""

        start_time = datetime.utcnow()
        conversation_id = message.conversation_id
        payload = message.payload
        request = payload.get("request", "")
        data_source_id = payload.get("data_source_id")
        additional_context = payload.get("context", "")
        skip_events = payload.get("skip_transparency_events", False)

        # Helper for events
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
            await emit(EventType.RECEIVED, "Received analytics request",
                      {"request": request[:100]}, 1)

            # Get data source context (schema + semantic profile)
            await emit(EventType.THINKING, "Loading data context", {}, 2)

            data_context = await self._get_data_context(db, data_source_id, user_id)
            if "error" in data_context:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    result={"error": data_context["error"]},
                    metadata={}
                )

            # LLM analyzes request and generates query plan
            await emit(EventType.THINKING, "Analyzing request and planning queries",
                      {"columns_available": len(data_context.get("columns", []))}, 3)

            query_plan = await self._plan_queries(request, data_context, additional_context)

            if query_plan.get("needs_clarification"):
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "needs_clarification": True,
                        "question": query_plan.get("clarification_question"),
                        "reason": query_plan.get("reason")
                    },
                    metadata={"type": "clarification_needed"}
                )

            # Execute queries
            await emit(EventType.ACTION, f"Executing {len(query_plan.get('queries', []))} queries",
                      {"query_count": len(query_plan.get("queries", []))}, 4)

            all_results = []
            queries_executed = []

            for i, query_info in enumerate(query_plan.get("queries", [])):
                sql = query_info.get("sql")
                purpose = query_info.get("purpose", "Query")

                # Safety check
                if not self._is_safe_query(sql):
                    self.logger.warning("unsafe_query_blocked", sql=sql[:100])
                    continue

                result = await self._execute_query(db, sql, data_source_id)

                if result.get("error"):
                    # Try self-correction
                    await emit(EventType.THINKING, f"Query error, attempting correction",
                              {"error": result["error"][:100]}, 4 + i)

                    corrected = await self._correct_query(
                        sql, result["error"], data_context
                    )
                    if corrected:
                        result = await self._execute_query(db, corrected, data_source_id)
                        sql = corrected

                if not result.get("error"):
                    all_results.append({
                        "purpose": purpose,
                        "data": result.get("data", []),
                        "row_count": result.get("row_count", 0)
                    })
                    queries_executed.append({"sql": sql, "purpose": purpose})

            # LLM synthesizes insights from results
            await emit(EventType.THINKING, "Synthesizing insights from data",
                      {"result_sets": len(all_results)}, 5)

            insights = await self._synthesize_insights(
                request, data_context, all_results, additional_context
            )

            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            await emit(EventType.RESULT, "Analysis complete",
                      {"insight_preview": insights.get("summary", "")[:200]}, 6)

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "results": all_results,
                    "insights": insights,
                    "queries_executed": queries_executed,
                    "visualization_hint": insights.get("visualization_hint", "table")
                },
                metadata={
                    "duration_ms": duration_ms,
                    "queries_run": len(queries_executed),
                    "total_rows": sum(r.get("row_count", 0) for r in all_results)
                }
            )

        except Exception as e:
            await emit(EventType.ERROR, f"Analysis failed: {str(e)[:100]}",
                      {"error": str(e)}, 99)

            return AgentResponse(
                status=AgentStatus.FAILED,
                result={"error": str(e)},
                metadata={}
            )

    async def _get_data_context(self, db: AsyncSession, data_source_id: str, user_id: str) -> Dict:
        """Get schema and semantic profile for data source."""

        # If no data_source_id, get most recent for user
        if not data_source_id:
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
                return {"error": "No data sources found"}
            data_source_id = str(row[0])
            file_name = row[1]
            metadata = row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}")
        else:
            result = await db.execute(
                text("""
                    SELECT file_name, metadata
                    FROM uploaded_files
                    WHERE id = :data_source_id
                """),
                {"data_source_id": data_source_id}
            )
            row = result.fetchone()
            if not row:
                return {"error": f"Data source {data_source_id} not found"}
            file_name = row[0]
            metadata = row[1] if isinstance(row[1], dict) else json.loads(row[1] or "{}")

        return {
            "data_source_id": data_source_id,
            "file_name": file_name,
            "columns": metadata.get("columns", []),
            "detected_types": metadata.get("detected_types", {}),
            "semantic_profile": metadata.get("semantic_profile", {}),
            "row_count": metadata.get("rows", 0)
        }

    async def _plan_queries(self, request: str, data_context: Dict, additional_context: str) -> Dict:
        """LLM plans what queries to run based on request and data context."""

        prompt = f"""You are a data analyst. Given a request and data context, plan SQL queries to answer it comprehensively.

REQUEST: {request}

DATA SOURCE: {data_context.get('file_name')}
TOTAL ROWS: {data_context.get('row_count', 0)}

SCHEMA (columns and types):
{json.dumps(data_context.get('detected_types', {}), indent=2)}

SEMANTIC PROFILE:
- Entity: {data_context.get('semantic_profile', {}).get('entity_name', 'unknown')}
- Domain: {data_context.get('semantic_profile', {}).get('domain', 'unknown')}
- Categories: {json.dumps(data_context.get('semantic_profile', {}).get('data_categories', {}), indent=2)}
- Field Descriptions: {json.dumps(data_context.get('semantic_profile', {}).get('field_descriptions', {}), indent=2)}

{f"ADDITIONAL CONTEXT: {additional_context}" if additional_context else ""}

IMPORTANT:
- Data is stored in the 'clients' table
- Each row's data is in JSONB columns: core_data and custom_data
- Access fields like: (core_data->>'field_name') or (custom_data->>'field_name')
- Cast to appropriate types: (core_data->>'field_name')::numeric
- Filter by data_source_id = '{data_context.get('data_source_id')}'

If the request is unclear or you need more information to provide a good analysis, respond with:
{{
  "needs_clarification": true,
  "clarification_question": "Your question to the user",
  "reason": "Why you need this clarification"
}}

Otherwise, respond with a query plan:
{{
  "needs_clarification": false,
  "understanding": "Your interpretation of what's being asked",
  "queries": [
    {{
      "purpose": "What this query answers",
      "sql": "SELECT ... FROM clients WHERE data_source_id = '...' ..."
    }}
  ]
}}

Generate queries that:
1. Directly answer the core request
2. Provide supporting statistics that add value
3. Surface interesting patterns relevant to the question

Return valid JSON only."""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.2}
            )
            response_text = response.text.strip()

            # Parse JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            return json.loads(response_text.strip())

        except Exception as e:
            self.logger.error("query_planning_error", error=str(e))
            return {"needs_clarification": True, "clarification_question": "Could you rephrase your question?", "reason": str(e)}

    def _is_safe_query(self, sql: str) -> bool:
        """Check if query is safe to execute (read-only)."""
        if not sql:
            return False
        sql_upper = sql.upper().strip()
        dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"]
        return not any(sql_upper.startswith(d) or f" {d} " in sql_upper for d in dangerous)

    async def _execute_query(self, db: AsyncSession, sql: str, data_source_id: str) -> Dict:
        """Execute a SQL query and return results."""
        try:
            result = await db.execute(text(sql))
            rows = result.fetchall()
            columns = result.keys()

            # Convert to list of dicts
            data = [dict(zip(columns, row)) for row in rows]

            # Handle special types for JSON serialization
            for row in data:
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):
                        row[key] = value.isoformat()
                    elif isinstance(value, (bytes,)):
                        row[key] = value.decode('utf-8', errors='replace')

            return {"data": data, "row_count": len(data)}

        except Exception as e:
            return {"error": str(e)}

    async def _correct_query(self, original_sql: str, error: str, data_context: Dict) -> Optional[str]:
        """LLM attempts to fix a failed query."""

        prompt = f"""The following SQL query failed. Fix it.

ORIGINAL QUERY:
{original_sql}

ERROR:
{error}

SCHEMA CONTEXT:
- Table: clients
- Data is in JSONB columns: core_data, custom_data
- Access fields: (core_data->>'field_name') or (custom_data->>'field_name')
- Available columns: {json.dumps(list(data_context.get('detected_types', {}).keys()))}

Return ONLY the corrected SQL query, no explanation."""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.1}
            )
            corrected = response.text.strip()

            # Clean up response
            if "```sql" in corrected:
                corrected = corrected.split("```sql")[1].split("```")[0]
            elif "```" in corrected:
                corrected = corrected.split("```")[1].split("```")[0]

            return corrected.strip()

        except Exception as e:
            self.logger.error("query_correction_error", error=str(e))
            return None

    async def _synthesize_insights(self, request: str, data_context: Dict, results: List[Dict], additional_context: str) -> Dict:
        """LLM synthesizes insights from query results."""

        # Prepare results summary for LLM
        results_summary = []
        for r in results:
            results_summary.append({
                "purpose": r.get("purpose"),
                "row_count": r.get("row_count"),
                "sample_data": r.get("data", [])[:10]  # First 10 rows
            })

        prompt = f"""You are a data analyst. Synthesize insights from these query results.

ORIGINAL REQUEST: {request}

DATA CONTEXT:
- Entity: {data_context.get('semantic_profile', {}).get('entity_name', 'record')}
- Domain: {data_context.get('semantic_profile', {}).get('domain', 'unknown')}

QUERY RESULTS:
{json.dumps(results_summary, indent=2, default=str)}

{f"ADDITIONAL CONTEXT: {additional_context}" if additional_context else ""}

Provide:
1. A clear summary answering the original request
2. Key findings backed by the data
3. Any interesting patterns or insights you notice
4. Suggested visualization type (bar, line, pie, table, or none)

Return valid JSON:
{{
  "summary": "Direct answer to the request with key numbers",
  "findings": [
    "Finding 1 with specific data",
    "Finding 2 with specific data"
  ],
  "insights": [
    "Insight or pattern noticed"
  ],
  "visualization_hint": "bar|line|pie|table"
}}"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.3}
            )
            response_text = response.text.strip()

            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            return json.loads(response_text.strip())

        except Exception as e:
            self.logger.error("insight_synthesis_error", error=str(e))
            return {
                "summary": "Analysis completed but insight synthesis failed",
                "findings": [],
                "insights": [],
                "visualization_hint": "table"
            }
