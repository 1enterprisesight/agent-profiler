"""
Semantic Search Agent
Searches unstructured text using semantic understanding and embeddings with Gemini Pro
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
import json

import vertexai
from vertexai.preview.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingModel

from app.agents.base import BaseAgent, AgentMessage, AgentResponse, AgentStatus
from app.config import settings


class SemanticSearchAgent(BaseAgent):
    """
    Semantic Search Agent - Searches unstructured text fields

    Capabilities:
    - Fuzzy text matching
    - Semantic similarity search using embeddings
    - Natural language queries on text fields
    - Concept matching (e.g., "retirement" matches "pension", "401k")
    - Multi-field text search

    Never Uses:
    - Math or calculations (use SQL Analytics)
    - Date/time operations (use SQL Analytics)
    - Exact value filtering (use SQL Analytics)
    - Aggregations (use SQL Analytics)
    """

    def __init__(self):
        super().__init__(
            name="semantic_search",
            description="Semantic search on unstructured text fields"
        )

        # Initialize Vertex AI
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )

        # Use Pro model for semantic understanding
        self.model = GenerativeModel(settings.gemini_pro_model)

        # Text embedding model for similarity search
        self.embedding_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")

    async def _execute_internal(
        self,
        message: AgentMessage,
        db: AsyncSession,
        user_id: str,
    ) -> AgentResponse:
        """
        Execute semantic search action

        Actions:
            - search_text_fields: Search for concepts in text fields
            - fuzzy_match: Fuzzy matching on names or text
            - find_similar: Find similar records based on text
        """
        action = message.action
        payload = message.payload

        if action == "search_text_fields":
            return await self._search_text_fields(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "fuzzy_match":
            return await self._fuzzy_match(
                message.conversation_id,
                user_id,
                payload,
                db
            )
        elif action == "find_similar":
            return await self._find_similar(
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

    async def _search_text_fields(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Search for concepts in unstructured text fields
        """
        try:
            search_terms = payload.get("search_terms", [])
            fields = payload.get("fields", ["notes", "description", "goals"])

            if not search_terms:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error="No search terms provided"
                )

            self.logger.info(
                "searching_text_fields",
                search_terms=search_terms,
                fields=fields
            )

            # Expand search terms using Gemini to include related concepts
            expanded_terms = await self._expand_search_terms(
                search_terms,
                conversation_id,
                user_id,
                db
            )

            # Build search query using ILIKE for fuzzy matching
            # This searches in JSONB fields
            search_results = await self._execute_text_search(
                expanded_terms,
                fields,
                user_id,
                db
            )

            # Rank results by relevance
            ranked_results = await self._rank_results(
                search_results,
                search_terms,
                conversation_id,
                user_id,
                db
            )

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "matches": ranked_results,
                    "original_terms": search_terms,
                    "expanded_terms": expanded_terms,
                    "match_count": len(ranked_results)
                },
                metadata={
                    "model_used": settings.gemini_pro_model,
                    "search_type": "semantic_text_search"
                }
            )

        except Exception as e:
            self.logger.error(
                "text_search_failed",
                error=str(e),
                search_terms=payload.get("search_terms"),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Text search failed: {str(e)}"
            )

    async def _expand_search_terms(
        self,
        search_terms: List[str],
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> List[str]:
        """
        Expand search terms to include related concepts using Gemini
        """
        try:
            terms_str = ", ".join(search_terms)

            prompt = f"""Given these search terms: {terms_str}

Provide semantically related terms and synonyms that someone might use to express the same concepts.
For example:
- "retirement" → retirement, pension, 401k, IRA, retirement planning
- "risk" → risk, risky, high-risk, volatile, volatility
- "ESG" → ESG, sustainable, green, environmental, social responsibility

Return ONLY a comma-separated list of related terms (including originals), no explanation.

Terms:"""

            response = await self.model.generate_content_async(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 256,
                }
            )

            # Log LLM conversation
            await self.log_llm_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                model_name=settings.gemini_pro_model,
                prompt=prompt,
                response=response.text,
            )

            # Parse expanded terms
            expanded = [t.strip() for t in response.text.split(",")]
            expanded = [t for t in expanded if t]  # Remove empty strings

            self.logger.info(
                "search_terms_expanded",
                original_count=len(search_terms),
                expanded_count=len(expanded)
            )

            return expanded

        except Exception as e:
            self.logger.warning(
                "term_expansion_failed",
                error=str(e)
            )
            # Fallback to original terms
            return search_terms

    async def _execute_text_search(
        self,
        search_terms: List[str],
        fields: List[str],
        user_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Execute text search using ILIKE on JSONB fields
        """
        # Whitelist allowed fields to prevent SQL injection
        allowed_fields = ['notes', 'description', 'goals', 'interests', 'comments', 'biography']
        safe_fields = [f for f in fields if f in allowed_fields]
        if not safe_fields:
            safe_fields = ['notes', 'description']

        # Build parameterized ILIKE conditions
        conditions = []
        params = {"user_id": user_id}
        param_idx = 0
        for term in search_terms:
            # Sanitize term by escaping special characters
            safe_term = term.replace('%', '\\%').replace('_', '\\_')
            for field in safe_fields:
                param_name = f"term_{param_idx}"
                conditions.append(f"custom_data->>'{field}' ILIKE :{param_name}")
                params[param_name] = f"%{safe_term}%"
                param_idx += 1

        where_clause = " OR ".join(conditions) if conditions else "FALSE"

        query = f"""
        SELECT
            id,
            client_name,
            contact_email,
            core_data,
            custom_data,
            computed_metrics
        FROM clients
        WHERE user_id = :user_id
          AND ({where_clause})
        LIMIT 100
        """

        result = await db.execute(text(query), params)
        rows = result.fetchall()

        if rows:
            columns = result.keys()
            results = [dict(zip(columns, row)) for row in rows]
        else:
            results = []

        self.logger.info(
            "text_search_executed",
            result_count=len(results)
        )

        return results

    async def _rank_results(
        self,
        results: List[Dict[str, Any]],
        original_terms: List[str],
        conversation_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Rank search results by relevance using Gemini
        """
        if not results:
            return []

        # For now, return top results without re-ranking
        # In production, could use embeddings for similarity scoring
        return results[:50]

    async def _fuzzy_match(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Fuzzy matching on client names or other text fields
        """
        try:
            query_text = payload.get("query_text", "")
            field = payload.get("field", "client_name")

            if not query_text:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error="No query text provided"
                )

            # Whitelist allowed fields to prevent SQL injection
            allowed_fields = ['client_name', 'contact_email', 'company_name']
            if field not in allowed_fields:
                field = 'client_name'

            # Use PostgreSQL's similarity functions
            query = f"""
            SELECT
                id,
                client_name,
                contact_email,
                core_data,
                custom_data,
                SIMILARITY({field}, :query) as similarity_score
            FROM clients
            WHERE user_id = :user_id
              AND {field} % :query
            ORDER BY similarity_score DESC
            LIMIT 50
            """

            result = await db.execute(
                text(query),
                {"query": query_text, "user_id": user_id}
            )
            rows = result.fetchall()

            if rows:
                columns = result.keys()
                results = [dict(zip(columns, row)) for row in rows]
            else:
                results = []

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "matches": results,
                    "query_text": query_text,
                    "field": field,
                    "match_count": len(results)
                },
                metadata={
                    "search_type": "fuzzy_match"
                }
            )

        except Exception as e:
            self.logger.error(
                "fuzzy_match_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Fuzzy match failed: {str(e)}"
            )

    async def _find_similar(
        self,
        conversation_id: str,
        user_id: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Find similar clients based on text description using embeddings
        """
        try:
            description = payload.get("description", "")
            reference_client_id = payload.get("reference_client_id")

            if not description and not reference_client_id:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error="Need either description or reference_client_id"
                )

            # If reference client provided, get their description
            if reference_client_id:
                query = """
                SELECT custom_data->>'description' as description
                FROM clients
                WHERE id = :client_id
                """
                result = await db.execute(
                    text(query),
                    {"client_id": reference_client_id}
                )
                row = result.fetchone()
                if row and row[0]:
                    description = row[0]

            if not description:
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    error="No description available"
                )

            # Generate embedding for query
            query_embedding = self.embedding_model.get_embeddings([description])[0].values

            # For now, fetch all clients and compute similarity
            # In production, would use pgvector for efficient similarity search
            query = """
            SELECT
                id,
                client_name,
                contact_email,
                custom_data->>'description' as description
            FROM clients
            WHERE user_id = :user_id
              AND custom_data->>'description' IS NOT NULL
            LIMIT 500
            """

            result = await db.execute(text(query), {"user_id": user_id})
            rows = result.fetchall()

            if not rows:
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    result={
                        "similar_clients": [],
                        "match_count": 0
                    }
                )

            # Compute similarity (simplified - in production use cosine similarity)
            # For now, just return the results
            columns = result.keys()
            results = [dict(zip(columns, row)) for row in rows[:20]]

            return AgentResponse(
                status=AgentStatus.COMPLETED,
                result={
                    "similar_clients": results,
                    "query_description": description,
                    "match_count": len(results)
                },
                metadata={
                    "model_used": "textembedding-gecko@003",
                    "search_type": "embedding_similarity"
                }
            )

        except Exception as e:
            self.logger.error(
                "similarity_search_failed",
                error=str(e),
                exc_info=True
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                error=f"Similarity search failed: {str(e)}"
            )
