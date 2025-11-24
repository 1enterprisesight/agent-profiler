"""
SQL Analytics Agent
Generates and executes SQL queries for quantitative analysis using Gemini Pro
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import json
from datetime import datetime

import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus
from app.config import settings


# Database schema information for SQL generation
DATABASE_SCHEMA = {
    "clients": {
        "description": "Client records from all data sources",
        "columns": {
            "id": "UUID - Primary key",
            "source_type": "VARCHAR - Data source type (csv, salesforce, wealthbox, etc.)",
            "source_id": "VARCHAR - Original ID in source system",
            "connection_id": "UUID - Reference to CRM connection",
            "client_name": "VARCHAR - Client full name",
            "contact_email": "VARCHAR - Primary email address",
            "company_name": "VARCHAR - Company/firm name",
            "core_data": "JSONB - Structured core fields (phone, address, aum, etc.)",
            "custom_data": "JSONB - Custom fields from source",
            "computed_metrics": "JSONB - Calculated scores and metrics",
            "synced_at": "TIMESTAMP - Last sync time",
            "created_at": "TIMESTAMP - Record creation time",
            "updated_at": "TIMESTAMP - Last update time"
        },
        "jsonb_fields": {
            "core_data": ["aum", "risk_score", "last_contact_date", "phone", "address", "age", "account_value"],
            "custom_data": ["varies by source"],
            "computed_metrics": ["engagement_score", "churn_risk", "lifetime_value"]
        },
        "indexes": ["source_type", "source_id", "contact_email", "core_data", "custom_data"]
    },
    "data_sources": {
        "description": "Uploaded files and data sources",
        "columns": {
            "id": "UUID - Primary key",
            "user_id": "VARCHAR - Owner user ID",
            "source_type": "VARCHAR - Source type",
            "source_name": "VARCHAR - Display name",
            "file_name": "VARCHAR - Original filename",
            "status": "VARCHAR - Processing status",
            "records_ingested": "INTEGER - Number of records imported",
            "meta_data": "JSONB - File metadata and schema info",
            "created_at": "TIMESTAMP - Upload time"
        }
    }
}


class SQLAnalyticsAgent(BaseAgent):
    """
    SQL Analytics Agent - Quantitative analysis using SQL

    Capabilities:
    - Math operations (SUM, AVG, COUNT, MIN, MAX)
    - Date/time calculations
    - Exact value filtering (WHERE col = value)
    - Aggregations with GROUP BY
    - Statistical calculations

    Never Uses:
    - LIKE or regex patterns (use Semantic Search Agent)
    - Fuzzy text matching
    - Natural language search in text fields
    """

    def __init__(self):
        super().__init__(
            name="sql_analytics",
            description="Quantitative analysis and SQL query generation"
        )

        # Initialize Vertex AI
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )

        # Use Pro model for complex SQL generation
        self.model = GenerativeModel(settings.gemini_pro_model)

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """
        Execute SQL analytics action

        Actions:
            - generate_and_execute_query: Generate SQL and execute it
            - filter_by_quantitative: Filter results by quantitative criteria
            - aggregate_data: Perform aggregations
            - calculate_metrics: Calculate statistical metrics
        """
        action = message.action
        payload = message.payload

        if action == "generate_and_execute_query":
            return await self._generate_and_execute_query(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "filter_by_quantitative":
            return await self._filter_by_quantitative(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "aggregate_data":
            return await self._aggregate_data(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "calculate_metrics":
            return await self._calculate_metrics(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        else:
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Unknown action: {action}"
            )

    async def _generate_and_execute_query(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Generate SQL query from natural language and execute it
        """
        try:
            query_intent = payload.get("query_intent", "")
            filters = payload.get("filters", [])
            client_ids = payload.get("client_ids")  # Optional pre-filtered list
            context = payload.get("context", {})

            self.logger.info(
                "generating_sql_query",
                query_intent=query_intent,
                has_filters=len(filters) > 0,
                has_client_ids=client_ids is not None
            )

            # Generate SQL using Gemini Pro
            sql_query = await self._generate_sql(
                query_intent,
                filters,
                client_ids,
                context,
                conversation_id,
                user_id,
                db
            )

            if not sql_query:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error="Failed to generate SQL query"
                )

            # Validate query for safety
            validation_result = self._validate_sql_query(sql_query)
            if not validation_result["safe"]:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error=f"Unsafe query: {validation_result['reason']}"
                )

            # Execute query
            results = await self._execute_query(
                sql_query,
                conversation_id,
                user_id,
                db
            )

            # Format results
            formatted_results = self._format_query_results(results, query_intent)

            # Generate insights
            insights = await self._generate_insights(
                query_intent,
                formatted_results,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "query": sql_query,
                    "results": formatted_results["data"],
                    "summary": formatted_results["summary"],
                    "insights": insights,
                    "row_count": formatted_results["row_count"]
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "query_type": "quantitative_analysis"
                }
            )

        except Exception as e:
            self.logger.error(
                "sql_query_generation_failed",
                error=str(e),
                query_intent=payload.get("query_intent"),
                exc_info=True
            )
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
        """
        Generate SQL query using Gemini Pro
        """
        # Build schema description
        schema_desc = self._build_schema_description()

        # Build context string
        context_str = ""
        if context:
            context_str = f"\n\nAdditional Context:\n{json.dumps(context, indent=2)}"

        # Build client_ids filter if provided
        client_ids_clause = ""
        if client_ids:
            ids_str = "', '".join(client_ids)
            client_ids_clause = f"\nFilter to these specific client IDs: [{ids_str}]"

        prompt = f"""You are a SQL query generator for a PostgreSQL database.

DATABASE SCHEMA:
{schema_desc}

CRITICAL RULES:
1. ONLY use quantitative operations:
   - Math: SUM, AVG, COUNT, MIN, MAX, calculations
   - Dates: DATE comparisons, INTERVAL calculations, AGE functions
   - Exact filtering: WHERE column = value, WHERE column > value, WHERE column IN (...)

2. NEVER use these (they belong to Semantic Search Agent):
   - LIKE or ILIKE patterns
   - Regex (~ or ~*)
   - Full-text search
   - Fuzzy matching

3. JSONB field access:
   - Use ->> for text: core_data->>'aum'
   - Use -> for JSON: core_data->'address'
   - Cast when needed: (core_data->>'aum')::numeric

4. Always include:
   - Proper JOIN conditions
   - Appropriate WHERE clauses
   - LIMIT to prevent huge result sets (default 100)
   - ORDER BY for consistent results

5. Return only the SELECT statement, no markdown or explanation

Query Intent: "{query_intent}"

Filters to apply: {json.dumps(filters) if filters else "None"}{client_ids_clause}{context_str}

EXAMPLES:

Intent: "Count all clients"
SELECT COUNT(*) as total_clients FROM clients;

Intent: "Calculate average AUM per client"
SELECT
    AVG((core_data->>'aum')::numeric) as avg_aum,
    COUNT(*) as total_clients,
    SUM((core_data->>'aum')::numeric) as total_aum
FROM clients
WHERE core_data->>'aum' IS NOT NULL;

Intent: "Find clients with AUM over $1M"
SELECT
    id, client_name, contact_email,
    (core_data->>'aum')::numeric as aum,
    core_data->>'last_contact_date' as last_contact
FROM clients
WHERE (core_data->>'aum')::numeric > 1000000
ORDER BY (core_data->>'aum')::numeric DESC
LIMIT 100;

Intent: "Clients not contacted in 60 days"
SELECT
    id, client_name, contact_email,
    core_data->>'last_contact_date' as last_contact,
    AGE(NOW(), (core_data->>'last_contact_date')::timestamp) as days_since_contact
FROM clients
WHERE (core_data->>'last_contact_date')::timestamp < NOW() - INTERVAL '60 days'
ORDER BY (core_data->>'last_contact_date')::timestamp ASC
LIMIT 100;

Intent: "Average AUM by risk score"
SELECT
    core_data->>'risk_score' as risk_score,
    COUNT(*) as client_count,
    AVG((core_data->>'aum')::numeric) as avg_aum,
    SUM((core_data->>'aum')::numeric) as total_aum
FROM clients
WHERE core_data->>'risk_score' IS NOT NULL
  AND core_data->>'aum' IS NOT NULL
GROUP BY core_data->>'risk_score'
ORDER BY (core_data->>'risk_score')::numeric DESC;

Now generate the SQL query for the intent above:"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={
                    "temperature": 0.1,  # Low temperature for precise SQL
                    "max_output_tokens": 1024,
                }
            )

            # Log LLM conversation
            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_pro_model,
                prompt=prompt,
                response=response.text,
            )

            # Clean response
            sql_query = response.text.strip()

            # Remove markdown code blocks if present
            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]
            elif sql_query.startswith("```"):
                sql_query = sql_query[3:]
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]

            sql_query = sql_query.strip()

            self.logger.info(
                "sql_query_generated",
                query_length=len(sql_query),
                has_select=sql_query.upper().startswith("SELECT")
            )

            return sql_query

        except Exception as e:
            self.logger.error(
                "sql_generation_failed",
                error=str(e),
                exc_info=True
            )
            return ""

    def _build_schema_description(self) -> str:
        """Build human-readable schema description"""
        desc = ""
        for table_name, table_info in DATABASE_SCHEMA.items():
            desc += f"\nTable: {table_name}\n"
            desc += f"Description: {table_info['description']}\n"
            desc += "Columns:\n"
            for col, col_desc in table_info["columns"].items():
                desc += f"  - {col}: {col_desc}\n"
            if "jsonb_fields" in table_info:
                desc += "Common JSONB fields:\n"
                for jsonb_col, fields in table_info["jsonb_fields"].items():
                    desc += f"  - {jsonb_col}: {', '.join(fields)}\n"
        return desc

    def _validate_sql_query(self, query: str) -> Dict[str, Any]:
        """
        Validate SQL query for safety
        """
        query_upper = query.upper()

        # Disallowed operations
        dangerous_operations = [
            ("DROP", "DROP operations not allowed"),
            ("TRUNCATE", "TRUNCATE operations not allowed"),
            ("DELETE", "DELETE operations not allowed"),
            ("UPDATE", "UPDATE operations not allowed"),
            ("INSERT", "INSERT operations not allowed"),
            ("ALTER", "ALTER operations not allowed"),
            ("CREATE", "CREATE operations not allowed"),
            ("GRANT", "GRANT operations not allowed"),
            ("REVOKE", "REVOKE operations not allowed"),
        ]

        for operation, reason in dangerous_operations:
            if operation in query_upper:
                return {"safe": False, "reason": reason}

        # Must be a SELECT query
        if not query_upper.strip().startswith("SELECT"):
            return {"safe": False, "reason": "Only SELECT queries allowed"}

        # Check for LIKE (should use Semantic Search instead)
        if " LIKE " in query_upper or " ILIKE " in query_upper:
            return {
                "safe": False,
                "reason": "LIKE queries not allowed - use Semantic Search Agent for text matching"
            }

        # Check for regex
        if "~" in query:
            return {
                "safe": False,
                "reason": "Regex patterns not allowed - use Semantic Search Agent"
            }

        return {"safe": True, "reason": "Query passed validation"}

    async def _execute_query(
        self,
        query: str,
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results
        """
        from app.models import SQLQueryLog

        start_time = datetime.utcnow()

        try:
            # Execute query
            result = await db.execute(text(query))

            # Fetch all results
            rows = result.fetchall()

            # Convert to list of dicts
            if rows:
                columns = result.keys()
                results = [dict(zip(columns, row)) for row in rows]
            else:
                results = []

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Log query execution
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

            self.logger.info(
                "query_executed",
                row_count=len(results),
                execution_time_ms=execution_time_ms
            )

            return results

        except SQLAlchemyError as e:
            self.logger.error(
                "query_execution_failed",
                error=str(e),
                query=query,
                exc_info=True
            )

            # Log failed query
            query_log = SQLQueryLog(
                session_id=conversation_id,
                agent_name="sql_analytics",
                query_text=query,
                error=str(e),
                execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
            )
            db.add(query_log)
            await db.commit()

            raise

    def _format_query_results(
        self,
        results: List[Dict[str, Any]],
        query_intent: str
    ) -> Dict[str, Any]:
        """
        Format query results for display
        """
        if not results:
            return {
                "data": [],
                "row_count": 0,
                "summary": "No results found"
            }

        row_count = len(results)

        # Generate summary based on results
        if row_count == 1 and len(results[0]) == 1:
            # Single scalar value (e.g., COUNT)
            key = list(results[0].keys())[0]
            value = results[0][key]
            summary = f"Result: {value}"
        else:
            summary = f"Found {row_count} result{'s' if row_count != 1 else ''}"

        return {
            "data": results,
            "row_count": row_count,
            "summary": summary
        }

    async def _generate_insights(
        self,
        query_intent: str,
        formatted_results: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Generate proactive insights from query results
        """
        results = formatted_results["data"]
        row_count = formatted_results["row_count"]

        if row_count == 0:
            return {
                "patterns": [],
                "suggestions": ["Try adjusting your filters", "Upload more data if needed"]
            }

        try:
            # Build prompt for insight generation
            prompt = f"""Analyze these SQL query results and provide brief insights.

Query Intent: "{query_intent}"

Results Summary:
- Row count: {row_count}
- Sample data: {json.dumps(results[:5], default=str)}

Provide insights as JSON:
{{
  "patterns": ["Pattern 1", "Pattern 2"],
  "suggestions": ["Suggestion 1", "Suggestion 2"]
}}

Keep each item to 1 sentence. Focus on actionable insights."""

            response = await self.model.generate_content_async(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 512,
                }
            )

            # Parse insights
            insights_text = response.text.strip()
            if insights_text.startswith("```json"):
                insights_text = insights_text[7:]
            if insights_text.startswith("```"):
                insights_text = insights_text[3:]
            if insights_text.endswith("```"):
                insights_text = insights_text[:-3]
            insights_text = insights_text.strip()

            insights = json.loads(insights_text)
            return insights

        except Exception as e:
            self.logger.warning(
                "insight_generation_failed",
                error=str(e)
            )
            return {
                "patterns": [],
                "suggestions": []
            }

    async def _filter_by_quantitative(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Filter existing results by quantitative criteria
        """
        # Simplified version - delegates to generate_and_execute_query
        return await self._generate_and_execute_query(
            conversation_id,
            user_id,
            payload,
            db
        )

    async def _aggregate_data(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Perform aggregation operations
        """
        # Simplified version - delegates to generate_and_execute_query
        return await self._generate_and_execute_query(
            conversation_id,
            user_id,
            payload,
            db
        )

    async def _calculate_metrics(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Calculate statistical metrics
        """
        # Simplified version - delegates to generate_and_execute_query
        return await self._generate_and_execute_query(
            conversation_id,
            user_id,
            payload,
            db
        )
