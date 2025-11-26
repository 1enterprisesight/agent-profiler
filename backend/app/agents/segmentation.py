"""
Segmentation Agent
Groups clients into meaningful cohorts using Gemini Pro
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json

import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus
from app.config import settings


class SegmentationAgent(BaseAgent):
    """
    Segmentation Agent - Groups clients into cohorts

    Capabilities:
    - Client clustering by behavior/attributes
    - Similarity-based grouping
    - Cohort analysis
    - Persona identification
    - Custom segment creation

    Uses Gemini Pro for intelligent segmentation logic
    """

    def __init__(self):
        super().__init__(
            name="segmentation",
            description="Groups clients into meaningful cohorts and segments"
        )

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
        Execute segmentation action

        Actions:
            - segment_clients: Segment clients by criteria
            - find_similar_clients: Find clients similar to a reference
            - create_personas: Generate client personas
            - cohort_analysis: Analyze specific cohorts
        """
        action = message.action
        payload = message.payload

        if action == "segment_clients":
            return await self._segment_clients(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "find_similar_clients":
            return await self._find_similar_clients(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "create_personas":
            return await self._create_personas(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "cohort_analysis":
            return await self._cohort_analysis(
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

    async def _segment_clients(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Segment clients into meaningful groups
        """
        try:
            criteria = payload.get("criteria", "engagement_level")
            num_segments = payload.get("num_segments", 4)

            self.logger.info(
                "segmenting_clients",
                criteria=criteria,
                num_segments=num_segments
            )

            # Fetch client data
            query = """
            SELECT
                id,
                client_name,
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
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "segments": [],
                        "message": "No clients to segment"
                    }
                )

            columns = result.keys()
            clients = [dict(zip(columns, row)) for row in rows]

            # Use Gemini to create intelligent segments
            segments = await self._create_segments_with_gemini(
                clients,
                criteria,
                num_segments,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "segments": segments,
                    "criteria": criteria,
                    "num_segments": len(segments),
                    "total_clients": len(clients)
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "analysis_type": "client_segmentation"
                }
            )

        except Exception as e:
            self.logger.error(
                "segmentation_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Segmentation failed: {str(e)}"
            )

    async def _find_similar_clients(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Find clients similar to a reference client or profile
        """
        try:
            reference_id = payload.get("reference_id")
            profile = payload.get("profile", {})

            # Get reference client if ID provided
            if reference_id:
                query = """
                SELECT core_data, custom_data, computed_metrics
                FROM clients
                WHERE id = :ref_id
                """
                result = await db.execute(text(query), {"ref_id": reference_id})
                row = result.fetchone()
                if row:
                    profile = {
                        "core_data": row[0],
                        "custom_data": row[1],
                        "computed_metrics": row[2]
                    }

            if not profile:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error="Need reference_id or profile"
                )

            # Fetch all clients for comparison
            query = """
            SELECT
                id,
                client_name,
                contact_email,
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
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "similar_clients": [],
                        "message": "No clients for comparison"
                    }
                )

            columns = result.keys()
            clients = [dict(zip(columns, row)) for row in rows]

            # Use Gemini to find similar clients
            similar = await self._find_similar_with_gemini(
                profile,
                clients,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "similar_clients": similar,
                    "reference_profile": profile,
                    "match_count": len(similar)
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "analysis_type": "similarity_matching"
                }
            )

        except Exception as e:
            self.logger.error(
                "similarity_search_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Similarity search failed: {str(e)}"
            )

    async def _create_personas(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Create client personas from data
        """
        try:
            num_personas = payload.get("num_personas", 5)

            # Fetch representative sample
            query = """
            SELECT
                client_name,
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
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "personas": [],
                        "message": "No data for persona creation"
                    }
                )

            columns = result.keys()
            clients = [dict(zip(columns, row)) for row in rows]

            # Use Gemini to create personas
            personas = await self._generate_personas_with_gemini(
                clients,
                num_personas,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "personas": personas,
                    "num_personas": len(personas),
                    "sample_size": len(clients)
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "analysis_type": "persona_generation"
                }
            )

        except Exception as e:
            self.logger.error(
                "persona_creation_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Persona creation failed: {str(e)}"
            )

    async def _cohort_analysis(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Analyze a specific cohort of clients
        """
        try:
            cohort_definition = payload.get("cohort_definition", {})

            # Build query based on cohort definition
            # Simplified - would build dynamic WHERE clause
            query = """
            SELECT
                id,
                client_name,
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
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "analysis": {},
                        "message": "No clients in cohort"
                    }
                )

            columns = result.keys()
            cohort = [dict(zip(columns, row)) for row in rows]

            # Analyze cohort with Gemini
            analysis = await self._analyze_cohort_with_gemini(
                cohort,
                cohort_definition,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "cohort_size": len(cohort),
                    "analysis": analysis
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "analysis_type": "cohort_analysis"
                }
            )

        except Exception as e:
            self.logger.error(
                "cohort_analysis_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Cohort analysis failed: {str(e)}"
            )

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
        except:
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
        except:
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
        except:
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
        except:
            return {}
