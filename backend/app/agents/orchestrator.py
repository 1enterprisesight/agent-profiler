"""
Orchestrator Agent - Phase D: Dynamic Discovery
Coordinates multi-agent workflows with:
- Dynamic agent discovery (no hardcoded capabilities)
- Complete transparency (emits events for every step)
- Data source awareness (includes user's sources in planning)
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
from datetime import datetime

import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus, EventType
from app.agents.schema_utils import get_schema_context
from app.config import settings


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator Agent - Phase D: Dynamic Discovery

    Uses Gemini Pro to:
    1. Break down user request into execution plan
    2. Route to agents sequentially (discovered dynamically)
    3. Emit transparency events at every step
    4. Aggregate final results with data source awareness
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Orchestrator describes itself for dynamic discovery"""
        return {
            "name": "orchestrator",
            "purpose": "Coordinates multi-agent workflows for complex requests",
            "when_to_use": [
                "User has a complex request requiring multiple agents",
                "Request needs to be broken down into steps",
                "Multiple data operations are needed"
            ],
            "when_not_to_use": [
                "Direct single-agent requests",
                "Simple queries that don't need coordination"
            ],
            "example_tasks": [
                "Upload this CSV and then analyze the clients",
                "Find high-value clients and segment them by engagement",
                "Compare data across my different sources"
            ],
            "data_source_aware": True
        }

    def get_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Orchestrator's internal capabilities"""
        return {
            "orchestrate": {
                "description": "Plan and execute multi-agent workflow",
                "examples": ["coordinate workflow", "multi-step request", "complex analysis"],
                "method": "_orchestrate_workflow"
            }
        }

    def __init__(self, agent_registry: Optional[Dict[str, BaseAgent]] = None):
        super().__init__()

        # Initialize Vertex AI
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )

        # Use Pro model for complex orchestration planning
        self.model = GenerativeModel(settings.gemini_pro_model)

        # Agent registry for executing steps
        self.agent_registry = agent_registry or {}

        # Dynamically discovered capabilities (populated when agents are registered)
        self._agent_capabilities: Dict[str, Dict[str, Any]] = {}

    def register_agents(self, agents: Dict[str, BaseAgent]) -> None:
        """
        Register agents and discover their capabilities dynamically.
        Called after all agents are instantiated.
        """
        self.agent_registry = agents
        self._agent_capabilities = self._discover_capabilities()
        self.logger.info(
            "agents_registered",
            agent_count=len(agents),
            agents=list(agents.keys())
        )

    # Common alternative names that LLMs might generate -> correct agent name
    AGENT_NAME_ALIASES = {
        # Data exploration/profiling -> data_discovery
        "data_profiler": "data_discovery",
        "data_profile": "data_discovery",
        "profiler": "data_discovery",
        "data_explorer": "data_discovery",
        "explorer": "data_discovery",
        "describe_data": "data_discovery",
        # Analytics aliases
        "data_analysis": "sql_analytics",
        "data_analyzer": "sql_analytics",
        "analytics": "sql_analytics",
        # Search aliases
        "search": "semantic_search",
        "text_search": "semantic_search",
        "client_search": "semantic_search",
        # Segmentation aliases
        "segment": "segmentation",
        "segments": "segmentation",
        # Benchmark aliases
        "benchmark_agent": "benchmark",
        "benchmarking": "benchmark",
        "compare": "benchmark",
        # Recommendation aliases
        "recommend": "recommendation",
        "recommendations": "recommendation",
        "ingest": "data_ingestion",
        "ingestion": "data_ingestion",
        "upload": "data_ingestion",
        "pattern": "pattern_recognition",
        "patterns": "pattern_recognition",
        "recognize": "pattern_recognition",
    }

    def _normalize_agent_name(self, agent_name: str) -> str:
        """Map alternative/incorrect agent names to correct ones."""
        normalized = agent_name.lower().strip()
        if normalized in self.agent_registry:
            return normalized
        if normalized in self.AGENT_NAME_ALIASES:
            correct_name = self.AGENT_NAME_ALIASES[normalized]
            self.logger.info(
                "agent_name_normalized",
                original=agent_name,
                normalized=correct_name
            )
            return correct_name
        return agent_name  # Return original if no mapping found

    def _discover_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """
        Dynamically discover agent capabilities from their get_agent_info() methods.
        No hardcoding - agents describe themselves.
        """
        capabilities = {}
        for name, agent in self.agent_registry.items():
            try:
                # Get agent's self-description
                info = agent.get_agent_info()
                capabilities[name] = {
                    "name": info.get("name", name),
                    "purpose": info.get("purpose", ""),
                    "when_to_use": info.get("when_to_use", []),
                    "when_not_to_use": info.get("when_not_to_use", []),
                    "example_tasks": info.get("example_tasks", []),
                    "data_source_aware": info.get("data_source_aware", False),
                }
                self.logger.debug(
                    "agent_capability_discovered",
                    agent=name,
                    purpose=info.get("purpose", "")
                )
            except Exception as e:
                self.logger.warning(
                    "failed_to_discover_agent_capability",
                    agent=name,
                    error=str(e)
                )
        return capabilities

    async def _get_user_data_sources(
        self,
        user_id: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Get summary of user's data sources for planning context.
        Orchestrator includes this in the planning prompt.
        """
        try:
            query = """
            SELECT
                source_type,
                COUNT(*) as client_count,
                MAX(synced_at) as last_sync
            FROM clients
            WHERE user_id = :user_id
            GROUP BY source_type
            ORDER BY client_count DESC
            """
            result = await db.execute(text(query), {"user_id": user_id})
            rows = result.fetchall()
            columns = result.keys()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            self.logger.warning(
                "failed_to_get_data_sources",
                user_id=user_id,
                error=str(e)
            )
            return []

    async def _get_typed_schema_context(
        self,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get typed schema context for routing queries to the right agent.
        Returns categorized fields: numeric/date → SQL, text → Semantic Search.
        """
        return await get_schema_context(db, user_id)

    async def _get_data_discovery_context(
        self,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get data discovery context including thresholds and statistics.
        Used to provide semantic meaning to vague terms in user queries.
        """
        try:
            query = """
            SELECT
                total_clients,
                sources_summary,
                field_completeness,
                numeric_stats,
                computed_thresholds,
                last_computed_at
            FROM data_metadata
            WHERE user_id = :user_id
            """
            result = await db.execute(text(query), {"user_id": user_id})
            row = result.fetchone()

            if row:
                import json
                return {
                    "total_clients": row[0],
                    "sources_summary": row[1] if isinstance(row[1], dict) else json.loads(row[1] or "{}"),
                    "field_completeness": row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}"),
                    "numeric_stats": row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
                    "computed_thresholds": row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}"),
                    "last_computed": row[5].isoformat() if row[5] else None,
                }
            return {}
        except Exception as e:
            self.logger.warning(
                "failed_to_get_discovery_context",
                user_id=user_id,
                error=str(e)
            )
            return {}

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """
        Coordinate multi-agent workflow

        Actions:
            - orchestrate: Plan and execute multi-agent workflow
        """
        action = message.action
        payload = message.payload

        if action == "orchestrate":
            return await self._orchestrate_workflow(
                message.conversation_id,
                user_id,
                payload.get("user_query", ""),
                payload.get("context", {}),
                db
            )
        else:
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Unknown action: {action}"
            )

    async def _orchestrate_workflow(
        self,
        conversation_id: str,
        user_id: str,
        user_query: str,
        context: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Orchestrate multi-agent workflow with full transparency

        Process:
        1. Emit 'received' event
        2. Get user's data sources for context
        3. Emit 'thinking' event while planning
        4. Create execution plan with Gemini
        5. Emit 'decision' event with plan
        6. Execute each step with 'action'/'result' events
        7. Aggregate final results
        """
        workflow_start = datetime.utcnow()

        try:
            # TRANSPARENCY: Received event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.RECEIVED,
                title="Received user request",
                details={"user_query": user_query, "context": context},
                step_number=0
            )

            # Get user's data sources for planning context
            data_sources = await self._get_user_data_sources(user_id, db)

            # Get data discovery context (thresholds, statistics)
            discovery_context = await self._get_data_discovery_context(user_id, db)

            # Get typed schema context (field types for routing)
            typed_schema = await self._get_typed_schema_context(user_id, db)

            # TRANSPARENCY: Thinking event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.THINKING,
                title="Analyzing request and planning workflow...",
                details={
                    "analyzing": user_query,
                    "available_agents": list(self._agent_capabilities.keys()),
                    "user_data_sources": data_sources,
                    "has_discovery_context": bool(discovery_context)
                },
                step_number=0
            )

            self.logger.info(
                "creating_execution_plan",
                user_query=user_query,
                conversation_id=conversation_id,
                data_sources=len(data_sources),
                has_thresholds=bool(discovery_context.get("computed_thresholds"))
            )

            # Add data sources, discovery context, and typed schema to planning context
            context["user_data_sources"] = data_sources
            context["discovery_context"] = discovery_context
            context["typed_schema"] = typed_schema

            # Query Understanding Layer - canonicalize and detect references
            conversation_history = context.get("conversation_history", [])
            query_understanding = await self._understand_query(
                user_query,
                typed_schema,
                conversation_history,
                conversation_id,
                user_id,
                db
            )
            context["query_understanding"] = query_understanding

            # Use clarified query if references were resolved
            effective_query = user_query
            if query_understanding.get("references_previous") and query_understanding.get("clarified_query"):
                effective_query = query_understanding["clarified_query"]
                self.logger.info(
                    "using_clarified_query",
                    original=user_query,
                    clarified=effective_query
                )

            plan_response = await self._create_execution_plan(
                effective_query, context, conversation_id, user_id, db
            )

            if not plan_response["success"]:
                # TRANSPARENCY: Error event
                await self.emit_event(
                    db=db,
                    session_id=conversation_id,
                    user_id=user_id,
                    event_type=EventType.ERROR,
                    title="Failed to create execution plan",
                    details={"error": plan_response.get("error")},
                    step_number=0
                )
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error=f"Failed to create plan: {plan_response.get('error')}"
                )

            execution_plan = plan_response["plan"]

            # TRANSPARENCY: Decision event - plan created
            agents_in_plan = [step["agent"] for step in execution_plan["steps"]]
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.DECISION,
                title=f"Created {len(execution_plan['steps'])}-step plan using {', '.join(agents_in_plan)}",
                details={
                    "execution_plan": execution_plan,
                    "overall_strategy": execution_plan.get("overall_strategy", ""),
                    "agents_selected": agents_in_plan
                },
                step_number=0
            )

            # Step 2: Execute plan sequentially
            workflow_results = []
            intermediate_context = {**context}

            for step_num, step in enumerate(execution_plan["steps"], 1):
                agent_name = step["agent"]
                task_desc = step.get("reasoning", step.get("action", ""))

                # TRANSPARENCY: Action event - starting step
                await self.emit_event(
                    db=db,
                    session_id=conversation_id,
                    user_id=user_id,
                    event_type=EventType.ACTION,
                    title=f"Step {step_num}: Delegating to {agent_name}",
                    details={
                        "agent": agent_name,
                        "task": task_desc,
                        "parameters": step.get("parameters", {})
                    },
                    step_number=step_num
                )

                self.logger.info(
                    "executing_workflow_step",
                    step=step_num,
                    total_steps=len(execution_plan["steps"]),
                    agent=step["agent"],
                    action=step["action"]
                )

                step_start = datetime.utcnow()

                # Execute this step
                step_result = await self._execute_step(
                    step,
                    intermediate_context,
                    conversation_id,
                    user_id,
                    db
                )

                step_duration = int((datetime.utcnow() - step_start).total_seconds() * 1000)

                workflow_results.append({
                    "step": step_num,
                    "agent": step["agent"],
                    "action": step["action"],
                    "result": step_result["result"],
                    "success": step_result["success"],
                    "error": step_result.get("error"),
                    "duration_ms": step_duration
                })

                # TRANSPARENCY: Result event for step
                if step_result["success"]:
                    await self.emit_event(
                        db=db,
                        session_id=conversation_id,
                        user_id=user_id,
                        event_type=EventType.RESULT,
                        title=f"Step {step_num} completed: {agent_name}",
                        details={
                            "agent": agent_name,
                            "result_summary": self._summarize_step_result(step_result["result"])
                        },
                        step_number=step_num,
                        duration_ms=step_duration
                    )
                else:
                    await self.emit_event(
                        db=db,
                        session_id=conversation_id,
                        user_id=user_id,
                        event_type=EventType.ERROR,
                        title=f"Step {step_num} failed: {agent_name}",
                        details={
                            "agent": agent_name,
                            "error": step_result.get("error")
                        },
                        step_number=step_num,
                        duration_ms=step_duration
                    )

                # If step failed, decide whether to continue or abort
                if not step_result["success"]:
                    if step.get("required", True):
                        self.logger.error(
                            "required_step_failed",
                            step=step_num,
                            agent=step["agent"],
                            error=step_result.get("error")
                        )
                        return AgentResponse(
                            status=AgentStatus.FAILED,
                            error=f"Required step {step_num} failed: {step_result.get('error')}",
                            result={
                                "plan": execution_plan,
                                "completed_steps": workflow_results
                            }
                        )
                    else:
                        self.logger.warning(
                            "optional_step_failed_continuing",
                            step=step_num,
                            agent=step["agent"]
                        )

                # Update context with results for next step
                intermediate_context[f"step_{step_num}_result"] = step_result["result"]

            # Step 3: Aggregate final results
            aggregated_result = await self._aggregate_results(
                user_query,
                execution_plan,
                workflow_results,
                conversation_id,
                user_id,
                db
            )

            workflow_duration = int((datetime.utcnow() - workflow_start).total_seconds() * 1000)

            # TRANSPARENCY: Final result event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.RESULT,
                title=f"Workflow complete: {len(execution_plan['steps'])} steps executed",
                details={
                    "answer_preview": aggregated_result.get("answer", "")[:200] + "..." if len(aggregated_result.get("answer", "")) > 200 else aggregated_result.get("answer", ""),
                    "key_findings": aggregated_result.get("key_findings", []),
                    "agents_used": [step["agent"] for step in execution_plan["steps"]],
                    "total_duration_ms": workflow_duration
                },
                step_number=len(execution_plan["steps"]) + 1,
                duration_ms=workflow_duration
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "answer": aggregated_result["answer"],
                    "execution_plan": execution_plan,
                    "workflow_results": workflow_results,
                    "agents_used": [step["agent"] for step in execution_plan["steps"]]
                },
                metadata={
                    "orchestration_model": settings.gemini_pro_model,
                    "total_steps": len(execution_plan["steps"]),
                    "successful_steps": sum(1 for r in workflow_results if r["success"]),
                    "total_duration_ms": workflow_duration
                }
            )

        except Exception as e:
            self.logger.error(
                "orchestration_failed",
                error=str(e),
                user_query=user_query,
                exc_info=True,
            )
            # TRANSPARENCY: Error event for unexpected failure
            try:
                await self.emit_event(
                    db=db,
                    session_id=conversation_id,
                    user_id=user_id,
                    event_type=EventType.ERROR,
                    title="Orchestration failed unexpectedly",
                    details={"error": str(e)},
                    step_number=0
                )
            except Exception:
                pass  # Don't fail on logging failure
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Orchestration failed: {str(e)}"
            )

    async def _create_execution_plan(
        self,
        user_query: str,
        context: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Create multi-step execution plan using Gemini Pro
        """
        try:
            prompt = self._build_planning_prompt(user_query, context)

            response = await self._call_gemini(prompt)

            # Log LLM conversation
            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_pro_model,
                prompt=prompt,
                response=response,
            )

            # Parse execution plan (with LLM repair on failure)
            plan = await self._parse_plan_response(
                response,
                conversation_id,
                user_id,
                db
            )

            return {
                "success": True,
                "plan": plan
            }

        except Exception as e:
            self.logger.error(
                "plan_creation_failed",
                error=str(e),
                exc_info=True
            )
            return {
                "success": False,
                "error": str(e)
            }

    def _build_planning_prompt(
        self,
        user_query: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Build prompt for Gemini Pro to create execution plan.
        Uses DYNAMICALLY DISCOVERED agent capabilities - no hardcoding.
        """

        # Build agent capabilities from dynamic discovery
        capabilities_desc = ""
        for agent_name, info in self._agent_capabilities.items():
            capabilities_desc += f"\n{agent_name}:\n"
            capabilities_desc += f"  Purpose: {info['purpose']}\n"
            if info.get("when_to_use"):
                capabilities_desc += f"  Use when: {'; '.join(info['when_to_use'])}\n"
            if info.get("when_not_to_use"):
                capabilities_desc += f"  NEVER use for: {'; '.join(info['when_not_to_use'])}\n"
            if info.get("example_tasks"):
                capabilities_desc += f"  Examples: {'; '.join(info['example_tasks'])}\n"

        # Build typed schema context (for field-aware routing)
        typed_schema = context.get("typed_schema", {})
        schema_desc = ""
        if typed_schema.get("has_schema"):
            schema_desc = "\n\nDISCOVERED DATA FIELDS (use for routing):\n"

            numeric_fields = typed_schema.get("numeric_fields", [])
            if numeric_fields:
                field_names = [f["name"] for f in numeric_fields]
                schema_desc += f"  NUMERIC fields (→ SQL Analytics): {', '.join(field_names)}\n"

            date_fields = typed_schema.get("date_fields", [])
            if date_fields:
                field_names = [f["name"] for f in date_fields]
                schema_desc += f"  DATE fields (→ SQL Analytics): {', '.join(field_names)}\n"

            text_fields = typed_schema.get("text_fields", [])
            if text_fields:
                field_names = [f["name"] for f in text_fields]
                schema_desc += f"  TEXT fields (→ Semantic Search): {', '.join(field_names)}\n"

            schema_desc += """
Use this schema information along with the agent descriptions above to determine which agent(s) are best suited for the user's query. Consider what type of operation the user is asking for (counting, searching, aggregating, etc.) and match it to the agent whose purpose and examples align best.
"""

        # Build data source context
        data_sources = context.get("user_data_sources", [])
        data_source_desc = ""
        if data_sources:
            data_source_desc = "\n\nUSER'S DATA SOURCES:\n"
            for src in data_sources:
                source_type = src.get("source_type", "unknown")
                count = src.get("client_count", 0)
                data_source_desc += f"  - {source_type}: {count} clients\n"
            data_source_desc += """
MULTI-SOURCE RULES:
1. If query mentions a specific source (e.g., "Salesforce clients"), filter by source_type
2. If query compares sources (e.g., "between CSV and Salesforce"), use cross-source logic
3. If query doesn't specify source, include all sources but show source breakdown
4. Always include source_type in results when relevant
"""

        # Build data discovery context (thresholds and statistics)
        discovery = context.get("discovery_context", {})
        thresholds_desc = ""
        if discovery:
            thresholds = discovery.get("computed_thresholds", {})
            numeric_stats = discovery.get("numeric_stats", {})
            field_completeness = discovery.get("field_completeness", {})

            if thresholds or numeric_stats:
                thresholds_desc = "\n\nDATA CONTEXT (computed from user's actual data):\n"

                if thresholds.get("high_value_aum"):
                    thresholds_desc += f"  - 'High value' clients = AUM >= ${thresholds['high_value_aum']:,.0f} (top 10% of this user's data)\n"
                if thresholds.get("medium_value_aum"):
                    thresholds_desc += f"  - 'Medium value' clients = AUM >= ${thresholds['medium_value_aum']:,.0f} (above median)\n"

                if numeric_stats.get("aum"):
                    aum = numeric_stats["aum"]
                    if aum.get("min") is not None and aum.get("max") is not None:
                        thresholds_desc += f"  - AUM range in data: ${aum['min']:,.0f} to ${aum['max']:,.0f}\n"

                if field_completeness:
                    low_fields = [f for f, pct in field_completeness.items() if pct < 50]
                    if low_fields:
                        thresholds_desc += f"  - Fields with low data (<50%): {', '.join(low_fields)}\n"

                thresholds_desc += """
USE THESE THRESHOLDS: When user says 'high value', 'wealthy', 'top clients' - use the computed high_value_aum threshold above.
This ensures queries match the user's actual data distribution, not arbitrary values.
"""

        # Build conversation history section - LLM decides relevance
        history = context.get("conversation_history", [])
        history_desc = ""
        if history:
            history_desc = "\n\nCONVERSATION HISTORY (use to understand context and references):\n"
            for i, msg in enumerate(history):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                # Truncate very long messages for the planning prompt
                content_preview = content[:300] + "..." if len(content) > 300 else content
                history_desc += f"{i+1}. [{role}]: {content_preview}\n"
                if msg.get("result_summary"):
                    # Include brief result summary
                    summaries = msg["result_summary"][:2]  # First 2 agent results
                    for s in summaries:
                        history_desc += f"   → {s.get('agent')}: {s.get('result_preview', '')[:150]}...\n"
            history_desc += """
HISTORY USAGE RULES:
1. If user says "those", "the previous", "from that list" - reference the most recent relevant result
2. If user asks a follow-up, use context from previous exchanges
3. For new/unrelated queries, history may not be relevant - use your judgment
"""

        # Build query understanding context if available
        query_understanding = context.get("query_understanding", {})
        understanding_desc = ""
        if query_understanding:
            if query_understanding.get("references_previous"):
                understanding_desc = f"\n\nQUERY ANALYSIS:\n"
                understanding_desc += f"- Original query references previous results\n"
                understanding_desc += f"- Clarified intent: {query_understanding.get('clarified_query', 'N/A')}\n"
                understanding_desc += f"- Relevant fields: {', '.join(query_understanding.get('relevant_fields', []))}\n"

        context_str = ""
        if context:
            # Remove internal context from display
            display_context = {k: v for k, v in context.items()
                              if k not in ["user_data_sources", "discovery_context",
                                          "conversation_history", "query_understanding",
                                          "original_user_query", "typed_schema"]}
            if display_context:
                context_str = f"\n\nAdditional Context:\n{json.dumps(display_context, indent=2)}"

        # Build explicit list of valid agent names
        valid_agents = list(self._agent_capabilities.keys())
        valid_agents_str = ", ".join(valid_agents)

        prompt = f"""You are an intelligent workflow orchestrator for a multi-agent client data analysis system.

Your job is to break down the user's request into a sequential execution plan using available agents.

CRITICAL CONSTRAINT - READ CAREFULLY:
The "agent" field MUST be one of these EXACT strings: {valid_agents_str}

FORBIDDEN: Do NOT invent new agent names like "natural_language_output", "response_formatter", "output", etc.
FORBIDDEN: Do NOT use spaces or different capitalization.
If you need to format output, that happens AFTER the workflow - just use the agents listed above.

AVAILABLE AGENTS:
{capabilities_desc}
{schema_desc}{data_source_desc}{thresholds_desc}{history_desc}{understanding_desc}
YOUR TASK:
Analyze the user's query and create a workflow plan using the agents described above.

PRINCIPLES:
1. Each agent describes WHEN to use it and WHEN NOT to use it - follow those guidelines
2. Provide VALUE: Don't just answer literally - consider what insights would help the user
3. Multi-agent workflows: If data retrieval alone isn't enough, chain agents to add analysis, patterns, or recommendations
4. Each agent has its own LLM - give it a natural language task description and it will figure out the details
5. Mark steps as "required": false if they add value but aren't essential to answer the question

User Query: "{user_query}"{context_str}

VALID AGENT NAMES (use ONLY these exact names): {valid_agents_str}

Respond ONLY with valid JSON:
{{
  "steps": [
    {{
      "agent": "MUST be one of: {valid_agents_str}",
      "task": "Natural language description of what this agent should do",
      "parameters": {{}},
      "reasoning": "Why this agent for this step",
      "required": true
    }}
  ],
  "overall_strategy": "Brief description of your approach"
}}

Create the execution plan:"""

        return prompt

    def _summarize_step_result(self, result: Any) -> str:
        """Generate a short summary of step result for transparency events"""
        if result is None:
            return "No result"
        if isinstance(result, dict):
            if "row_count" in result:
                return f"Found {result['row_count']} records"
            if "segments" in result:
                return f"Created {len(result['segments'])} segments"
            if "patterns" in result:
                return f"Detected {len(result['patterns'])} patterns"
            if "recommendations" in result:
                return f"Generated {len(result['recommendations'])} recommendations"
            if "matches" in result:
                return f"Found {len(result['matches'])} matches"
            # Generic summary
            keys = list(result.keys())[:3]
            return f"Result with {len(result)} fields: {', '.join(keys)}"
        if isinstance(result, list):
            return f"List with {len(result)} items"
        return str(result)[:100]

    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini Pro model"""
        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={
                    "temperature": 0.2,  # Low temperature for consistent planning
                    "max_output_tokens": 2048,
                }
            )
            return response.text
        except Exception as e:
            self.logger.error(
                "gemini_call_failed",
                error=str(e),
                exc_info=True,
            )
            raise

    async def _understand_query(
        self,
        user_query: str,
        schema: Dict[str, Any],
        history: List[Dict[str, Any]],
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Query understanding layer - canonicalizes queries and detects references.
        The LLM decides what's relevant from conversation history.
        """
        # Format history for LLM - let it decide what's relevant
        history_str = ""
        if history:
            history_str = "\n\nCONVERSATION HISTORY:\n"
            for i, msg in enumerate(history):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                history_str += f"{i+1}. [{role}]: {content}\n"
                if msg.get("result_summary"):
                    history_str += f"   Results: {json.dumps(msg['result_summary'][:2])}...\n"

        # Format schema for LLM
        schema_fields = []
        if schema.get("has_schema"):
            for f in schema.get("numeric_fields", []):
                schema_fields.append(f["name"])
            for f in schema.get("text_fields", []):
                schema_fields.append(f["name"])
            for f in schema.get("date_fields", []):
                schema_fields.append(f["name"])

        prompt = f"""Analyze this user query in the context of the conversation.

CURRENT QUERY: "{user_query}"

AVAILABLE DATA FIELDS: {', '.join(schema_fields) if schema_fields else 'Unknown - will be discovered'}
{history_str}

Your task:
1. Determine the CANONICAL INTENT - what the user actually wants
2. Detect if this REFERENCES PREVIOUS results (e.g., "show me more", "filter those", "from the previous list")
3. Identify which DATA FIELDS are relevant to this query
4. Create a CLARIFIED QUERY that resolves any references to previous results

Respond with JSON ONLY:
{{
    "canonical_intent": "Clear statement of what user wants",
    "references_previous": true/false,
    "previous_reference_type": "results|query|none",
    "relevant_fields": ["field1", "field2"],
    "clarified_query": "Rewritten query with resolved references",
    "ambiguities": ["Any unclear aspects that might need clarification"]
}}"""

        try:
            response = await self._call_gemini(prompt)

            # Log the understanding call
            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_pro_model,
                prompt=prompt,
                response=response,
            )

            # Parse response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            understanding = json.loads(response.strip())

            self.logger.info(
                "query_understood",
                original=user_query,
                canonical=understanding.get("canonical_intent"),
                references_previous=understanding.get("references_previous"),
                clarified=understanding.get("clarified_query")
            )

            return understanding

        except Exception as e:
            self.logger.warning(
                "query_understanding_failed",
                error=str(e),
                user_query=user_query
            )
            # Fallback - return basic understanding
            return {
                "canonical_intent": user_query,
                "references_previous": False,
                "previous_reference_type": "none",
                "relevant_fields": [],
                "clarified_query": user_query,
                "ambiguities": []
            }

    async def _repair_json_with_llm(
        self,
        malformed_json: str,
        error_message: str,
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> str:
        """
        Use LLM to repair malformed JSON. Single retry attempt.
        """
        prompt = f"""Fix this malformed JSON. Return ONLY valid JSON, no explanation.

MALFORMED JSON:
{malformed_json}

PARSE ERROR:
{error_message}

Return the corrected JSON only:"""

        try:
            response = await self._call_gemini(prompt)

            # Log the repair attempt
            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_pro_model,
                prompt=prompt,
                response=response,
            )

            self.logger.info(
                "json_repair_attempted",
                original_error=error_message,
                repair_response_length=len(response)
            )

            return response.strip()

        except Exception as e:
            self.logger.error(
                "json_repair_failed",
                error=str(e),
                original_error=error_message
            )
            raise

    async def _parse_plan_response(
        self,
        response: str,
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Parse JSON execution plan from Gemini with LLM-based repair on failure"""
        original_response = response

        def clean_json(text: str) -> str:
            """Clean markdown formatting from JSON response"""
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            return text.strip()

        try:
            # Clean response
            cleaned = clean_json(response)

            # Parse JSON
            plan = json.loads(cleaned)

            # Validate
            if "steps" not in plan or not isinstance(plan["steps"], list):
                raise ValueError("Plan must contain 'steps' array")

            valid_agents = set(self.agent_registry.keys())

            for step in plan["steps"]:
                # Required: agent and either task or action
                if "agent" not in step:
                    raise ValueError("Step missing required field: agent")
                if "task" not in step and "action" not in step:
                    raise ValueError("Step must have 'task' or 'action' field")

                # Validate and normalize agent name
                raw_agent = step["agent"]
                normalized_agent = self._normalize_agent_name(raw_agent)

                if normalized_agent not in valid_agents:
                    # Log the invalid agent for debugging
                    self.logger.warning(
                        "invalid_agent_in_plan",
                        requested=raw_agent,
                        normalized=normalized_agent,
                        valid_agents=list(valid_agents)
                    )
                    raise ValueError(
                        f"Invalid agent '{raw_agent}' in plan. "
                        f"Valid agents: {', '.join(sorted(valid_agents))}"
                    )

                # Update step with normalized agent name
                step["agent"] = normalized_agent

                # Normalize: copy task to action if action missing (backward compat)
                if "task" in step and "action" not in step:
                    step["action"] = step["task"]

                # Ensure parameters exists
                if "parameters" not in step:
                    step["parameters"] = {}

            return plan

        except json.JSONDecodeError as e:
            # Attempt LLM-based repair (single retry)
            self.logger.warning(
                "json_parse_failed_attempting_repair",
                error=str(e),
                response_preview=original_response[:200]
            )

            try:
                repaired = await self._repair_json_with_llm(
                    original_response,
                    str(e),
                    conversation_id,
                    user_id,
                    db
                )
                cleaned_repair = clean_json(repaired)
                plan = json.loads(cleaned_repair)

                self.logger.info(
                    "json_repair_successful",
                    original_error=str(e)
                )

                # Still need to validate the repaired plan
                if "steps" not in plan or not isinstance(plan["steps"], list):
                    raise ValueError("Repaired plan must contain 'steps' array")

                valid_agents = set(self.agent_registry.keys())
                for step in plan["steps"]:
                    if "agent" not in step:
                        raise ValueError("Step missing required field: agent")
                    if "task" not in step and "action" not in step:
                        raise ValueError("Step must have 'task' or 'action' field")

                    raw_agent = step["agent"]
                    normalized_agent = self._normalize_agent_name(raw_agent)
                    if normalized_agent not in valid_agents:
                        raise ValueError(f"Invalid agent '{raw_agent}' in repaired plan")
                    step["agent"] = normalized_agent
                    if "task" in step and "action" not in step:
                        step["action"] = step["task"]
                    if "parameters" not in step:
                        step["parameters"] = {}

                return plan

            except Exception as repair_error:
                self.logger.error(
                    "json_repair_also_failed",
                    original_error=str(e),
                    repair_error=str(repair_error),
                    response=original_response,
                )
                raise ValueError(f"Failed to parse execution plan (repair also failed): {str(e)}")

    async def _execute_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Execute a single workflow step by calling the appropriate agent.
        Passes original query, schema, and history so agent's LLM has full context.
        """
        raw_agent_name = step["agent"]
        agent_name = self._normalize_agent_name(raw_agent_name)
        action = step["action"]
        parameters = step["parameters"]

        try:
            # Get agent from registry (using normalized name)
            agent = self.agent_registry.get(agent_name)

            if not agent:
                available = list(self.agent_registry.keys())
                self.logger.warning(
                    "agent_not_available",
                    requested=raw_agent_name,
                    normalized=agent_name,
                    available=available
                )
                return {
                    "success": False,
                    "result": None,
                    "error": f"Agent '{agent_name}' not found. Available: {', '.join(available)}"
                }

            # Enrich payload with context for sub-agent's LLM
            # This allows each agent to understand the full conversation context
            # INCLUDING results from previous workflow steps
            previous_step_results = {
                k: v for k, v in context.items()
                if k.startswith("step_") and k.endswith("_result")
            }

            enriched_payload = {
                **parameters,
                "original_user_query": context.get("original_user_query", ""),
                "schema_context": context.get("typed_schema", {}),
                "conversation_history": context.get("conversation_history", []),
                "query_understanding": context.get("query_understanding", {}),
                "previous_step_results": previous_step_results,
            }

            # Create agent message with enriched payload
            agent_message = AgentMessage(
                agent_type=agent_name,
                action=action,
                payload=enriched_payload,
                conversation_id=conversation_id,
            )

            # Execute agent
            self.logger.info(
                "executing_agent",
                agent=agent_name,
                action=action
            )

            response = await agent.execute(agent_message, db, user_id)

            if response.is_success:
                return {
                    "success": True,
                    "result": response.result,
                    "metadata": response.metadata
                }
            else:
                return {
                    "success": False,
                    "result": None,
                    "error": response.error
                }

        except Exception as e:
            self.logger.error(
                "step_execution_failed",
                agent=agent_name,
                action=action,
                error=str(e),
                exc_info=True
            )
            return {
                "success": False,
                "result": None,
                "error": f"Step execution failed: {str(e)}"
            }

    async def _aggregate_results(
        self,
        user_query: str,
        execution_plan: Dict[str, Any],
        workflow_results: List[Dict[str, Any]],
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Aggregate results from all steps into final answer using Gemini Pro
        """
        try:
            prompt = f"""You are aggregating results from a multi-agent workflow.

Original User Query: "{user_query}"

Execution Plan Strategy: {execution_plan.get("overall_strategy", "N/A")}

Results from each step:
{json.dumps(workflow_results, indent=2)}

Synthesize these results into a clear, natural language answer for the user.
Focus on directly answering their question using the data from the workflow steps.

Respond with JSON:
{{
  "answer": "Natural language answer to the user",
  "key_findings": ["Finding 1", "Finding 2"],
  "data_summary": {{}}
}}
"""

            response = await self._call_gemini(prompt)

            # Log aggregation LLM call
            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_pro_model,
                prompt=prompt,
                response=response,
            )

            # Parse response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            aggregated = json.loads(response)
            return aggregated

        except Exception as e:
            self.logger.error(
                "aggregation_failed",
                error=str(e),
                exc_info=True
            )
            # Fallback aggregation
            return {
                "answer": f"Workflow completed with {len(workflow_results)} steps. See workflow_results for details.",
                "key_findings": [],
                "data_summary": {}
            }
