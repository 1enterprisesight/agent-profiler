"""
Data Ingestion Agent - Phase D: Self-Describing
Handles CSV uploads, CRM connections, and data synchronization.
Follows the segmentation.py template pattern.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
import json
import uuid

import vertexai
from vertexai.preview.generative_models import GenerativeModel
from google.cloud import storage

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus, EventType
from app.models import Client, DataSource
from app.config import settings


class DataIngestionAgent(BaseAgent):
    """
    Data Ingestion Agent - Phase D: Self-Describing

    Handles data imports with complete transparency.
    Uses LLM to interpret tasks - NO hardcoded action routing.
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Agent describes itself for dynamic discovery by orchestrator."""
        return {
            "name": "data_ingestion",
            "purpose": "Import and process data from CSV files and CRM connections",
            "when_to_use": [
                "User wants to upload or import data",
                "User mentions CSV files or spreadsheets",
                "User wants to connect to a CRM like Salesforce",
                "User needs to sync data from external source",
                "User uses words like 'upload', 'import', 'connect', 'sync'"
            ],
            "when_not_to_use": [
                "User wants to query or analyze existing data",
                "User wants to search or filter data",
                "User needs calculations or aggregations"
            ],
            "example_tasks": [
                "Upload this CSV file",
                "Import my client data",
                "Connect to Salesforce",
                "Sync data from my CRM"
            ],
            "data_source_aware": True
        }

    def get_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Agent's internal capabilities for LLM-driven task routing."""
        return {
            "upload_csv": {
                "description": "Process and import data from uploaded CSV file",
                "examples": ["upload", "csv", "spreadsheet", "file", "import csv"],
                "method": "_upload_csv"
            },
            "connect_crm": {
                "description": "Connect to a CRM system like Salesforce or Wealthbox",
                "examples": ["connect", "salesforce", "crm", "wealthbox", "integration"],
                "method": "_connect_crm"
            },
            "sync_data": {
                "description": "Synchronize data from connected sources",
                "examples": ["sync", "refresh", "update", "pull"],
                "method": "_sync_data"
            },
            "map_fields": {
                "description": "Create or update field mappings between source and system",
                "examples": ["map", "fields", "mapping", "schema"],
                "method": "_map_fields"
            }
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
                details={"capabilities": list(self.get_capabilities().keys())}, step_number=2)

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

            # Trigger metadata computation for data discovery
            try:
                await self._trigger_metadata_computation(db, user_id)
            except Exception as e:
                self.logger.warning("metadata_computation_failed", error=str(e))

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
            return "upload_csv", payload

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
            return result.get("capability", "upload_csv"), params
        except:
            return "upload_csv", payload

    async def _execute_capability(self, capability: str, params: Dict, conversation_id: str, user_id: str, db: AsyncSession):
        """Execute the chosen capability."""
        if capability == "upload_csv":
            return await self._upload_csv(conversation_id, user_id, params, db)
        elif capability == "connect_crm":
            return await self._connect_crm(conversation_id, user_id, params, db)
        elif capability == "sync_data":
            return await self._sync_data(conversation_id, user_id, params, db)
        return await self._map_fields(conversation_id, user_id, params, db)

    async def _upload_csv(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Process uploaded CSV file."""
        file_path = payload.get("file_path")
        file_name = payload.get("file_name", "upload.csv")
        dataset_name = payload.get("dataset_name", "CSV Upload")

        if not file_path:
            return {"error": "Missing file_path", "records_ingested": 0}

        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            return {"error": f"Failed to read CSV: {str(e)}", "records_ingested": 0}

        if df.empty:
            return {"error": "CSV file is empty", "records_ingested": 0}

        # Create data source record
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
            }
        )
        db.add(data_source)
        await db.flush()

        # Analyze schema
        field_mappings = await self._analyze_csv_schema(df, conversation_id, user_id, db)

        # Ingest rows
        ingested_count = 0
        failed_rows = []

        for idx, row in df.iterrows():
            try:
                client_data = self._transform_row(row, field_mappings)
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
            "field_mappings": field_mappings,
        }

    async def _analyze_csv_schema(self, df: pd.DataFrame, conversation_id: str, user_id: str, db: AsyncSession):
        """Analyze CSV and create field mappings."""
        sample = df.head(5).to_dict('records')

        prompt = f"""Map CSV columns to standard fields.
Columns: {list(df.columns)}
Sample: {json.dumps(sample, default=str)}

Map to: client_name, contact_email, company_name, or custom_*
Return JSON: {{"mappings": {{"csv_col": {{"target_field": "field", "confidence": 0.9}}}}}}"""

        try:
            response = await self.model.generate_content_async(prompt, generation_config={"temperature": 0.2})
            text = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except:
            return {"mappings": {col: {"target_field": f"custom_{col}", "confidence": 0.5} for col in df.columns}}

    def _transform_row(self, row: pd.Series, field_mappings: Dict) -> Dict:
        """Transform row using field mappings."""
        result = {"core_data": {}, "custom_data": {}}
        mappings = field_mappings.get("mappings", {})

        for col, val in row.items():
            if pd.isna(val):
                continue
            mapping = mappings.get(col, {})
            target = mapping.get("target_field", f"custom_{col}")

            if target == "client_name":
                result["client_name"] = val
            elif target == "contact_email":
                result["contact_email"] = val
            elif target == "company_name":
                result["company_name"] = val
            elif target.startswith("custom_"):
                result["custom_data"][target[7:]] = val
            else:
                result["core_data"][target] = val

        return result

    async def _connect_crm(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Connect to CRM (placeholder)."""
        return {
            "message": "CRM connector will be available in Phase 3",
            "status": "pending_implementation",
            "records_ingested": 0
        }

    async def _sync_data(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Sync data from connected sources (placeholder)."""
        return {
            "message": "Data sync will be available in Phase 3",
            "status": "pending_implementation",
            "records_ingested": 0
        }

    async def _map_fields(self, conversation_id: str, user_id: str, payload: Dict, db: AsyncSession):
        """Create field mappings (placeholder)."""
        return {
            "message": "Field mapping UI will be available in Phase 3",
            "status": "pending_implementation",
            "records_ingested": 0
        }

    async def _trigger_metadata_computation(self, db: AsyncSession, user_id: str):
        """
        Trigger metadata computation after successful data ingestion.
        This populates the data_metadata table for the DataDiscoveryAgent.
        """
        from app.agents.data_discovery import DataDiscoveryAgent

        discovery_agent = DataDiscoveryAgent()
        await discovery_agent._compute_metadata(db, user_id)
        self.logger.info("metadata_computed_after_ingestion", user_id=user_id)
