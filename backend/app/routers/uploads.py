"""
File Upload API Endpoints
Handles CSV file uploads for data ingestion
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import tempfile
import os
from pathlib import Path

import structlog
from google.cloud import storage

from app.database import get_db
from app.auth import get_current_user
from app.config import settings
from app.agents.base import AgentMessage
from app.agents.data_ingestion import DataIngestionAgent


logger = structlog.get_logger()
router = APIRouter(prefix="/api/uploads", tags=["uploads"])

# Initialize agent
data_ingestion = DataIngestionAgent()

# Initialize storage client
storage_client = storage.Client(project=settings.google_cloud_project)


@router.post("/csv")
async def upload_csv(
    file: UploadFile = File(...),
    dataset_name: Optional[str] = Form(None),
    conversation_id: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload CSV file for data ingestion

    The file will be:
    1. Validated
    2. Uploaded to Cloud Storage
    3. Processed by Data Ingestion Agent
    4. Schema analyzed using Gemini
    5. Data imported into PostgreSQL
    """
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only CSV files are supported"
            )

        logger.info(
            "csv_upload_started",
            filename=file.filename,
            user_id=user_id,
        )

        # Read file content
        content = await file.read()

        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )

        # Save to temporary file for processing
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.csv') as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            # Upload to Cloud Storage for archival
            bucket = storage_client.bucket(settings.gcs_bucket_name)
            blob_name = f"uploads/{user_id}/{file.filename}"
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(temp_path)

            gcs_path = f"gs://{settings.gcs_bucket_name}/{blob_name}"

            logger.info(
                "csv_uploaded_to_gcs",
                gcs_path=gcs_path,
                size_bytes=len(content),
            )

            # Process with Data Ingestion Agent
            agent_message = AgentMessage(
                agent_type="data_ingestion",
                action="upload_csv",
                payload={
                    "file_path": temp_path,
                    "file_name": file.filename,
                    "dataset_name": dataset_name or file.filename,
                    "gcs_path": gcs_path,
                },
                conversation_id=conversation_id,
            )

            response = await data_ingestion.execute(agent_message, db, user_id)

            if not response.is_success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Data ingestion failed: {response.error}"
                )

            logger.info(
                "csv_processing_completed",
                records_ingested=response.result.get("records_ingested"),
                filename=file.filename,
            )

            return {
                "status": "success",
                "message": "CSV file uploaded and processed successfully",
                "file_name": file.filename,
                "gcs_path": gcs_path,
                "result": response.result,
            }

        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning("failed_to_delete_temp_file", error=str(e))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "csv_upload_failed",
            error=str(e),
            filename=file.filename if file else None,
            user_id=user_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CSV upload failed: {str(e)}"
        )


@router.get("/history")
async def get_upload_history(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get upload history for the current user
    """
    try:
        from app.models import DataSource
        from sqlalchemy import select

        result = await db.execute(
            select(DataSource)
            .where(DataSource.user_id == user_id)
            .order_by(DataSource.created_at.desc())
            .limit(50)
        )
        data_sources = result.scalars().all()

        return {
            "uploads": [
                {
                    "id": str(ds.id),
                    "source_type": ds.source_type,
                    "source_name": ds.source_name,
                    "file_name": ds.file_name,
                    "status": ds.status,
                    "records_ingested": ds.records_ingested,
                    "created_at": ds.created_at.isoformat(),
                    "metadata": ds.metadata,
                }
                for ds in data_sources
            ]
        }

    except Exception as e:
        logger.error(
            "get_upload_history_failed",
            error=str(e),
            user_id=user_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get upload history: {str(e)}"
        )
