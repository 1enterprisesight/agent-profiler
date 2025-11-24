"""
Data Ingestion Agent
Handles CSV uploads, CRM connections, schema discovery, and data synchronization
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import pandas as pd
import json
from datetime import datetime
import uuid

import vertexai
from vertexai.preview.generative_models import GenerativeModel
from google.cloud import storage

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus
from app.models import (
    Client,
    DataSource,
    CRMConnection,
    CRMSchema,
    FieldMapping,
    DataTransformationLog,
)
from app.config import settings


class DataIngestionAgent(BaseAgent):
    """
    Data Ingestion Agent - Handles all data input operations
    Uses Gemini Flash for schema mapping and data transformation
    """

    def __init__(self):
        super().__init__(
            name="data_ingestion",
            description="Handles CSV uploads, CRM connections, and data synchronization"
        )

        # Initialize Vertex AI
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )

        self.model = GenerativeModel(settings.gemini_flash_model)
        self.storage_client = storage.Client(project=settings.google_cloud_project)

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """
        Execute data ingestion actions

        Actions:
            - upload_csv: Process uploaded CSV file
            - connect_salesforce: Set up Salesforce connection
            - discover_schema: Discover CRM schema
            - sync_data: Sync data from CRM
            - map_fields: Create intelligent field mappings
        """
        action = message.action
        payload = message.payload

        if action == "upload_csv":
            return await self._upload_csv(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "connect_salesforce":
            return await self._connect_salesforce(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "discover_schema":
            return await self._discover_schema(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "map_fields":
            return await self._map_fields(
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

    async def _upload_csv(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Process uploaded CSV file

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            payload: Contains file_path, file_name, dataset_name
            db: Database session

        Returns:
            AgentResponse with ingestion results
        """
        try:
            file_path = payload.get("file_path")
            file_name = payload.get("file_name")
            dataset_name = payload.get("dataset_name", "CSV Upload")

            if not file_path:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error="Missing file_path in payload"
                )

            self.logger.info(
                "processing_csv",
                file_name=file_name,
                conversation_id=conversation_id,
            )

            # Read CSV file
            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error=f"Failed to read CSV: {str(e)}"
                )

            # Validate CSV has data
            if df.empty:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error="CSV file is empty"
                )

            # Create data source record
            data_source = DataSource(
                user_id=user_id,
                source_type="csv",
                source_name=dataset_name,
                file_name=file_name,
                file_path=file_path,
                status="processing",
                metadata={
                    "rows": len(df),
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                }
            )
            db.add(data_source)
            await db.flush()

            # Discover schema and map fields using Gemini
            field_mappings = await self._analyze_csv_schema(
                conversation_id,
                user_id,
                df,
                db
            )

            # Transform and ingest data
            ingested_count = 0
            failed_rows = []

            for idx, row in df.iterrows():
                try:
                    client_data = await self._transform_row(
                        row,
                        field_mappings,
                        conversation_id,
                        user_id,
                        db
                    )

                    # Create client record
                    client = Client(
                        source_type="csv",
                        source_id=f"csv_{data_source.id}_{idx}",
                        data_source_id=data_source.id,
                        user_id=user_id,
                        client_name=client_data.get("client_name"),
                        contact_email=client_data.get("contact_email"),
                        company_name=client_data.get("company_name"),
                        core_data=client_data.get("core_data", {}),
                        custom_data=client_data.get("custom_data", {}),
                        tags=client_data.get("tags", []),
                    )
                    db.add(client)
                    ingested_count += 1

                except Exception as e:
                    self.logger.warning(
                        "failed_to_ingest_row",
                        row_index=idx,
                        error=str(e),
                    )
                    failed_rows.append({"row": idx, "error": str(e)})

            # Update data source status
            data_source.status = "completed"
            data_source.records_ingested = ingested_count
            await db.commit()

            self.logger.info(
                "csv_ingestion_completed",
                ingested=ingested_count,
                failed=len(failed_rows),
                conversation_id=conversation_id,
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "data_source_id": str(data_source.id),
                    "records_ingested": ingested_count,
                    "records_failed": len(failed_rows),
                    "total_rows": len(df),
                    "columns": list(df.columns),
                    "field_mappings": field_mappings,
                    "failed_rows": failed_rows[:10],  # First 10 failures
                },
                metadata={
                    "file_name": file_name,
                    "dataset_name": dataset_name,
                }
            )

        except Exception as e:
            self.logger.error(
                "csv_upload_failed",
                error=str(e),
                conversation_id=conversation_id,
                exc_info=True,
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"CSV upload failed: {str(e)}"
            )

    async def _analyze_csv_schema(
        self,
        conversation_id: str,
        user_id: str,
        df: pd.DataFrame,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Use Gemini to analyze CSV schema and create intelligent field mappings

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            df: DataFrame
            db: Database session

        Returns:
            Field mapping dictionary
        """
        try:
            # Get sample data (first 5 rows)
            sample_data = df.head(5).to_dict('records')

            # Build prompt for Gemini
            prompt = f"""Analyze this CSV data and create intelligent field mappings for a client database.

CSV Columns: {list(df.columns)}

Sample Data (first 5 rows):
{json.dumps(sample_data, indent=2, default=str)}

Map the CSV columns to these standard fields:
- client_name: Full name of client/contact
- contact_email: Email address
- contact_phone: Phone number
- company_name: Company/organization name
- address_*: Address fields (street, city, state, zip)
- financial_*: Financial data fields
- custom_*: Any custom/unmapped fields

Respond ONLY with valid JSON in this format:
{{
  "mappings": {{
    "csv_column_name": {{
      "target_field": "standard_field_name",
      "confidence": 0.95,
      "transformation": "lowercase|uppercase|trim|none"
    }}
  }},
  "unmapped_columns": ["column1", "column2"],
  "data_quality": {{
    "completeness": 0.85,
    "issues": ["description of any data quality issues"]
  }}
}}"""

            # Call Gemini
            response = await self.model.generate_content_async(
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "max_output_tokens": 2048,
                }
            )

            # Log LLM conversation
            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_flash_model,
                prompt=prompt,
                response=response.text,
            )

            # Parse response
            mapping = self._parse_mapping_response(response.text)

            return mapping

        except Exception as e:
            self.logger.error(
                "schema_analysis_failed",
                error=str(e),
                exc_info=True,
            )
            # Return default mapping if Gemini fails
            return {
                "mappings": {col: {"target_field": f"custom_{col}", "confidence": 0.5, "transformation": "none"} for col in df.columns},
                "unmapped_columns": [],
                "data_quality": {"completeness": 1.0, "issues": []}
            }

    def _parse_mapping_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from Gemini"""
        try:
            # Clean response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            return json.loads(response)
        except json.JSONDecodeError as e:
            self.logger.error(
                "failed_to_parse_mapping_response",
                error=str(e),
                response=response,
            )
            return {
                "mappings": {},
                "unmapped_columns": [],
                "data_quality": {"completeness": 0.5, "issues": ["Failed to parse mapping"]}
            }

    async def _transform_row(
        self,
        row: pd.Series,
        field_mappings: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Transform a single row using field mappings

        Args:
            row: DataFrame row
            field_mappings: Field mapping dictionary
            conversation_id: Conversation ID
            user_id: User ID
            db: Database session

        Returns:
            Transformed client data dictionary
        """
        result = {
            "core_data": {},
            "custom_data": {},
        }

        mappings = field_mappings.get("mappings", {})

        for col_name, col_value in row.items():
            # Skip null values
            if pd.isna(col_value):
                continue

            mapping = mappings.get(col_name, {})
            target_field = mapping.get("target_field", f"custom_{col_name}")
            transformation = mapping.get("transformation", "none")

            # Apply transformation
            transformed_value = self._apply_transformation(col_value, transformation)

            # Map to standard fields or custom data
            if target_field == "client_name":
                result["client_name"] = transformed_value
            elif target_field == "contact_email":
                result["contact_email"] = transformed_value
            elif target_field == "company_name":
                result["company_name"] = transformed_value
            elif target_field.startswith("custom_"):
                result["custom_data"][target_field[7:]] = transformed_value
            else:
                result["core_data"][target_field] = transformed_value

        return result

    def _apply_transformation(self, value: Any, transformation: str) -> Any:
        """Apply transformation to a value"""
        if transformation == "lowercase" and isinstance(value, str):
            return value.lower()
        elif transformation == "uppercase" and isinstance(value, str):
            return value.upper()
        elif transformation == "trim" and isinstance(value, str):
            return value.strip()
        else:
            return value

    async def _connect_salesforce(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Set up Salesforce connection (placeholder for Phase 3)

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            payload: Contains instance_url, client_id, client_secret
            db: Database session

        Returns:
            AgentResponse
        """
        # Placeholder - will be implemented in Phase 3
        return AgentResponse(
            status=AgentStatus.COMPLETED,
            result={
                "message": "Salesforce connector will be available in Phase 3",
                "status": "pending_implementation"
            }
        )

    async def _discover_schema(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Discover CRM schema (placeholder for Phase 3)
        """
        return AgentResponse(
            status=AgentStatus.COMPLETED,
            result={
                "message": "Schema discovery will be available in Phase 3",
                "status": "pending_implementation"
            }
        )

    async def _map_fields(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Create field mappings (placeholder for Phase 3)
        """
        return AgentResponse(
            status=AgentStatus.COMPLETED,
            result={
                "message": "Field mapping will be available in Phase 3",
                "status": "pending_implementation"
            }
        )
