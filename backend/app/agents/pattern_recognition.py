"""
Pattern Recognition Agent
Identifies trends, anomalies, and patterns in data using Gemini Pro
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
from datetime import datetime

import vertexai
from vertexai.preview.generative_models import GenerativeModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus
from app.config import settings


class PatternRecognitionAgent(BaseAgent):
    """
    Pattern Recognition Agent - Identifies patterns and anomalies

    Capabilities:
    - Trend detection over time
    - Anomaly detection
    - Correlation analysis
    - Change point detection
    - Behavioral pattern identification

    Uses Gemini Pro for complex pattern analysis
    """

    def __init__(self):
        super().__init__(
            name="pattern_recognition",
            description="Identifies trends, anomalies, and patterns in data"
        )

        # Initialize Vertex AI
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )

        # Use Pro model for complex pattern analysis
        self.model = GenerativeModel(settings.gemini_pro_model)

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """
        Execute pattern recognition action

        Actions:
            - analyze_trends: Identify trends in data over time
            - detect_anomalies: Find unusual or outlier records
            - find_correlations: Discover correlations between variables
            - identify_patterns: General pattern identification
        """
        action = message.action
        payload = message.payload

        if action == "analyze_trends":
            return await self._analyze_trends(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "detect_anomalies":
            return await self._detect_anomalies(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "find_correlations":
            return await self._find_correlations(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "identify_patterns":
            return await self._identify_patterns(
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

    async def _analyze_trends(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Analyze trends in data over time
        """
        try:
            metric = payload.get("metric", "engagement")
            time_period = payload.get("time_period", "6_months")

            self.logger.info(
                "analyzing_trends",
                metric=metric,
                time_period=time_period
            )

            # Fetch time-series data
            data = await self._fetch_time_series_data(metric, time_period, db)

            if not data:
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "trends": [],
                        "message": "Insufficient data for trend analysis"
                    }
                )

            # Analyze trends using Gemini
            trends = await self._detect_trends_with_gemini(
                data,
                metric,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "metric": metric,
                    "time_period": time_period,
                    "trends": trends,
                    "data_points": len(data)
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "analysis_type": "trend_detection"
                }
            )

        except Exception as e:
            self.logger.error(
                "trend_analysis_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Trend analysis failed: {str(e)}"
            )

    async def _detect_anomalies(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Detect anomalies and outliers in data
        """
        try:
            field = payload.get("field", "aum")
            threshold = payload.get("threshold", 2.0)  # Standard deviations

            self.logger.info(
                "detecting_anomalies",
                field=field,
                threshold=threshold
            )

            # Fetch data and calculate statistics
            query = f"""
            SELECT
                id,
                client_name,
                (core_data->>'{field}')::numeric as value,
                core_data,
                custom_data
            FROM clients
            WHERE core_data->>'{field}' IS NOT NULL
              AND (core_data->>'{field}')::numeric > 0
            """

            result = await db.execute(text(query))
            rows = result.fetchall()

            if not rows or len(rows) < 10:
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "anomalies": [],
                        "message": "Insufficient data for anomaly detection"
                    }
                )

            columns = result.keys()
            data = [dict(zip(columns, row)) for row in rows]

            # Use Gemini to identify anomalies
            anomalies = await self._identify_anomalies_with_gemini(
                data,
                field,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "field": field,
                    "anomalies": anomalies,
                    "anomaly_count": len(anomalies),
                    "total_records": len(data)
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "analysis_type": "anomaly_detection"
                }
            )

        except Exception as e:
            self.logger.error(
                "anomaly_detection_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Anomaly detection failed: {str(e)}"
            )

    async def _find_correlations(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Find correlations between variables
        """
        try:
            fields = payload.get("fields", ["aum", "engagement_score", "risk_score"])

            self.logger.info(
                "finding_correlations",
                fields=fields
            )

            # Fetch multi-field data
            data = await self._fetch_multivariate_data(fields, db)

            if not data or len(data) < 30:
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "correlations": [],
                        "message": "Insufficient data for correlation analysis"
                    }
                )

            # Analyze correlations using Gemini
            correlations = await self._analyze_correlations_with_gemini(
                data,
                fields,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "fields": fields,
                    "correlations": correlations,
                    "sample_size": len(data)
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "analysis_type": "correlation_analysis"
                }
            )

        except Exception as e:
            self.logger.error(
                "correlation_analysis_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Correlation analysis failed: {str(e)}"
            )

    async def _identify_patterns(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        General pattern identification in dataset
        """
        try:
            dataset_summary = payload.get("dataset_summary", {})

            # Fetch sample data for analysis
            query = """
            SELECT
                client_name,
                core_data,
                custom_data,
                computed_metrics
            FROM clients
            ORDER BY RANDOM()
            LIMIT 100
            """

            result = await db.execute(text(query))
            rows = result.fetchall()

            if not rows:
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "patterns": [],
                        "message": "No data available for pattern analysis"
                    }
                )

            columns = result.keys()
            data = [dict(zip(columns, row)) for row in rows]

            # Use Gemini to identify patterns
            patterns = await self._detect_patterns_with_gemini(
                data,
                dataset_summary,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "patterns": patterns,
                    "sample_size": len(data)
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "analysis_type": "general_pattern_identification"
                }
            )

        except Exception as e:
            self.logger.error(
                "pattern_identification_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Pattern identification failed: {str(e)}"
            )

    async def _fetch_time_series_data(
        self,
        metric: str,
        time_period: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Fetch time-series data for trend analysis"""
        # Placeholder - would fetch actual time-series data
        return []

    async def _fetch_multivariate_data(
        self,
        fields: List[str],
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Fetch multi-field data for correlation analysis"""
        field_selects = [f"(core_data->>'{f}')::numeric as {f}" for f in fields]
        query = f"""
        SELECT
            id,
            client_name,
            {', '.join(field_selects)}
        FROM clients
        WHERE {' AND '.join([f"core_data->>'{f}' IS NOT NULL" for f in fields])}
        LIMIT 500
        """

        result = await db.execute(text(query))
        rows = result.fetchall()

        if rows:
            columns = result.keys()
            return [dict(zip(columns, row)) for row in rows]
        return []

    async def _detect_trends_with_gemini(
        self,
        data: List[Dict[str, Any]],
        metric: str,
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> List[Dict[str, str]]:
        """Use Gemini to detect trends"""
        prompt = f"""Analyze this time-series data for {metric} and identify trends.

Data summary: {len(data)} data points

Provide 2-3 key trends as JSON:
[
  {{"trend": "Description", "confidence": "high/medium/low"}},
  ...
]
"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 512}
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

            return json.loads(text.strip())
        except:
            return []

    async def _identify_anomalies_with_gemini(
        self,
        data: List[Dict[str, Any]],
        field: str,
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Use Gemini to identify anomalies"""
        # Calculate basic statistics
        values = [d["value"] for d in data if d["value"] is not None]
        avg = sum(values) / len(values) if values else 0
        sorted_vals = sorted(values)
        median = sorted_vals[len(sorted_vals) // 2] if sorted_vals else 0

        prompt = f"""Analyze this data for anomalies in {field}.

Statistics:
- Count: {len(values)}
- Average: {avg:.2f}
- Median: {median:.2f}
- Min: {min(values) if values else 0:.2f}
- Max: {max(values) if values else 0:.2f}

Top 10 values: {sorted_vals[-10:] if values else []}

Identify 3-5 potential anomalies and explain why as JSON:
[
  {{"type": "outlier/unusual_pattern", "description": "What's unusual", "severity": "high/medium/low"}},
  ...
]
"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 512}
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

    async def _analyze_correlations_with_gemini(
        self,
        data: List[Dict[str, Any]],
        fields: List[str],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> List[Dict[str, str]]:
        """Use Gemini to analyze correlations"""
        prompt = f"""Analyze correlations between these fields: {', '.join(fields)}

Sample data (first 10 records):
{json.dumps(data[:10], indent=2, default=str)}

Total records: {len(data)}

Identify 2-3 interesting correlations as JSON:
[
  {{"fields": ["field1", "field2"], "relationship": "positive/negative/non-linear", "insight": "What this means"}},
  ...
]
"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 512}
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

    async def _detect_patterns_with_gemini(
        self,
        data: List[Dict[str, Any]],
        dataset_summary: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> List[Dict[str, str]]:
        """Use Gemini to detect general patterns"""
        prompt = f"""Analyze this client dataset and identify interesting patterns.

Sample data (10 random clients):
{json.dumps(data[:10], indent=2, default=str)}

Total clients: {len(data)}

Identify 3-5 interesting patterns as JSON:
[
  {{"pattern": "Pattern description", "prevalence": "Percentage or count", "insight": "Why this matters"}},
  ...
]

Focus on actionable business insights."""

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
            return []
