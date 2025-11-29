"""
Semantic Search Agent - Phase D: Self-Describing
Searches unstructured text using semantic understanding and embeddings.
Follows the segmentation.py template pattern.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json

import vertexai
from vertexai.preview.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus, EventType
from app.agents.schema_utils import get_schema_context, build_semantic_search_fields
from app.config import settings


class SemanticSearchAgent(BaseAgent):
    """
    Semantic Search Agent - Phase D: Self-Describing

    Searches unstructured text with complete transparency.
    Uses LLM to interpret tasks - NO hardcoded action routing.
    """

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Agent describes itself for dynamic discovery by orchestrator."""
        return {
            "name": "semantic_search",
            "purpose": "Search unstructured text using semantic understanding and fuzzy matching",
            "when_to_use": [
                "User is searching for concepts or topics in notes/descriptions",
                "User wants fuzzy text matching (approximate name search)",
                "User needs semantic similarity (find related content)",
                "User asks about interests, goals, or preferences in text fields",
                "User uses words like 'mentions', 'about', 'interested in', 'similar to'"
            ],
            "when_not_to_use": [
                "User needs mathematical calculations",
                "User wants exact value filtering (use SQL)",
                "User needs date/time operations",
                "User wants to count or aggregate numbers"
            ],
            "example_tasks": [
                "Find clients interested in retirement planning",
                "Search for notes mentioning ESG investing",
                "Find clients with names similar to 'Smith'",
                "Look for clients who mentioned real estate"
            ],
            "data_source_aware": True
        }

    def get_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Agent's internal capabilities for LLM-driven task routing."""
        return {
            "search_text": {
                "description": "Search for concepts in text fields like notes, descriptions, goals",
                "examples": ["search", "find mentions", "look for", "interested in", "about"],
                "method": "_search_text_fields"
            },
            "fuzzy_match": {
                "description": "Fuzzy matching on names or text (approximate string matching)",
                "examples": ["similar name", "sounds like", "approximate match", "fuzzy"],
                "method": "_fuzzy_match"
            },
            "find_similar": {
                "description": "Find similar records based on text description or profile",
                "examples": ["similar clients", "like this", "matching profile", "lookalikes"],
                "method": "_find_similar"
            }
        }

    def __init__(self):
        super().__init__()

        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )

        self.model = GenerativeModel(settings.gemini_pro_model)
        self.embedding_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """Execute semantic search task using LLM-driven interpretation."""
        task = message.action
        payload = message.payload
        conversation_id = message.conversation_id
        start_time = datetime.utcnow()

        try:
            # TRANSPARENCY: Received event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.RECEIVED,
                title=f"Received: {task[:50]}..." if len(task) > 50 else f"Received: {task}",
                details={"task": task, "payload": payload},
                step_number=1
            )

            # TRANSPARENCY: Thinking event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.THINKING,
                title="Analyzing search requirements...",
                details={"task": task, "available_capabilities": list(self.get_capabilities().keys())},
                step_number=2
            )

            # LLM-driven task interpretation
            capability, params = await self._interpret_task(task, payload, conversation_id, user_id, db)

            # TRANSPARENCY: Decision event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.DECISION,
                title=f"Using '{capability}' capability",
                details={"capability": capability, "parameters": params},
                step_number=3
            )

            # TRANSPARENCY: Action event
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.ACTION,
                title=f"Executing {capability}...",
                details={"search_terms": params.get("search_terms", [])},
                step_number=4
            )

            # Execute capability
            result = await self._execute_capability(capability, params, conversation_id, user_id, db)

            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # TRANSPARENCY: Result event
            match_count = result.get("match_count", 0)
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.RESULT,
                title=f"Found {match_count} matches",
                details={"match_count": match_count, "capability": capability},
                step_number=5,
                duration_ms=duration_ms
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result=result,
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "capability_used": capability,
                    "duration_ms": duration_ms
                }
            )

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self.emit_event(
                db=db,
                session_id=conversation_id,
                user_id=user_id,
                event_type=EventType.ERROR,
                title=f"Semantic search failed: {str(e)[:50]}",
                details={"error": str(e), "task": task},
                step_number=5,
                duration_ms=duration_ms
            )
            self.logger.error("semantic_search_failed", error=str(e), exc_info=True)
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Semantic search failed: {str(e)}"
            )

    async def _interpret_task(
        self,
        task: str,
        payload: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> tuple[str, Dict[str, Any]]:
        """LLM decides which capability to use."""
        capabilities = self.get_capabilities()
        caps_desc = "\n".join([
            f"- {name}: {info['description']}"
            for name, info in capabilities.items()
        ])

        prompt = f"""You are the Semantic Search Agent. Analyze this task and decide which capability to use.

CAPABILITIES:
{caps_desc}

TASK: "{task}"
CONTEXT: {json.dumps(payload, default=str) if payload else "None"}

Respond with JSON only:
{{
  "capability": "capability_name",
  "parameters": {{
    "search_terms": ["term1", "term2"],
    "fields": ["notes", "description"],
    "query_text": "text for fuzzy match if applicable"
  }}
}}"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 512}
            )

            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            result = json.loads(text.strip())
            capability = result.get("capability", "search_text")
            params = result.get("parameters", {})
            params.update(payload)
            return capability, params

        except Exception as e:
            self.logger.warning("task_interpretation_failed", error=str(e))
            return "search_text", payload

    async def _execute_capability(
        self,
        capability: str,
        params: Dict[str, Any],
        conversation_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Execute the chosen capability."""
        if capability == "search_text":
            return await self._search_text_fields(conversation_id, user_id, params, db)
        elif capability == "fuzzy_match":
            return await self._fuzzy_match(conversation_id, user_id, params, db)
        elif capability == "find_similar":
            return await self._find_similar(conversation_id, user_id, params, db)
        else:
            return await self._search_text_fields(conversation_id, user_id, params, db)

    async def _search_text_fields(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Search for concepts in unstructured text fields."""
        search_terms = payload.get("search_terms", [])
        fields = payload.get("fields", ["notes", "description", "goals"])

        if not search_terms:
            # Extract from task if not provided
            task = payload.get("task", "")
            search_terms = [task] if task else []

        if not search_terms:
            return {"matches": [], "match_count": 0, "message": "No search terms"}

        # Expand search terms
        expanded = await self._expand_search_terms(search_terms, conversation_id, user_id, db)

        # Execute search
        results = await self._execute_text_search(expanded, fields, user_id, db)

        return {
            "matches": results,
            "original_terms": search_terms,
            "expanded_terms": expanded,
            "match_count": len(results)
        }

    async def _expand_search_terms(
        self,
        terms: List[str],
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> List[str]:
        """Expand search terms to include related concepts."""
        try:
            prompt = f"""Given these search terms: {', '.join(terms)}

Provide related terms and synonyms (e.g., "retirement" → retirement, pension, 401k).
Return ONLY a comma-separated list:"""

            response = await self.model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 256}
            )

            expanded = [t.strip() for t in response.text.split(",")]
            return [t for t in expanded if t]
        except:
            return terms

    async def _execute_text_search(
        self,
        search_terms: List[str],
        fields: List[str],
        user_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Execute text search using ILIKE on dynamically discovered text fields."""
        # Get dynamic schema context - only use text fields
        schema_context = await get_schema_context(db, user_id)
        allowed_fields = build_semantic_search_fields(schema_context)

        # Use requested fields if they're valid text fields, otherwise use all text fields
        safe_fields = [f for f in fields if f in allowed_fields]
        if not safe_fields:
            safe_fields = allowed_fields[:10]  # Limit to first 10 text fields

        conditions = []
        params = {"user_id": user_id}
        idx = 0
        for term in search_terms:
            safe_term = term.replace('%', '\\%').replace('_', '\\_')
            for field in safe_fields:
                param_name = f"term_{idx}"
                # Determine if field is in core_data or custom_data
                field_info = schema_context.get("all_fields", {}).get(field, {})
                location = field_info.get("location", "custom_data")
                conditions.append(f"{location}->>'{field}' ILIKE :{param_name}")
                params[param_name] = f"%{safe_term}%"
                idx += 1

        where_clause = " OR ".join(conditions) if conditions else "FALSE"

        query = f"""
        SELECT id, client_name, contact_email, core_data, custom_data
        FROM clients
        WHERE user_id = :user_id AND ({where_clause})
        LIMIT 100
        """

        result = await db.execute(text(query), params)
        rows = result.fetchall()
        columns = result.keys()
        return [dict(zip(columns, row)) for row in rows] if rows else []

    async def _fuzzy_match(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Fuzzy matching on names or text."""
        query_text = payload.get("query_text", "")
        field = payload.get("field", "client_name")

        if not query_text:
            return {"matches": [], "match_count": 0, "message": "No query text"}

        allowed_fields = ['client_name', 'contact_email', 'company_name']
        if field not in allowed_fields:
            field = 'client_name'

        query = f"""
        SELECT id, client_name, contact_email, core_data, custom_data,
               SIMILARITY({field}, :query) as similarity_score
        FROM clients
        WHERE user_id = :user_id AND {field} % :query
        ORDER BY similarity_score DESC
        LIMIT 50
        """

        result = await db.execute(text(query), {"query": query_text, "user_id": user_id})
        rows = result.fetchall()
        columns = result.keys()
        results = [dict(zip(columns, row)) for row in rows] if rows else []

        return {
            "matches": results,
            "query_text": query_text,
            "field": field,
            "match_count": len(results)
        }

    async def _find_similar(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Find similar clients based on description."""
        description = payload.get("description", "")
        reference_id = payload.get("reference_client_id")

        if reference_id:
            query = """
            SELECT custom_data->>'description' as desc
            FROM clients WHERE id = :cid AND user_id = :user_id
            """
            result = await db.execute(text(query), {"cid": reference_id, "user_id": user_id})
            row = result.fetchone()
            if row and row[0]:
                description = row[0]

        if not description:
            return {"similar_clients": [], "match_count": 0, "message": "No description"}

        # Fetch clients with descriptions
        query = """
        SELECT id, client_name, contact_email, custom_data->>'description' as description
        FROM clients
        WHERE user_id = :user_id AND custom_data->>'description' IS NOT NULL
        LIMIT 500
        """

        result = await db.execute(text(query), {"user_id": user_id})
        rows = result.fetchall()
        columns = result.keys()
        results = [dict(zip(columns, row)) for row in rows[:20]] if rows else []

        return {
            "similar_clients": results,
            "query_description": description,
            "match_count": len(results)
        }
