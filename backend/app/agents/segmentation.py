"""
Segmentation Agent - Phase D: Self-Describing Template
Groups clients into meaningful cohorts using LLM-driven task interpretation.

This is the TEMPLATE for all other agents. Key patterns:
1. get_agent_info() - Agent describes itself for orchestrator discovery
2. get_capabilities() - Internal routing capabilities
3. _interpret_task() - LLM decides which capability to use (NO hardcoded action routing)
4. emit_event() - Transparency events throughout execution
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json

import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus, EventType
from app.config import settings


class SegmentationAgent(BaseAgent):
    """
    Segmentation Agent - Phase D: Self-Describing

    Groups clients into meaningful cohorts with complete transparency.
    Uses LLM to interpret tasks - NO hardcoded action routing.
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """
        Agent describes itself for dynamic discovery by orchestrator.
        This is called by the orchestrator to build its planning prompt.
        """
        return {
            "name": "segmentation",
            "purpose": "Group clients into meaningful cohorts, segments, and personas",
            "when_to_use": [
                "User wants to group or cluster clients",
                "User asks about segments, cohorts, or personas",
                "User wants to find similar clients",
                "User asks for client profiling or categorization",
                "User wants to understand client types"
            ],
            "when_not_to_use": [
                "User needs numerical calculations or aggregations",
                "User is searching for specific text in notes",
                "User wants to import or upload data",
                "User needs exact value filtering (use SQL instead)"
            ],
            "example_tasks": [
                "Segment my clients by engagement level",
                "Find clients similar to my top performers",
                "Create personas for my client base",
                "Group clients by investment style",
                "Identify different client types"
            ],
            "data_source_aware": True  # Can work with multi-source data
        }

    def get_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """
        Agent's internal capabilities for LLM-driven task routing.
        The agent's LLM uses this to decide which method to call.
        """
        return {
            "segment_clients": {
                "description": "Group clients into segments based on criteria like engagement, value, or behavior",
                "examples": ["segment by", "group clients", "create clusters", "categorize"],
                "method": "_segment_clients"
            },
            "find_similar": {
                "description": "Find clients similar to a reference client or profile",
                "examples": ["find similar", "clients like", "lookalikes", "matching profile"],
                "method": "_find_similar_clients"
            },
            "create_personas": {
                "description": "Generate client personas that represent common client types",
                "examples": ["create personas", "client types", "profiles", "archetypes"],
                "method": "_create_personas"
            },
            "cohort_analysis": {
                "description": "Analyze characteristics and patterns within a specific group of clients",
                "examples": ["analyze cohort", "group analysis", "cohort patterns"],
                "method": "_cohort_analysis"
            }
        }

    def __init__(self):
        super().__init__()

        # Initialize Vertex AI
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )

        # Use Pro model for complex segmentation logic
        self.model = GenerativeModel(settings.gemini_pro_model)

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """
        Execute segmentation task using LLM-driven interpretation.
        NO hardcoded action routing - the LLM decides what to do.
        """
        task = message.action  # This is now natural language from orchestrator
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
                title=f"Received task: {task[:50]}..." if len(task) > 50 else f"Received task: {task}",
                details={"task": task, "payload": payload},
                step_number=1
            )

            # TRANSPARENCY: Thinking event - interpreting the task
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.THINKING,
                title="Analyzing task to determine approach...",
                details={
                    "task": task,
                    "available_capabilities": list(self.get_capabilities().keys())
                },
                step_number=2
            )

            # LLM-driven task interpretation
            capability, interpretation = await self._interpret_task(
                task, payload, conversation_id, user_id, db
            )

            # TRANSPARENCY: Decision event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.DECISION,
                title=f"Decided to use '{capability}' capability",
                details={
                    "selected_capability": capability,
                    "interpretation": interpretation,
                    "reasoning": f"Task '{task}' maps to {capability}"
                },
                step_number=3
            )

            # TRANSPARENCY: Action event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.ACTION,
                title=f"Executing {capability}...",
                details={"capability": capability, "parameters": interpretation},
                step_number=4
            )

            # Execute the chosen capability
            result = await self._execute_capability(
                capability,
                interpretation,
                conversation_id,
                user_id,
                db
            )

            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # TRANSPARENCY: Result event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.RESULT,
                title=self._summarize_result(capability, result),
                details={"capability": capability, "result_preview": self._preview_result(result)},
                step_number=5,
                duration_ms=duration_ms
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result=result,
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "capability_used": capability,
                    "duration_ms": duration_ms
                }
            )

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # TRANSPARENCY: Error event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.ERROR,
                title=f"Segmentation failed: {str(e)[:50]}",
                details={"error": str(e), "task": task},
                step_number=5,
                duration_ms=duration_ms
            )

            self.logger.error(
                "segmentation_failed",
                error=str(e),
                task=task,
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Segmentation failed: {str(e)}"
            )

    async def _interpret_task(
        self,
        task: str,
        payload: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> tuple[str, Dict[str, Any]]:
        """
        Use LLM to interpret the task and decide which capability to use.
        This replaces hardcoded `if action == "..."` routing.
        """
        capabilities = self.get_capabilities()
        capabilities_desc = "\n".join([
            f"- {name}: {info['description']} (examples: {', '.join(info['examples'])})"
            for name, info in capabilities.items()
        ])

        prompt = f"""You are the Segmentation Agent. Analyze this task and decide which capability to use.

AVAILABLE CAPABILITIES:
{capabilities_desc}

USER TASK: "{task}"

ADDITIONAL CONTEXT: {json.dumps(payload, default=str) if payload else "None"}

Respond with JSON only:
{{
  "capability": "capability_name",
  "parameters": {{
    "criteria": "what to segment/analyze by (if applicable)",
    "num_segments": number (if applicable, default 4),
    "num_personas": number (if applicable, default 5),
    "reference_id": "client ID if mentioned",
    "cohort_definition": {{}}
  }},
  "reasoning": "Why this capability fits the task"
}}
"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 512}
            )

            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_pro_model,
                prompt=prompt,
                response=response.text
            )

            # Parse response
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            result = json.loads(text.strip())

            capability = result.get("capability", "segment_clients")
            parameters = result.get("parameters", {})

            # Merge with payload (payload takes precedence)
            parameters.update(payload)

            return capability, parameters

        except Exception as e:
            self.logger.warning(
                "task_interpretation_failed_using_default",
                error=str(e),
                task=task
            )
            # Default to segment_clients if interpretation fails
            return "segment_clients", payload

    async def _execute_capability(
        self,
        capability: str,
        parameters: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Execute the chosen capability.
        """
        if capability == "segment_clients":
            return await self._segment_clients(
                conversation_id, user_id, parameters, db
            )
        elif capability == "find_similar":
            return await self._find_similar_clients(
                conversation_id, user_id, parameters, db
            )
        elif capability == "create_personas":
            return await self._create_personas(
                conversation_id, user_id, parameters, db
            )
        elif capability == "cohort_analysis":
            return await self._cohort_analysis(
                conversation_id, user_id, parameters, db
            )
        else:
            # Unknown capability - try segment_clients as default
            self.logger.warning(
                "unknown_capability_using_default",
                capability=capability
            )
            return await self._segment_clients(
                conversation_id, user_id, parameters, db
            )

    def _summarize_result(self, capability: str, result: Dict[str, Any]) -> str:
        """Generate summary for transparency event"""
        if capability == "segment_clients":
            return f"Created {result.get('num_segments', 0)} segments from {result.get('total_clients', 0)} clients"
        elif capability == "find_similar":
            return f"Found {result.get('match_count', 0)} similar clients"
        elif capability == "create_personas":
            return f"Generated {result.get('num_personas', 0)} client personas"
        elif capability == "cohort_analysis":
            return f"Analyzed cohort of {result.get('cohort_size', 0)} clients"
        return "Segmentation complete"

    def _preview_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Create a preview of results for transparency (avoid huge payloads)"""
        preview = {}
        for key, value in result.items():
            if isinstance(value, list):
                preview[key] = f"[{len(value)} items]"
            elif isinstance(value, dict):
                preview[key] = f"{{...{len(value)} keys}}"
            else:
                preview[key] = value
        return preview

    # =========================================================================
    # CAPABILITY IMPLEMENTATIONS (unchanged from original, but with user_id)
    # =========================================================================

    async def _segment_clients(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Segment clients into meaningful groups"""
        criteria = payload.get("criteria", "engagement_level")
        num_segments = payload.get("num_segments", 4)

        self.logger.info(
            "segmenting_clients",
            criteria=criteria,
            num_segments=num_segments
        )

        # Fetch client data (CRITICAL: user_id filter)
        query = """
        SELECT
            id,
            client_name,
            source_type,
            core_data,
            custom_data,
            computed_metrics
        FROM clients
        WHERE user_id = :user_id
        LIMIT 500
        """

        result = await db.execute(text(query), {"user_id": user_id})
        rows = result.fetchall()

        if not rows:
            return {
                "segments": [],
                "message": "No clients to segment",
                "total_clients": 0,
                "num_segments": 0
            }

        columns = result.keys()
        clients = [dict(zip(columns, row)) for row in rows]

        # Use Gemini to create intelligent segments
        segments = await self._create_segments_with_gemini(
            clients, criteria, num_segments, conversation_id, user_id, db
        )

        return {
            "segments": segments,
            "criteria": criteria,
            "num_segments": len(segments),
            "total_clients": len(clients)
        }

    async def _find_similar_clients(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Find clients similar to a reference client or profile"""
        reference_id = payload.get("reference_id")
        profile = payload.get("profile", {})

        # Get reference client if ID provided
        if reference_id:
            query = """
            SELECT core_data, custom_data, computed_metrics
            FROM clients
            WHERE id = :ref_id AND user_id = :user_id
            """
            result = await db.execute(text(query), {"ref_id": reference_id, "user_id": user_id})
            row = result.fetchone()
            if row:
                profile = {
                    "core_data": row[0],
                    "custom_data": row[1],
                    "computed_metrics": row[2]
                }

        if not profile:
            return {
                "similar_clients": [],
                "message": "Need reference_id or profile",
                "match_count": 0
            }

        # Fetch all clients for comparison (CRITICAL: user_id filter)
        query = """
        SELECT
            id,
            client_name,
            contact_email,
            source_type,
            core_data,
            custom_data,
            computed_metrics
        FROM clients
        WHERE user_id = :user_id
        LIMIT 500
        """

        result = await db.execute(text(query), {"user_id": user_id})
        rows = result.fetchall()

        if not rows:
            return {
                "similar_clients": [],
                "message": "No clients for comparison",
                "match_count": 0
            }

        columns = result.keys()
        clients = [dict(zip(columns, row)) for row in rows]

        # Use Gemini to find similar clients
        similar = await self._find_similar_with_gemini(
            profile, clients, conversation_id, user_id, db
        )

        return {
            "similar_clients": similar,
            "reference_profile": profile,
            "match_count": len(similar)
        }

    async def _create_personas(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Create client personas from data"""
        num_personas = payload.get("num_personas", 5)

        # Fetch representative sample (CRITICAL: user_id filter)
        query = """
        SELECT
            client_name,
            source_type,
            core_data,
            custom_data,
            computed_metrics
        FROM clients
        WHERE user_id = :user_id
        ORDER BY RANDOM()
        LIMIT 200
        """

        result = await db.execute(text(query), {"user_id": user_id})
        rows = result.fetchall()

        if not rows:
            return {
                "personas": [],
                "message": "No data for persona creation",
                "num_personas": 0,
                "sample_size": 0
            }

        columns = result.keys()
        clients = [dict(zip(columns, row)) for row in rows]

        # Use Gemini to create personas
        personas = await self._generate_personas_with_gemini(
            clients, num_personas, conversation_id, user_id, db
        )

        return {
            "personas": personas,
            "num_personas": len(personas),
            "sample_size": len(clients)
        }

    async def _cohort_analysis(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Analyze a specific cohort of clients"""
        cohort_definition = payload.get("cohort_definition", {})

        # Fetch clients (CRITICAL: user_id filter)
        query = """
        SELECT
            id,
            client_name,
            source_type,
            core_data,
            custom_data,
            computed_metrics
        FROM clients
        WHERE user_id = :user_id
        LIMIT 500
        """

        result = await db.execute(text(query), {"user_id": user_id})
        rows = result.fetchall()

        if not rows:
            return {
                "analysis": {},
                "message": "No clients in cohort",
                "cohort_size": 0
            }

        columns = result.keys()
        cohort = [dict(zip(columns, row)) for row in rows]

        # Analyze cohort with Gemini
        analysis = await self._analyze_cohort_with_gemini(
            cohort, cohort_definition, conversation_id, user_id, db
        )

        return {
            "cohort_size": len(cohort),
            "analysis": analysis
        }

    # =========================================================================
    # GEMINI HELPER METHODS (unchanged from original)
    # =========================================================================

    async def _create_segments_with_gemini(
        self,
        clients: List[Dict[str, Any]],
        criteria: str,
        num_segments: int,
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Use Gemini to create intelligent segments"""
        prompt = f"""Analyze these clients and create {num_segments} meaningful segments based on {criteria}.

Sample clients (first 20):
{json.dumps(clients[:20], indent=2, default=str)}

Total clients: {len(clients)}

Create {num_segments} distinct segments with JSON format:
[
  {{
    "name": "Segment Name",
    "description": "What defines this segment",
    "characteristics": ["Trait 1", "Trait 2"],
    "estimated_size": "Percentage",
    "priority": "high/medium/low"
  }},
  ...
]
"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.4, "max_output_tokens": 1024}
            )

            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_pro_model,
                prompt=prompt,
                response=response.text
            )

            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            return json.loads(text.strip())
        except Exception as e:
            self.logger.error("segment_creation_failed", error=str(e))
            return []

    async def _find_similar_with_gemini(
        self,
        profile: Dict[str, Any],
        clients: List[Dict[str, Any]],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Use Gemini to find similar clients"""
        prompt = f"""Find the 10 most similar clients to this reference profile:

Reference Profile:
{json.dumps(profile, indent=2, default=str)}

Candidate Clients:
{json.dumps(clients[:50], indent=2, default=str)}

Return the 10 most similar as JSON:
[
  {{
    "client_id": "uuid",
    "client_name": "Name",
    "similarity_score": 0.0-1.0,
    "similarity_reason": "Why they're similar"
  }},
  ...
]
"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.2, "max_output_tokens": 1024}
            )

            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_pro_model,
                prompt=prompt,
                response=response.text
            )

            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            return json.loads(text.strip())
        except Exception as e:
            self.logger.error("similarity_search_failed", error=str(e))
            return []

    async def _generate_personas_with_gemini(
        self,
        clients: List[Dict[str, Any]],
        num_personas: int,
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Use Gemini to generate client personas"""
        prompt = f"""Analyze these clients and create {num_personas} distinct personas that represent common client types.

Sample clients:
{json.dumps(clients[:30], indent=2, default=str)}

Total sample: {len(clients)} clients

Create {num_personas} personas as JSON:
[
  {{
    "persona_name": "The [Type]",
    "description": "Brief description",
    "demographics": {{"age_range": "", "typical_aum": ""}},
    "behaviors": ["Behavior 1", "Behavior 2"],
    "goals": ["Goal 1", "Goal 2"],
    "pain_points": ["Pain 1", "Pain 2"],
    "estimated_percentage": "% of client base"
  }},
  ...
]
"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.5, "max_output_tokens": 1536}
            )

            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_pro_model,
                prompt=prompt,
                response=response.text
            )

            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            return json.loads(text.strip())
        except Exception as e:
            self.logger.error("persona_generation_failed", error=str(e))
            return []

    async def _analyze_cohort_with_gemini(
        self,
        cohort: List[Dict[str, Any]],
        cohort_definition: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Use Gemini to analyze a cohort"""
        prompt = f"""Analyze this client cohort:

Cohort Definition: {json.dumps(cohort_definition, default=str)}
Cohort Size: {len(cohort)}

Sample clients:
{json.dumps(cohort[:20], indent=2, default=str)}

Provide cohort analysis as JSON:
{{
  "summary": "Overall cohort summary",
  "key_characteristics": ["Characteristic 1", "Characteristic 2"],
  "opportunities": ["Opportunity 1", "Opportunity 2"],
  "risks": ["Risk 1", "Risk 2"],
  "recommendations": ["Action 1", "Action 2"]
}}
"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 1024}
            )

            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_pro_model,
                prompt=prompt,
                response=response.text
            )

            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            return json.loads(text.strip())
        except Exception as e:
            self.logger.error("cohort_analysis_failed", error=str(e))
            return {}
