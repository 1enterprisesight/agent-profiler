"""
SSE Streaming API Endpoints
Real-time streaming of agent transparency events
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Set, Optional
import asyncio
import json
import uuid
from datetime import datetime

import structlog

from app.database import get_db_session, async_session_factory
from app.auth import User, get_user_from_token, get_current_user
from app.models import Conversation, TransparencyEvent, ConversationMessage


logger = structlog.get_logger()
router = APIRouter(prefix="/api/stream", tags=["streaming"])


async def get_new_events(
    db: AsyncSession,
    conversation_id: str,
    user_id: str,
    seen_event_ids: Set[str],
    after_timestamp=None
) -> list:
    """
    Fetch transparency events not yet seen by the client.

    If after_timestamp is provided, only fetches events created after that time
    (used for multi-query conversations to only show current query's events).
    """
    try:
        conditions = [
            TransparencyEvent.session_id == uuid.UUID(conversation_id),
            TransparencyEvent.user_id == user_id
        ]

        # Only get events after the user message timestamp
        if after_timestamp:
            conditions.append(TransparencyEvent.created_at > after_timestamp)

        query = select(TransparencyEvent).where(
            and_(*conditions)
        ).order_by(TransparencyEvent.created_at)

        result = await db.execute(query)
        events = result.scalars().all()

        # Filter to only new events
        new_events = [e for e in events if str(e.id) not in seen_event_ids]

        return new_events

    except Exception as e:
        logger.error("get_new_events_failed", error=str(e))
        return []


def event_to_dict(event: TransparencyEvent) -> dict:
    """Convert TransparencyEvent to dict for JSON serialization."""
    return {
        "id": str(event.id),
        "session_id": str(event.session_id),
        "agent_name": event.agent_name,
        "event_type": event.event_type,
        "title": event.title,
        "details": event.details or {},
        "step_number": event.step_number,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "duration_ms": event.duration_ms,
    }


def is_workflow_complete(events: list) -> bool:
    """
    Check if the workflow is complete based on events.
    Complete when we see a final 'result' or 'error' event from orchestrator.
    """
    for event in events:
        if event.agent_name == "orchestrator":
            if event.event_type in ("result", "error"):
                # Any result/error event from orchestrator with step_number > 0 is final
                # (removed overly strict "complete" title requirement)
                if event.step_number and event.step_number > 0:
                    return True
    return False


async def check_conversation_has_response(
    db: AsyncSession,
    conversation_id: str,
    after_message_id: Optional[str] = None
) -> dict:
    """
    Check if the conversation has an assistant response (meaning workflow is done).
    Returns the response if found.

    If after_message_id is provided, only looks for assistant messages that were
    created after that user message (for multi-query conversations).
    """
    try:
        # If we have a specific user message to track, find its timestamp first
        after_timestamp = None
        if after_message_id:
            user_msg_query = select(ConversationMessage).where(
                ConversationMessage.id == uuid.UUID(after_message_id)
            )
            user_msg_result = await db.execute(user_msg_query)
            user_msg = user_msg_result.scalar_one_or_none()
            if user_msg:
                after_timestamp = user_msg.created_at

        # Build query for assistant response
        conditions = [
            ConversationMessage.session_id == uuid.UUID(conversation_id),
            ConversationMessage.role == "assistant"
        ]

        # Only look for responses after the tracked user message
        if after_timestamp:
            conditions.append(ConversationMessage.created_at > after_timestamp)

        query = select(ConversationMessage).where(
            and_(*conditions)
        ).order_by(ConversationMessage.created_at.desc()).limit(1)

        result = await db.execute(query)
        message = result.scalar_one_or_none()

        if message:
            return {
                "complete": True,
                "message_id": str(message.id),
                "content": message.content,
                "metadata": message.meta_data,
            }
        return {"complete": False}

    except Exception as e:
        logger.error("check_conversation_response_failed", error=str(e))
        return {"complete": False}


@router.get("/events/{conversation_id}")
async def stream_events(
    conversation_id: str,
    token: Optional[str] = Query(None, description="JWT token for SSE auth"),
    message_id: Optional[str] = Query(None, description="User message ID to track (for multi-query conversations)"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Stream transparency events for a conversation in real-time using SSE.

    The client should connect to this endpoint after calling /chat/start
    to receive real-time updates as agents process the request.

    Auth: Uses query param token (for EventSource which doesn't support headers).

    Events are streamed as:
    - event: Event type (event, complete, error)
    - data: JSON payload

    The stream ends when:
    - Workflow completes (sends 'complete' event)
    - Error occurs (sends 'error' event)
    - Client disconnects
    """
    # Authenticate via query param token (EventSource doesn't support headers)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token required for SSE"
        )

    try:
        user = await get_user_from_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    user_id = user.user_id

    # Verify conversation exists and belongs to user
    result = await db.execute(
        select(Conversation).where(
            and_(
                Conversation.id == uuid.UUID(conversation_id),
                Conversation.user_id == user_id
            )
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Get user message timestamp for filtering (if message_id provided)
    user_message_timestamp = None
    if message_id:
        try:
            msg_result = await db.execute(
                select(ConversationMessage).where(
                    ConversationMessage.id == uuid.UUID(message_id)
                )
            )
            user_msg = msg_result.scalar_one_or_none()
            if user_msg:
                user_message_timestamp = user_msg.created_at
                logger.info("tracking_message", message_id=message_id, timestamp=str(user_message_timestamp))
        except Exception as e:
            logger.warning("failed_to_get_user_message_timestamp", error=str(e))

    async def event_generator():
        """Generate SSE events as they become available."""
        seen_event_ids: Set[str] = set()
        max_iterations = 300  # 5 minutes max (300 * 1 second)
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1

                # Create a new session for each poll to avoid stale data
                from app.database import async_session_factory
                async with async_session_factory() as poll_db:
                    # Get new events (optionally filtered by timestamp)
                    new_events = await get_new_events(
                        poll_db, conversation_id, user_id, seen_event_ids,
                        after_timestamp=user_message_timestamp
                    )

                    # Send each new event
                    for event in new_events:
                        seen_event_ids.add(str(event.id))
                        event_data = event_to_dict(event)

                        yield f"event: event\ndata: {json.dumps(event_data)}\n\n"

                    # Check if workflow is complete (only for NEW events)
                    workflow_done = is_workflow_complete(new_events)

                    # Fallback: Also check if assistant message exists (every 5 iterations)
                    # This catches cases where events don't have the expected format
                    if not workflow_done and iteration % 5 == 0:
                        response_check = await check_conversation_has_response(
                            poll_db, conversation_id, after_message_id=message_id
                        )
                        if response_check.get("complete"):
                            workflow_done = True

                    if workflow_done:
                        # Get the final response (only responses after our tracked message)
                        response_check = await check_conversation_has_response(
                            poll_db, conversation_id, after_message_id=message_id
                        )

                        complete_data = {
                            "type": "complete",
                            "conversation_id": conversation_id,
                            "total_events": len(seen_event_ids),
                            "response": response_check if response_check.get("complete") else None
                        }
                        yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                        return

                # Wait before polling again
                await asyncio.sleep(0.5)

            # Timeout - send complete anyway
            yield f"event: complete\ndata: {json.dumps({'type': 'timeout', 'conversation_id': conversation_id})}\n\n"

        except asyncio.CancelledError:
            logger.info("stream_cancelled", conversation_id=conversation_id)
            raise
        except Exception as e:
            logger.error("stream_error", error=str(e), conversation_id=conversation_id)
            error_data = {"type": "error", "message": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/events/{conversation_id}/poll")
async def poll_events(
    conversation_id: str,
    last_event_id: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Poll for new events (fallback for clients that don't support SSE).

    Args:
        conversation_id: Conversation to poll
        last_event_id: Last event ID received (optional)

    Returns:
        List of new events since last_event_id
    """
    user_id = current_user.user_id

    # Verify conversation exists and belongs to user
    result = await db.execute(
        select(Conversation).where(
            and_(
                Conversation.id == uuid.UUID(conversation_id),
                Conversation.user_id == user_id
            )
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Get events
    query = select(TransparencyEvent).where(
        and_(
            TransparencyEvent.session_id == uuid.UUID(conversation_id),
            TransparencyEvent.user_id == user_id
        )
    ).order_by(TransparencyEvent.created_at)

    result = await db.execute(query)
    all_events = result.scalars().all()

    # Filter to events after last_event_id if provided
    if last_event_id:
        found = False
        events = []
        for event in all_events:
            if found:
                events.append(event)
            elif str(event.id) == last_event_id:
                found = True
    else:
        events = all_events

    # Check if complete
    is_complete = is_workflow_complete(list(events)) if events else False

    # Get response if complete
    response = None
    if is_complete:
        response_check = await check_conversation_has_response(db, conversation_id)
        if response_check.get("complete"):
            response = response_check

    return {
        "conversation_id": conversation_id,
        "events": [event_to_dict(e) for e in events],
        "is_complete": is_complete,
        "response": response,
        "total_events": len(all_events),
    }
