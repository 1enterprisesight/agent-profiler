"""
Pattern Recognition Agent - Phase D: Self-Describing
Identifies trends, anomalies, and patterns in data using Gemini Pro.
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


class PatternRecognitionAgent(BaseAgent):
    """
    Pattern Recognition Agent - Phase D: Self-Describing

    Identifies patterns and anomalies with complete transparency.
    Uses LLM to interpret tasks - NO hardcoded action routing.
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Agent describes itself for dynamic discovery by orchestrator."""
        return {
            "name": "pattern_recognition",
            "purpose": "Identify trends, anomalies, correlations, and behavioral patterns in data",
            "when_to_use": [
                "User wants to identify trends over time",
                "User needs to detect anomalies or outliers",
                "User wants to find correlations between variables",
                "User asks about patterns in behavior or data",
                "User uses words like 'trend', 'anomaly', 'unusual', 'correlation'"
            ],
            "when_not_to_use": [
                "User needs simple counts or averages (use SQL)",
                "User wants to search text (use semantic search)",
                "User wants to segment or cluster (use segmentation)"
            ],
            "example_tasks": [
                "Identify trends in client engagement",
                "Detect unusual account activity",
                "Find correlations between AUM and engagement",
                "What patterns do you see in my client data?"
            ],
            "data_source_aware": True
        }

    def get_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Agent's internal capabilities for LLM-driven task routing."""
        return {
            "analyze_trends": {
                "description": "Identify trends in data over time",
                "examples": ["trend", "over time", "trajectory", "direction"],
                "method": "_analyze_trends"
            },
            "detect_anomalies": {
                "description": "Find unusual or outlier records",
                "examples": ["anomaly", "unusual", "outlier", "unexpected"],
                "method": "_detect_anomalies"
            },
            "find_correlations": {
                "description": "Discover correlations between variables",
                "examples": ["correlation", "relationship", "related", "affects"],
                "method": "_find_correlations"
            },
            "identify_patterns": {
                "description": "General pattern identification in dataset",
                "examples": ["patterns", "insights", "behaviors", "observations"],
                "method": "_identify_patterns"
            }
        }

    def __init__(self):
        super().__init__()
        vertexai.init(project=settings.google_cloud_project, location=settings.vertex_ai_location)
        self.model = GenerativeModel(settings.gemini_pro_model)

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """Execute pattern recognition task using LLM-driven interpretation."""
        task = message.action
        payload = message.payload
        conversation_id = message.conversation_id
        start_time = datetime.utcnow()

        try:
            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.RECEIVED, title=f"Received: {task[:50]}...",
                details={"task": task}, step_number=1)

            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.THINKING, title="Analyzing for patterns...",
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
                event_type=EventType.RESULT, title=f"Pattern analysis complete",
                details={"patterns_found": len(result.get("patterns", []))}, step_number=5, duration_ms=duration_ms)

            return AgentResponse(status=AgentStatus.COMPLETED, result=result,
                metadata={"model_used": settings.gemini_pro_model, "duration_ms": duration_ms})

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.ERROR, title=f"Pattern recognition failed",
                details={"error": str(e)}, step_number=5, duration_ms=duration_ms)
            return AgentResponse(status=AgentStatus.FAILED, error=f"Pattern recognition failed: {str(e)}")

    async def _interpret_task(self, task: str, payload: Dict, conversation_id: str, user_id: str, db: AsyncSession):
        """LLM decides which capability to use."""
        caps = "\n".join([f"- {k}: {v['description']}" for k, v in self.get_capabilities().items()])
        prompt = f"""Analyze task and choose capability.
CAPABILITIES:\n{caps}
TASK: "{task}"
Respond JSON: {{"capability": "name", "parameters": {{}}}}"""

        try:
            response = await self.model.generate_content_async(prompt, generation_config={"temperature": 0.1})
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(text)
            params = result.get("parameters", {})
            params.update(payload)
            return result.get("capability", "identify_patterns"), params
        except:
            return "identify_patterns", payload

    async def _execute_capability(self, capability: str, params: Dict, conversation_id: str, user_id: str, db: AsyncSession):
        """Execute the chosen capability."""
        if capability == "analyze_trends":
            return await self._analyze_trends(conversation_id, user_id, params, db)
        elif capability == "detect_anomalies":
            return await self._detect_anomalies(conversation_id, user_id, params, db)
        elif capability == "find_correlations":
            return await self._find_correlations(conversation_id, user_id, params, db)
        return await self._identify_patterns(conversation_id, user_id, params, db)

    async def _analyze_trends(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Analyze trends in data over time."""
        return {"trends": [], "message": "Trend analysis - sample implementation", "data_points": 0}

    async def _detect_anomalies(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Detect anomalies in data."""
        field = payload.get("field", "aum")
        allowed = ['aum', 'engagement_score', 'risk_score', 'age', 'account_value']
        if field not in allowed:
            field = 'aum'

        query = f"""
        SELECT id, client_name, (core_data->>'{field}')::numeric as value, core_data
        FROM clients WHERE user_id = :user_id AND core_data->>'{field}' IS NOT NULL LIMIT 500
        """
        result = await db.execute(text(query), {"user_id": user_id})
        rows = result.fetchall()
        if not rows or len(rows) < 10:
            return {"anomalies": [], "message": "Insufficient data"}

        columns = result.keys()
        data = [dict(zip(columns, row)) for row in rows]
        values = [d["value"] for d in data if d["value"]]
        avg = sum(values) / len(values) if values else 0

        prompt = f"""Analyze for anomalies in {field}.
Stats: Count={len(values)}, Avg={avg:.2f}, Max={max(values) if values else 0}
Return JSON: [{{"type": "outlier", "description": "...", "severity": "high/medium/low"}}]"""

        try:
            response = await self.model.generate_content_async(prompt, generation_config={"temperature": 0.3})
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            anomalies = json.loads(text)
        except:
            anomalies = []

        return {"field": field, "anomalies": anomalies, "total_records": len(data)}

    async def _find_correlations(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Find correlations between variables."""
        fields = payload.get("fields", ["aum", "engagement_score"])
        return {"fields": fields, "correlations": [], "sample_size": 0}

    async def _identify_patterns(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """General pattern identification."""
        query = """
        SELECT client_name, core_data, custom_data, computed_metrics
        FROM clients WHERE user_id = :user_id ORDER BY RANDOM() LIMIT 100
        """
        result = await db.execute(text(query), {"user_id": user_id})
        rows = result.fetchall()
        if not rows:
            return {"patterns": [], "message": "No data"}

        columns = result.keys()
        data = [dict(zip(columns, row)) for row in rows]

        prompt = f"""Identify patterns in this client data.
Sample: {json.dumps(data[:10], default=str)}
Return JSON: [{{"pattern": "description", "prevalence": "percent", "insight": "why it matters"}}]"""

        try:
            response = await self.model.generate_content_async(prompt, generation_config={"temperature": 0.3})
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            patterns = json.loads(text)
        except:
            patterns = []

        return {"patterns": patterns, "sample_size": len(data)}
