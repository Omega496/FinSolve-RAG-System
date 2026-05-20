"""
Markdown chunking logic for FinSolve RAG.
Implements the chunking strategy from AGENTS.md:
- ### level primary split
- #### level secondary split for long sections
- Atomic tables and diagrams
- Header breadcrumb prepend
- Parent-child chunk pairs
"""

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

# ─── Configuration ─────────────────────────────────────────────────────
TARGET_TOKENS_MIN = 300
TARGET_TOKENS_MAX = 500
CHILD_TOKENS_MAX = 150
PARENT_TOKENS_MAX = 400
TOKENS_PER_CHAR_ESTIMATE = 0.25  # ~4 chars per token (English)

# ─── Patterns ──────────────────────────────────────────────────────────
HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
TABLE_ROW_PATTERN = re.compile(r"^\|.*\|$", re.MULTILINE)
TABLE_SEPARATOR_PATTERN = re.compile(r"^\|[-\s|:]+\|$", re.MULTILINE)
ASCII_DIAGRAM_PATTERN = re.compile(
    r"(?:[\-+|/\\^v><]{3,}|(?:\s{2,}[|/\\^v><]))", re.MULTILINE
)


@dataclass
class Chunk:
    """Represents a document chunk with metadata."""

    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    header_breadcrumb: str = ""
    header_level: int = 0
    header_title: str = ""
    content_type: str = "text"  # text, table, diagram, glossary, hr_record
    chunk_type: str = "child"  # child, parent, atomic
    parent_id: Optional[str] = None
    token_count: int = 0
    source_file: str = ""
    employee_id: Optional[str] = None  # For HR records
    sensitivity: str = "low"  # high, medium, low
    access_roles: list = field(default_factory=list)  # Roles allowed to access


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length."""
    return int(len(text) * TOKENS_PER_CHAR_ESTIMATE)


def parse_headers(content: str) -> list[dict]:
    """
    Parse markdown headers and their positions.

    Returns:
        List of dicts with 'level', 'title', 'start', 'end' keys
    """
    headers = []
    for match in HEADER_PATTERN.finditer(content):
        level = len(match.group(1))
        title = match.group(2).strip()
        headers.append({
            "level": level,
            "title": title,
            "start": match.start(),
            "end": match.end(),
        })

    # Set end positions (header content extends until next header of same/higher level)
    for i, header in enumerate(headers):
        next_header_start = len(content)
        for j in range(i + 1, len(headers)):
            if headers[j]["level"] <= header["level"]:
                next_header_start = headers[j]["start"]
                break
        header["content_end"] = next_header_start

    return headers


def build_breadcrumb(headers: list[dict], current_idx: int) -> str:
    """
    Build header breadcrumb for a given header position.

    Args:
        headers: List of parsed headers
        current_idx: Index of current header in headers list

    Returns:
        Breadcrumb string: [§Parent > §Child > §Grandchild]
    """
    if current_idx < 0 or current_idx >= len(headers):
        return ""

    current_level = headers[current_idx]["level"]
    breadcrumb_parts = []

    # Walk backwards to find ancestor headers
    for i in range(current_idx, -1, -1):
        if headers[i]["level"] < current_level:
            breadcrumb_parts.insert(0, f"§{headers[i]['title']}")
            current_level = headers[i]["level"]

    # Add current header
    breadcrumb_parts.append(f"§{headers[current_idx]['title']}")

    return "[" + " > ".join(breadcrumb_parts) + "]"


def is_table_block(text: str) -> bool:
    """Check if text contains a markdown table."""
    lines = text.strip().split("\n")
    table_rows = sum(1 for line in lines if TABLE_ROW_PATTERN.match(line.strip()))
    return table_rows >= 2  # At least header + separator


def extract_table_block(text: str, start_pos: int) -> tuple[str, int]:
    """
    Extract a complete table block starting from position.

    Returns:
        (table_text, end_position)
    """
    lines = text[start_pos:].split("\n")
    table_lines = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if TABLE_ROW_PATTERN.match(stripped) or TABLE_SEPARATOR_PATTERN.match(stripped):
            table_lines.append(line)
            in_table = True
        elif in_table:
            break  # End of table
        else:
            continue  # Skip non-table lines before table

    table_text = "\n".join(table_lines)
    end_pos = start_pos + len(table_text)
    return table_text, end_pos


def is_ascii_diagram(text: str) -> bool:
    """Check if text contains an ASCII diagram."""
    lines = text.strip().split("\n")
    diagram_lines = sum(1 for line in lines if ASCII_DIAGRAM_PATTERN.search(line))
    return diagram_lines >= 2


def is_appendix_section(title: str) -> bool:
    """Check if a header is an appendix (glossary, contacts, etc.)."""
    title_lower = title.lower()
    return any(keyword in title_lower for keyword in ["glossary", "appendix", "contacts", "references", "acronyms"])


def chunk_markdown(content: str, source_file: str = "") -> list[Chunk]:
    """
    Chunk markdown content according to FinSolve strategy.

    Args:
        content: Raw markdown text
        source_file: Source filename for metadata

    Returns:
        List of Chunk objects with text and preliminary metadata
    """
    headers = parse_headers(content)
    chunks = []

    # Find ### level headers (primary split points)
    h3_headers = [h for h in headers if h["level"] == 3]

    for h3_idx, h3_header in enumerate(h3_headers):
        h3_actual_idx = headers.index(h3_header)
        h3_content = content[h3_header["end"]:h3_header["content_end"]]
        h3_breadcrumb = build_breadcrumb(headers, h3_actual_idx)

        # Check for tables and diagrams in this section
        if is_table_block(h3_content):
            # Atomic table chunk
            table_text, _ = extract_table_block(h3_content, 0)
            chunks.append(Chunk(
                text=f"{h3_breadcrumb}\n\n{table_text}",
                header_breadcrumb=h3_breadcrumb,
                header_level=3,
                header_title=h3_header["title"],
                content_type="table",
                chunk_type="atomic",
                token_count=estimate_tokens(table_text),
                source_file=source_file,
            ))
            continue

        if is_ascii_diagram(h3_content):
            # Atomic diagram chunk
            chunks.append(Chunk(
                text=f"{h3_breadcrumb}\n\n{h3_content.strip()}",
                header_breadcrumb=h3_breadcrumb,
                header_level=3,
                header_title=h3_header["title"],
                content_type="diagram",
                chunk_type="atomic",
                token_count=estimate_tokens(h3_content),
                source_file=source_file,
            ))
            continue

        # Check if this is an appendix section
        if is_appendix_section(h3_header["title"]):
            chunks.append(Chunk(
                text=f"{h3_breadcrumb}\n\n{h3_content.strip()}",
                header_breadcrumb=h3_breadcrumb,
                header_level=3,
                header_title=h3_header["title"],
                content_type="glossary",
                chunk_type="atomic",
                token_count=estimate_tokens(h3_content),
                source_file=source_file,
            ))
            continue

        # Find #### headers within this section
        h4_headers = [
            h for h in headers
            if h["level"] == 4
            and h3_header["end"] <= h["start"] < h3_header["content_end"]
        ]

        if not h4_headers:
            # No subsections — chunk the whole section
            token_count = estimate_tokens(h3_content)
            if token_count > 0:
                # Create parent chunk
                parent_chunk = Chunk(
                    text=f"{h3_breadcrumb}\n\n{h3_content.strip()}",
                    header_breadcrumb=h3_breadcrumb,
                    header_level=3,
                    header_title=h3_header["title"],
                    content_type="text",
                    chunk_type="parent",
                    token_count=token_count,
                    source_file=source_file,
                )
                chunks.append(parent_chunk)

                # If content is long enough, also create child chunk
                if token_count >= CHILD_TOKENS_MAX:
                    child_chunk = Chunk(
                        text=f"{h3_breadcrumb}\n\n{h3_content.strip()[:int(CHILD_TOKENS_MAX / TOKENS_PER_CHAR_ESTIMATE)]}",
                        header_breadcrumb=h3_breadcrumb,
                        header_level=3,
                        header_title=h3_header["title"],
                        content_type="text",
                        chunk_type="child",
                        parent_id=parent_chunk.chunk_id,
                        token_count=CHILD_TOKENS_MAX,
                        source_file=source_file,
                    )
                    chunks.append(child_chunk)
        else:
            # Has subsections — process #### headers
            parent_content_parts = []
            child_chunks_to_merge = []

            for h4_idx, h4_header in enumerate(h4_headers):
                h4_actual_idx = headers.index(h4_header)
                h4_content = content[h4_header["end"]:h4_header["content_end"]]
                h4_breadcrumb = build_breadcrumb(headers, h4_actual_idx)
                h4_tokens = estimate_tokens(h4_content)

                # Check for atomic content in #### section
                if is_table_block(h4_content):
                    table_text, _ = extract_table_block(h4_content, 0)
                    chunks.append(Chunk(
                        text=f"{h4_breadcrumb}\n\n{table_text}",
                        header_breadcrumb=h4_breadcrumb,
                        header_level=4,
                        header_title=h4_header["title"],
                        content_type="table",
                        chunk_type="atomic",
                        token_count=estimate_tokens(table_text),
                        source_file=source_file,
                    ))
                    parent_content_parts.append(h4_content)
                    continue

                if is_ascii_diagram(h4_content):
                    chunks.append(Chunk(
                        text=f"{h4_breadcrumb}\n\n{h4_content.strip()}",
                        header_breadcrumb=h4_breadcrumb,
                        header_level=4,
                        header_title=h4_header["title"],
                        content_type="diagram",
                        chunk_type="atomic",
                        token_count=estimate_tokens(h4_content),
                        source_file=source_file,
                    ))
                    parent_content_parts.append(h4_content)
                    continue

                if is_appendix_section(h4_header["title"]):
                    chunks.append(Chunk(
                        text=f"{h4_breadcrumb}\n\n{h4_content.strip()}",
                        header_breadcrumb=h4_breadcrumb,
                        header_level=4,
                        header_title=h4_header["title"],
                        content_type="glossary",
                        chunk_type="atomic",
                        token_count=estimate_tokens(h4_content),
                        source_file=source_file,
                    ))
                    parent_content_parts.append(h4_content)
                    continue

                # Short section — merge with siblings
                if h4_tokens < CHILD_TOKENS_MAX:
                    child_chunks_to_merge.append({
                        "text": h4_content,
                        "breadcrumb": h4_breadcrumb,
                        "title": h4_header["title"],
                        "tokens": h4_tokens,
                    })
                    parent_content_parts.append(h4_content)
                    continue

                # Normal section — create child chunk
                parent_content_parts.append(h4_content)

                # Create child chunk
                child_chunk = Chunk(
                    text=f"{h4_breadcrumb}\n\n{h4_content.strip()}",
                    header_breadcrumb=h4_breadcrumb,
                    header_level=4,
                    header_title=h4_header["title"],
                    content_type="text",
                    chunk_type="child",
                    token_count=h4_tokens,
                    source_file=source_file,
                )
                chunks.append(child_chunk)

            # Merge short #### sections
            if child_chunks_to_merge:
                merged_text = "\n\n".join(
                    f"{item['breadcrumb']}\n\n{item['text'].strip()}"
                    for item in child_chunks_to_merge
                )
                merged_tokens = sum(item["tokens"] for item in child_chunks_to_merge)

                if merged_tokens >= CHILD_TOKENS_MAX:
                    merged_chunk = Chunk(
                        text=f"{h3_breadcrumb}\n\n{merged_text}",
                        header_breadcrumb=h3_breadcrumb,
                        header_level=3,
                        header_title=h3_header["title"],
                        content_type="text",
                        chunk_type="child",
                        token_count=merged_tokens,
                        source_file=source_file,
                    )
                    chunks.append(merged_chunk)

            # Create parent chunk from all #### content
            parent_text = "\n\n".join(parent_content_parts).strip()
            parent_tokens = estimate_tokens(parent_text)

            if parent_tokens > 0:
                parent_chunk = Chunk(
                    text=f"{h3_breadcrumb}\n\n{parent_text}",
                    header_breadcrumb=h3_breadcrumb,
                    header_level=3,
                    header_title=h3_header["title"],
                    content_type="text",
                    chunk_type="parent",
                    token_count=parent_tokens,
                    source_file=source_file,
                )
                chunks.append(parent_chunk)

                # Link child chunks to parent
                for chunk in chunks:
                    if chunk.chunk_type == "child" and chunk.parent_id is None:
                        chunk.parent_id = parent_chunk.chunk_id

    return chunks


def chunk_excel_row(row_data: dict, source_file: str = "") -> Chunk:
    """
    Chunk a single Excel row as an atomic chunk.

    Args:
        row_data: Dictionary of column_name: value pairs
        source_file: Source filename for metadata

    Returns:
        Chunk object for the row
    """
    # Extract employee_id if present (try common field names)
    employee_id = None
    for id_field in ["employee_id", "Employee ID", "emp_id", "ID", "id"]:
        if id_field in row_data and row_data[id_field] is not None:
            employee_id = str(row_data[id_field])
            break

    # Format row as readable text
    text_parts = [f"{key}: {value}" for key, value in row_data.items() if value is not None]
    text = "Employee Record: [" + ", ".join(text_parts) + "]"

    return Chunk(
        text=text,
        header_breadcrumb="",
        header_level=0,
        header_title="",
        content_type="hr_record",
        chunk_type="atomic",
        parent_id=None,
        token_count=estimate_tokens(text),
        source_file=source_file,
        employee_id=employee_id,
        sensitivity="high",
        access_roles=["hr", "c_suite"],
    )


def chunk_excel_file(file_path: str | Path, source_file: str = "") -> list[Chunk]:
    """
    Read Excel file and create one chunk per row (one chunk per employee record).

    Args:
        file_path: Path to Excel file (.xlsx, .xls)
        source_file: Source filename for metadata (defaults to file_path name)

    Returns:
        List of Chunk objects — one per row, never combined
    """
    file_path = Path(file_path)
    if not source_file:
        source_file = file_path.name

    # Read Excel using pandas + openpyxl
    df = pd.read_excel(file_path, engine="openpyxl")

    # Clean column names (strip whitespace)
    df.columns = df.columns.str.strip()

    chunks = []
    for _, row in df.iterrows():
        # Convert row to dict, drop NaN values
        row_data = row.dropna().to_dict()

        # Create one chunk per row — never combine
        chunk = chunk_excel_row(row_data, source_file=source_file)
        chunks.append(chunk)

    return chunks
