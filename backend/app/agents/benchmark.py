"""
Benchmark Agent - Phase D: Self-Describing
Evaluates data quality and risk metrics using Gemini Flash.
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


class BenchmarkAgent(BaseAgent):
    """
    Benchmark Agent - Phase D: Self-Describing

    Evaluates data quality and risk with complete transparency.
    Uses LLM to interpret tasks - NO hardcoded action routing.
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Agent describes itself for dynamic discovery by orchestrator."""
        return {
            "name": "benchmark",
            "purpose": "Evaluate data quality, risk metrics, and compliance status",
            "when_to_use": [
                "User wants to check data completeness or quality",
                "User needs to assess client risk levels",
                "User wants to evaluate compliance status",
                "User asks about data quality scores or metrics",
                "User uses words like 'quality', 'completeness', 'risk', 'compliance'"
            ],
            "when_not_to_use": [
                "User needs calculations or aggregations (use SQL)",
                "User wants to segment clients (use segmentation)",
                "User wants recommendations (use recommendation agent)"
            ],
            "example_tasks": [
                "Check data completeness",
                "Assess client risk levels",
                "Evaluate data quality",
                "What's my data quality score?"
            ],
            "data_source_aware": True
        }

    def get_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Agent's internal capabilities for LLM-driven task routing."""
        return {
            "check_completeness": {
                "description": "Evaluate data completeness across required fields",
                "examples": ["completeness", "missing", "filled", "complete"],
                "method": "_check_completeness"
            },
            "assess_risk": {
                "description": "Assess client risk levels",
                "examples": ["risk", "risky", "high risk", "risk level"],
                "method": "_assess_risk"
            },
            "evaluate_compliance": {
                "description": "Check compliance status against rules",
                "examples": ["compliance", "compliant", "regulations", "rules"],
                "method": "_evaluate_compliance"
            },
            "quality_score": {
                "description": "Calculate overall data quality score",
                "examples": ["quality", "score", "grade", "overall"],
                "method": "_calculate_quality_score"
            }
        }

    def __init__(self):
        super().__init__()
        vertexai.init(project=settings.google_cloud_project, location=settings.vertex_ai_location)
        self.model = GenerativeModel(settings.gemini_flash_model)

    async def _execute_internal(self, message: AgentMessage, db: AsyncSession, user_id: str) -> AgentResponse:
        """Execute benchmark task using LLM-driven interpretation."""
        task = message.action
        payload = message.payload
        conversation_id = message.conversation_id
        start_time = datetime.utcnow()

        try:
            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.RECEIVED, title=f"Received: {task[:50]}...",
                details={"task": task}, step_number=1)

            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.THINKING, title="Analyzing benchmark requirements...",
                details={"capabilities": list(self.get_capabilities().keys())}, step_number=2)

            capability, params = await self._interpret_task(task, payload, conversation_id, user_id, db)

            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.DECISION, title=f"Using '{capability}' capability",
                details={"capability": capability}, step_number=3)

            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.ACTION, title=f"Executing {capability}...",
                details={}, step_number=4)

            result = await self._execute_capability(capability, params, conversation_id, user_id, db)
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.RESULT, title=f"Benchmark complete",
                details={"score": result.get("completeness_score") or result.get("overall_quality_score", 0)},
                step_number=5, duration_ms=duration_ms)

            return AgentResponse(status=AgentStatus.COMPLETED, result=result,
                metadata={"model_used": settings.gemini_flash_model, "duration_ms": duration_ms})

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.ERROR, title=f"Benchmark failed",
                details={"error": str(e)}, step_number=5, duration_ms=duration_ms)
            return AgentResponse(status=AgentStatus.FAILED, error=f"Benchmark failed: {str(e)}")

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
            return result.get("capability", "check_completeness"), params
        except:
            return "check_completeness", payload

    async def _execute_capability(self, capability: str, params: Dict, conversation_id: str, user_id: str, db: AsyncSession):
        """Execute the chosen capability."""
        if capability == "check_completeness":
            return await self._check_completeness(conversation_id, user_id, params, db)
        elif capability == "assess_risk":
            return await self._assess_risk(conversation_id, user_id, params, db)
        elif capability == "evaluate_compliance":
            return await self._evaluate_compliance(conversation_id, user_id, params, db)
        return await self._calculate_quality_score(conversation_id, user_id, params, db)

    async def _check_completeness(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Check data completeness."""
        required_fields = payload.get("required_fields", ["client_name", "contact_email", "aum"])

        query = """SELECT id, client_name, contact_email, core_data, custom_data
                   FROM clients WHERE user_id = :user_id LIMIT 1000"""
        result = await db.execute(text(query), {"user_id": user_id})
        rows = result.fetchall()

        if not rows:
            return {"completeness_score": 0, "message": "No clients"}

        columns = result.keys()
        clients = [dict(zip(columns, row)) for row in rows]
        field_scores = {}

        for field in required_fields:
            complete = 0
            for client in clients:
                if field in ["client_name", "contact_email"]:
                    if client.get(field):
                        complete += 1
                else:
                    core = client.get("core_data", {}) or {}
                    if core.get(field):
                        complete += 1
            field_scores[field] = (complete / len(clients)) * 100

        overall = sum(field_scores.values()) / len(field_scores) if field_scores else 0
        recommendations = [f"Improve {f} ({s:.0f}%)" for f, s in field_scores.items() if s < 80]

        return {
            "completeness_score": overall,
            "field_scores": field_scores,
            "total_clients": len(clients),
            "recommendations": recommendations
        }

    async def _assess_risk(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Assess client risk levels."""
        query = """SELECT id, client_name, core_data, computed_metrics
                   FROM clients WHERE user_id = :user_id LIMIT 500"""
        result = await db.execute(text(query), {"user_id": user_id})
        rows = result.fetchall()

        if not rows:
            return {"high_risk_clients": [], "message": "No clients"}

        columns = result.keys()
        clients = [dict(zip(columns, row)) for row in rows]

        prompt = f"""Assess risk for clients.
Sample: {json.dumps(clients[:20], default=str)}
Return JSON: {{"distribution": {{"high": 0, "medium": 0, "low": 0}}, "high_risk": [], "factors": []}}"""

        try:
            response = await self.model.generate_content_async(prompt, generation_config={"temperature": 0.1})
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            assessment = json.loads(text)
        except:
            assessment = {"distribution": {}, "high_risk": [], "factors": []}

        return {
            "risk_distribution": assessment.get("distribution", {}),
            "high_risk_clients": assessment.get("high_risk", []),
            "risk_factors": assessment.get("factors", []),
            "total_assessed": len(clients)
        }

    async def _evaluate_compliance(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Evaluate compliance status."""
        return {"compliance_score": 100, "issues": [], "message": "Compliance check placeholder"}

    async def _calculate_quality_score(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Calculate overall quality score."""
        query = """SELECT id, client_name, contact_email, core_data, custom_data
                   FROM clients WHERE user_id = :user_id ORDER BY RANDOM() LIMIT 200"""
        result = await db.execute(text(query), {"user_id": user_id})
        rows = result.fetchall()

        if not rows:
            return {"overall_quality_score": 0, "message": "No data"}

        columns = result.keys()
        clients = [dict(zip(columns, row)) for row in rows]

        prompt = f"""Evaluate data quality.
Sample: {json.dumps(clients[:15], default=str)}
Return JSON: {{"overall": 0-100, "dimensions": {{}}, "strengths": [], "improvements": []}}"""

        try:
            response = await self.model.generate_content_async(prompt, generation_config={"temperature": 0.1})
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            quality = json.loads(text)
        except:
            quality = {"overall": 50, "dimensions": {}, "strengths": [], "improvements": []}

        return {
            "overall_quality_score": quality.get("overall", 50),
            "dimension_scores": quality.get("dimensions", {}),
            "strengths": quality.get("strengths", []),
            "improvements_needed": quality.get("improvements", []),
            "sample_size": len(clients)
        }
