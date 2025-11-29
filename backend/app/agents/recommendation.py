"""
Recommendation Agent - Phase D: Self-Describing
Generates actionable recommendations using Gemini Pro.
Follows the segmentation.py template pattern.
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


class RecommendationAgent(BaseAgent):
    """
    Recommendation Agent - Phase D: Self-Describing

    Generates recommendations with complete transparency.
    Uses LLM to interpret tasks - NO hardcoded action routing.
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Agent describes itself for dynamic discovery by orchestrator."""
        return {
            "name": "recommendation",
            "purpose": "Generate actionable recommendations, prioritize tasks, and suggest next best actions",
            "when_to_use": [
                "User wants recommendations or suggestions",
                "User needs to prioritize tasks or outreach",
                "User asks for next best action",
                "User wants improvement suggestions",
                "User uses words like 'recommend', 'suggest', 'prioritize', 'what should I do'"
            ],
            "when_not_to_use": [
                "User needs data analysis (use other agents first)",
                "User wants to search or query data",
                "User needs to segment clients"
            ],
            "example_tasks": [
                "What actions should I prioritize?",
                "Suggest which clients to contact first",
                "What's the next best action for client X?",
                "Recommend data quality improvements"
            ],
            "data_source_aware": True
        }

    def get_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Agent's internal capabilities for LLM-driven task routing."""
        return {
            "recommend_actions": {
                "description": "Generate prioritized action recommendations",
                "examples": ["recommend", "suggest", "what should", "actions"],
                "method": "_recommend_actions"
            },
            "prioritize_tasks": {
                "description": "Prioritize tasks or client outreach",
                "examples": ["prioritize", "order", "rank", "most important"],
                "method": "_prioritize_tasks"
            },
            "suggest_improvements": {
                "description": "Suggest improvements for data or processes",
                "examples": ["improve", "better", "enhance", "optimize"],
                "method": "_suggest_improvements"
            },
            "next_best_action": {
                "description": "Determine next best action for a client or situation",
                "examples": ["next", "best action", "what to do", "for this client"],
                "method": "_next_best_action"
            }
        }

    def __init__(self):
        super().__init__()
        vertexai.init(project=settings.google_cloud_project, location=settings.vertex_ai_location)
        self.model = GenerativeModel(settings.gemini_pro_model)

    async def _execute_internal(self, message: AgentMessage, db: AsyncSession, user_id: str) -> AgentResponse:
        """Execute recommendation task using LLM-driven interpretation."""
        task = message.action
        payload = message.payload
        conversation_id = message.conversation_id
        start_time = datetime.utcnow()

        try:
            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.RECEIVED, title=f"Received: {task[:50]}...",
                details={"task": task}, step_number=1)

            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.THINKING, title="Analyzing for recommendations...",
                details={"capabilities": list(self.get_capabilities().keys())}, step_number=2)

            capability, params = await self._interpret_task(task, payload, conversation_id, user_id, db)

            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.DECISION, title=f"Using '{capability}' capability",
                details={"capability": capability}, step_number=3)

            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.ACTION, title=f"Generating {capability}...",
                details={}, step_number=4)

            result = await self._execute_capability(capability, params, conversation_id, user_id, db)
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            rec_count = len(result.get("recommendations", [])) or len(result.get("prioritized_tasks", []))
            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.RESULT, title=f"Generated {rec_count} recommendations",
                details={"count": rec_count}, step_number=5, duration_ms=duration_ms)

            return AgentResponse(status=AgentStatus.COMPLETED, result=result,
                metadata={"model_used": settings.gemini_pro_model, "duration_ms": duration_ms})

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.ERROR, title=f"Recommendation failed",
                details={"error": str(e)}, step_number=5, duration_ms=duration_ms)
            return AgentResponse(status=AgentStatus.FAILED, error=f"Recommendation failed: {str(e)}")

    async def _interpret_task(self, task: str, payload: Dict, conversation_id: str, user_id: str, db: AsyncSession):
        """LLM decides which capability to use."""
        caps = "\n".join([f"- {k}: {v['description']}" for k, v in self.get_capabilities().items()])
        prompt = f"""Choose capability for task.
CAPABILITIES:\n{caps}
TASK: "{task}"
Respond JSON: {{"capability": "name", "parameters": {{}}}}"""

        try:
            response = await self.model.generate_content_async(prompt, generation_config={"temperature": 0.1})
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(text)
            params = result.get("parameters", {})
            params.update(payload)
            return result.get("capability", "recommend_actions"), params
        except:
            return "recommend_actions", payload

    async def _execute_capability(self, capability: str, params: Dict, conversation_id: str, user_id: str, db: AsyncSession):
        """Execute the chosen capability."""
        if capability == "recommend_actions":
            return await self._recommend_actions(conversation_id, user_id, params, db)
        elif capability == "prioritize_tasks":
            return await self._prioritize_tasks(conversation_id, user_id, params, db)
        elif capability == "suggest_improvements":
            return await self._suggest_improvements(conversation_id, user_id, params, db)
        return await self._next_best_action(conversation_id, user_id, params, db)

    async def _recommend_actions(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Generate prioritized action recommendations."""
        context = payload.get("context", {})

        query = """SELECT id, client_name, core_data, computed_metrics
                   FROM clients WHERE user_id = :user_id ORDER BY RANDOM() LIMIT 100"""
        result = await db.execute(text(query), {"user_id": user_id})
        rows = result.fetchall()

        if not rows:
            return {"recommendations": [], "message": "No data"}

        columns = result.keys()
        clients = [dict(zip(columns, row)) for row in rows]

        prompt = f"""Generate 5-7 prioritized action recommendations.
Context: {json.dumps(context, default=str)}
Clients: {json.dumps(clients[:10], default=str)}
Return JSON: [{{"action": "...", "reasoning": "...", "priority": "high/medium/low", "effort": "low/medium/high"}}]"""

        try:
            response = await self.model.generate_content_async(prompt, generation_config={"temperature": 0.4})
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            recommendations = json.loads(text)
        except:
            recommendations = []

        return {
            "recommendations": recommendations,
            "total_recommendations": len(recommendations),
            "priority_breakdown": {"high": sum(1 for r in recommendations if r.get("priority") == "high"),
                                  "medium": sum(1 for r in recommendations if r.get("priority") == "medium"),
                                  "low": sum(1 for r in recommendations if r.get("priority") == "low")}
        }

    async def _prioritize_tasks(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Prioritize tasks or client outreach."""
        criteria = payload.get("criteria", "impact")

        query = """SELECT id, client_name, core_data, computed_metrics
                   FROM clients WHERE user_id = :user_id LIMIT 200"""
        result = await db.execute(text(query), {"user_id": user_id})
        rows = result.fetchall()

        columns = result.keys()
        clients = [dict(zip(columns, row)) for row in rows]

        prompt = f"""Prioritize items based on {criteria}.
Items: {json.dumps(clients[:20], default=str)}
Return JSON: [{{"item": "description", "priority_rank": 1, "reasoning": "...", "urgency": "high/medium/low"}}]"""

        try:
            response = await self.model.generate_content_async(prompt, generation_config={"temperature": 0.3})
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            prioritized = json.loads(text)
        except:
            prioritized = []

        return {"prioritized_tasks": prioritized, "criteria": criteria, "total_items": len(prioritized)}

    async def _suggest_improvements(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Suggest improvements."""
        focus_area = payload.get("focus_area", "data_quality")

        query = """SELECT COUNT(*) as total, COUNT(contact_email) as has_email
                   FROM clients WHERE user_id = :user_id"""
        result = await db.execute(text(query), {"user_id": user_id})
        row = result.fetchone()
        current_state = dict(zip(result.keys(), row)) if row else {}

        prompt = f"""Suggest improvements for {focus_area}.
Current: {json.dumps(current_state, default=str)}
Return JSON: [{{"improvement": "...", "recommendation": "...", "difficulty": "easy/medium/hard"}}]"""

        try:
            response = await self.model.generate_content_async(prompt, generation_config={"temperature": 0.4})
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            improvements = json.loads(text)
        except:
            improvements = []

        return {"improvements": improvements, "focus_area": focus_area, "total_suggestions": len(improvements)}

    async def _next_best_action(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Determine next best action."""
        client_id = payload.get("client_id")
        situation = payload.get("situation", {})

        client_data = None
        if client_id:
            query = """SELECT id, client_name, contact_email, core_data, custom_data
                       FROM clients WHERE id = :cid AND user_id = :user_id"""
            result = await db.execute(text(query), {"cid": client_id, "user_id": user_id})
            row = result.fetchone()
            if row:
                client_data = dict(zip(result.keys(), row))

        prompt = f"""Determine next best action.
Client: {json.dumps(client_data, default=str) if client_data else "N/A"}
Situation: {json.dumps(situation, default=str)}
Return JSON: {{"action": "...", "reasoning": "...", "outcome": "...", "priority": "high/medium/low"}}"""

        try:
            response = await self.model.generate_content_async(prompt, generation_config={"temperature": 0.3})
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            next_action = json.loads(text)
        except:
            next_action = {"action": "Review data", "reasoning": "Insufficient info", "outcome": "N/A", "priority": "low"}

        return {
            "recommended_action": next_action.get("action"),
            "reasoning": next_action.get("reasoning"),
            "expected_outcome": next_action.get("outcome"),
            "priority": next_action.get("priority")
        }
