"""
SQL Analytics Agent - Phase D: Self-Describing
Generates and executes SQL queries for quantitative analysis using Gemini Pro.
Follows the segmentation.py template pattern.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import json

import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus, EventType
from app.agents.schema_utils import get_schema_context, build_sql_schema_description
from app.config import settings


class SQLAnalyticsAgent(BaseAgent):
    """
    SQL Analytics Agent - Phase D: Self-Describing

    Quantitative analysis using SQL with complete transparency.
    Uses LLM to interpret tasks - NO hardcoded action routing.
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Agent describes itself for dynamic discovery by orchestrator."""
        return {
            "name": "sql_analytics",
            "purpose": "Quantitative analysis using SQL - counting, aggregating, filtering, and ranking data",
            "when_to_use": [
                "User needs to COUNT records (e.g., 'how many clients', 'number of contacts')",
                "User wants aggregations: SUM, AVG, MIN, MAX, COUNT",
                "User wants to GROUP BY any field - including text fields like company, city, or category",
                "User asks for 'most common', 'top N', 'breakdown by', 'count by'",
                "User needs mathematical calculations on numeric fields",
                "User wants to filter by exact values, ranges, or dates",
                "User needs to sort or rank records"
            ],
            "when_not_to_use": [
                "User is searching for meaning/concepts in text (use semantic_search)",
                "User wants fuzzy text matching or similarity (use semantic_search)",
                "User wants AI-driven clustering or personas (use segmentation)",
                "User needs pattern recognition or anomaly detection (use pattern_recognition)"
            ],
            "example_tasks": [
                "How many clients do I have?",
                "Show the most common companies and count of clients for each",
                "What is the average AUM per client?",
                "Count clients by data source",
                "Show top 10 cities by number of clients",
                "Find clients with AUM over $1M",
                "Breakdown of clients by company"
            ],
            "data_source_aware": True
        }

    def get_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Agent's internal capabilities for LLM-driven task routing."""
        return {
            "generate_and_execute": {
                "description": "Generate SQL from natural language and execute it",
                "examples": ["query", "find", "count", "calculate", "show", "list"],
                "method": "_generate_and_execute_query"
            },
            "aggregate_data": {
                "description": "Perform aggregations like SUM, AVG, COUNT with GROUP BY",
                "examples": ["total", "average", "sum", "group by", "breakdown"],
                "method": "_aggregate_data"
            },
            "filter_quantitative": {
                "description": "Filter data by numerical criteria or date ranges",
                "examples": ["greater than", "less than", "between", "before", "after"],
                "method": "_filter_by_quantitative"
            }
        }

    def __init__(self):
        super().__init__()

        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )

        self.model = GenerativeModel(settings.gemini_pro_model)

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """Execute SQL analytics task using LLM-driven interpretation."""
        task = message.action
        payload = message.payload
        conversation_id = message.conversation_id
        start_time = datetime.utcnow()

        try:
            # TRANSPARENCY: Received event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.RECEIVED,
                title=f"Received: {task[:50]}..." if len(task) > 50 else f"Received: {task}",
                details={"task": task, "payload": payload},
                step_number=1
            )

            # TRANSPARENCY: Thinking event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.THINKING,
                title="Analyzing query requirements...",
                details={"task": task, "available_capabilities": list(self.get_capabilities().keys())},
                step_number=2
            )

            # Build query intent from task
            query_intent = task
            if payload.get("query_intent"):
                query_intent = payload.get("query_intent")

            # TRANSPARENCY: Decision event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.DECISION,
                title="Generating SQL query...",
                details={"query_intent": query_intent},
                step_number=3
            )

            # Generate SQL
            sql_query = await self._generate_sql(
                query_intent,
                payload.get("filters", []),
                payload.get("client_ids"),
                payload.get("context", {}),
                conversation_id,
                user_id,
                db
            )

            if not sql_query:
                await self.emit_event(
                    db=db,
                    session_id=conversation_id,
                    user_id=user_id,
                    event_type=EventType.ERROR,
                    title="Failed to generate SQL query",
                    details={"query_intent": query_intent},
                    step_number=4
                )
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error="Failed to generate SQL query"
                )

            # Validate query
            validation = self._validate_sql_query(sql_query)
            if not validation["safe"]:
                await self.emit_event(
                    db=db,
                    session_id=conversation_id,
                    user_id=user_id,
                    event_type=EventType.ERROR,
                    title=f"Unsafe query: {validation['reason']}",
                    details={"query": sql_query, "reason": validation["reason"]},
                    step_number=4
                )
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error=f"Unsafe query: {validation['reason']}"
                )

            # TRANSPARENCY: Action event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.ACTION,
                title="Executing SQL query...",
                details={"query_preview": sql_query[:200] + "..." if len(sql_query) > 200 else sql_query},
                step_number=4
            )

            # Execute query
            results = await self._execute_query(sql_query, conversation_id, user_id, db)
            formatted = self._format_query_results(results, query_intent)

            # Generate insights
            insights = await self._generate_insights(
                query_intent, formatted, conversation_id, user_id, db
            )

            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # TRANSPARENCY: Result event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.RESULT,
                title=f"Query returned {formatted['row_count']} results",
                details={
                    "row_count": formatted["row_count"],
                    "summary": formatted["summary"],
                    "has_insights": bool(insights.get("patterns"))
                },
                step_number=5,
                duration_ms=duration_ms
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "query": sql_query,
                    "results": formatted["data"],
                    "summary": formatted["summary"],
                    "insights": insights,
                    "row_count": formatted["row_count"]
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "duration_ms": duration_ms
                }
            )

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            # Rollback any failed transaction before trying to emit error event
            try:
                await db.rollback()
            except Exception:
                pass

            try:
                await self.emit_event(
                    db=db,
                    session_id=conversation_id,
                    user_id=user_id,
                    event_type=EventType.ERROR,
                    title=f"SQL analytics failed: {str(e)[:50]}",
                    details={"error": str(e), "task": task},
                    step_number=5,
                    duration_ms=duration_ms
                )
            except Exception as emit_error:
                self.logger.warning("failed_to_emit_error_event", error=str(emit_error))

            self.logger.error("sql_analytics_failed", error=str(e), exc_info=True)
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"SQL analytics failed: {str(e)}"
            )

    async def _generate_sql(
        self,
        query_intent: str,
        filters: List[str],
        client_ids: Optional[List[str]],
        context: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> str:
        """Generate SQL query using Gemini Pro with dynamic schema."""
        # Get dynamic schema context for this user
        schema_context = await get_schema_context(db, user_id)
        schema_desc = build_sql_schema_description(schema_context)

        context_str = f"\n\nAdditional Context:\n{json.dumps(context, indent=2)}" if context else ""
        client_ids_clause = ""
        if client_ids:
            ids_str = "', '".join(client_ids)
            client_ids_clause = f"\nFilter to these specific client IDs: [{ids_str}]"

        prompt = f"""You are a SQL query generator for a PostgreSQL database.

{schema_desc}

CRITICAL RULES:
1. SECURITY - MANDATORY: Every query MUST include "WHERE user_id = :user_id"
2. USE EXACT FIELD PATHS from schema - e.g., custom_data->>'companies', core_data->>'aum'
3. ONLY use quantitative operations: SUM, AVG, COUNT, MIN, MAX, date math, GROUP BY
4. NEVER use LIKE, ILIKE, regex, or full-text search - those belong to Semantic Search
5. For numeric operations: cast to numeric, e.g., (core_data->>'aum')::numeric
6. Always include LIMIT (default 100) for SELECT queries, unless doing COUNT/SUM/AVG aggregation
7. For custom fields not in core columns, use: custom_data->>'field_name' or core_data->>'field_name'

Query Intent: "{query_intent}"
Filters: {json.dumps(filters) if filters else "None"}{client_ids_clause}{context_str}

Return ONLY the SELECT statement, no markdown:"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 1024}
            )

            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_pro_model,
                prompt=prompt,
                response=response.text,
            )

            sql = response.text.strip()
            if sql.startswith("```sql"):
                sql = sql[6:]
            elif sql.startswith("```"):
                sql = sql[3:]
            if sql.endswith("```"):
                sql = sql[:-3]

            return sql.strip()

        except Exception as e:
            self.logger.error("sql_generation_failed", error=str(e), exc_info=True)
            return ""

    def _validate_sql_query(self, query: str) -> Dict[str, Any]:
        """Validate SQL query for safety."""
        query_upper = query.upper()

        dangerous = [
            ("DROP", "DROP not allowed"), ("TRUNCATE", "TRUNCATE not allowed"),
            ("DELETE", "DELETE not allowed"), ("UPDATE", "UPDATE not allowed"),
            ("INSERT", "INSERT not allowed"), ("ALTER", "ALTER not allowed"),
            ("CREATE", "CREATE not allowed"), ("GRANT", "GRANT not allowed"),
        ]

        for op, reason in dangerous:
            if op in query_upper:
                return {"safe": False, "reason": reason}

        if not query_upper.strip().startswith("SELECT"):
            return {"safe": False, "reason": "Only SELECT queries allowed"}

        if " LIKE " in query_upper or " ILIKE " in query_upper:
            return {"safe": False, "reason": "LIKE queries not allowed - use Semantic Search"}

        if ":user_id" not in query.lower() and "user_id" not in query.lower():
            return {"safe": False, "reason": "Query must include user_id filter"}

        return {"safe": True, "reason": "Query passed validation"}

    async def _execute_query(
        self,
        query: str,
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Execute SQL query and return results."""
        from app.models import SQLQueryLog

        start_time = datetime.utcnow()

        try:
            result = await db.execute(text(query), {"user_id": user_id})
            rows = result.fetchall()

            if rows:
                columns = result.keys()
                results = [dict(zip(columns, row)) for row in rows]
            else:
                results = []

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            query_log = SQLQueryLog(
                session_id=conversation_id,
                agent_name="sql_analytics",
                query_text=query,
                result_summary={
                    "row_count": len(results),
                    "columns": list(columns) if rows else [],
                    "execution_time_ms": execution_time_ms
                },
                execution_time_ms=execution_time_ms
            )
            db.add(query_log)
            await db.commit()

            return results

        except SQLAlchemyError as e:
            self.logger.error("query_execution_failed", error=str(e), query=query)
            raise

    def _format_query_results(self, results: List[Dict[str, Any]], query_intent: str) -> Dict[str, Any]:
        """Format query results for display."""
        if not results:
            return {"data": [], "row_count": 0, "summary": "No results found"}

        row_count = len(results)

        if row_count == 1 and len(results[0]) == 1:
            key = list(results[0].keys())[0]
            value = results[0][key]
            summary = f"Result: {value}"
        else:
            summary = f"Found {row_count} result{'s' if row_count != 1 else ''}"

        return {"data": results, "row_count": row_count, "summary": summary}

    async def _generate_insights(
        self,
        query_intent: str,
        formatted_results: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Generate insights from query results."""
        results = formatted_results["data"]
        if not results:
            return {"patterns": [], "suggestions": []}

        try:
            prompt = f"""Analyze these SQL query results and provide brief insights.

Query Intent: "{query_intent}"
Results Summary: {len(results)} rows
Sample: {json.dumps(results[:5], default=str)}

Provide as JSON:
{{"patterns": ["Pattern 1"], "suggestions": ["Suggestion 1"]}}"""

            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 512}
            )

            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            return json.loads(text.strip())
        except:
            return {"patterns": [], "suggestions": []}

    async def _filter_by_quantitative(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession) -> AgentResponse:
        """Filter by quantitative criteria - delegates to main method."""
        return await self._execute_internal(
            AgentMessage(conversation_id=conversation_id, action=payload.get("query_intent", "filter data"), payload=payload),
            db, user_id
        )

    async def _aggregate_data(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession) -> AgentResponse:
        """Aggregate data - delegates to main method."""
        return await self._execute_internal(
            AgentMessage(conversation_id=conversation_id, action=payload.get("query_intent", "aggregate data"), payload=payload),
            db, user_id
        )
