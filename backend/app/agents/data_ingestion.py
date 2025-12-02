"""
Data Ingestion Agent

Processes external data files and loads records into the system.
Handles file parsing, type detection, field mapping inference, and database persistence.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
import numpy as np
import json
import uuid

import vertexai
from vertexai.preview.generative_models import GenerativeModel
from google.cloud import storage

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus, EventType, register_agent
from app.models import Client, DataSource
from app.config import settings


@register_agent
class DataIngestionAgent(BaseAgent):
    """
    Processes external data files and loads records into the system.
    Handles file parsing, type detection, field mapping inference, and database persistence.
    Returns ingestion results with record counts and mapping decisions.
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Agent metadata for orchestrator's dynamic routing."""
        return {
            "name": "data_ingestion",
            "description": "Processes external data files and loads records into the system",
            "capabilities": [
                "Process structured data files and persist records to database",
                "Detect data types for each column (numeric, date, boolean, text)",
                "Infer field mappings between source columns and system entities",
                "Track ingestion status and report results"
            ],
            "inputs": {
                "file_path": "Path to uploaded file",
                "file_name": "Original filename",
                "dataset_name": "User-provided name for this data source"
            },
            "outputs": {
                "data_source_id": "ID of created data source record",
                "records_ingested": "Count of successfully imported records",
                "detected_types": "Column type detection results",
                "field_mappings": "Column-to-field mapping decisions",
                "requires_metadata_refresh": "Signal for post-ingestion processing"
            }
        }

    def _get_internal_capabilities(self) -> Dict[str, str]:
        """Internal capability descriptions for LLM task interpretation."""
        return {
            "process_file": "Process and import data from an uploaded file",
            "connect_service": "Establish connection to external data service (future)",
            "sync_source": "Synchronize data from connected source (future)"
        }

    def __init__(self):
        super().__init__()
        vertexai.init(project=settings.google_cloud_project, location=settings.vertex_ai_location)
        self.model = GenerativeModel(settings.gemini_flash_model)
        self.storage_client = storage.Client(project=settings.google_cloud_project)

    async def _execute_internal(self, message: AgentMessage, db: AsyncSession, user_id: str) -> AgentResponse:
        """Execute data ingestion task using LLM-driven interpretation."""
        task = message.action
        payload = message.payload
        conversation_id = message.conversation_id
        start_time = datetime.utcnow()

        # Skip transparency events for direct uploads (no chat session)
        skip_events = payload.get("skip_transparency_events", False)

        async def maybe_emit_event(**kwargs):
            """Only emit event if we have a valid chat session."""
            if not skip_events:
                await self.emit_event(**kwargs)

        try:
            await maybe_emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.RECEIVED, title=f"Received: {task[:50]}...",
                details={"task": task}, step_number=1)

            await maybe_emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.THINKING, title="Analyzing ingestion requirements...",
                details={"capabilities": list(self._get_internal_capabilities().keys())}, step_number=2)

            capability, params = await self._interpret_task(task, payload, conversation_id, user_id, db)

            await maybe_emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.DECISION, title=f"Using '{capability}' capability",
                details={"capability": capability}, step_number=3)

            await maybe_emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.ACTION, title=f"Executing {capability}...",
                details={}, step_number=4)

            result = await self._execute_capability(capability, params, conversation_id, user_id, db)
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            records = result.get("records_ingested", 0)
            await maybe_emit_event(db=db, session_id=conversation_id, user_id=user_id,
                event_type=EventType.RESULT, title=f"Ingested {records} records",
                details={"records": records}, step_number=5, duration_ms=duration_ms)

            return AgentResponse(status=AgentStatus.COMPLETED, result=result,
                metadata={"model_used": settings.gemini_flash_model, "duration_ms": duration_ms})

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            if not skip_events:
                try:
                    await self.emit_event(db=db, session_id=conversation_id, user_id=user_id,
                        event_type=EventType.ERROR, title=f"Ingestion failed: {str(e)[:40]}",
                        details={"error": str(e)}, step_number=5, duration_ms=duration_ms)
                except Exception:
                    pass  # Don't fail on event emit error
            return AgentResponse(status=AgentStatus.FAILED, error=f"Data ingestion failed: {str(e)}")

    async def _interpret_task(self, task: str, payload: Dict, conversation_id: str, user_id: str, db: AsyncSession):
        """LLM decides which capability to use."""
        # For data ingestion, we often have explicit file_path in payload
        if payload.get("file_path"):
            return "process_file", payload

        caps = "\n".join([f"- {k}: {v}" for k, v in self._get_internal_capabilities().items()])
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
            return result.get("capability", "process_file"), params
        except:
            return "process_file", payload

    async def _execute_capability(self, capability: str, params: Dict, conversation_id: str, user_id: str, db: AsyncSession):
        """Execute the chosen capability."""
        if capability == "process_file":
            return await self._process_file(conversation_id, user_id, params, db)
        elif capability == "connect_service":
            return await self._connect_service(conversation_id, user_id, params, db)
        elif capability == "sync_source":
            return await self._sync_source(conversation_id, user_id, params, db)
        # Default to process_file
        return await self._process_file(conversation_id, user_id, params, db)

    async def _process_file(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Process uploaded file with type detection and field mapping."""
        file_path = payload.get("file_path")
        file_name = payload.get("file_name", "upload.csv")
        dataset_name = payload.get("dataset_name", "Data Upload")

        if not file_path:
            return {"error": "Missing file_path", "records_ingested": 0}

        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            return {"error": f"Failed to read file: {str(e)}", "records_ingested": 0}

        if df.empty:
            return {"error": "File is empty", "records_ingested": 0}

        # Step 1: Detect column types programmatically
        detected_types = self._detect_column_types(df)

        # Step 2: Analyze schema and get field mappings (LLM)
        schema_analysis = await self._analyze_schema(df, detected_types)
        field_mappings = schema_analysis.get("mappings", {})

        # Step 3: Create data source record with full schema info
        data_source = DataSource(
            user_id=user_id,
            file_type="csv",
            file_name=file_name,
            gcs_path=payload.get("gcs_path", ""),
            status="processing",
            meta_data={
                "dataset_name": dataset_name,
                "rows": len(df),
                "columns": list(df.columns),
                "detected_types": detected_types,
                "field_mappings": field_mappings,
            }
        )
        db.add(data_source)
        await db.flush()

        # Step 4: Ingest rows with type-aware transformation
        ingested_count = 0
        failed_rows = []

        for idx, row in df.iterrows():
            try:
                client_data = self._transform_row(row, field_mappings, detected_types)
                client = Client(
                    user_id=user_id,
                    source_type="csv",
                    source_id=f"csv_{data_source.id}_{idx}",
                    data_source_id=data_source.id,
                    client_name=client_data.get("client_name"),
                    contact_email=client_data.get("contact_email"),
                    company_name=client_data.get("company_name"),
                    core_data=client_data.get("core_data", {}),
                    custom_data=client_data.get("custom_data", {}),
                )
                db.add(client)
                ingested_count += 1
            except Exception as e:
                failed_rows.append({"row": idx, "error": str(e)})

        data_source.status = "completed"
        data_source.records_imported = ingested_count
        data_source.processed_at = datetime.utcnow()
        await db.commit()

        return {
            "data_source_id": str(data_source.id),
            "records_ingested": ingested_count,
            "records_failed": len(failed_rows),
            "total_rows": len(df),
            "columns": list(df.columns),
            "detected_types": detected_types,
            "field_mappings": field_mappings,
            "requires_metadata_refresh": True,  # Signal for caller to trigger discovery
        }

    def _detect_column_types(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """
        Detect data types for each column using pandas + heuristics.
        Returns type info for proper JSONB storage.
        """
        detected_types = {}

        for col in df.columns:
            col_data = df[col].dropna()
            if col_data.empty:
                detected_types[col] = {"type": "text", "nullable": True}
                continue

            nullable = df[col].isna().any()
            sample_values = col_data.head(5).tolist()

            # Try numeric detection
            try:
                numeric_col = pd.to_numeric(col_data, errors='raise')
                # Check if integer or float
                if (numeric_col == numeric_col.astype(int)).all():
                    detected_types[col] = {
                        "type": "int",
                        "nullable": nullable,
                        "sample_values": [int(v) for v in sample_values[:3]]
                    }
                else:
                    detected_types[col] = {
                        "type": "float",
                        "nullable": nullable,
                        "sample_values": [float(v) for v in sample_values[:3]]
                    }
                continue
            except (ValueError, TypeError):
                pass

            # Try date detection
            try:
                pd.to_datetime(col_data, errors='raise', infer_datetime_format=True)
                detected_types[col] = {
                    "type": "date",
                    "nullable": nullable,
                    "sample_values": [str(v) for v in sample_values[:3]]
                }
                continue
            except (ValueError, TypeError):
                pass

            # Try boolean detection
            bool_values = {'true', 'false', 'yes', 'no', '1', '0', 't', 'f', 'y', 'n'}
            str_values = col_data.astype(str).str.lower().unique()
            if set(str_values).issubset(bool_values):
                detected_types[col] = {
                    "type": "bool",
                    "nullable": nullable,
                    "sample_values": [str(v) for v in sample_values[:3]]
                }
                continue

            # Default to text
            detected_types[col] = {
                "type": "text",
                "nullable": nullable,
                "sample_values": [str(v) for v in sample_values[:3]]
            }

        return detected_types

    def _cast_value(self, value: Any, detected_type: str) -> Any:
        """Cast value to detected type for proper JSONB storage."""
        if pd.isna(value) or value is None:
            return None

        if detected_type == "int":
            try:
                return int(float(value))
            except (ValueError, TypeError):
                return None

        if detected_type == "float":
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        if detected_type == "date":
            try:
                return pd.to_datetime(value).isoformat()
            except (ValueError, TypeError):
                return str(value)

        if detected_type == "bool":
            str_val = str(value).lower()
            return str_val in ('true', 'yes', '1', 't', 'y')

        # Default: text
        return str(value)

    async def _analyze_schema(self, df: pd.DataFrame, detected_types: Dict) -> Dict:
        """
        LLM analyzes schema with type context for field mapping.
        """
        sample = df.head(5).to_dict('records')

        # Build type summary for prompt
        type_summary = {col: info["type"] for col, info in detected_types.items()}

        prompt = f"""Analyze this data schema and map columns to standard fields.

COLUMNS: {list(df.columns)}
DETECTED TYPES: {json.dumps(type_summary)}
SAMPLE DATA: {json.dumps(sample, default=str)}

Map each column to one of:
- client_name (text field for entity name)
- contact_email (text field for email)
- company_name (text field for company/organization)
- core_data.<field_name> (for important business fields)
- custom_data.<field_name> (for other fields)

Return JSON:
{{
  "mappings": {{
    "column_name": {{"target": "client_name|contact_email|company_name|core_data.X|custom_data.X", "confidence": 0.0-1.0}}
  }}
}}"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.2}
            )
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception:
            # Fallback: map all to custom_data
            return {
                "mappings": {
                    col: {"target": f"custom_data.{col}", "confidence": 0.5}
                    for col in df.columns
                }
            }

    def _transform_row(self, row: pd.Series, field_mappings: Dict, detected_types: Dict) -> Dict:
        """Transform row using field mappings with type-aware casting."""
        result = {"core_data": {}, "custom_data": {}}

        for col, val in row.items():
            mapping = field_mappings.get(col, {})
            target = mapping.get("target", f"custom_data.{col}")
            col_type = detected_types.get(col, {}).get("type", "text")

            # Cast value to proper type
            typed_val = self._cast_value(val, col_type)
            if typed_val is None:
                continue

            # Route to appropriate field
            if target == "client_name":
                result["client_name"] = str(typed_val)
            elif target == "contact_email":
                result["contact_email"] = str(typed_val)
            elif target == "company_name":
                result["company_name"] = str(typed_val)
            elif target.startswith("core_data."):
                field_name = target[10:]  # Remove "core_data." prefix
                result["core_data"][field_name] = typed_val
            elif target.startswith("custom_data."):
                field_name = target[12:]  # Remove "custom_data." prefix
                result["custom_data"][field_name] = typed_val
            else:
                # Default to custom_data
                result["custom_data"][col] = typed_val

        return result

    async def _connect_service(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Establish connection to external data service (future implementation)."""
        return {
            "message": "External service connections will be available in a future release",
            "status": "pending_implementation",
            "records_ingested": 0,
            "requires_metadata_refresh": False,
        }

    async def _sync_source(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Synchronize data from connected source (future implementation)."""
        return {
            "message": "Data synchronization will be available in a future release",
            "status": "pending_implementation",
            "records_ingested": 0,
            "requires_metadata_refresh": False,
        }
