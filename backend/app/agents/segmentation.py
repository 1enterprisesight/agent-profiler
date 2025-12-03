"""
Segmentation Agent

LLM-powered agent that groups and segments entities based on
characteristics and values. Creates actionable segments for business decisions.
Uses Gemini to understand data patterns and create meaningful groupings.
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
class SegmentationAgent(BaseAgent):
    """
    Groups and segments entities into meaningful categories.
    LLM determines segmentation strategies based on data context
    and generates queries for value tiers, categories, and clusters.
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Agent metadata for orchestrator's dynamic routing."""
        return {
            "name": "segmentation",
            "description": "Groups and segments entities into meaningful categories based on characteristics and values",
            "capabilities": [
                "Segment entities by value tiers (high/medium/low based on percentiles)",
                "Group data by categorical attributes (region, type, category)",
                "Identify natural clusters and groupings in the data",
                "Calculate segment sizes, percentages, and distributions",
                "Provide segment profiles with key characteristics (averages, totals)"
            ],
            "inputs": {
                "request": "The segmentation request from orchestrator",
                "data_source_id": "ID of the data source to analyze",
                "context": "Additional context from conversation (optional)",
                "previous_results": "Results from prior agents (optional)"
            },
            "outputs": {
                "results": "Segment data as structured results",
                "insights": "LLM-generated segment interpretation",
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
        """Execute segmentation analysis - LLM-driven grouping and categorization."""

        start_time = datetime.utcnow()
        conversation_id = message.conversation_id
        payload = message.payload
        request = payload.get("request", "")
        data_source_id = payload.get("data_source_id")
        additional_context = payload.get("context", "")
        previous_results = payload.get("previous_results", [])
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
            await emit(EventType.RECEIVED, "Received segmentation request",
                      {"request": request[:100]}, 1)

            # Get data source context (schema + semantic profile) - uses shared BaseAgent method
            await emit(EventType.THINKING, "Loading data context", {}, 2)

            data_context = await self.get_data_context(db, data_source_id, user_id)
            if not data_context:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    result={"error": "No data source found"},
                    metadata={}
                )

            # LLM analyzes request and generates segmentation queries
            await emit(EventType.THINKING, "Analyzing segmentation strategy",
                      {"columns_available": len(data_context.get("columns", []))}, 3)

            query_plan = await self._plan_queries(request, data_context, additional_context, previous_results)

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
            await emit(EventType.ACTION, f"Executing {len(query_plan.get('queries', []))} segmentation queries",
                      {"query_count": len(query_plan.get("queries", []))}, 4)

            all_results = []
            queries_executed = []

            for i, query_info in enumerate(query_plan.get("queries", [])):
                sql = query_info.get("sql")
                purpose = query_info.get("purpose", "Query")

                # Log the generated query for debugging
                self.logger.info("generated_segmentation_query", purpose=purpose, sql=sql)

                # Safety check
                if not self._is_safe_query(sql):
                    self.logger.warning("unsafe_query_blocked", sql=sql[:100])
                    continue

                result = await self._execute_query(db, sql, data_source_id, conversation_id)

                if result.get("error"):
                    # Try self-correction
                    await emit(EventType.THINKING, f"Query error, attempting correction",
                              {"error": result["error"][:100], "failed_sql": sql[:500]}, 4 + i)

                    corrected = await self._correct_query(
                        sql, result["error"], data_context
                    )
                    if corrected:
                        result = await self._execute_query(db, corrected, data_source_id, conversation_id)
                        sql = corrected

                if not result.get("error"):
                    all_results.append({
                        "purpose": purpose,
                        "data": result.get("data", []),
                        "row_count": result.get("row_count", 0)
                    })
                    queries_executed.append({"sql": sql, "purpose": purpose})

            # LLM synthesizes insights from segmentation results
            await emit(EventType.THINKING, "Synthesizing segment insights",
                      {"result_sets": len(all_results)}, 5)

            insights = await self._synthesize_insights(
                request, data_context, all_results, additional_context
            )

            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            await emit(EventType.RESULT, "Segmentation complete",
                      {"insight_preview": insights.get("summary", "")[:200]}, 6)

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "results": all_results,
                    "insights": insights,
                    "queries_executed": queries_executed,
                    "visualization_hint": insights.get("visualization_hint", "bar")
                },
                metadata={
                    "duration_ms": duration_ms,
                    "queries_run": len(queries_executed),
                    "total_rows": sum(r.get("row_count", 0) for r in all_results)
                }
            )

        except Exception as e:
            await emit(EventType.ERROR, f"Segmentation failed: {str(e)[:100]}",
                      {"error": str(e)}, 99)

            return AgentResponse(
                status=AgentStatus.FAILED,
                result={"error": str(e)},
                metadata={}
            )

    def _build_sql_expressions(self, data_context: Dict) -> Dict[str, str]:
        """Convert field_mappings to exact SQL expressions."""
        raw_mappings = data_context.get('field_mappings', {})
        sql_expressions = {}
        for col, mapping in raw_mappings.items():
            target = mapping.get('target', '') if isinstance(mapping, dict) else mapping
            if target.startswith('core_data.'):
                key = target.replace('core_data.', '')
                sql_expressions[col] = f"(core_data->>'{key}')"
            elif target.startswith('custom_data.'):
                key = target.replace('custom_data.', '')
                sql_expressions[col] = f"(custom_data->>'{key}')"
            else:
                sql_expressions[col] = target
        return sql_expressions

    async def _plan_queries(self, request: str, data_context: Dict, additional_context: str, previous_results: List[Dict] = None) -> Dict:
        """LLM plans segmentation queries based on request and data context."""

        sql_expressions = self._build_sql_expressions(data_context)

        # Prepare previous results summary if available
        previous_results_summary = []
        if previous_results:
            for pr in previous_results:
                previous_results_summary.append({
                    "agent": pr.get("agent"),
                    "task": pr.get("task"),
                    "summary": pr.get("result", {}).get("insights", {}).get("summary", "")[:200]
                })

        prompt = f"""You are a data segmentation analyst generating PostgreSQL queries.

REQUEST: {request}

=== DATA SOURCE ===
File: {data_context.get('file_name')}
Rows: {data_context.get('row_count', 0)}
Entity: {data_context.get('semantic_profile', {}).get('entity_name', 'unknown')}
Domain: {data_context.get('semantic_profile', {}).get('domain', 'unknown')}

=== LOGICAL COLUMNS (names, types, samples) ===
{json.dumps(data_context.get('detected_types', {}), indent=2)}

=== FIELD DESCRIPTIONS (semantic meaning of each column) ===
{json.dumps(data_context.get('semantic_profile', {}).get('field_descriptions', {}), indent=2)}

=== SQL EXPRESSIONS (copy these exactly) ===
Data is stored in table 'clients'. Use these exact SQL expressions for each column:
{json.dumps(sql_expressions, indent=2)}

IMPORTANT: Copy these expressions exactly as shown. Do not modify them.

{f"=== PREVIOUS AGENT RESULTS ===" if previous_results_summary else ""}
{json.dumps(previous_results_summary, indent=2) if previous_results_summary else ""}

{f"ADDITIONAL CONTEXT: {additional_context}" if additional_context else ""}

=== QUERY GENERATION RULES ===
1. Map user terms to logical columns using FIELD DESCRIPTIONS
2. Copy the exact SQL expression from SQL EXPRESSIONS section
3. For numeric operations, cast with ::numeric (e.g., (core_data->>'value')::numeric)
4. Required filter: WHERE data_source_id = '{data_context.get('data_source_id')}'
5. Filter nulls on analyzed columns
6. CRITICAL: Always alias every column with AS using readable names

=== SEGMENTATION-SPECIFIC INSTRUCTIONS ===
Generate queries that create meaningful segments:

1. **Value Tier Segmentation** (if numeric data available):
   - Use percentiles to create tiers (e.g., top 20% = High, middle 60% = Medium, bottom 20% = Low)
   - Use NTILE(3) or NTILE(4) for even distribution
   - Or use subqueries with percentile_cont() for custom breakpoints

2. **Categorical Grouping**:
   - GROUP BY categorical columns (region, type, category)
   - Include COUNT(*) for segment size
   - Include SUM/AVG of key metrics per segment

3. **Multi-dimensional Segments** (if appropriate):
   - Combine multiple attributes (e.g., region + value tier)
   - Create cross-tabulations

4. **Segment Profiles**:
   - For each segment, calculate key characteristics
   - Include percentages of total

If the request is unclear, respond with:
{{
  "needs_clarification": true,
  "clarification_question": "Your question to the user",
  "reason": "Why you need this clarification"
}}

Otherwise, respond with a query plan:
{{
  "needs_clarification": false,
  "understanding": "Your interpretation of the segmentation request",
  "segmentation_approach": "Brief description of how you'll segment the data",
  "queries": [
    {{
      "purpose": "What segment this query creates or profiles",
      "sql": "SELECT ... FROM clients WHERE data_source_id = '...' ..."
    }}
  ]
}}

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
            self.logger.error("segmentation_query_planning_error", error=str(e))
            return {"needs_clarification": True, "clarification_question": "Could you rephrase your segmentation request?", "reason": str(e)}

    def _is_safe_query(self, sql: str) -> bool:
        """Check if query is safe to execute (read-only)."""
        if not sql:
            return False
        sql_upper = sql.upper().strip()
        dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"]
        return not any(sql_upper.startswith(d) or f" {d} " in sql_upper for d in dangerous)

    async def _execute_query(
        self,
        db: AsyncSession,
        sql: str,
        data_source_id: str,
        session_id: str = None
    ) -> Dict:
        """Execute a read-only SQL query using autocommit connection."""
        from app.database import engine
        from app.models import SQLQueryLog
        from app.config import settings
        import uuid

        start_time = datetime.utcnow()
        error_msg = None
        row_count = 0

        try:
            # Use raw connection with autocommit - no transaction, failures don't block
            async with engine.connect() as conn:
                result = await conn.execute(text(sql))
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

                row_count = len(data)
                return {"data": data, "row_count": row_count}

        except Exception as e:
            error_msg = str(e)
            self.logger.warning("segmentation_query_failed", error=error_msg[:200])
            return {"error": error_msg}

        finally:
            # Log query to sql_query_log table
            if settings.enable_sql_query_logging and session_id:
                try:
                    execution_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    query_log = SQLQueryLog(
                        id=uuid.uuid4(),
                        session_id=session_id,
                        agent_name=self.name,
                        query_text=sql,
                        result_summary={"row_count": row_count} if not error_msg else None,
                        execution_time_ms=execution_ms,
                        error=error_msg
                    )
                    db.add(query_log)
                    await db.flush()
                except Exception as log_err:
                    self.logger.warning("failed_to_log_query", error=str(log_err)[:100])

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
            self.logger.error("segmentation_query_correction_error", error=str(e))
            return None

    async def _synthesize_insights(self, request: str, data_context: Dict, results: List[Dict], additional_context: str) -> Dict:
        """LLM synthesizes segmentation insights from query results."""

        # Prepare results summary for LLM
        results_summary = []
        for r in results:
            results_summary.append({
                "purpose": r.get("purpose"),
                "row_count": r.get("row_count"),
                "sample_data": r.get("data", [])[:15]  # First 15 rows for segments
            })

        prompt = f"""You are a segmentation analyst. Synthesize insights from these segmentation results.

ORIGINAL REQUEST: {request}

DATA CONTEXT:
- Entity: {data_context.get('semantic_profile', {}).get('entity_name', 'record')}
- Domain: {data_context.get('semantic_profile', {}).get('domain', 'unknown')}
- Total Records: {data_context.get('row_count', 0)}

SEGMENTATION RESULTS:
{json.dumps(results_summary, indent=2, default=str)}

{f"ADDITIONAL CONTEXT: {additional_context}" if additional_context else ""}

Provide segmentation-focused insights:
1. A clear summary of the segments identified
2. Key characteristics of each segment (size, value, distinguishing features)
3. Business implications of the segmentation
4. Suggested visualization type (bar, pie, table - segments are often best as bar or pie)

Return valid JSON:
{{
  "summary": "Overview of segments identified with key numbers",
  "segments": [
    {{
      "name": "Segment name",
      "size": "Count or percentage",
      "characteristics": "Key distinguishing features"
    }}
  ],
  "findings": [
    "Key finding about segments",
    "Another finding with data"
  ],
  "insights": [
    "Strategic insight or recommendation"
  ],
  "visualization_hint": "bar|pie|table"
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
            self.logger.error("segmentation_insight_synthesis_error", error=str(e))
            return {
                "summary": "Segmentation completed but insight synthesis failed",
                "segments": [],
                "findings": [],
                "insights": [],
                "visualization_hint": "bar"
            }
