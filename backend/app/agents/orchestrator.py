"""
Orchestrator Agent

The central brain of the multi-agent system.
Uses LLM to interpret user requests, manage conversation context,
ask clarifying questions, and route to specialized agents.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import (
    BaseAgent, AgentMessage, AgentResponse, AgentStatus,
    EventType, AgentRegistry, register_agent
)
from app.config import settings


@register_agent
class OrchestratorAgent(BaseAgent):
    """
    Central orchestrator that interprets user requests,
    manages conversation context, and routes to specialized agents.
    Uses LLM for all decision-making - no hardcoded routing.
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Agent metadata - orchestrator is special, routes to others."""
        return {
            "name": "orchestrator",
            "description": "Interprets user requests and coordinates specialized agents to deliver comprehensive analysis",
            "capabilities": [
                "Interpret natural language requests in context of conversation history",
                "Ask clarifying questions when needed for better analysis",
                "Decompose complex requests into quantitative and semantic components",
                "Route tasks to specialized agents based on their capabilities",
                "Synthesize agent outputs into cohesive insights"
            ],
            "inputs": {
                "message": "User's natural language message",
                "session_id": "Conversation session ID for context",
                "data_source_id": "Active data source (optional)"
            },
            "outputs": {
                "response": "Natural language response to user",
                "agent_activities": "Record of agents invoked",
                "needs_clarification": "Whether asking user a question"
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
        """Process user message and orchestrate agent responses."""

        start_time = datetime.utcnow()
        session_id = message.conversation_id or str(uuid.uuid4())
        payload = message.payload
        user_message = payload.get("message", "")
        data_source_id = payload.get("data_source_id")

        # Helper for events
        async def emit(event_type: EventType, title: str, details: Dict = None, step: int = 1):
            await self.emit_event(
                db=db,
                user_id=user_id,
                session_id=session_id,
                event_type=event_type,
                title=title,
                details=details or {},
                step_number=step
            )

        try:
            # Ensure conversation session exists before emitting events
            await self._ensure_session_exists(db, session_id, user_id, user_message)

            await emit(EventType.RECEIVED, "Received user message",
                      {"message_preview": user_message[:100]}, 1)

            # Get conversation history
            history = await self._get_conversation_history(db, session_id)

            # Get data context if available (uses shared BaseAgent method)
            data_context = await self.get_data_context(db, data_source_id, user_id)
            if data_context and "data_source_id" in data_context:
                data_source_id = data_context["data_source_id"]

            # Get available agents from registry
            available_agents = AgentRegistry.get_registry_schema()
            # Filter out orchestrator itself
            available_agents = [a for a in available_agents if a["name"] != "orchestrator"]

            # LLM interprets the request
            await emit(EventType.THINKING, "Interpreting request",
                      {"has_history": len(history) > 0, "has_data": data_context is not None}, 2)

            interpretation = await self._interpret_request(
                user_message, history, data_context, available_agents
            )

            # Check if clarification needed
            if interpretation.get("needs_clarification"):
                await emit(EventType.RESULT, "Asking for clarification", {}, 3)

                # Save assistant message to history
                await self._save_message(db, session_id, user_id, "user", user_message)
                await self._save_message(db, session_id, user_id, "assistant",
                                        interpretation.get("clarification_question"))

                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "response": interpretation.get("clarification_question"),
                        "needs_clarification": True,
                        "reason": interpretation.get("reason"),
                        "agent_activities": []
                    },
                    metadata={"type": "clarification"}
                )

            # Check if can answer directly from context
            if interpretation.get("can_answer_directly"):
                await emit(EventType.RESULT, "Answering from context", {}, 3)

                direct_response = interpretation.get("response", "")

                # Save messages to history
                await self._save_message(db, session_id, user_id, "user", user_message)
                await self._save_message(db, session_id, user_id, "assistant", direct_response)

                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "response": direct_response,
                        "agent_activities": [],
                        "answered_from_context": True
                    },
                    metadata={"type": "direct_response", "session_id": session_id}
                )

            # Execute the plan
            await emit(EventType.ACTION, f"Executing analysis plan",
                      {"tasks": len(interpretation.get("tasks", []))}, 3)

            agent_results = []
            for i, task in enumerate(interpretation.get("tasks", [])):
                agent_name = task.get("agent")
                task_request = task.get("request")

                await emit(EventType.ACTION, f"Invoking {agent_name}",
                          {"task": task_request[:100]}, 4 + i)

                result = await self._invoke_agent(
                    db, user_id, session_id, agent_name, task_request, data_source_id
                )
                agent_results.append({
                    "agent": agent_name,
                    "task": task_request,
                    "result": result
                })

            # Synthesize final response
            await emit(EventType.THINKING, "Synthesizing insights",
                      {"agent_results": len(agent_results)}, 10)

            final_response = await self._synthesize_response(
                user_message, interpretation, agent_results, data_context
            )

            # Save messages to history (summary only - full results flow through system, not stored in logs)
            await self._save_message(db, session_id, user_id, "user", user_message)
            agent_summary = [
                {"agent": a.get("agent"), "task": a.get("task", "")[:100]}
                for a in agent_results
            ]
            await self._save_message(db, session_id, user_id, "assistant",
                                    final_response.get("response"),
                                    {"agent_activities": agent_summary})

            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            await emit(EventType.RESULT, "Analysis complete",
                      {"response_length": len(final_response.get("response", ""))}, 11)

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "response": final_response.get("response"),
                    "data": final_response.get("data"),
                    "visualization": final_response.get("visualization"),
                    "agent_activities": agent_results,
                    "needs_clarification": False
                },
                metadata={
                    "duration_ms": duration_ms,
                    "agents_invoked": [r["agent"] for r in agent_results],
                    "session_id": session_id
                }
            )

        except Exception as e:
            self.logger.error("orchestrator_error", error=str(e))
            await emit(EventType.ERROR, f"Error: {str(e)[:100]}", {"error": str(e)}, 99)

            return AgentResponse(
                status=AgentStatus.FAILED,
                result={"error": str(e)},
                metadata={}
            )

    async def _get_conversation_history(self, db: AsyncSession, session_id: str) -> List[Dict]:
        """Get recent conversation history for context."""
        try:
            result = await db.execute(
                text("""
                    SELECT role, content, created_at
                    FROM conversation_messages
                    WHERE session_id = :session_id
                    ORDER BY created_at DESC
                    LIMIT 20
                """),
                {"session_id": session_id}
            )
            rows = result.fetchall()
            # Reverse to get chronological order
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
        except Exception as e:
            self.logger.warning("failed_to_get_history", error=str(e))
            return []

    # NOTE: Uses shared get_data_context() from BaseAgent

    async def _interpret_request(
        self,
        message: str,
        history: List[Dict],
        data_context: Optional[Dict],
        available_agents: List[Dict]
    ) -> Dict:
        """LLM interprets the request and creates an execution plan."""

        # Build context strings
        history_str = "\n".join([f"{h['role']}: {h['content']}" for h in history[-10:]]) if history else "No previous conversation."

        data_str = "No data source loaded."
        if data_context:
            semantic = data_context.get("semantic_profile", {})
            data_str = f"""
=== DATA SOURCE ===
File: {data_context.get('file_name')}
Total Rows: {data_context.get('row_count', 0)}

=== SCHEMA ===
Columns and Types:
{json.dumps(data_context.get('detected_types', {}), indent=2)}

=== SEMANTIC PROFILE ===
Domain: {semantic.get('domain', 'unknown')}
Domain Description: {semantic.get('domain_description', '')}

Entity: {semantic.get('entity_name', 'unknown')} ({semantic.get('entity_type', 'unknown')})
Primary Key: {semantic.get('primary_key', 'unknown')}

Relationships:
{json.dumps(semantic.get('relationships', []), indent=2)}

Data Categories:
{json.dumps(semantic.get('data_categories', {}), indent=2)}

Field Descriptions:
{json.dumps(semantic.get('field_descriptions', {}), indent=2)}

Suggested Analyses:
{json.dumps(semantic.get('suggested_analyses', []), indent=2)}
"""

        agents_str = "\n".join([
            f"- {a['name']}: {a['description']}\n  Capabilities: {', '.join(a.get('capabilities', [])[:3])}"
            for a in available_agents
        ])

        prompt = f"""You are an intelligent data analysis orchestrator.

CONVERSATION HISTORY:
{history_str}

CURRENT USER MESSAGE:
{message}

{data_str}

AVAILABLE AGENTS:
{agents_str}

You have the full schema and semantic profile of the data source above.
If this context is sufficient to answer the user's query, respond directly.
If you need to query or compute against the actual data rows, route to the appropriate agent.

Respond with JSON:

If you can answer directly from the context above:
{{
  "can_answer_directly": true,
  "response": "Your direct answer using the schema and semantic profile provided above"
}}

If you need to query/analyze actual data rows:
{{
  "can_answer_directly": false,
  "understanding": "Your interpretation of what the user wants",
  "analysis_approach": "How you plan to analyze this",
  "tasks": [
    {{
      "agent": "agent_name",
      "request": "Specific task for this agent"
    }}
  ]
}}

If clarification is truly needed:
{{
  "needs_clarification": true,
  "clarification_question": "Your question to better understand what they want",
  "reason": "Why you need this information"
}}

Return valid JSON only."""

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
            self.logger.error("interpretation_error", error=str(e))
            return {
                "needs_clarification": True,
                "clarification_question": "I had trouble understanding your request. Could you please rephrase it?",
                "reason": str(e)
            }

    async def _invoke_agent(
        self,
        db: AsyncSession,
        user_id: str,
        session_id: str,
        agent_name: str,
        request: str,
        data_source_id: Optional[str]
    ) -> Dict:
        """Invoke a specific agent with a task."""

        agent_class = AgentRegistry.get_agent(agent_name)
        if not agent_class:
            return {"error": f"Agent '{agent_name}' not found in registry"}

        try:
            agent = agent_class()
            agent_message = AgentMessage(
                agent_type=agent_name,
                action="execute",
                payload={
                    "request": request,
                    "data_source_id": data_source_id,
                    "context": ""
                },
                conversation_id=session_id
            )

            response = await agent.execute(agent_message, db, user_id)

            if response.is_success:
                return response.result
            else:
                return {"error": response.error or "Agent execution failed"}

        except Exception as e:
            self.logger.error("agent_invocation_error", agent=agent_name, error=str(e))
            return {"error": str(e)}

    async def _synthesize_response(
        self,
        user_message: str,
        interpretation: Dict,
        agent_results: List[Dict],
        data_context: Optional[Dict]
    ) -> Dict:
        """LLM synthesizes agent results into a cohesive response."""

        # Prepare results for LLM
        results_summary = []
        all_data = []
        visualization_hint = "table"

        for ar in agent_results:
            result = ar.get("result", {})
            results_summary.append({
                "agent": ar.get("agent"),
                "task": ar.get("task"),
                "insights": result.get("insights", {}),
                "summary": result.get("insights", {}).get("summary", "") if isinstance(result.get("insights"), dict) else ""
            })

            # Collect data for response
            if result.get("results"):
                for r in result["results"]:
                    if r.get("data"):
                        all_data.extend(r["data"][:50])  # Limit data

            if result.get("visualization_hint"):
                visualization_hint = result["visualization_hint"]

        prompt = f"""You are presenting data analysis findings to a user. Synthesize these agent results into a clear, insightful response.

USER'S ORIGINAL QUESTION:
{user_message}

YOUR UNDERSTANDING:
{interpretation.get('understanding', '')}

AGENT RESULTS:
{json.dumps(results_summary, indent=2, default=str)}

Create a response that:
1. Directly addresses the user's question
2. Presents key findings with specific numbers
3. Highlights interesting insights or patterns
4. Is conversational but data-driven
5. Uses markdown formatting for clarity (headers, bullets, bold for key numbers)

Do NOT just list raw data - interpret it and explain what it means.
Keep the response focused and valuable - quality over quantity.

Return the response text (with markdown formatting). Do not wrap in JSON."""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.4}
            )

            return {
                "response": response.text.strip(),
                "data": all_data[:100] if all_data else None,
                "visualization": {"type": visualization_hint, "data": all_data[:50]} if all_data else None
            }

        except Exception as e:
            self.logger.error("synthesis_error", error=str(e))
            return {
                "response": "I analyzed your request but had trouble synthesizing the results. Here's what I found:\n\n" +
                           "\n".join([f"- {r.get('agent')}: {r.get('result', {}).get('insights', {}).get('summary', 'No summary')}" for r in agent_results]),
                "data": all_data,
                "visualization": None
            }

    async def _ensure_session_exists(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: str,
        title: str = "Chat Session"
    ):
        """Ensure conversation session exists before emitting events."""
        try:
            await db.execute(
                text("""
                    INSERT INTO conversation_sessions (id, user_id, title, is_active, created_at, last_activity_at)
                    VALUES (:session_id, :user_id, :title, true, NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING
                """),
                {"session_id": session_id, "user_id": user_id, "title": title[:100]}
            )
            await db.commit()
        except Exception as e:
            self.logger.warning("failed_to_ensure_session", error=str(e))

    async def _save_message(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: Dict = None
    ):
        """Save a message to conversation history."""
        try:
            # Ensure session exists
            await db.execute(
                text("""
                    INSERT INTO conversation_sessions (id, user_id, title, is_active, created_at, last_activity_at)
                    VALUES (:session_id, :user_id, :title, true, NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE SET last_activity_at = NOW()
                """),
                {"session_id": session_id, "user_id": user_id, "title": content[:100]}
            )

            # Save message
            await db.execute(
                text("""
                    INSERT INTO conversation_messages (id, session_id, role, content, meta_data, created_at)
                    VALUES (:id, :session_id, :role, :content, :metadata, NOW())
                """),
                {
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                    "metadata": json.dumps(metadata) if metadata else None
                }
            )

            await db.commit()

        except Exception as e:
            self.logger.warning("failed_to_save_message", error=str(e))
