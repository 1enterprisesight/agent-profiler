"""
Schema Utilities - Dynamic Schema Context for All Agents

This module provides shared functions for retrieving typed schema context
that all agents can use to understand the user's data structure.

Key principle:
- NUMERIC/DATE fields → SQL Analytics (math, never LIKE/regex)
- TEXT fields → Semantic Search (meaning, never math)

IMPORTANT: NO HARDCODED SCHEMAS. Everything is discovered from the actual data.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import re
from decimal import Decimal, InvalidOperation


async def get_schema_context(db: AsyncSession, user_id: str) -> Dict[str, Any]:
    """
    Dynamically discover schema from user's actual data.

    NO HARDCODING - queries the clients table to discover all fields
    in custom_data and core_data JSONB columns, then infers their types.

    Returns:
        dict with:
            - numeric_fields: list of {name, location, samples} for SQL Analytics
            - date_fields: list of {name, location, samples} for SQL Analytics
            - text_fields: list of {name, location, samples} for Semantic Search
            - boolean_fields: list of {name, location, samples} for SQL Analytics
            - all_fields: dict of field_name -> full field info
            - has_schema: bool indicating if any fields were discovered
    """
    schema = {
        "numeric_fields": [],
        "date_fields": [],
        "text_fields": [],
        "boolean_fields": [],
        "all_fields": {},
        "has_schema": False
    }

    # Discover all custom_data fields
    custom_fields_query = text("""
        SELECT DISTINCT jsonb_object_keys(custom_data) as field_name
        FROM clients
        WHERE user_id = :user_id
          AND custom_data IS NOT NULL
          AND custom_data != '{}'::jsonb
    """)

    try:
        result = await db.execute(custom_fields_query, {"user_id": user_id})
        custom_fields = [row[0] for row in result.fetchall()]
    except Exception:
        custom_fields = []

    # Discover all core_data fields
    core_fields_query = text("""
        SELECT DISTINCT jsonb_object_keys(core_data) as field_name
        FROM clients
        WHERE user_id = :user_id
          AND core_data IS NOT NULL
          AND core_data != '{}'::jsonb
    """)

    try:
        result = await db.execute(core_fields_query, {"user_id": user_id})
        core_fields = [row[0] for row in result.fetchall()]
    except Exception:
        core_fields = []

    # Analyze each custom_data field
    for field_name in custom_fields:
        field_info = await _analyze_field(db, user_id, field_name, "custom_data")
        schema["all_fields"][field_name] = field_info
        _categorize_field(schema, field_info)

    # Analyze each core_data field
    for field_name in core_fields:
        field_info = await _analyze_field(db, user_id, field_name, "core_data")
        schema["all_fields"][field_name] = field_info
        _categorize_field(schema, field_info)

    schema["has_schema"] = len(schema["all_fields"]) > 0
    return schema


async def _analyze_field(
    db: AsyncSession,
    user_id: str,
    field_name: str,
    location: str
) -> Dict[str, Any]:
    """
    Analyze a field by sampling values and inferring its type.
    """
    # Sample values from the field
    sample_query = text(f"""
        SELECT {location}->>:field_name as val
        FROM clients
        WHERE user_id = :user_id
          AND {location}->>:field_name IS NOT NULL
          AND {location}->>:field_name != ''
        LIMIT 50
    """)

    try:
        result = await db.execute(sample_query, {"field_name": field_name, "user_id": user_id})
        samples = [row[0] for row in result.fetchall() if row[0]]
    except Exception:
        samples = []

    # Infer type from samples
    field_type = _infer_type(samples)

    return {
        "name": field_name,
        "location": location,
        "type": field_type,
        "samples": samples[:5],
        "access_path": f"{location}->>'{field_name}'"
    }


def _infer_type(samples: List[str]) -> str:
    """
    Infer data type from sample values.
    Uses 80% threshold - if 80%+ of samples match a type, use that type.
    """
    if not samples:
        return "text"

    numeric_count = 0
    date_count = 0
    boolean_count = 0

    for sample in samples:
        if not sample or not str(sample).strip():
            continue

        sample_str = str(sample).strip()

        # Check boolean
        if sample_str.lower() in ('true', 'false', 'yes', 'no', '0', '1', 't', 'f', 'y', 'n'):
            boolean_count += 1
            continue

        # Check numeric
        if _is_numeric(sample_str):
            numeric_count += 1
            continue

        # Check date
        if _is_date(sample_str):
            date_count += 1
            continue

    total = len([s for s in samples if s and str(s).strip()])
    if total == 0:
        return "text"

    threshold = 0.8

    if numeric_count / total >= threshold:
        return "numeric"
    if date_count / total >= threshold:
        return "date"
    if boolean_count / total >= threshold:
        return "boolean"

    return "text"


def _is_numeric(value: str) -> bool:
    """Check if value is numeric."""
    if not value:
        return False
    cleaned = value.replace(",", "").replace("$", "").replace("%", "").replace(" ", "")
    try:
        Decimal(cleaned)
        return True
    except (InvalidOperation, ValueError):
        pass
    try:
        float(cleaned)
        return True
    except ValueError:
        return False


def _is_date(value: str) -> bool:
    """Check if value looks like a date."""
    if not value or len(value) < 6:
        return False
    if value.isdigit() and len(value) <= 4:
        return False

    date_patterns = [
        r'^\d{4}-\d{2}-\d{2}',
        r'^\d{2}/\d{2}/\d{4}',
        r'^\d{2}-\d{2}-\d{4}',
        r'^\d{1,2}/\d{1,2}/\d{2,4}',
    ]

    for pattern in date_patterns:
        if re.match(pattern, value):
            return True
    return False


def _categorize_field(schema: Dict, field_info: Dict):
    """Add field to the appropriate category list."""
    field_type = field_info.get("type", "text")

    if field_type == "numeric":
        schema["numeric_fields"].append(field_info)
    elif field_type == "date":
        schema["date_fields"].append(field_info)
    elif field_type == "boolean":
        schema["boolean_fields"].append(field_info)
    else:
        schema["text_fields"].append(field_info)


def build_sql_schema_description(schema_context: Dict[str, Any]) -> str:
    """
    Build schema description for SQL query generation.
    ONLY includes fields discovered from the actual data.
    """
    lines = ["Table: clients"]
    lines.append("Base columns: id (UUID), user_id (VARCHAR - ALWAYS filter by this), client_name, contact_email, company_name, source_type, created_at, synced_at")

    if not schema_context.get("has_schema"):
        lines.append("\nNo custom fields discovered yet. Query base columns only.")
        return "\n".join(lines)

    # Numeric fields - discovered from data
    if schema_context.get("numeric_fields"):
        lines.append("\nNumeric fields (use for math/aggregation):")
        for field in schema_context["numeric_fields"]:
            samples_str = ", ".join(str(s) for s in (field.get("samples") or [])[:3])
            access = field['access_path']
            if samples_str:
                lines.append(f"  - ({access})::numeric  (examples: {samples_str})")
            else:
                lines.append(f"  - ({access})::numeric")

    # Date fields
    if schema_context.get("date_fields"):
        lines.append("\nDate fields (use for date filtering):")
        for field in schema_context["date_fields"]:
            lines.append(f"  - {field['access_path']}")

    # Boolean fields
    if schema_context.get("boolean_fields"):
        lines.append("\nBoolean fields:")
        for field in schema_context["boolean_fields"]:
            lines.append(f"  - {field['access_path']}")

    # Text fields - mention they exist but shouldn't be used with LIKE
    if schema_context.get("text_fields"):
        text_names = [f["name"] for f in schema_context["text_fields"]]
        lines.append(f"\nText fields (DO NOT query with SQL - use Semantic Search): {', '.join(text_names)}")

    lines.append("\nCRITICAL: Never use LIKE/ILIKE. Route text searches to Semantic Search agent.")

    return "\n".join(lines)


def build_semantic_search_fields(schema_context: Dict[str, Any]) -> List[str]:
    """
    Get list of text field names for semantic search.
    Returns ONLY fields discovered from the actual data.
    """
    return [field["name"] for field in schema_context.get("text_fields", [])]


def get_field_access_path(schema_context: Dict[str, Any], field_name: str) -> Optional[str]:
    """Get the SQL access path for a field name."""
    if field_name in schema_context.get("all_fields", {}):
        return schema_context["all_fields"][field_name].get("access_path")
    return None


def get_field_type(schema_context: Dict[str, Any], field_name: str) -> Optional[str]:
    """Get the data type for a field name."""
    if field_name in schema_context.get("all_fields", {}):
        return schema_context["all_fields"][field_name].get("type")
    return None
