"""
LLM + rule-based metadata assignment.
Uses Nemotron via Ollama to assign metadata schema from AGENTS.md.
"""

import json
import os
from typing import Optional

import httpx

# ─── Configuration ─────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "nemotron-3-super:cloud")

# ─── Valid Metadata Values ─────────────────────────────────────────────
VALID_DEPARTMENTS = ["engineering", "finance", "marketing", "hr", "general"]
VALID_CONTENT_TYPES = [
    "technical", "financial", "expense", "campaign",
    "hr_record", "policy", "summary", "diagram", "glossary"
]
VALID_CHUNK_TYPES = ["child", "parent", "atomic"]
VALID_SENSITIVITY = ["high", "medium", "low"]
VALID_QUARTERS = ["Q1", "Q2", "Q3", "Q4", "annual"]
VALID_YEARS = ["2024", "2025", None]
VALID_ACCESS_ROLES = ["engineering", "finance", "marketing", "hr", "c_suite", "employee"]

# ─── Metadata Prompt ──────────────────────────────────────────────────
METADATA_PROMPT = """You are a metadata tagger for FinSolve's internal document system.

Analyze the following text chunk and assign metadata. Return ONLY valid JSON — no preamble, no markdown backticks, no explanation.

METADATA SCHEMA (return exactly these fields):
{{
  "doc_id": "string — document identifier (filename or descriptive ID)",
  "department": "engineering | finance | marketing | hr | general",
  "content_type": "technical | financial | expense | campaign | hr_record | policy | summary | diagram | glossary",
  "access_roles": ["list", "of", "permitted", "roles"],
  "quarter": "Q1 | Q2 | Q3 | Q4 | annual | null",
  "year": "2024 | 2025 | null",
  "sensitivity": "high | medium | low"
}}

VALID VALUES (use ONLY these — no hallucination):
- department: {departments}
- content_type: {content_types}
- access_roles: {access_roles}
- quarter: {quarters}
- year: {years}
- sensitivity: {sensitivity}

ACCESS ROLE RULES:
- Engineering Architecture docs: [engineering, c_suite]
- Marketing docs: [marketing, c_suite]
- Marketing expense chunks: [finance, marketing, c_suite]
- Finance docs: [finance, c_suite]
- Employee Handbook: [engineering, finance, marketing, hr, c_suite, employee]
- HR Employee Dataset: [hr, c_suite]

TEXT CHUNK:
\"\"\"
{chunk_text}
\"\"\"

SOURCE FILE: {source_file}
HEADER BREADCRUMB: {header_breadcrumb}

Return ONLY the JSON object:"""


async def tag_metadata(
    chunk_text: str,
    source_file: str = "",
    header_breadcrumb: str = "",
    preliminary_metadata: Optional[dict] = None,
) -> dict:
    """
    Call Nemotron via Ollama to assign metadata to a chunk.

    Args:
        chunk_text: Raw text content of the chunk
        source_file: Source filename for context
        header_breadcrumb: Header breadcrumb for context
        preliminary_metadata: Pre-existing metadata to merge (rule-based)

    Returns:
        Metadata dict matching AGENTS.md schema
    """
    # Format prompt with chunk info
    prompt = METADATA_PROMPT.format(
        departments=", ".join(VALID_DEPARTMENTS),
        content_types=", ".join(VALID_CONTENT_TYPES),
        access_roles=", ".join(VALID_ACCESS_ROLES),
        quarters=", ".join([q for q in VALID_QUARTERS if q]),
        years=", ".join([str(y) for y in VALID_YEARS if y]),
        sensitivity=", ".join(VALID_SENSITIVITY),
        chunk_text=chunk_text[:2000],  # Truncate to avoid token limits
        source_file=source_file,
        header_breadcrumb=header_breadcrumb,
    )

    # Call Ollama API
    metadata = await _call_ollama(prompt)

    # Merge with preliminary metadata if provided
    if preliminary_metadata:
        metadata = _merge_metadata(preliminary_metadata, metadata)

    # Validate and clean metadata
    metadata = _validate_metadata(metadata)

    return metadata


async def _call_ollama(prompt: str) -> dict:
    """
    Call Ollama API and parse JSON response.

    Args:
        prompt: Formatted prompt string

    Returns:
        Parsed metadata dict
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,  # Low temp for consistent output
            "num_predict": 500,
        }
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

            result = response.json()
            raw_output = result.get("response", "")

            # Parse JSON from response
            return _parse_json_response(raw_output)

    except httpx.HTTPStatusError as e:
        print(f"Ollama API error: {e}")
        return _get_default_metadata()
    except Exception as e:
        print(f"Metadata tagging error: {e}")
        return _get_default_metadata()


def _parse_json_response(raw_output: str) -> dict:
    """
    Safely parse JSON from LLM response.

    Args:
        raw_output: Raw text from LLM

    Returns:
        Parsed dict or default metadata on failure
    """
    # Clean common LLM output issues
    cleaned = raw_output.strip()

    # Remove markdown code blocks if present
    if cleaned.startswith("```"):
        # Find the first { and last }
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start != -1 and end > start:
            cleaned = cleaned[start:end]

    # Try to extract JSON object
    try:
        # Find JSON object boundaries
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1

        if start != -1 and end > start:
            json_str = cleaned[start:end]
            return json.loads(json_str)
        else:
            # Try parsing the whole string
            return json.loads(cleaned)

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw output: {raw_output[:200]}")
        return _get_default_metadata()


def _merge_metadata(preliminary: dict, llm_metadata: dict) -> dict:
    """
    Merge preliminary (rule-based) metadata with LLM-assigned metadata.
    LLM values take precedence, but preliminary fills gaps.

    Args:
        preliminary: Rule-based metadata
        llm_metadata: LLM-assigned metadata

    Returns:
        Merged metadata dict
    """
    merged = preliminary.copy()

    for key, value in llm_metadata.items():
        if value is not None and value != "":
            merged[key] = value

    return merged


def _validate_metadata(metadata: dict) -> dict:
    """
    Validate metadata values against allowed enums.

    Args:
        metadata: Raw metadata dict

    Returns:
        Validated and cleaned metadata
    """
    validated = metadata.copy()

    # Validate department
    if validated.get("department") not in VALID_DEPARTMENTS:
        validated["department"] = "general"

    # Validate content_type
    if validated.get("content_type") not in VALID_CONTENT_TYPES:
        validated["content_type"] = "text"

    # Validate access_roles (must be list of valid roles)
    roles = validated.get("access_roles", [])
    if not isinstance(roles, list):
        roles = [roles]
    validated["access_roles"] = [r for r in roles if r in VALID_ACCESS_ROLES]
    if not validated["access_roles"]:
        validated["access_roles"] = ["employee"]

    # Validate quarter
    if validated.get("quarter") not in VALID_QUARTERS + [None]:
        validated["quarter"] = None

    # Validate year
    if validated.get("year") not in VALID_YEARS:
        validated["year"] = None

    # Validate sensitivity
    if validated.get("sensitivity") not in VALID_SENSITIVITY:
        validated["sensitivity"] = "low"

    # Ensure required string fields exist
    for field in ["doc_id", "header_breadcrumb", "source_file"]:
        if not validated.get(field):
            validated[field] = ""

    return validated


def _get_default_metadata() -> dict:
    """
    Return safe default metadata when LLM fails.

    Returns:
        Default metadata dict
    """
    return {
        "doc_id": "",
        "department": "general",
        "content_type": "text",
        "access_roles": ["employee"],
        "quarter": None,
        "year": None,
        "sensitivity": "low",
    }
