"""
Qdrant payload filter builder per role.

Enforces RBAC at the retrieval layer — filters are applied server-side
before any chunks reach the LLM. Client cannot override or modify.

RBAC Matrix (from AGNNTS.md):
┌─────────────────────────────────┬─────────────┬─────────┬──────────┬────┬─────────┬──────────┐
│ Document                        │ Engineering │ Finance │ Marketing│ HR │ C-Suite │ Employee │
├─────────────────────────────────┼─────────────┼─────────┼──────────┼────┼─────────┼──────────┤
│ Engineering Architecture        │ ✅          │ ❌      │ ❌       │ ❌ │ ✅      │ ❌       │
│ Marketing Q1-Q4 + Summary       │ ❌          │ ❌      │ ✅       │ ❌ │ ✅      │ ❌       │
│   (campaign content)            │             │         │          │    │         │          │
│ Marketing Q1-Q4 (expense only)  │ ❌          │ ✅      │ ✅       │ ❌ │ ✅      │ ❌       │
│ Finance Quarterly + Summary     │ ❌          │ ✅      │ ❌       │ ❌ │ ✅      │ ❌       │
│ Employee Handbook               │ ✅          │ ✅      │ ✅       │ ✅ │ ✅      │ ✅       │
│ HR Employee Dataset             │ ❌          │ ❌      │ ❌       │ ✅ │ ✅      │ ❌       │
└─────────────────────────────────┴─────────────┴─────────┴──────────┴────┴─────────┴──────────┘

Finance special rule: When accessing marketing department chunks, finance
users can ONLY see expense content_type — not campaign content.
"""

from qdrant_client.models import Filter, FieldCondition, MatchValue


# ─── Valid Roles ──────────────────────────────────────────────────────
VALID_ROLES = frozenset({
    "engineering",
    "finance",
    "marketing",
    "hr",
    "c_suite",
    "employee",
})

# Non-marketing departments (used for finance role restriction)
_NON_MARKETING_DEPARTMENTS = ("engineering", "finance", "hr", "general")


def build_rbac_filter(role: str) -> Filter:
    """
    Build a Qdrant payload filter that enforces RBAC for the given role.

    The filter applies three rules simultaneously:
        1. The user's role must be present in the chunk's access_roles list.
           (access_roles metadata is populated during ingestion based on the
           RBAC matrix — this single check encodes all role-to-document perms.)
        2. Only child chunks are returned (chunk_type == "child").
           Parent chunks are fetched separately in the parent_child_swap node.
        3. For finance role: marketing department chunks are restricted to
           content_type == "expense" only (not campaign content).

    Args:
        role: The authenticated user's role string.
              Must be one of: engineering, finance, marketing, hr, c_suite, employee

    Returns:
        Qdrant Filter object to pass to client.scroll() or client.search()

    Raises:
        ValueError: If role is not a valid RBAC role.
    """
    if role not in VALID_ROLES:
        raise ValueError(
            f"Invalid role: {role!r}. "
            f"Must be one of: {', '.join(sorted(VALID_ROLES))}"
        )

    # ── Rule 1: Role must be in chunk's access_roles list ──────────
    role_filter = FieldCondition(
        key="access_roles",
        match=MatchValue(value=role),
    )

    # ── Rule 2: Only retrieve child chunks ─────────────────────────
    child_filter = FieldCondition(
        key="chunk_type",
        match=MatchValue(value="child"),
    )

    # ── Rule 3: Finance → marketing expense-only restriction ───────
    if role == "finance":
        return _build_finance_filter(role_filter, child_filter)

    # ── Standard filter for all other roles ─────────────────────────
    return Filter(must=[role_filter, child_filter])


def _build_finance_filter(
    role_filter: FieldCondition,
    child_filter: FieldCondition,
) -> Filter:
    """
    Build filter for finance role with marketing expense-only restriction.

    Finance users can access chunks where:
        (role in access_roles) AND (chunk_type = child) AND
        (
            department in [engineering, finance, hr, general]
            OR
            (department = marketing AND content_type = expense)
        )

    Expressed in Qdrant using should (minimum 1) for the OR logic:
        must: [role_filter, child_filter]
        should (min 1): [dept=engineering, dept=finance, dept=hr,
                         dept=general, (dept=marketing AND type=expense)]

    Since Qdrant doesn't support != directly, we enumerate the allowed
    non-marketing departments as positive conditions.
    """
    # Branches for allowed department access (any content_type)
    dept_branches = [
        Filter(must=[FieldCondition(key="department", match=MatchValue(value=dept))])
        for dept in _NON_MARKETING_DEPARTMENTS
    ]

    # Branch for marketing department: expense content_type only
    marketing_expense_branch = Filter(
        must=[
            FieldCondition(key="department", match=MatchValue(value="marketing")),
            FieldCondition(key="content_type", match=MatchValue(value="expense")),
        ]
    )

    return Filter(
        must=[role_filter, child_filter],
        should=[*dept_branches, marketing_expense_branch],
    )
