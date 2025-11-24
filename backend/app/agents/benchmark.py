"""
Benchmark Agent
Evaluates data quality and risk metrics using Gemini Flash for fast rule-based assessments
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json

import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus
from app.config import settings


class BenchmarkAgent(BaseAgent):
    """
    Benchmark Agent - Evaluates quality and risk

    Capabilities:
    - Data completeness scoring
    - Risk assessment
    - Compliance checking
    - Quality metrics evaluation
    - Benchmark comparisons

    Uses Gemini Flash for fast rule-based evaluations
    """

    def __init__(self):
        super().__init__(
            name="benchmark",
            description="Evaluates data quality, risk, and compliance metrics"
        )

        # Initialize Vertex AI
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )

        # Use Flash model for fast rule-based evaluations
        self.model = GenerativeModel(settings.gemini_flash_model)

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """
        Execute benchmark action

        Actions:
            - check_completeness: Evaluate data completeness
            - assess_risk: Assess client risk levels
            - evaluate_compliance: Check compliance status
            - calculate_quality_score: Overall quality metrics
        """
        action = message.action
        payload = message.payload

        if action == "check_completeness":
            return await self._check_completeness(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "assess_risk":
            return await self._assess_risk(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "evaluate_compliance":
            return await self._evaluate_compliance(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "calculate_quality_score":
            return await self._calculate_quality_score(
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

    async def _check_completeness(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Check data completeness across required fields
        """
        try:
            required_fields = payload.get("required_fields", [
                "client_name", "contact_email", "aum", "last_contact_date"
            ])

            self.logger.info(
                "checking_completeness",
                required_fields=required_fields
            )

            # Fetch client data
            query = """
            SELECT
                id,
                client_name,
                contact_email,
                core_data,
                custom_data
            FROM clients
            LIMIT 1000
            """

            result = await db.execute(text(query))
            rows = result.fetchall()

            if not rows:
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "completeness_score": 0,
                        "message": "No clients to evaluate"
                    }
                )

            columns = result.keys()
            clients = [dict(zip(columns, row)) for row in rows]

            # Calculate completeness
            completeness_report = self._calculate_completeness(clients, required_fields)

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "completeness_score": completeness_report["overall_score"],
                    "field_scores": completeness_report["field_scores"],
                    "missing_data_count": completeness_report["missing_count"],
                    "total_clients": len(clients),
                    "recommendations": completeness_report["recommendations"]
                },
                metadata={
                    "model_used": settings.gemini_flash_model,
                    "evaluation_type": "data_completeness"
                }
            )

        except Exception as e:
            self.logger.error(
                "completeness_check_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Completeness check failed: {str(e)}"
            )

    async def _assess_risk(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Assess client risk levels
        """
        try:
            sort_by = payload.get("sort_by", "risk_score")
            limit = payload.get("limit", 20)

            # Fetch clients with risk data
            query = f"""
            SELECT
                id,
                client_name,
                contact_email,
                core_data,
                computed_metrics
            FROM clients
            WHERE computed_metrics IS NOT NULL
            LIMIT 500
            """

            result = await db.execute(text(query))
            rows = result.fetchall()

            if not rows:
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "high_risk_clients": [],
                        "message": "No clients with risk data"
                    }
                )

            columns = result.keys()
            clients = [dict(zip(columns, row)) for row in rows]

            # Assess risk using Gemini
            risk_assessment = await self._assess_risk_with_gemini(
                clients,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "risk_distribution": risk_assessment["distribution"],
                    "high_risk_clients": risk_assessment["high_risk"][:limit],
                    "risk_factors": risk_assessment["factors"],
                    "total_assessed": len(clients)
                },
                metadata={
                    "model_used": settings.gemini_flash_model,
                    "evaluation_type": "risk_assessment"
                }
            )

        except Exception as e:
            self.logger.error(
                "risk_assessment_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Risk assessment failed: {str(e)}"
            )

    async def _evaluate_compliance(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Evaluate compliance status
        """
        try:
            compliance_rules = payload.get("rules", [])

            # Fetch clients
            query = """
            SELECT
                id,
                client_name,
                core_data,
                custom_data
            FROM clients
            LIMIT 500
            """

            result = await db.execute(text(query))
            rows = result.fetchall()

            if not rows:
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "compliance_score": 100,
                        "issues": [],
                        "message": "No clients to evaluate"
                    }
                )

            columns = result.keys()
            clients = [dict(zip(columns, row)) for row in rows]

            # Evaluate compliance
            compliance_report = await self._evaluate_compliance_with_gemini(
                clients,
                compliance_rules,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "compliance_score": compliance_report["score"],
                    "issues": compliance_report["issues"],
                    "compliant_count": compliance_report["compliant"],
                    "non_compliant_count": compliance_report["non_compliant"],
                    "total_evaluated": len(clients)
                },
                metadata={
                    "model_used": settings.gemini_flash_model,
                    "evaluation_type": "compliance_check"
                }
            )

        except Exception as e:
            self.logger.error(
                "compliance_evaluation_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Compliance evaluation failed: {str(e)}"
            )

    async def _calculate_quality_score(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Calculate overall data quality score
        """
        try:
            # Fetch sample of clients
            query = """
            SELECT
                id,
                client_name,
                contact_email,
                core_data,
                custom_data,
                computed_metrics
            FROM clients
            ORDER BY RANDOM()
            LIMIT 200
            """

            result = await db.execute(text(query))
            rows = result.fetchall()

            if not rows:
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "quality_score": 0,
                        "message": "No data to evaluate"
                    }
                )

            columns = result.keys()
            clients = [dict(zip(columns, row)) for row in rows]

            # Calculate quality using Gemini
            quality_report = await self._calculate_quality_with_gemini(
                clients,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "overall_quality_score": quality_report["overall"],
                    "dimension_scores": quality_report["dimensions"],
                    "strengths": quality_report["strengths"],
                    "improvements_needed": quality_report["improvements"],
                    "sample_size": len(clients)
                },
                metadata={
                    "model_used": settings.gemini_flash_model,
                    "evaluation_type": "quality_scoring"
                }
            )

        except Exception as e:
            self.logger.error(
                "quality_scoring_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Quality scoring failed: {str(e)}"
            )

    def _calculate_completeness(
        self,
        clients: List[Dict[str, Any]],
        required_fields: List[str]
    ) -> Dict[str, Any]:
        """Calculate completeness scores"""
        field_scores = {}
        missing_count = 0

        for field in required_fields:
            complete = 0
            for client in clients:
                # Check if field exists and is not empty
                if field in ["client_name", "contact_email"]:
                    if client.get(field):
                        complete += 1
                else:
                    # Check in core_data or custom_data
                    core = client.get("core_data", {}) or {}
                    custom = client.get("custom_data", {}) or {}
                    if core.get(field) or custom.get(field):
                        complete += 1

            field_scores[field] = (complete / len(clients)) * 100 if clients else 0
            if field_scores[field] < 100:
                missing_count += 1

        overall_score = sum(field_scores.values()) / len(field_scores) if field_scores else 0

        recommendations = []
        for field, score in field_scores.items():
            if score < 80:
                recommendations.append(f"Improve {field} completeness (currently {score:.1f}%)")

        return {
            "overall_score": overall_score,
            "field_scores": field_scores,
            "missing_count": missing_count,
            "recommendations": recommendations
        }

    async def _assess_risk_with_gemini(
        self,
        clients: List[Dict[str, Any]],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Use Gemini to assess risk"""
        prompt = f"""Assess client risk levels based on this sample data.

Sample clients: {json.dumps(clients[:20], indent=2, default=str)}
Total clients: {len(clients)}

Provide risk assessment as JSON:
{{
  "distribution": {{"high": count, "medium": count, "low": count}},
  "high_risk": [list of high risk client descriptions],
  "factors": ["Risk factor 1", "Risk factor 2"]
}}
"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 1024}
            )

            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_flash_model,
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
            return {"distribution": {}, "high_risk": [], "factors": []}

    async def _evaluate_compliance_with_gemini(
        self,
        clients: List[Dict[str, Any]],
        rules: List[str],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Use Gemini to evaluate compliance"""
        prompt = f"""Evaluate compliance for these clients.

Compliance Rules: {json.dumps(rules)}
Sample Clients: {json.dumps(clients[:10], indent=2, default=str)}

Provide compliance report as JSON:
{{
  "score": 0-100,
  "compliant": count,
  "non_compliant": count,
  "issues": ["Issue 1", "Issue 2"]
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
                model_name=settings.gemini_flash_model,
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
            return {"score": 0, "compliant": 0, "non_compliant": 0, "issues": []}

    async def _calculate_quality_with_gemini(
        self,
        clients: List[Dict[str, Any]],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Use Gemini to calculate quality score"""
        prompt = f"""Calculate data quality score for these clients.

Sample Clients: {json.dumps(clients[:15], indent=2, default=str)}
Total Clients: {len(clients)}

Evaluate quality as JSON:
{{
  "overall": 0-100,
  "dimensions": {{"completeness": 0-100, "accuracy": 0-100, "consistency": 0-100}},
  "strengths": ["Strength 1", "Strength 2"],
  "improvements": ["Improvement 1", "Improvement 2"]
}}
"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 768}
            )

            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_flash_model,
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
            return {"overall": 0, "dimensions": {}, "strengths": [], "improvements": []}
