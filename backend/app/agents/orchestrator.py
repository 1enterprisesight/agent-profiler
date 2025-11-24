"""
Orchestrator Agent
Routes user requests to appropriate specialized agents using Gemini Flash
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import json

import vertexai
from vertexai.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus
from app.config import settings


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator Agent - Routes requests to specialized agents
    Uses Gemini Flash for fast intent classification and routing
    """

    def __init__(self):
        super().__init__(
            name="orchestrator",
            description="Routes user requests to appropriate specialized agents"
        )

        # Initialize Vertex AI
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )

        self.model = GenerativeModel(settings.gemini_flash_model)

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """
        Route user request to appropriate agent

        Actions:
            - route: Determine which agent should handle the request
        """
        action = message.action
        payload = message.payload

        if action == "route":
            return await self._route_request(
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

    async def _route_request(
        self,
        conversation_id: str,
        user_id: str,
        user_query: str,
        context: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Analyze user query and determine routing

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            user_query: User's natural language request
            context: Additional context (available data sources, etc.)
            db: Database session

        Returns:
            AgentResponse with routing decision
        """
        try:
            # Build routing prompt
            prompt = self._build_routing_prompt(user_query, context)

            # Call Gemini Flash for fast intent classification
            response = await self._call_gemini(prompt)

            # Log LLM conversation
            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_flash_model,
                prompt=prompt,
                response=response,
            )

            # Parse routing decision
            routing = self._parse_routing_response(response)

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "target_agent": routing["target_agent"],
                    "action": routing["action"],
                    "parameters": routing["parameters"],
                    "reasoning": routing["reasoning"],
                },
                metadata={
                    "model_used": settings.gemini_flash_model,
                }
            )

        except Exception as e:
            self.logger.error(
                "routing_failed",
                error=str(e),
                user_query=user_query,
                exc_info=True,
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Failed to route request: {str(e)}"
            )

    def _build_routing_prompt(
        self,
        user_query: str,
        context: Dict[str, Any]
    ) -> str:
        """Build prompt for Gemini to determine routing"""

        available_agents = """
Available Agents:
1. data_ingestion - Handles data upload, CRM connections, schema discovery
   Actions: upload_csv, connect_salesforce, sync_crm_data

2. sql_analytics - Executes SQL queries, performs calculations
   Actions: generate_sql, execute_query, analyze_data

3. pattern_recognition - Identifies trends, anomalies, patterns
   Actions: find_patterns, detect_anomalies, analyze_trends

4. segmentation - Groups clients into cohorts
   Actions: segment_clients, find_similar_clients, cluster_analysis

5. benchmark - Evaluates completeness, risk, compliance
   Actions: check_completeness, assess_risk, evaluate_compliance

6. recommendation - Suggests actions based on analysis
   Actions: recommend_actions, prioritize_tasks, suggest_improvements
"""

        context_str = ""
        if context:
            context_str = f"\n\nContext:\n{json.dumps(context, indent=2)}"

        prompt = f"""You are an intelligent routing system for a multi-agent client data analysis platform.

{available_agents}

User Query: "{user_query}"{context_str}

Analyze the user's query and determine:
1. Which agent should handle this request
2. What action that agent should perform
3. What parameters to pass to the agent
4. Brief reasoning for your decision

Respond ONLY with valid JSON in this exact format:
{{
  "target_agent": "agent_name",
  "action": "action_name",
  "parameters": {{}},
  "reasoning": "Brief explanation"
}}

Examples:

User: "Upload this CSV file with client data"
{{
  "target_agent": "data_ingestion",
  "action": "upload_csv",
  "parameters": {{"validate_schema": true}},
  "reasoning": "User wants to ingest data from CSV file"
}}

User: "How many clients do we have?"
{{
  "target_agent": "sql_analytics",
  "action": "generate_sql",
  "parameters": {{"query_intent": "count clients"}},
  "reasoning": "User wants a simple SQL count query"
}}

User: "Which clients are most at risk?"
{{
  "target_agent": "benchmark",
  "action": "assess_risk",
  "parameters": {{"sort_by": "risk_score", "limit": 10}},
  "reasoning": "User wants risk assessment and ranking"
}}

User: "Show me trends in client engagement"
{{
  "target_agent": "pattern_recognition",
  "action": "analyze_trends",
  "parameters": {{"metric": "engagement", "time_period": "6_months"}},
  "reasoning": "User wants temporal trend analysis"
}}

Now analyze the user query above and respond with JSON:"""

        return prompt

    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini Flash model"""
        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={
                    "temperature": 0.1,  # Low temperature for consistent routing
                    "max_output_tokens": 512,
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

    def _parse_routing_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from Gemini"""
        try:
            # Clean response (remove markdown code blocks if present)
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            # Parse JSON
            routing = json.loads(response)

            # Validate required fields
            required_fields = ["target_agent", "action", "parameters", "reasoning"]
            for field in required_fields:
                if field not in routing:
                    raise ValueError(f"Missing required field: {field}")

            return routing

        except json.JSONDecodeError as e:
            self.logger.error(
                "failed_to_parse_routing_response",
                error=str(e),
                response=response,
            )
            # Fallback to data ingestion if parsing fails
            return {
                "target_agent": "data_ingestion",
                "action": "help",
                "parameters": {},
                "reasoning": "Failed to parse routing, defaulting to data ingestion"
            }
