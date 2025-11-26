"""
Recommendation Agent
Generates actionable recommendations using Gemini Pro
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json

import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus
from app.config import settings


class RecommendationAgent(BaseAgent):
    """
    Recommendation Agent - Generates actionable recommendations

    Capabilities:
    - Action prioritization
    - Improvement suggestions
    - Next best action recommendations
    - Personalized recommendations
    - Strategic recommendations

    Uses Gemini Pro for intelligent recommendation generation
    """

    def __init__(self):
        super().__init__(
            name="recommendation",
            description="Generates actionable recommendations and next best actions"
        )

        # Initialize Vertex AI
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )

        # Use Pro model for intelligent recommendations
        self.model = GenerativeModel(settings.gemini_pro_model)

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """
        Execute recommendation action

        Actions:
            - recommend_actions: Generate prioritized action recommendations
            - prioritize_tasks: Prioritize tasks or outreach
            - suggest_improvements: Suggest data/process improvements
            - next_best_action: Determine next best action for specific client
        """
        action = message.action
        payload = message.payload

        if action == "recommend_actions":
            return await self._recommend_actions(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "prioritize_tasks":
            return await self._prioritize_tasks(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "suggest_improvements":
            return await self._suggest_improvements(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "next_best_action":
            return await self._next_best_action(
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

    async def _recommend_actions(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Generate prioritized action recommendations
        """
        try:
            context = payload.get("context", {})
            analysis_results = payload.get("analysis_results", {})

            self.logger.info(
                "generating_recommendations",
                has_context=bool(context),
                has_analysis=bool(analysis_results)
            )

            # Fetch relevant data for recommendations
            query = """
            SELECT
                id,
                client_name,
                core_data,
                computed_metrics
            FROM clients
            WHERE user_id = :user_id
            ORDER BY RANDOM()
            LIMIT 100
            """

            result = await db.execute(text(query), {"user_id": user_id})
            rows = result.fetchall()

            if not rows:
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "recommendations": [],
                        "message": "No data for recommendations"
                    }
                )

            columns = result.keys()
            clients = [dict(zip(columns, row)) for row in rows]

            # Generate recommendations using Gemini
            recommendations = await self._generate_recommendations_with_gemini(
                clients,
                context,
                analysis_results,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "recommendations": recommendations,
                    "total_recommendations": len(recommendations),
                    "priority_breakdown": self._categorize_by_priority(recommendations)
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "recommendation_type": "general_actions"
                }
            )

        except Exception as e:
            self.logger.error(
                "recommendation_generation_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Recommendation generation failed: {str(e)}"
            )

    async def _prioritize_tasks(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Prioritize tasks or client outreach
        """
        try:
            task_list = payload.get("tasks", [])
            criteria = payload.get("criteria", "impact")

            # Fetch client data for context
            query = """
            SELECT
                id,
                client_name,
                core_data,
                computed_metrics
            FROM clients
            WHERE user_id = :user_id
            LIMIT 200
            """

            result = await db.execute(text(query), {"user_id": user_id})
            rows = result.fetchall()

            columns = result.keys()
            clients = [dict(zip(columns, row)) for row in rows]

            # Prioritize using Gemini
            prioritized = await self._prioritize_with_gemini(
                task_list or clients,
                criteria,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "prioritized_tasks": prioritized,
                    "criteria": criteria,
                    "total_items": len(prioritized)
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "recommendation_type": "task_prioritization"
                }
            )

        except Exception as e:
            self.logger.error(
                "task_prioritization_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Task prioritization failed: {str(e)}"
            )

    async def _suggest_improvements(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Suggest improvements for data or processes
        """
        try:
            focus_area = payload.get("focus_area", "data_quality")
            current_metrics = payload.get("current_metrics", {})

            # Analyze current state
            query = """
            SELECT
                COUNT(*) as total_clients,
                COUNT(contact_email) as has_email,
                COUNT(CASE WHEN core_data->>'aum' IS NOT NULL THEN 1 END) as has_aum,
                COUNT(CASE WHEN core_data->>'last_contact_date' IS NOT NULL THEN 1 END) as has_contact_date
            FROM clients
            WHERE user_id = :user_id
            """

            result = await db.execute(text(query), {"user_id": user_id})
            row = result.fetchone()

            if row:
                current_state = dict(zip(result.keys(), row))
            else:
                current_state = {}

            # Generate improvement suggestions using Gemini
            improvements = await self._suggest_improvements_with_gemini(
                focus_area,
                current_state,
                current_metrics,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "improvements": improvements,
                    "focus_area": focus_area,
                    "current_state": current_state,
                    "total_suggestions": len(improvements)
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "recommendation_type": "improvement_suggestions"
                }
            )

        except Exception as e:
            self.logger.error(
                "improvement_suggestion_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Improvement suggestion failed: {str(e)}"
            )

    async def _next_best_action(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Determine next best action for a specific client or situation
        """
        try:
            client_id = payload.get("client_id")
            situation = payload.get("situation", {})

            # Get client data if ID provided
            client_data = None
            if client_id:
                query = """
                SELECT
                    id,
                    client_name,
                    contact_email,
                    core_data,
                    custom_data,
                    computed_metrics
                FROM clients
                WHERE id = :client_id
                """

                result = await db.execute(text(query), {"client_id": client_id})
                row = result.fetchone()

                if row:
                    columns = result.keys()
                    client_data = dict(zip(columns, row))

            # Determine next best action using Gemini
            next_action = await self._determine_next_action_with_gemini(
                client_data,
                situation,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "recommended_action": next_action["action"],
                    "reasoning": next_action["reasoning"],
                    "expected_outcome": next_action["outcome"],
                    "priority": next_action["priority"]
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "recommendation_type": "next_best_action"
                }
            )

        except Exception as e:
            self.logger.error(
                "next_action_determination_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Next action determination failed: {str(e)}"
            )

    def _categorize_by_priority(
        self,
        recommendations: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Categorize recommendations by priority"""
        breakdown = {"high": 0, "medium": 0, "low": 0}
        for rec in recommendations:
            priority = rec.get("priority", "medium").lower()
            if priority in breakdown:
                breakdown[priority] += 1
        return breakdown

    async def _generate_recommendations_with_gemini(
        self,
        clients: List[Dict[str, Any]],
        context: Dict[str, Any],
        analysis_results: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Use Gemini to generate recommendations"""
        prompt = f"""Based on this client data and analysis, generate 5-7 prioritized action recommendations.

Context: {json.dumps(context, default=str)}
Analysis Results: {json.dumps(analysis_results, default=str)}
Sample Clients: {json.dumps(clients[:10], indent=2, default=str)}

Generate recommendations as JSON:
[
  {{
    "action": "Specific action to take",
    "reasoning": "Why this action is recommended",
    "expected_impact": "What impact this will have",
    "priority": "high/medium/low",
    "effort": "low/medium/high",
    "timeframe": "immediate/short-term/long-term"
  }},
  ...
]

Focus on actionable, specific recommendations."""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.4, "max_output_tokens": 1536}
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

    async def _prioritize_with_gemini(
        self,
        items: List[Any],
        criteria: str,
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Use Gemini to prioritize items"""
        prompt = f"""Prioritize these items based on {criteria}.

Items: {json.dumps(items[:20], indent=2, default=str)}

Prioritize as JSON:
[
  {{
    "item": "Item description",
    "priority_rank": 1,
    "reasoning": "Why this priority",
    "urgency": "high/medium/low"
  }},
  ...
]

Return top 10 prioritized items."""

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
            return []

    async def _suggest_improvements_with_gemini(
        self,
        focus_area: str,
        current_state: Dict[str, Any],
        current_metrics: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Use Gemini to suggest improvements"""
        prompt = f"""Suggest improvements for {focus_area}.

Current State: {json.dumps(current_state, default=str)}
Current Metrics: {json.dumps(current_metrics, default=str)}

Provide improvement suggestions as JSON:
[
  {{
    "improvement": "What to improve",
    "current_gap": "What's missing or suboptimal",
    "recommendation": "Specific steps to take",
    "expected_benefit": "What this will achieve",
    "difficulty": "easy/medium/hard"
  }},
  ...
]

Provide 5-7 specific, actionable improvements."""

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

    async def _determine_next_action_with_gemini(
        self,
        client_data: Optional[Dict[str, Any]],
        situation: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Use Gemini to determine next best action"""
        prompt = f"""Determine the next best action for this situation.

Client Data: {json.dumps(client_data, indent=2, default=str) if client_data else "N/A"}
Situation: {json.dumps(situation, default=str)}

Determine next action as JSON:
{{
  "action": "Specific next action to take",
  "reasoning": "Why this is the best next step",
  "outcome": "Expected result of this action",
  "priority": "high/medium/low",
  "alternative_actions": ["Alternative 1", "Alternative 2"]
}}

Focus on the single most impactful next step."""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 768}
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
            return {
                "action": "Unable to determine action",
                "reasoning": "Insufficient data",
                "outcome": "N/A",
                "priority": "low"
            }
