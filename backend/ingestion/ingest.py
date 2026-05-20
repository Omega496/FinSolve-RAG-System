"""
Main ingestion pipeline runner.
Routes files to chunkers, tags metadata, validates, encodes, and upserts to Qdrant.

Usage:
    python -m ingestion.ingest --data-dir ./data/documents
"""

import argparse
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from qdrant_client.models import PointStruct

from .chunker import Chunk, chunk_excel_file, chunk_markdown
from .embedder import encode_both
from .metadata_tagger import tag_metadata
from .validator import ValidationResult, apply_defaults, validate_metadata
from ..retrieval.qdrant_client import ensure_collection, get_qdrant_client

# ─── Configuration ─────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".md", ".xlsx"}
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "finsolve_chunks")


async def ingest_directory(data_dir: str | Path) -> None:
    """
    Ingest all supported files from a directory.

    Args:
        data_dir: Path to directory containing source documents
    """
    data_dir = Path(data_dir)

    if not data_dir.exists():
        print(f"Error: Directory not found: {data_dir}")
        sys.exit(1)

    # Ensure Qdrant collection exists
    ensure_collection()
    client = get_qdrant_client()

    # Find all supported files
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(data_dir.rglob(f"*{ext}"))

    if not files:
        print(f"No supported files found in {data_dir}")
        print(f"Supported extensions: {SUPPORTED_EXTENSIONS}")
        return

    print(f"\n{'='*60}")
    print(f"FinSolve Document Ingestion Pipeline")
    print(f"{'='*60}")
    print(f"Source directory: {data_dir}")
    print(f"Files found: {len(files)}")
    print(f"{'='*60}\n")

    # Track statistics
    total_chunks = 0
    department_counts = Counter()
    role_counts = Counter()
    override_count = 0

    # Process each file
    for file_path in sorted(files):
        print(f"\n📄 Processing: {file_path.name}")
        print("-" * 40)

        # Route to correct chunker
        chunks = _chunk_file(file_path)
        print(f"   Chunks created: {len(chunks)}")

        if not chunks:
            continue

        # Process each chunk
        file_overrides = 0
        points_to_upsert = []

        for i, chunk in enumerate(chunks):
            # Step 1: Run metadata tagger (LLM)
            metadata = await tag_metadata(
                chunk_text=chunk.text,
                source_file=chunk.source_file,
                header_breadcrumb=chunk.header_breadcrumb,
                preliminary_metadata={
                    "content_type": chunk.content_type,
                    "chunk_type": chunk.chunk_type,
                    "parent_id": chunk.parent_id,
                    "header_breadcrumb": chunk.header_breadcrumb,
                    "source_file": chunk.source_file,
                    "employee_id": chunk.employee_id,
                    "sensitivity": chunk.sensitivity,
                    "access_roles": chunk.access_roles,
                },
            )

            # Step 2: Run validator (rule-based safety net)
            validation_result = validate_metadata(metadata, chunk.text)

            if validation_result.overrides:
                file_overrides += len(validation_result.overrides)
                for override in validation_result.overrides:
                    print(f"   ⚠️  Override: {override}")

            if validation_result.flags:
                for flag in validation_result.flags:
                    print(f"   🚩 Flag: {flag}")

            # Apply defaults for any remaining missing fields
            final_metadata = apply_defaults(validation_result.metadata)

            # Step 3: Encode with BGE-M3 (both dense and sparse)
            vectors = encode_both([chunk.text])

            # Step 4: Prepare Qdrant point
            point = PointStruct(
                id=chunk.chunk_id,
                vector={
                    "dense": vectors[0]["dense"],
                    "bm25": vectors[0]["sparse"],
                },
                payload={
                    "text": chunk.text,
                    **final_metadata,
                },
            )
            points_to_upsert.append(point)

            # Track statistics
            department_counts[final_metadata.get("department", "general")] += 1
            for role in final_metadata.get("access_roles", []):
                role_counts[role] += 1

        # Batch upsert to Qdrant
        if points_to_upsert:
            client.upsert(
                collection_name=QDRANT_COLLECTION,
                points=points_to_upsert,
            )

        total_chunks += len(chunks)
        override_count += file_overrides
        print(f"   ✅ Ingested: {len(chunks)} chunks")

    # Print summary
    _print_summary(total_chunks, department_counts, role_counts, override_count)


def _chunk_file(file_path: Path) -> list[Chunk]:
    """
    Route file to correct chunker based on extension.

    Args:
        file_path: Path to file

    Returns:
        List of Chunk objects
    """
    ext = file_path.suffix.lower()

    if ext == ".md":
        content = file_path.read_text(encoding="utf-8")
        return chunk_markdown(content, source_file=file_path.name)

    elif ext == ".xlsx":
        return chunk_excel_file(file_path, source_file=file_path.name)

    else:
        print(f"   ⚠️  Unsupported file type: {ext}")
        return []


def _print_summary(
    total_chunks: int,
    department_counts: Counter,
    role_counts: Counter,
    override_count: int,
) -> None:
    """Print ingestion summary statistics."""
    print(f"\n{'='*60}")
    print(f"Ingestion Complete")
    print(f"{'='*60}")
    print(f"Total chunks ingested: {total_chunks}")
    print(f"Validation overrides: {override_count}")

    print(f"\n📊 Chunks by Department:")
    for dept, count in sorted(department_counts.items()):
        print(f"   {dept}: {count}")

    print(f"\n🔐 Chunks by Access Role:")
    for role, count in sorted(role_counts.items()):
        print(f"   {role}: {count}")

    print(f"\n{'='*60}\n")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="FinSolve Document Ingestion Pipeline"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data/documents",
        help="Path to directory containing source documents",
    )
    args = parser.parse_args()

    asyncio.run(ingest_directory(args.data_dir))


if __name__ == "__main__":
    main()
