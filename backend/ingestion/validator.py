"""
Rule-based metadata validation layer.
Safety net that enforces hard rules regardless of LLM output.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

# ─── Valid Enum Values ─────────────────────────────────────────────────
VALID_DEPARTMENTS = {"engineering", "finance", "marketing", "hr", "general"}
VALID_CONTENT_TYPES = {
    "technical", "financial", "expense", "campaign",
    "hr_record", "policy", "summary", "diagram", "glossary"
}
VALID_CHUNK_TYPES = {"child", "parent", "atomic"}
VALID_SENSITIVITY = {"high", "medium", "low"}
VALID_QUARTERS = {"Q1", "Q2", "Q3", "Q4", "annual", None}
VALID_ACCESS_ROLES = {"engineering", "finance", "marketing", "hr", "c_suite", "employee"}

# ─── Salary/Payroll Keywords ──────────────────────────────────────────
SALARY_KEYWORDS = re.compile(
    r"\b(?:salary|payroll|compensation|wage|bonus|stipend|remuneration|"
    r"incentive|commission|overtime|deduction|tax\s*exemption|"
    r"provident\s*fund|pf|esi|gratuity|pension|reimbursement)\b",
    re.IGNORECASE
)


@dataclass
class ValidationResult:
    """Result of metadata validation."""

    metadata: dict = field(default_factory=dict)
    overrides: list = field(default_factory=list)  # List of override descriptions
    flags: list = field(default_factory=list)  # List of review flags
    is_valid: bool = True


def validate_metadata(metadata: dict, chunk_text: str = "") -> ValidationResult:
    """
    Validate and enforce metadata rules.

    Args:
        metadata: Metadata dict from LLM or rule-based tagger
        chunk_text: Raw chunk text for keyword detection

    Returns:
        ValidationResult with validated metadata, overrides, and flags
    """
    result = ValidationResult(metadata=metadata.copy())

    # Step 1: Check access_roles is never empty
    _ensure_access_roles(result)

    # Step 2: Enforce salary/payroll keyword rules
    _enforce_salary_rules(result, chunk_text)

    # Step 3: Enforce hr_record content_type rules
    _enforce_hr_record_rules(result)

    # Step 4: Enforce technical content_type rules
    _enforce_technical_rules(result)

    # Step 5: Enforce financial content_type rules
    _enforce_financial_rules(result)

    # Step 6: Flag low-confidence chunks
    _flag_low_confidence(result)

    return result


def _ensure_access_roles(result: ValidationResult) -> None:
    """Check that access_roles is never empty."""
    roles = result.metadata.get("access_roles", [])

    if not roles or not isinstance(roles, list) or len(roles) == 0:
        result.metadata["access_roles"] = ["employee"]
        result.overrides.append(
            "access_roles was empty — set to [employee] (most restrictive)"
        )


def _enforce_salary_rules(result: ValidationResult, chunk_text: str) -> None:
    """
    Enforce hard rules for salary/payroll content.
    Any chunk containing salary keywords must be restricted to [hr, c_suite].
    """
    if not chunk_text:
        return

    if SALARY_KEYWORDS.search(chunk_text):
        current_roles = set(result.metadata.get("access_roles", []))
        required_roles = {"hr", "c_suite"}

        if not required_roles.issubset(current_roles):
            # Override: restrict to hr + c_suite only
            result.metadata["access_roles"] = ["hr", "c_suite"]
            result.metadata["sensitivity"] = "high"
            result.overrides.append(
                f"Salary/payroll keyword detected — access_roles restricted to [hr, c_suite], "
                f"sensitivity set to high (was: {list(current_roles)})"
            )


def _enforce_hr_record_rules(result: ValidationResult) -> None:
    """Enforce that hr_record content_type always maps to [hr, c_suite]."""
    if result.metadata.get("content_type") == "hr_record":
        current_roles = set(result.metadata.get("access_roles", []))
        required_roles = {"hr", "c_suite"}

        if not required_roles.issubset(current_roles):
            result.metadata["access_roles"] = ["hr", "c_suite"]
            result.overrides.append(
                f"hr_record content_type requires access_roles [hr, c_suite] — "
                f"overrode from {list(current_roles)}"
            )

        # HR records are always high sensitivity
        if result.metadata.get("sensitivity") != "high":
            result.metadata["sensitivity"] = "high"
            result.overrides.append(
                "hr_record content_type requires sensitivity=high"
            )


def _enforce_technical_rules(result: ValidationResult) -> None:
    """Enforce that technical content_type always includes engineering."""
    if result.metadata.get("content_type") == "technical":
        current_roles = set(result.metadata.get("access_roles", []))

        if "engineering" not in current_roles:
            result.metadata["access_roles"] = list(current_roles | {"engineering"})
            result.overrides.append(
                f"technical content_type requires engineering in access_roles — "
                f"added engineering to {list(current_roles)}"
            )


def _enforce_financial_rules(result: ValidationResult) -> None:
    """Enforce that financial content_type always includes finance and c_suite."""
    if result.metadata.get("content_type") == "financial":
        current_roles = set(result.metadata.get("access_roles", []))
        required_roles = {"finance", "c_suite"}

        missing = required_roles - current_roles
        if missing:
            result.metadata["access_roles"] = list(current_roles | required_roles)
            result.overrides.append(
                f"financial content_type requires finance + c_suite in access_roles — "
                f"added {list(missing)} to {list(current_roles)}"
            )


def _flag_low_confidence(result: ValidationResult) -> None:
    """Flag chunks where LLM confidence seems low."""
    metadata = result.metadata

    # Check for missing required fields
    required_fields = ["doc_id", "department", "content_type", "access_roles"]
    for field in required_fields:
        if not metadata.get(field):
            result.flags.append(f"Missing required field: {field}")
            result.is_valid = False

    # Check for invalid enum values
    if metadata.get("department") and metadata["department"] not in VALID_DEPARTMENTS:
        result.flags.append(f"Invalid department: {metadata['department']}")
        result.is_valid = False

    if metadata.get("content_type") and metadata["content_type"] not in VALID_CONTENT_TYPES:
        result.flags.append(f"Invalid content_type: {metadata['content_type']}")
        result.is_valid = False

    if metadata.get("chunk_type") and metadata["chunk_type"] not in VALID_CHUNK_TYPES:
        result.flags.append(f"Invalid chunk_type: {metadata['chunk_type']}")
        result.is_valid = False

    if metadata.get("sensitivity") and metadata["sensitivity"] not in VALID_SENSITIVITY:
        result.flags.append(f"Invalid sensitivity: {metadata['sensitivity']}")
        result.is_valid = False

    if metadata.get("quarter") and metadata["quarter"] not in VALID_QUARTERS:
        result.flags.append(f"Invalid quarter: {metadata['quarter']}")
        result.is_valid = False

    # Check access_roles is a list of valid values
    roles = metadata.get("access_roles", [])
    if isinstance(roles, list):
        invalid_roles = [r for r in roles if r not in VALID_ACCESS_ROLES]
        if invalid_roles:
            result.flags.append(f"Invalid access_roles: {invalid_roles}")
            result.is_valid = False


def apply_defaults(metadata: dict) -> dict:
    """
    Apply safe defaults for missing fields.

    Args:
        metadata: Metadata dict with possible missing fields

    Returns:
        Metadata dict with defaults applied
    """
    defaults = {
        "doc_id": "",
        "department": "general",
        "content_type": "text",
        "access_roles": ["employee"],
        "quarter": None,
        "year": None,
        "sensitivity": "low",
        "chunk_type": "atomic",
        "parent_id": None,
        "header_breadcrumb": "",
        "source_file": "",
    }

    result = metadata.copy()
    for key, default_value in defaults.items():
        if key not in result or result[key] is None:
            result[key] = default_value

    return result
