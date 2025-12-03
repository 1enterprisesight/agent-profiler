# Agent Architecture - Blueprint for All Agents

**Created:** 2025-12-03
**Purpose:** Single source of truth for building agents
**Reference Implementation:** `sql_analytics.py` (working, don't modify)

---

## CRITICAL RULES

### 1. DO NOT MODIFY WORKING AGENTS
- `orchestrator.py` - Working, don't touch
- `sql_analytics.py` - Working, don't touch
- `data_ingestion.py` - Working, don't touch
- `data_discovery.py` - Working, don't touch
- `base.py` - Working, don't touch

### 2. ALL NEW AGENTS MUST FOLLOW THIS PATTERN
- Copy the SQL Analytics pattern exactly
- Use same code structure
- Use same method signatures
- Use same transparency events

### 3. NO HARDCODING
- NO keyword-based routing
- NO agent-to-agent awareness (agents don't know about each other)
- LLM decides everything via prompts
- Agents describe CAPABILITIES, not specific queries

---

## ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR                             │
│  - Receives user message                                         │
│  - Gets available agents from AgentRegistry                      │
│  - LLM decides which agents to invoke                           │
│  - Passes previous_results to each agent                        │
│  - Synthesizes final response                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT REGISTRY                              │
│  - Singleton pattern                                             │
│  - Agents self-register via @register_agent decorator           │
│  - Provides schema for LLM prompt injection                     │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │ SQL Agent   │     │ Segment     │     │ Pattern     │
   │ (Quant)     │     │ Agent       │     │ Agent       │
   └─────────────┘     └─────────────┘     └─────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │   (clients      │
                    │    table)       │
                    └─────────────────┘
```

### Key Points:
- **Flat architecture** - Each agent is independent
- **Self-contained** - Each agent generates its own SQL
- **Gemini-driven** - LLM makes all decisions
- **No agent-to-agent calls** - Orchestrator coordinates everything

---

## AGENT REGISTRATION PATTERN

Every agent MUST use the `@register_agent` decorator:

```python
from app.agents.base import (
    BaseAgent, AgentMessage, AgentResponse, AgentStatus,
    EventType, register_agent
)

@register_agent
class MyAgent(BaseAgent):
    """Agent description for orchestrator discovery."""

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """Metadata for orchestrator's LLM routing."""
        return {
            "name": "my_agent",
            "description": "What this agent does (capability-focused, NO keywords)",
            "capabilities": [
                "First capability description",
                "Second capability description",
            ],
            "inputs": {
                "request": "Natural language request from orchestrator",
                "data_source_id": "ID of data source to analyze",
                "context": "Additional context (optional)",
                "previous_results": "Results from prior agents (optional)"
            },
            "outputs": {
                "results": "Query results as structured data",
                "insights": "LLM-generated interpretation",
                "queries_executed": "SQL queries that were run",
                "visualization_hint": "Suggested chart type"
            }
        }
```

---

## DATA FLOW: ORCHESTRATOR → AGENT

### What Orchestrator Passes to Each Agent:

```python
payload = {
    "request": "Natural language task description",
    "data_source_id": "uuid-of-data-source",
    "context": "Additional context string",
    "previous_results": [  # Results from agents called earlier
        {
            "agent": "sql_analytics",
            "task": "what was requested",
            "result": { ... full result object ... }
        }
    ]
}
```

### Agent Receives Via:

```python
async def _execute_internal(
    self,
    message: AgentMessage,
    db: AsyncSession,
    user_id: str
) -> AgentResponse:

    payload = message.payload
    request = payload.get("request", "")
    data_source_id = payload.get("data_source_id")
    additional_context = payload.get("context", "")
    previous_results = payload.get("previous_results", [])  # From prior agents
```

---

## REQUIRED METHODS (Copy from SQL Analytics)

### 1. `__init__(self)`
```python
def __init__(self):
    super().__init__()
    vertexai.init(
        project=settings.google_cloud_project,
        location=settings.vertex_ai_location
    )
    self.model = GenerativeModel(settings.gemini_flash_model)
```

### 2. `get_data_context()` - ALREADY IN BaseAgent
```python
# Don't implement - use inherited method
data_context = await self.get_data_context(db, data_source_id, user_id)
```

Returns:
```python
{
    "data_source_id": "uuid",
    "file_name": "name.csv",
    "row_count": 3480,
    "columns": ["col1", "col2", ...],
    "detected_types": {
        "col1": {"type": "text", "nullable": false, "sample_values": [...]},
    },
    "semantic_profile": {
        "domain": "healthcare",
        "entity_name": "doctor",
        "field_descriptions": {...},
        ...
    },
    "field_mappings": {
        "Area": {"target": "custom_data.area"},
        ...
    }
}
```

### 3. `_build_sql_expressions()` - Convert field_mappings to SQL
```python
def _build_sql_expressions(self, data_context: Dict) -> Dict[str, str]:
    """Convert field_mappings to exact SQL expressions."""
    raw_mappings = data_context.get('field_mappings', {})
    sql_expressions = {}
    for col, mapping in raw_mappings.items():
        target = mapping.get('target', '') if isinstance(mapping, dict) else mapping
        if target.startswith('core_data.'):
            key = target.replace('core_data.', '')
            sql_expressions[col] = f"(core_data->>'{key}')"
        elif target.startswith('custom_data.'):
            key = target.replace('custom_data.', '')
            sql_expressions[col] = f"(custom_data->>'{key}')"
        else:
            sql_expressions[col] = target
    return sql_expressions
```

### 4. `_is_safe_query()` - Validate read-only
```python
def _is_safe_query(self, sql: str) -> bool:
    """Check if query is safe to execute (read-only)."""
    if not sql:
        return False
    sql_upper = sql.upper().strip()
    dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"]
    return not any(sql_upper.startswith(d) or f" {d} " in sql_upper for d in dangerous)
```

### 5. `_execute_query()` - Run SQL with autocommit
```python
async def _execute_query(
    self,
    db: AsyncSession,
    sql: str,
    data_source_id: str,
    session_id: str = None
) -> Dict:
    """Execute a read-only SQL query using autocommit connection."""
    from app.database import engine

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql))
            rows = result.fetchall()
            columns = result.keys()

            data = [dict(zip(columns, row)) for row in rows]

            # Handle special types for JSON serialization
            for row in data:
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):
                        row[key] = value.isoformat()
                    elif isinstance(value, (bytes,)):
                        row[key] = value.decode('utf-8', errors='replace')

            return {"data": data, "row_count": len(data)}

    except Exception as e:
        return {"error": str(e)}
```

### 6. `_correct_query()` - Self-correction on errors
```python
async def _correct_query(self, original_sql: str, error: str, data_context: Dict) -> Optional[str]:
    """LLM attempts to fix a failed query."""

    prompt = f"""The following SQL query failed. Fix it.

ORIGINAL QUERY:
{original_sql}

ERROR:
{error}

SCHEMA CONTEXT:
- Table: clients
- Data is in JSONB columns: core_data, custom_data
- Access fields: (core_data->>'field_name') or (custom_data->>'field_name')
- Available columns: {json.dumps(list(data_context.get('detected_types', {}).keys()))}

Return ONLY the corrected SQL query, no explanation."""

    try:
        response = await self.model.generate_content_async(
            prompt,
            generation_config={"temperature": 0.1}
        )
        corrected = response.text.strip()

        if "```sql" in corrected:
            corrected = corrected.split("```sql")[1].split("```")[0]
        elif "```" in corrected:
            corrected = corrected.split("```")[1].split("```")[0]

        return corrected.strip()

    except Exception as e:
        return None
```

---

## TRANSPARENCY EVENTS PATTERN

Every agent MUST emit transparency events for UI visibility:

```python
async def _execute_internal(self, message, db, user_id):
    conversation_id = message.conversation_id

    # Helper for events
    async def emit(event_type: EventType, title: str, details: Dict = None, step: int = 1):
        await self.emit_event(
            db=db,
            user_id=user_id,
            session_id=conversation_id,
            event_type=event_type,
            title=title,
            details=details or {},
            step_number=step
        )

    # Standard event flow:
    await emit(EventType.RECEIVED, "Received request", {"request": request[:100]}, 1)
    await emit(EventType.THINKING, "Loading data context", {}, 2)
    await emit(EventType.THINKING, "Analyzing and planning", {}, 3)
    await emit(EventType.ACTION, "Executing queries", {"count": N}, 4)
    await emit(EventType.THINKING, "Synthesizing insights", {}, 5)
    await emit(EventType.RESULT, "Analysis complete", {"summary": "..."}, 6)

    # On error:
    await emit(EventType.ERROR, f"Failed: {error}", {"error": str(e)}, 99)
```

---

## GEMINI PROMPT PATTERN

Each agent has a specialized prompt. Key sections:

```python
prompt = f"""You are a [AGENT ROLE] generating PostgreSQL queries.

REQUEST: {request}

=== DATA SOURCE ===
File: {data_context.get('file_name')}
Rows: {data_context.get('row_count', 0)}
Entity: {data_context.get('semantic_profile', {}).get('entity_name', 'unknown')}
Domain: {data_context.get('semantic_profile', {}).get('domain', 'unknown')}

=== LOGICAL COLUMNS (names, types, samples) ===
{json.dumps(data_context.get('detected_types', {}), indent=2)}

=== FIELD DESCRIPTIONS (semantic meaning) ===
{json.dumps(data_context.get('semantic_profile', {}).get('field_descriptions', {}), indent=2)}

=== SQL EXPRESSIONS (copy exactly) ===
{json.dumps(sql_expressions, indent=2)}

=== PREVIOUS AGENT RESULTS ===
{json.dumps(previous_results_summary, indent=2) if previous_results else "None"}

=== QUERY GENERATION RULES ===
1. Map user terms to logical columns using FIELD DESCRIPTIONS
2. Copy exact SQL expression from SQL EXPRESSIONS section
3. For numeric operations, cast with ::numeric
4. Required filter: WHERE data_source_id = '{data_context.get('data_source_id')}'
5. Filter nulls on analyzed columns
6. CRITICAL: Always alias every column with AS using readable names

=== [AGENT-SPECIFIC INSTRUCTIONS] ===
[What this agent should look for and how to structure queries]

Return valid JSON only."""
```

---

## AGENT RESPONSE STRUCTURE

All agents MUST return this structure:

```python
return AgentResponse(
    status=AgentStatus.COMPLETED,
    result={
        "results": [
            {
                "purpose": "What this query answered",
                "data": [...],  # List of dicts
                "row_count": N
            }
        ],
        "insights": {
            "summary": "Key finding in one sentence",
            "findings": ["Finding 1", "Finding 2"],
            "insights": ["Pattern noticed"],
            "visualization_hint": "bar|line|pie|table"
        },
        "queries_executed": [
            {"sql": "SELECT ...", "purpose": "..."}
        ],
        "visualization_hint": "bar"
    },
    metadata={
        "duration_ms": N,
        "queries_run": N,
        "total_rows": N
    }
)
```

---

## AGENTS TO BUILD (Priority Order)

| # | Agent | File | Purpose | Status |
|---|-------|------|---------|--------|
| 1 | **Segmentation** | `segmentation.py` | Group entities by value tiers, categories, clusters | COMPLETE |
| 2 | **Pattern Recognition** | `pattern_recognition.py` | Trends, anomalies, time-series, distributions | COMPLETE |
| 3 | **Opportunity** | `opportunity.py` | High-potential entities, upsell candidates | PENDING |
| 4 | **Business Impact** | `business_impact.py` | Simulation, "what-if" scenarios | PENDING |
| 5 | **Risk** | `risk.py` | At-risk entity detection, warning signs | PENDING |
| 6 | **Benchmark** | `benchmark.py` | Compare against historical/industry data | PENDING |
| 7 | **Semantic Text** | `semantic_text.py` | Text matching/analysis using LLM (not ILIKE) | PENDING |
| 8 | **Semantic Search** | `semantic_search.py` | Vector/embedding search (if data has embeddings) | PENDING |

---

## DETAILED AGENT SPECIFICATIONS

### Agent 1: SEGMENTATION AGENT

**File:** `backend/app/agents/segmentation.py`
**Name:** `segmentation`

**Purpose:**
Group and segment entities into meaningful categories based on characteristics and values. Creates actionable segments for business decisions.

**When Orchestrator Should Route Here:**
- User asks to "segment", "group", "categorize", "tier", "cluster" entities
- User wants to identify "high value", "medium value", "low value" groups
- User asks about "distribution" across categories
- User wants to "classify" or "bucket" data

**Capabilities (for `get_agent_info()`):**
```python
[
    "Segment entities by value tiers (high/medium/low based on percentiles)",
    "Group data by categorical attributes (region, type, category)",
    "Identify natural clusters and groupings in the data",
    "Calculate segment sizes, percentages, and distributions",
    "Provide segment profiles with key characteristics (averages, totals)"
]
```

**Query Types to Generate:**
1. **Value Tier Segmentation** - Group by percentile ranges (top 20%, middle 60%, bottom 20%)
2. **Categorical Grouping** - Group by text columns with counts and aggregates
3. **Multi-dimensional Segmentation** - Combine multiple attributes (region + tier)
4. **Segment Profiling** - Calculate characteristics per segment (avg, sum, count)

**Example Insights to Generate:**
- "High Value segment contains 245 entities (15.2%) with average sales of $125,000"
- "The West region has the highest concentration of High Value customers (32%)"
- "3 segments identified: Enterprise (12%), Mid-Market (45%), SMB (43%)"

---

### Agent 2: PATTERN RECOGNITION AGENT

**File:** `backend/app/agents/pattern_recognition.py`
**Name:** `pattern_recognition`

**Purpose:**
Identify trends, anomalies, time-series patterns, and statistical distributions in data. Surfaces hidden patterns that aren't obvious from raw data.

**When Orchestrator Should Route Here:**
- User asks about "trends", "patterns", "changes over time"
- User wants to find "anomalies", "outliers", "unusual" data points
- User asks about "distribution", "spread", "variance"
- User wants to know what's "increasing", "decreasing", "stable"
- User asks about "highs", "lows", "averages"

**Capabilities (for `get_agent_info()`):**
```python
[
    "Detect trends over time (increasing, decreasing, stable, cyclical)",
    "Identify anomalies and outliers (values beyond normal range)",
    "Analyze statistical distributions (concentration, spread, skew)",
    "Find top performers and bottom performers",
    "Calculate period-over-period changes and growth rates"
]
```

**Query Types to Generate:**
1. **Trend Analysis** - Order by date, calculate running totals/averages
2. **Outlier Detection** - Find values beyond 2 standard deviations
3. **Distribution Analysis** - Min, max, avg, median, percentiles
4. **Top/Bottom Analysis** - Rank and identify extremes
5. **Change Detection** - Compare current vs previous periods

**Example Insights to Generate:**
- "Sales show a 15% upward trend over the past 6 months"
- "5 entities identified as outliers with sales 3x above average"
- "Distribution is right-skewed: median ($45K) is below mean ($62K)"
- "Top 10% of entities account for 45% of total revenue"

---

### Agent 3: OPPORTUNITY AGENT

**File:** `backend/app/agents/opportunity.py`
**Name:** `opportunity`

**Purpose:**
Identify high-potential entities and growth opportunities. Finds candidates for upsell, cross-sell, expansion, or increased engagement.

**When Orchestrator Should Route Here:**
- User asks about "opportunities", "potential", "growth"
- User wants to find "upsell", "cross-sell" candidates
- User asks "who should we focus on", "where to invest"
- User wants to identify "high potential", "underserved" entities
- User asks about "expansion" or "growth" targets

**Capabilities (for `get_agent_info()`):**
```python
[
    "Identify high-potential entities showing growth indicators",
    "Find upsell candidates (high engagement, low spend)",
    "Detect underserved segments with expansion potential",
    "Rank opportunities by potential value",
    "Identify entities similar to top performers"
]
```

**Query Types to Generate:**
1. **Growth Indicators** - Entities with increasing metrics
2. **Gap Analysis** - High engagement + low spend = opportunity
3. **Lookalike Analysis** - Similar to top performers but lower tier
4. **Underserved Detection** - Categories with low penetration
5. **Potential Scoring** - Rank by opportunity indicators

**Example Insights to Generate:**
- "47 entities identified as upsell candidates: high engagement, below-average spend"
- "West region is underserved: 15% of entities, only 8% of revenue"
- "12 entities show growth trajectory similar to current top performers"

---

### Agent 4: BUSINESS IMPACT AGENT

**File:** `backend/app/agents/business_impact.py`
**Name:** `business_impact`

**Purpose:**
Simulate scenarios and model business impact. Answers "what-if" questions and projects outcomes based on data patterns.

**When Orchestrator Should Route Here:**
- User asks "what if", "what would happen if"
- User wants to model "impact", "effect", "consequence"
- User asks about "projections", "forecasts", "predictions"
- User wants to understand "revenue impact", "cost impact"
- User asks about "scenarios" or "simulations"

**Capabilities (for `get_agent_info()`):**
```python
[
    "Model impact of changes (price changes, volume changes)",
    "Project outcomes based on historical patterns",
    "Simulate scenarios with different assumptions",
    "Calculate sensitivity to key variables",
    "Estimate revenue/cost impact of decisions"
]
```

**Query Types to Generate:**
1. **Baseline Metrics** - Current state for comparison
2. **Historical Patterns** - Past responses to similar changes
3. **Sensitivity Analysis** - Impact of X% change in variable Y
4. **Projection Queries** - Extend trends into future
5. **Scenario Comparison** - Multiple "what-if" calculations

**Example Insights to Generate:**
- "A 10% price increase could impact revenue by $2.3M based on historical elasticity"
- "If current trends continue, Q4 revenue projected at $15.2M (+12% YoY)"
- "Losing the top 5 accounts would reduce revenue by 23%"

---

### Agent 5: RISK AGENT

**File:** `backend/app/agents/risk.py`
**Name:** `risk`

**Purpose:**
Identify at-risk entities and warning signs. Detects potential problems before they become critical.

**When Orchestrator Should Route Here:**
- User asks about "risk", "at-risk", "churn", "declining"
- User wants to find "warning signs", "red flags"
- User asks "who might we lose", "what's concerning"
- User wants to identify "problems", "issues", "threats"
- User asks about "declining" or "dropping" metrics

**Capabilities (for `get_agent_info()`):**
```python
[
    "Identify at-risk entities showing decline indicators",
    "Detect warning signs (declining engagement, reduced activity)",
    "Flag entities with concerning patterns",
    "Calculate risk scores based on multiple factors",
    "Identify entities needing immediate attention"
]
```

**Query Types to Generate:**
1. **Decline Detection** - Entities with decreasing metrics
2. **Warning Signs** - Below-average engagement, missed thresholds
3. **Risk Scoring** - Combine multiple risk factors
4. **Churn Indicators** - Patterns similar to past losses
5. **Attention Needed** - Entities requiring intervention

**Example Insights to Generate:**
- "23 entities flagged as at-risk: declining engagement over 3 months"
- "High-value account ABC Corp shows 40% activity decline - needs attention"
- "Risk concentration: 60% of at-risk revenue is in West region"

---

### Agent 6: BENCHMARK AGENT

**File:** `backend/app/agents/benchmark.py`
**Name:** `benchmark`

**Purpose:**
Compare entities against benchmarks, averages, and standards. Provides relative performance context.

**When Orchestrator Should Route Here:**
- User asks to "compare", "benchmark", "vs average"
- User wants to know "how does X compare to Y"
- User asks about "performance vs peers", "relative to others"
- User wants to see "above/below average" analysis
- User asks about "rankings" or "standings"

**Capabilities (for `get_agent_info()`):**
```python
[
    "Compare entities against group averages",
    "Benchmark performance vs peers in same category",
    "Calculate relative performance (% above/below average)",
    "Rank entities within their segments",
    "Compare current performance to historical benchmarks"
]
```

**Query Types to Generate:**
1. **Average Comparison** - Entity value vs group average
2. **Peer Comparison** - Performance within same category
3. **Percentile Ranking** - Where entity falls in distribution
4. **Historical Comparison** - Current vs past performance
5. **Category Benchmarks** - Best-in-class per segment

**Example Insights to Generate:**
- "Entity XYZ is 25% above category average in sales"
- "Ranked #3 out of 45 entities in the West region"
- "Performance improved from 65th percentile to 78th percentile YoY"

---

### Agent 7: SEMANTIC TEXT AGENT

**File:** `backend/app/agents/semantic_text.py`
**Name:** `semantic_text`

**Purpose:**
Perform intelligent text matching and analysis using LLM understanding. Replaces brittle ILIKE/REGEX searches with semantic understanding.

**When Orchestrator Should Route Here:**
- User asks to find entities by description that requires understanding
- User wants to match text that doesn't have exact keywords
- User asks about categories that require inference (e.g., "semiconductor companies")
- User wants text-based filtering with fuzzy matching
- User needs context-aware text search

**Capabilities (for `get_agent_info()`):**
```python
[
    "Find entities matching semantic descriptions (not just keywords)",
    "Categorize text values using LLM understanding",
    "Identify entities belonging to inferred categories",
    "Perform fuzzy text matching with context awareness",
    "Enrich text data with semantic classifications"
]
```

**How It Works (Fetch-Reason-Query Pattern):**
1. Fetch distinct text values from relevant column
2. Send to Gemini: "Which of these are semiconductor companies?"
3. Gemini returns: ['Intel', 'AMD', 'Nvidia']
4. Generate SQL: `WHERE company_name IN ('Intel', 'AMD', 'Nvidia')`

**NO ILIKE, NO REGEX** - LLM does the matching.

**Example Use Cases:**
- "Show me all semiconductor companies" → LLM identifies Intel, AMD, Nvidia
- "Find retail businesses" → LLM identifies Amazon, Target, Walmart
- "Which doctors specialize in cardiology?" → LLM infers from specialties

---

### Agent 8: SEMANTIC SEARCH AGENT

**File:** `backend/app/agents/semantic_search.py`
**Name:** `semantic_search`

**Purpose:**
Perform vector-based similarity search on embedded data. Only used when data source has vector embeddings.

**When Orchestrator Should Route Here:**
- User asks for "similar to", "like this", "related to"
- User wants semantic similarity (not exact matching)
- Data source has embedding columns
- User asks natural language questions against text fields

**Capabilities (for `get_agent_info()`):**
```python
[
    "Find entities similar to a reference entity or description",
    "Perform semantic similarity search on embedded text",
    "Answer natural language questions against text data",
    "Retrieve contextually relevant records",
    "Rank results by semantic relevance"
]
```

**Prerequisites:**
- Data source must have embedding columns (pgvector)
- Embeddings generated during data ingestion
- If no embeddings, this agent should NOT be used

**How It Works:**
1. Convert user query to embedding vector
2. Perform cosine similarity search against stored embeddings
3. Return top N most similar records
4. Synthesize findings with LLM

**Example Use Cases:**
- "Find customers similar to ABC Corp"
- "Which products are related to our top seller?"
- "Show me records about supply chain issues" (semantic, not keyword)

---

## SEGMENTATION AGENT SPECIFICATION

### Purpose
Group and segment entities into meaningful categories based on characteristics and values.

### Capabilities (for `get_agent_info()`)
- Segment entities by value tiers (high/medium/low)
- Group data by categorical attributes
- Identify natural clusters and groupings
- Calculate segment sizes and distributions
- Provide segment profiles and characteristics

### Gemini Prompt Focus
Instruct Gemini to generate queries that:
1. Group by categorical columns
2. Calculate value distributions (percentiles for tiers)
3. Count entities per segment
4. Calculate segment characteristics (avg, sum, etc.)
5. Identify outlier segments

### Example Queries to Generate
```sql
-- Value tier segmentation
SELECT
    CASE
        WHEN (custom_data->>'sales')::numeric > percentile_75 THEN 'High Value'
        WHEN (custom_data->>'sales')::numeric > percentile_25 THEN 'Medium Value'
        ELSE 'Low Value'
    END AS segment,
    COUNT(*) AS count,
    AVG((custom_data->>'sales')::numeric) AS avg_sales
FROM clients
WHERE data_source_id = '...'
GROUP BY segment

-- Category grouping
SELECT
    (custom_data->>'region') AS region,
    COUNT(*) AS count,
    SUM((custom_data->>'sales')::numeric) AS total_sales
FROM clients
WHERE data_source_id = '...'
GROUP BY region
ORDER BY total_sales DESC
```

---

## PATTERN RECOGNITION AGENT SPECIFICATION

### Purpose
Identify trends, anomalies, time-series patterns, and distributions in data.

### Capabilities (for `get_agent_info()`)
- Detect trends over time (increasing, decreasing, stable)
- Identify anomalies and outliers
- Analyze distributions (normal, skewed, bimodal)
- Find seasonality or cyclical patterns
- Calculate statistical measures (mean, median, std dev)

### Gemini Prompt Focus
Instruct Gemini to generate queries that:
1. Order by date/time columns
2. Calculate moving averages
3. Find min/max/outliers (beyond 2 std dev)
4. Group by time periods (day, week, month)
5. Compare current vs historical

### Example Queries to Generate
```sql
-- Trend analysis
SELECT
    DATE_TRUNC('month', (custom_data->>'date')::date) AS month,
    SUM((custom_data->>'sales')::numeric) AS total_sales,
    COUNT(*) AS transaction_count
FROM clients
WHERE data_source_id = '...'
GROUP BY month
ORDER BY month

-- Outlier detection
SELECT *
FROM clients
WHERE data_source_id = '...'
  AND (custom_data->>'sales')::numeric > (
      SELECT AVG((custom_data->>'sales')::numeric) + 2 * STDDEV((custom_data->>'sales')::numeric)
      FROM clients WHERE data_source_id = '...'
  )
```

---

## ORCHESTRATOR UPDATE REQUIRED

**File:** `orchestrator.py`
**Method:** `_invoke_agent()`
**Change:** Pass accumulated results to each agent

```python
# Current (line ~391-397):
payload={
    "request": request,
    "data_source_id": data_source_id,
    "context": ""
}

# Updated:
payload={
    "request": request,
    "data_source_id": data_source_id,
    "context": "",
    "previous_results": accumulated_results  # ADD THIS
}
```

**In the execution loop (line ~166):**
```python
agent_results = []
for i, task in enumerate(interpretation.get("tasks", [])):
    # ... existing code ...

    result = await self._invoke_agent(
        db, user_id, session_id, agent_name, task_request,
        data_source_id,
        previous_results=agent_results  # Pass accumulated results
    )
```

---

## FRONTEND DISPLAY

Agent results cascade in the UI via `agentActivities` array:

```
┌─────────────────────────────────────┐
│ Chat Conversation                   │
│ [User message]                      │
│ [Assistant response]                │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Agent Network Diagram               │
│ [Shows which agents were invoked]   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ SQL Analytics Results               │  ← First agent
│ [Table + Chart]                     │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Segmentation Results                │  ← Second agent
│ [Segments + Chart]                  │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Pattern Recognition Results         │  ← Third agent
│ [Trends + Chart]                    │
└─────────────────────────────────────┘
```

Each `AnalysisResultsPanel` component renders one agent's results.

---

## CHECKLIST FOR NEW AGENT

- [ ] File: `backend/app/agents/{agent_name}.py`
- [ ] `@register_agent` decorator
- [ ] `get_agent_info()` with capabilities (NO keywords)
- [ ] `__init__()` with Gemini model init
- [ ] `_execute_internal()` main logic
- [ ] `_build_sql_expressions()` helper
- [ ] `_plan_queries()` with agent-specific prompt
- [ ] `_is_safe_query()` validation
- [ ] `_execute_query()` with autocommit
- [ ] `_correct_query()` self-correction
- [ ] `_synthesize_insights()` for interpretation
- [ ] Transparency events at each step
- [ ] Return standard AgentResponse structure
- [ ] Import in `__init__.py` to trigger registration
- [ ] Test with orchestrator routing
- [ ] Deploy

---

## REVISION LOG

| Date | Change | Author |
|------|--------|--------|
| 2025-12-03 | Initial architecture document | Claude |
| 2025-12-03 | Implemented Segmentation Agent | Claude |
| 2025-12-03 | Implemented Pattern Recognition Agent | Claude |

