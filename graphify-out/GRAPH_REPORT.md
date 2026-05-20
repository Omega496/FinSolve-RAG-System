# Graph Report - .  (2026-05-20)

## Corpus Check
- Corpus is ~28,036 words - fits in a single context window. You may not need a graph.

## Summary
- 164 nodes · 175 edges · 47 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]

## God Nodes (most connected - your core abstractions)
1. `ingest_directory()` - 11 edges
2. `chunk_markdown()` - 11 edges
3. `validate_metadata()` - 10 edges
4. `tag_metadata()` - 6 edges
5. `login()` - 5 edges
6. `verify_jwt()` - 5 edges
7. `initialize_collection()` - 5 edges
8. `_call_ollama()` - 5 edges
9. `_chunk_file()` - 5 edges
10. `chunk_excel_row()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `ingest_directory()` --calls--> `get_qdrant_client()`  [EXTRACTED]
  backend/ingestion/ingest.py → backend/retrieval/qdrant_client.py
- `ingest_directory()` --calls--> `ensure_collection()`  [EXTRACTED]
  backend/ingestion/ingest.py → backend/retrieval/qdrant_client.py
- `ingest_directory()` --calls--> `validate_metadata()`  [EXTRACTED]
  backend/ingestion/ingest.py → backend/ingestion/validator.py
- `ingest_directory()` --calls--> `tag_metadata()`  [EXTRACTED]
  backend/ingestion/ingest.py → backend/ingestion/metadata_tagger.py
- `ingest_directory()` --calls--> `encode_both()`  [EXTRACTED]
  backend/ingestion/ingest.py → backend/ingestion/embedder.py

## Communities (47 total, 0 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (23): build_breadcrumb(), Chunk, chunk_excel_file(), chunk_excel_row(), chunk_markdown(), estimate_tokens(), extract_table_block(), is_appendix_section() (+15 more)

### Community 1 - "Community 1"
Cohesion: 0.14
Nodes (16): get_current_user(), FastAPI dependency for JWT-based route protection. Reads JWT from httpOnly cooki, FastAPI dependency that extracts and verifies the JWT from httpOnly cookie., create_jwt(), decode_token_from_cookie(), get_role_from_token(), JWT creation, verification, cookie setting. Uses python-jose for JWT operations., Extract and return the role from a verified JWT.      Args:         token: JWT s (+8 more)

### Community 2 - "Community 2"
Cohesion: 0.16
Nodes (17): _enforce_financial_rules(), _enforce_hr_record_rules(), _enforce_salary_rules(), _enforce_technical_rules(), _ensure_access_roles(), _flag_low_confidence(), Rule-based metadata validation layer. Safety net that enforces hard rules regard, Enforce that hr_record content_type always maps to [hr, c_suite]. (+9 more)

### Community 3 - "Community 3"
Cohesion: 0.21
Nodes (13): _call_ollama(), _get_default_metadata(), _merge_metadata(), _parse_json_response(), LLM + rule-based metadata assignment. Uses Nemotron via Ollama to assign metadat, Call Ollama API and parse JSON response.      Args:         prompt: Formatted pr, Safely parse JSON from LLM response.      Args:         raw_output: Raw text fro, Merge preliminary (rule-based) metadata with LLM-assigned metadata.     LLM valu (+5 more)

### Community 4 - "Community 4"
Cohesion: 0.21
Nodes (11): get_me(), health_check(), LoginRequest, LoginResponse, logout(), FinSolve RAG System — FastAPI Application Entry Point, Clear the httpOnly authentication cookie., Protected route — returns current user's name, role, and session_id. (+3 more)

### Community 5 - "Community 5"
Cohesion: 0.21
Nodes (11): clear_cache(), encode_both(), encode_dense(), encode_sparse(), _get_model(), BGE-M3 embedding wrapper. Provides dense, sparse, and hybrid embeddings for FinS, Clear the cached model to free memory., Get or load the BGE-M3 model (cached after first load).      Returns:         Lo (+3 more)

### Community 6 - "Community 6"
Cohesion: 0.24
Nodes (10): _chunk_file(), ingest_directory(), main(), _print_summary(), Main ingestion pipeline runner. Routes files to chunkers, tags metadata, validat, Route file to correct chunker based on extension.      Args:         file_path:, Print ingestion summary statistics., Ingest all supported files from a directory.      Args:         data_dir: Path t (+2 more)

### Community 7 - "Community 7"
Cohesion: 0.27
Nodes (9): _create_payload_indexes(), ensure_collection(), get_qdrant_client(), initialize_collection(), Qdrant connection + collection setup. Supports hybrid retrieval (dense + sparse, Ensure collection exists and is properly configured.     Safe to call multiple t, Get or create a singleton Qdrant client connection.      Returns:         Connec, Create the finsolve_chunks collection if it doesn't exist.     Configures: (+1 more)

### Community 8 - "Community 8"
Cohesion: 0.40
Nodes (5): _build_finance_filter(), build_rbac_filter(), Qdrant payload filter builder per role.  Enforces RBAC at the retrieval layer —, Build a Qdrant payload filter that enforces RBAC for the given role.      The fi, Build filter for finance role with marketing expense-only restriction.      Fina

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ingest_directory()` connect `Community 6` to `Community 2`, `Community 3`, `Community 5`, `Community 7`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `validate_metadata()` connect `Community 2` to `Community 6`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `_chunk_file()` connect `Community 6` to `Community 0`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **What connects `FinSolve RAG System — FastAPI Application Entry Point`, `Authenticate user, create JWT, set httpOnly cookie.     Returns user name and ro`, `Clear the httpOnly authentication cookie.` to the rest of the system?**
  _60 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.12318840579710146 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.13725490196078433 - nodes in this community are weakly interconnected._