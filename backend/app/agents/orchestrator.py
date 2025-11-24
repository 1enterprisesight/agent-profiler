"""
Orchestrator Agent
Coordinates multi-agent workflows using sequential execution with Gemini Pro
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
import json
from datetime import datetime

import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus
from app.config import settings


# Agent Capability Registry
AGENT_CAPABILITIES = {
    "data_ingestion": {
        "purpose": "Import and process data from various sources",
        "model": "flash",  # Use Flash for schema discovery
        "capabilities": [
            "upload_csv_files",
            "connect_to_crms",
            "discover_schemas",
            "map_fields_intelligently",
            "validate_and_import_data"
        ],
        "use_cases": [
            "Upload CSV file with client data",
            "Connect to Salesforce",
            "Import data from Wealthbox",
            "Sync CRM data"
        ],
        "never_use_for": [
            "Querying existing data",
            "Analysis or calculations",
            "Searching or filtering data"
        ]
    },
    "sql_analytics": {
        "purpose": "Quantitative analysis on structured data using SQL",
        "model": "pro",  # Use Pro for complex SQL generation
        "capabilities": [
            "mathematical_operations",
            "aggregations_sum_avg_count",
            "date_time_calculations",
            "structured_filtering_exact_matches",
            "grouping_and_sorting",
            "joins_across_tables",
            "statistical_calculations"
        ],
        "use_cases": [
            "Count clients by segment",
            "Calculate average AUM per client",
            "Find clients where last_contact > 90 days ago",
            "Sum total assets by advisor",
            "Calculate year-over-year growth"
        ],
        "never_use_for": [
            "LIKE or regex queries on unstructured text",
            "Fuzzy text matching",
            "Semantic similarity searches",
            "Natural language search in notes/descriptions"
        ]
    },
    "semantic_search": {
        "purpose": "Search unstructured text using semantic understanding",
        "model": "pro",  # Use Pro for semantic understanding
        "capabilities": [
            "fuzzy_text_matching",
            "semantic_similarity_search",
            "natural_language_queries_on_text",
            "embedding_based_search",
            "concept_matching"
        ],
        "use_cases": [
            "Find clients with notes mentioning 'retirement planning'",
            "Search for similar client descriptions",
            "Find clients interested in 'ESG investing'",
            "Fuzzy match on client names"
        ],
        "never_use_for": [
            "Math or calculations",
            "Date/time operations",
            "Exact value filtering",
            "Aggregations"
        ]
    },
    "pattern_recognition": {
        "purpose": "Identify trends, anomalies, and patterns in data",
        "model": "pro",  # Use Pro for complex pattern analysis
        "capabilities": [
            "trend_detection",
            "anomaly_detection",
            "correlation_analysis",
            "time_series_analysis",
            "change_point_detection"
        ],
        "use_cases": [
            "Identify trends in client engagement",
            "Detect unusual account activity",
            "Find correlations between client behaviors"
        ]
    },
    "segmentation": {
        "purpose": "Group clients into meaningful cohorts",
        "model": "pro",
        "capabilities": [
            "client_clustering",
            "similarity_grouping",
            "cohort_analysis",
            "persona_identification"
        ],
        "use_cases": [
            "Segment clients by engagement level",
            "Find similar clients to high-value ones",
            "Create client personas"
        ]
    },
    "benchmark": {
        "purpose": "Evaluate data quality and risk metrics",
        "model": "flash",  # Use Flash for rule-based evaluations
        "capabilities": [
            "data_completeness_scoring",
            "risk_assessment",
            "compliance_checking",
            "quality_metrics"
        ],
        "use_cases": [
            "Check data completeness",
            "Assess client risk levels",
            "Evaluate compliance status"
        ]
    },
    "recommendation": {
        "purpose": "Generate actionable recommendations",
        "model": "pro",
        "capabilities": [
            "action_prioritization",
            "improvement_suggestions",
            "next_best_action",
            "personalized_recommendations"
        ],
        "use_cases": [
            "Suggest which clients to contact first",
            "Recommend data quality improvements",
            "Prioritize outreach actions"
        ]
    }
}


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator Agent - Coordinates multi-agent workflows

    Uses Gemini Pro to:
    1. Break down user request into execution plan
    2. Route to agents sequentially
    3. Evaluate results and decide next steps
    4. Aggregate final results
    """

    def __init__(self, agent_registry: Optional[Dict[str, BaseAgent]] = None):
        super().__init__(
            name="orchestrator",
            description="Coordinates multi-agent workflows for complex requests"
        )

        # Initialize Vertex AI
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )

        # Use Pro model for complex orchestration planning
        self.model = GenerativeModel(settings.gemini_pro_model)

        # Agent registry for executing steps
        self.agent_registry = agent_registry or {}

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
        Orchestrate multi-agent workflow

        Process:
        1. Create execution plan
        2. Execute each step sequentially
        3. Evaluate results and adapt plan
        4. Aggregate final results
        """
        try:
            # Step 1: Create execution plan
            self.logger.info(
                "creating_execution_plan",
                user_query=user_query,
                conversation_id=conversation_id
            )

            plan_response = await self._create_execution_plan(
                user_query, context, conversation_id, user_id, db
            )

            if not plan_response["success"]:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error=f"Failed to create plan: {plan_response.get('error')}"
                )

            execution_plan = plan_response["plan"]

            # Step 2: Execute plan sequentially
            workflow_results = []
            intermediate_context = {**context}

            for step_num, step in enumerate(execution_plan["steps"], 1):
                self.logger.info(
                    "executing_workflow_step",
                    step=step_num,
                    total_steps=len(execution_plan["steps"]),
                    agent=step["agent"],
                    action=step["action"]
                )

                # Execute this step
                step_result = await self._execute_step(
                    step,
                    intermediate_context,
                    conversation_id,
                    user_id,
                    db
                )

                workflow_results.append({
                    "step": step_num,
                    "agent": step["agent"],
                    "action": step["action"],
                    "result": step_result["result"],
                    "success": step_result["success"],
                    "error": step_result.get("error")
                })

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
                    "successful_steps": sum(1 for r in workflow_results if r["success"])
                }
            )

        except Exception as e:
            self.logger.error(
                "orchestration_failed",
                error=str(e),
                user_query=user_query,
                exc_info=True,
            )
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

            # Parse execution plan
            plan = self._parse_plan_response(response)

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
        """Build prompt for Gemini Pro to create execution plan"""

        # Build agent capabilities description
        capabilities_desc = ""
        for agent_name, details in AGENT_CAPABILITIES.items():
            capabilities_desc += f"\n{agent_name}:\n"
            capabilities_desc += f"  Purpose: {details['purpose']}\n"
            capabilities_desc += f"  Model: Gemini {details['model'].upper()}\n"
            capabilities_desc += f"  Capabilities: {', '.join(details['capabilities'])}\n"
            capabilities_desc += f"  Use cases: {'; '.join(details['use_cases'])}\n"
            if "never_use_for" in details:
                capabilities_desc += f"  NEVER use for: {'; '.join(details['never_use_for'])}\n"

        context_str = ""
        if context:
            context_str = f"\n\nAvailable Context:\n{json.dumps(context, indent=2)}"

        prompt = f"""You are an intelligent workflow orchestrator for a multi-agent client data analysis system.

Your job is to break down the user's request into a sequential execution plan using available agents.

AVAILABLE AGENTS AND THEIR CAPABILITIES:
{capabilities_desc}

CRITICAL ROUTING RULES:
1. SQL Analytics Agent:
   - USE FOR: Math, calculations, aggregations, date operations, exact value filtering
   - NEVER USE FOR: LIKE queries, regex, fuzzy text matching, semantic search

2. Semantic Search Agent:
   - USE FOR: Unstructured text search, fuzzy matching, similarity, concepts
   - NEVER USE FOR: Math, calculations, exact filtering, date operations

3. Each agent is independent and has its own LLM (Flash or Pro)
4. Agents never call other agents - only YOU coordinate the workflow
5. Results from each step feed into the next step

User Query: "{user_query}"{context_str}

Create a sequential execution plan. For simple requests (single agent), create a 1-step plan.
For complex requests, break into multiple steps.

Respond ONLY with valid JSON in this format:
{{
  "steps": [
    {{
      "agent": "agent_name",
      "action": "action_name",
      "parameters": {{}},
      "reasoning": "Why this step is needed",
      "required": true
    }}
  ],
  "overall_strategy": "Brief description of the overall approach"
}}

EXAMPLES:

Simple Request:
User: "How many clients do we have?"
{{
  "steps": [
    {{
      "agent": "sql_analytics",
      "action": "generate_and_execute_query",
      "parameters": {{"query_intent": "count all clients"}},
      "reasoning": "Simple COUNT query on clients table",
      "required": true
    }}
  ],
  "overall_strategy": "Single SQL query to count clients"
}}

Complex Request:
User: "Upload this CSV, then show me clients with AUM over $1M who haven't been contacted in 60 days"
{{
  "steps": [
    {{
      "agent": "data_ingestion",
      "action": "upload_csv",
      "parameters": {{"validate_schema": true}},
      "reasoning": "First need to import the CSV data",
      "required": true
    }},
    {{
      "agent": "sql_analytics",
      "action": "generate_and_execute_query",
      "parameters": {{
        "filters": ["aum > 1000000", "last_contact_date < NOW() - INTERVAL '60 days'"]
      }},
      "reasoning": "Use SQL for quantitative filtering (AUM > 1M) and date math (60 days)",
      "required": true
    }}
  ],
  "overall_strategy": "Import data first, then query with SQL for math and date operations"
}}

Semantic + SQL Example:
User: "Find clients interested in retirement planning with AUM over $500k"
{{
  "steps": [
    {{
      "agent": "semantic_search",
      "action": "search_text_fields",
      "parameters": {{
        "search_terms": ["retirement planning", "retirement", "pension"],
        "fields": ["notes", "interests", "goals"]
      }},
      "reasoning": "Use semantic search for unstructured text matching on 'retirement planning'",
      "required": true
    }},
    {{
      "agent": "sql_analytics",
      "action": "filter_by_quantitative",
      "parameters": {{
        "client_ids": "from_previous_step",
        "filters": ["aum > 500000"]
      }},
      "reasoning": "Use SQL for quantitative filtering (AUM > 500k) on semantic search results",
      "required": true
    }}
  ],
  "overall_strategy": "Semantic search for concept, then SQL for quantitative filtering"
}}

Now analyze the user query and create the execution plan:"""

        return prompt

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

    def _parse_plan_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON execution plan from Gemini"""
        try:
            # Clean response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            # Parse JSON
            plan = json.loads(response)

            # Validate
            if "steps" not in plan or not isinstance(plan["steps"], list):
                raise ValueError("Plan must contain 'steps' array")

            for step in plan["steps"]:
                required_fields = ["agent", "action", "parameters", "reasoning"]
                for field in required_fields:
                    if field not in step:
                        raise ValueError(f"Step missing required field: {field}")

            return plan

        except json.JSONDecodeError as e:
            self.logger.error(
                "failed_to_parse_plan",
                error=str(e),
                response=response,
            )
            raise ValueError(f"Failed to parse execution plan: {str(e)}")

    async def _execute_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Execute a single workflow step by calling the appropriate agent
        """
        agent_name = step["agent"]
        action = step["action"]
        parameters = step["parameters"]

        try:
            # Get agent from registry
            agent = self.agent_registry.get(agent_name)

            if not agent:
                self.logger.warning(
                    "agent_not_available",
                    agent_name=agent_name
                )
                return {
                    "success": False,
                    "result": None,
                    "error": f"Agent '{agent_name}' not yet implemented"
                }

            # Create agent message
            agent_message = AgentMessage(
                agent_type=agent_name,
                action=action,
                payload=parameters,
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
