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

from app.database import get_db_session
from app.auth import get_current_user, User
from app.config import settings
from app.agents.base import AgentMessage
from app.agents.data_ingestion import DataIngestionAgent
from app.agents.data_discovery import DataDiscoveryAgent


logger = structlog.get_logger()
router = APIRouter(prefix="/api/uploads", tags=["uploads"])

# Initialize agents
data_ingestion = DataIngestionAgent()
data_discovery = DataDiscoveryAgent()

# Initialize storage client
storage_client = storage.Client(project=settings.google_cloud_project)


@router.post("/csv")
async def upload_csv(
    file: UploadFile = File(...),
    dataset_name: Optional[str] = Form(None),
    conversation_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
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
    user_id = current_user.user_id
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
            # Skip transparency events for direct uploads (no chat session)
            agent_message = AgentMessage(
                agent_type="data_ingestion",
                action="upload_csv",
                payload={
                    "file_path": temp_path,
                    "file_name": file.filename,
                    "dataset_name": dataset_name or file.filename,
                    "gcs_path": gcs_path,
                    "skip_transparency_events": True,  # No chat session for direct uploads
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

            # Chain: Trigger Discovery Agent to add semantic understanding
            # This is endpoint orchestration, not agent cross-awareness
            discovery_result = None
            if response.result.get("requires_metadata_refresh"):
                data_source_id = response.result.get("data_source_id")
                logger.info(
                    "triggering_discovery_agent",
                    data_source_id=data_source_id,
                )

                discovery_message = AgentMessage(
                    agent_type="data_discovery",
                    action="analyze",
                    payload={
                        "data_source_id": data_source_id,
                    },
                    conversation_id=conversation_id,
                )

                discovery_response = await data_discovery.execute(
                    discovery_message, db, user_id
                )

                if discovery_response.is_success:
                    discovery_result = discovery_response.result.get("semantic_profile")
                    logger.info(
                        "discovery_agent_completed",
                        entity_type=discovery_result.get("entity_type") if discovery_result else None,
                        domain=discovery_result.get("domain") if discovery_result else None,
                    )
                else:
                    logger.warning(
                        "discovery_agent_failed",
                        error=discovery_response.error,
                    )

            return {
                "status": "success",
                "message": "CSV file uploaded and processed successfully",
                "file_name": file.filename,
                "gcs_path": gcs_path,
                "result": response.result,
                "semantic_profile": discovery_result,
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get upload history for the current user
    """
    user_id = current_user.user_id
    try:
        from app.models import DataSource
        from sqlalchemy import select

        result = await db.execute(
            select(DataSource)
            .where(DataSource.user_id == user_id)
            .order_by(DataSource.uploaded_at.desc())
            .limit(50)
        )
        data_sources = result.scalars().all()

        return {
            "uploads": [
                {
                    "id": str(ds.id),
                    "source_type": ds.file_type or "csv",
                    "source_name": ds.file_name,
                    "file_name": ds.file_name,
                    "status": ds.status,
                    "records_ingested": ds.records_imported or 0,
                    "created_at": ds.uploaded_at.isoformat() if ds.uploaded_at else None,
                    "metadata": ds.meta_data,
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


@router.delete("/{data_source_id}")
async def delete_data_source(
    data_source_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Delete a data source and all associated client records

    This will:
    1. Verify the data source belongs to the user
    2. Delete all client records from this source
    3. Delete the data source record
    4. Remove the file from Cloud Storage
    """
    user_id = current_user.user_id
    try:
        from app.models import DataSource, Client
        from sqlalchemy import select, delete
        import uuid

        # Parse UUID
        try:
            ds_uuid = uuid.UUID(data_source_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid data source ID format"
            )

        # Get data source
        result = await db.execute(
            select(DataSource)
            .where(DataSource.id == ds_uuid)
            .where(DataSource.user_id == user_id)
        )
        data_source = result.scalar_one_or_none()

        if not data_source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data source not found or access denied"
            )

        logger.info(
            "deleting_data_source",
            data_source_id=data_source_id,
            user_id=user_id,
            file_name=data_source.file_name,
        )

        # Delete all client records from this source
        delete_result = await db.execute(
            delete(Client).where(Client.data_source_id == ds_uuid)
        )
        deleted_clients = delete_result.rowcount

        # Delete the data source
        await db.delete(data_source)
        await db.commit()

        # Try to delete from Cloud Storage (non-blocking)
        if data_source.gcs_path:
            try:
                bucket_name = settings.gcs_bucket_name
                blob_path = data_source.gcs_path.replace(f"gs://{bucket_name}/", "")
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_path)
                blob.delete()
                logger.info("gcs_file_deleted", gcs_path=data_source.gcs_path)
            except Exception as e:
                logger.warning("gcs_delete_failed", error=str(e), gcs_path=data_source.gcs_path)

        logger.info(
            "data_source_deleted",
            data_source_id=data_source_id,
            deleted_clients=deleted_clients,
        )

        return {
            "status": "success",
            "message": f"Data source deleted successfully",
            "deleted_clients": deleted_clients,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "delete_data_source_failed",
            error=str(e),
            data_source_id=data_source_id,
            user_id=user_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete data source: {str(e)}"
        )
