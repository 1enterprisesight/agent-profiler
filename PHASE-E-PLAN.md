# Agent Profiler - Phase E: Layout, Streaming & Schema Discovery

## Overview

Three interconnected improvements to make the Agent Profiler usable and show the multi-agent system in action:

1. **Dynamic Schema Discovery** - CRITICAL: System can't see user's custom columns
2. **Layout**: Hero agent network with page scroll below
3. **Real-time Streaming**: True SSE to see agents working as it happens
4. **Data-Aware Routing**: Orchestrator understands what the data IS

---

## Part 1: Dynamic Schema Discovery (CRITICAL BUG FIX)

### Problem

**The system has hardcoded schemas and can't see user's actual data fields.**

When user uploads CSV with "companies" column:
1. Data Ingestion stores it as `custom_data->>'companies'` ✓
2. SQL Agent has hardcoded `DATABASE_SCHEMA` - doesn't know "companies" exists ✗
3. Semantic Search has hardcoded `allowed_fields = ['notes', 'description', ...]` ✗
4. Data Discovery only checks hardcoded fields ✗
5. User asks "show me top companies" → **"Column not found"**

### Architectural Principle: Right Tool for Right Data Type

**CRITICAL RULE:**
```
- NUMERIC fields (revenue, AUM, counts) → SQL Analytics (math, aggregations)
- DATE fields (created_at, last_contact) → SQL Analytics (date math, filtering)
- TEXT fields (notes, descriptions, goals) → Semantic Search (meaning, similarity)

SQL Analytics should NEVER use:
- LIKE queries on free-form text
- Regex on text fields
- String pattern matching for semantic meaning

Semantic Search should NEVER:
- Do math or aggregations
- Filter by exact numeric values
- Perform date calculations
```

This means schema discovery must include **DATA TYPES**, not just field names.

### Solution: Dynamic Field Discovery WITH Data Types

**Step 1: Discover fields AND their types on data upload**

```python
# In data_ingestion.py, after upload:
async def _discover_schema(self, db, user_id) -> dict:
    """Discover fields and infer their data types."""

    # Get all custom fields
    fields_query = text("""
        SELECT DISTINCT jsonb_object_keys(custom_data) as field_name
        FROM clients WHERE user_id = :user_id
    """)

    # For each field, sample values to infer type
    schema = {}
    for field in fields:
        sample_query = text(f"""
            SELECT custom_data->>'{field}' as val
            FROM clients WHERE user_id = :user_id
            AND custom_data->>'{field}' IS NOT NULL
            LIMIT 100
        """)
        samples = await db.execute(sample_query, {"user_id": user_id})

        # Infer type from samples
        field_type = self._infer_field_type(samples)
        schema[field] = {
            "type": field_type,  # "numeric", "date", "text", "boolean"
            "samples": samples[:5],
            "null_pct": null_percentage,
        }

    return schema

def _infer_field_type(self, samples: list[str]) -> str:
    """Infer data type from sample values."""
    if all(self._is_numeric(s) for s in samples if s):
        return "numeric"
    if all(self._is_date(s) for s in samples if s):
        return "date"
    if all(s.lower() in ('true', 'false', 'yes', 'no', '0', '1') for s in samples if s):
        return "boolean"
    return "text"
```

**Step 2: Store schema with types**

```sql
CREATE TABLE user_data_schema (
    user_id VARCHAR,
    data_source_id UUID,
    field_name VARCHAR,
    field_type VARCHAR,  -- "numeric", "date", "text", "boolean"
    sample_values JSONB,
    null_percentage FLOAT,
    updated_at TIMESTAMP,
    PRIMARY KEY (user_id, data_source_id, field_name)
);
```

**Step 3: Pass typed schema to ALL agents**

```python
schema_context = {
    "numeric_fields": ["revenue", "aum", "age", "score"],  # → SQL Analytics
    "date_fields": ["created_at", "last_contact", "dob"],  # → SQL Analytics
    "text_fields": ["notes", "description", "goals", "companies"],  # → Semantic Search
    "all_fields": {...}
}
```

**Step 4: Agents enforce boundaries**

SQL Analytics: Only use numeric/date fields, NEVER LIKE/regex on text
Semantic Search: Only search text fields, NEVER do math

### Cross-Agent Schema Flow

```
Data Upload
    ↓
_discover_schema() runs
    ↓
Schema stored in DB with field types
    ↓
On query, schema_context built:
    ├── numeric_fields → SQL Analytics
    ├── date_fields → SQL Analytics
    └── text_fields → Semantic Search
    ↓
Orchestrator routes based on field types
    ↓
Each agent receives only relevant fields
    ↓
Agents enforce boundaries
```

---

## Part 2: Layout Redesign (Hero Network + Scroll)

### New Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER (sticky top)                                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │           AGENT NETWORK (Hero Section)              │   │
│  │           Min-height: 350px, responsive             │   │
│  │           Full-width, prominent placement           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────┐  ┌────────────────────────┐  │
│  │   CHAT INTERFACE         │  │  DATA SOURCES          │  │
│  │   Natural height         │  │  (Collapsible)         │  │
│  │   Messages grow          │  ├────────────────────────┤  │
│  │                          │  │  WORKFLOW DISPLAY      │  │
│  │                          │  │  (Auto-scrolls)        │  │
│  └──────────────────────────┘  └────────────────────────┘  │
│                                                             │
│  PAGE SCROLLS NATURALLY                                     │
└─────────────────────────────────────────────────────────────┘
│  STICKY CHAT INPUT BAR (fixed bottom)                       │
└─────────────────────────────────────────────────────────────┘
```

### Key Changes

- Remove `h-[calc(100vh-120px)]` viewport lock
- Replace emoji with lucide-react icons
- Responsive node sizing
- Better labels (full names, not truncated)

---

## Part 3: Real-time SSE Streaming

### Architecture

```
User sends message
        ↓
POST /chat/start → Returns conv_id immediately
        ↓
GET /stream/events/{conv_id} (SSE connection)
        ↓
Events stream to frontend in real-time
        ↓
GET /chat/result (fetch final answer)
```

### Backend: New streaming.py

```python
@router.get("/stream/events/{conversation_id}")
async def stream_events(conversation_id: str):
    async def event_generator():
        seen_events = set()
        while True:
            new_events = await get_new_events(db, conversation_id, seen_events)
            for event in new_events:
                yield f"data: {json.dumps(event_to_dict(event))}\n\n"
            if is_workflow_complete(new_events):
                yield "data: {\"type\": \"complete\"}\n\n"
                break
            await asyncio.sleep(0.3)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## Part 4: Data-Aware Intelligent Routing

### Solution

Orchestrator fetches data context BEFORE planning:
- Schema (columns, types)
- Data summary ("This is customer CRM data with AUM, engagement scores")

```python
async def _get_data_context(self, db, user_id) -> dict:
    schema = await self._get_data_schema(db, user_id)
    cached_summary = await self._get_cached_data_summary(db, user_id)
    return {
        "schema": schema,
        "data_type": cached_summary["data_type"],
        "key_entities": cached_summary["key_entities"],
        "key_metrics": cached_summary["key_metrics"],
    }
```

---

## Part 5: Real Analytics & Business Insights

Agents should provide ANALYSIS, not just data:

```
CURRENT: "You have 47 clients with AUM > $1M. Average engagement: 6.2"

IMPROVED:
"KEY FINDINGS:
- 47 clients (12% of base) hold 68% of total AUM
- Their engagement is 6.2, BELOW portfolio average of 7.1

INSIGHT: Highest-value clients are less engaged - significant risk.

RECOMMENDATIONS:
1. Prioritize outreach to 15 high-AUM clients with engagement < 5
2. Review when you last contacted clients with AUM > $2M"
```

---

## Implementation Order

### Phase 1: Dynamic Schema Discovery (CRITICAL - FIX FIRST)
1. Add `_discover_schema()` to data_ingestion.py
2. Add `_infer_field_type()`
3. Create `user_data_schema` table
4. Create shared `get_schema_context()` function
5. Update sql_analytics.py - dynamic schema, no LIKE on text
6. Update semantic_search.py - dynamic schema, no math
7. Update orchestrator.py - typed schema in planning
8. Test with CSV upload

### Phase 2: Backend Streaming
9. Create `streaming.py` with SSE endpoint
10. Modify `conversations.py` - async start endpoint
11. Register routes

### Phase 3: Data-Aware Orchestration & Real Analytics
12. Add `_get_data_context()` to orchestrator
13. Update agent prompts for INSIGHTS
14. Update `_aggregate_results()` to synthesize like analyst

### Phase 4: Frontend Streaming Consumer
15. Create `eventStream.ts`
16. Update `ChatInterface.tsx` to use streaming

### Phase 5: Layout Redesign
17. Update `App.tsx` - hero network, page scroll
18. Update `AgentNetwork.tsx` - lucide icons, responsive sizing

### Phase 6: Polish & Integration
19. Add auto-scroll to WorkflowDisplay
20. Test and deploy

---

## Critical Files

### Backend
- `backend/app/agents/data_ingestion.py` - schema discovery
- `backend/app/agents/sql_analytics.py` - dynamic schema
- `backend/app/agents/semantic_search.py` - dynamic schema
- `backend/app/agents/orchestrator.py` - routing + context
- `backend/app/routers/streaming.py` (NEW)

### Frontend
- `frontend/src/App.tsx` - layout
- `frontend/src/components/AgentNetwork.tsx` - icons, sizing
- `frontend/src/components/ChatInterface.tsx` - streaming
- `frontend/src/services/eventStream.ts` (NEW)

---

## Success Criteria

1. **Schema Discovery**: "show top companies" works if there's a "companies" column
2. **Type Routing**: Numeric → SQL, Text → Semantic (never mixed)
3. **Layout**: Agent network prominent, page scrolls naturally
4. **Streaming**: Events appear in real-time during processing
5. **Insights**: Responses include findings, patterns, recommendations
6. **Visual**: Can SEE agents working - nodes light up, events stream live
