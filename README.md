# FinSolve RAG System

> Internal enterprise chatbot with RBAC-enforced document retrieval, guardrails, and full audit trail.

---

## Overview

FinSolve is a Retrieval-Augmented Generation (RAG) system that allows employees to query company documents using natural language. Access is strictly controlled via Role-Based Access Control (RBAC) — each employee only sees data they're authorized to access.

### Key Features

- **RBAC Enforcement** — Qdrant payload filters restrict document access by role
- **Hybrid Retrieval** — Dense (BGE-M3) + Sparse (BM25) with Reciprocal Rank Fusion
- **Guardrails** — NeMo Guardrails for input + PII regex scanner for output
- **Streaming** — Real-time token streaming via SSE
- **Audit Trail** — Structured JSON logging for all queries and security events
- **Fully Local** — Docker Compose deployment, no external dependencies

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Frontend (React)                              │
│                    http://localhost:3000                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │  Login   │  │   Chat   │  │  Sidebar │  │  Admin   │                 │
│  │  Page    │  │  Layout  │  │  + Badge │  │  Panel   │                 │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘                 │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ SSE + REST
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Backend (FastAPI)                                │
│                    http://localhost:8000                                │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    LangGraph Pipeline                           │    │
│  │                                                                 │    │
│  │   input_guardrail ─→ rbac_router ─→ retriever ─→ parent_swap    │    │
│  │         │                                          │            │    │
│  │         ▼ (blocked)                                 ▼           │    │
│  │        END                                     generator        │    │
│  │                                                      │          │    │
│  │                                                      ▼          │    │
│  │                                               output_scanner    │    │
│  │                                                      │          │    │
│  │                                                      ▼          │    │
│  │                                               memory_update     │    │
│  │                                                      │          │    │
│  │                                                      ▼          │    │
│  │                                                     END         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │   JWT    │  │   RBAC   │  │  Hybrid  │  │  PII     │                 │
│  │   Auth   │  │  Filter  │  │ Retriever│  │ Scanner  │                 │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘                 │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│    Qdrant    │        │    Ollama    │        │    NeMo      │
│  Port 6333   │        │  Port 11434  │        │  Guardrails  │
│  Vector DB   │        │    LLM       │        │  (optional)  │
└──────────────┘        └──────────────┘        └──────────────┘
```

---

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Docker | 24.0+ | Container runtime |
| Docker Compose | 2.20+ | Multi-service orchestration |
| Python | 3.11+ | Backend runtime |
| uv | Latest | Python package manager |
| Node.js | 18+ | Frontend build |
| Ollama | Latest | LLM inference |

---

## Quick Start

### 1. Clone and Configure

```bash
git clone <repository-url>
cd finsolve-rag-system

# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 2. Configure Environment Variables

```bash
# JWT (generate a secure secret)
JWT_SECRET_KEY=your-secure-random-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=8

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION=finsolve_chunks

# Ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=nemotron-3-super:cloud

# BGE-M3 Embedding
EMBEDDING_MODEL=BAAI/bge-m3

# LangSmith (optional - for tracing)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=finsolve-rag

# NeMo Guardrails
NEMO_CONFIG_PATH=./guardrails/nemo_config

# Monitoring
AUDIT_LOG_PATH=./logs/audit.jsonl
```

### 3. Start Services

```bash
# Start all services
docker compose up -d

# Pull Ollama model (first time only)
docker compose exec ollama ollama pull nemotron-3-super:cloud

# Verify services are healthy
curl http://localhost:8000/health
```

### 4. Install Dependencies (Local Development)

```bash
# Backend
cd backend
uv pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 5. Run Ingestion Pipeline

```bash
# Place documents in backend/data/documents/
# Supports: .md (markdown) and .xlsx (Excel)

# Run ingestion
cd backend
python -m backend.ingestion.ingest
```

### 6. Access the Application

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## Test Users

| Email | Password | Role | Access Level |
|-------|----------|------|--------------|
| alice@finsolve.com | test123 | Engineering | Engineering docs, Employee Handbook |
| bob@finsolve.com | test123 | Finance | Finance docs, Marketing expenses, Employee Handbook |
| carol@finsolve.com | test123 | Marketing | Marketing docs, Employee Handbook |
| dave@finsolve.com | test123 | HR | HR dataset, Employee Handbook |
| eve@finsolve.com | test123 | C-Suite | All documents |
| frank@finsolve.com | test123 | Employee | Employee Handbook only |

---

## RBAC Matrix

| Document | Engineering | Finance | Marketing | HR | C-Suite | Employee |
|----------|:-----------:|:-------:|:---------:|:--:|:-------:|:--------:|
| Engineering Architecture | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Marketing Q1-Q4 (campaign) | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ |
| Marketing Q1-Q4 (expense) | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Finance Quarterly | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Employee Handbook | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| HR Employee Dataset | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |

**Finance Special Rule:** Finance users can only access expense-type content from Marketing department.

---

## Running Tests

### Integration Tests

```bash
cd backend
python -m pytest tests/test_pipeline.py -v

# Or run directly
python tests/test_pipeline.py
```

### Security Audit

```bash
python tests/test_rbac_security.py
```

### Full Stack Validation

```bash
./scripts/validate_stack.sh
```

This script:
1. Starts Docker Compose
2. Waits for all services to be healthy
3. Verifies health endpoints
4. Runs ingestion pipeline
5. Tests queries for all 6 roles
6. Runs security audit
7. Prints STACK READY or STACK FAILED

---

## API Endpoints

### Public Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| POST | `/auth/login` | Authenticate user |
| POST | `/auth/logout` | Clear session |

### Protected Routes (JWT Required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/me` | Get current user info |
| POST | `/query` | RAG query with SSE streaming |

### Admin Routes (C-Suite Only)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/audit/logs` | Last 100 audit log entries |
| GET | `/audit/guardrail-events` | Guardrail events with date filter |

---

## SSE Streaming Format

The `/query` endpoint returns Server-Sent Events:

```
data: {"type": "token", "content": "Hello"}

data: {"type": "token", "content": " world"}

data: {"type": "sources", "content": [{"doc_id": "...", "header": "...", "source_file": "..."}]}

data: {"type": "done", "content": null}
```

**Event Types:**
- `token` — Streamed LLM token
- `sources` — Source citations array
- `blocked` — Guardrail block with reason
- `error` — Error message (never exposes internals)
- `done` — Stream complete

---

## Architecture Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Vector Store | Qdrant | Native hybrid retrieval + expressive payload filters |
| Retrieval | Hybrid + RRF | Technical terms need keyword matching (BGE-M3) |
| Chunking | Parent-child | Retrieval precision + LLM context richness |
| Guardrails | NeMo + PII regex | LLM-as-judge deferred — overkill for this scope |
| Memory | Sliding window 5 turns | Enterprise queries short-session; no extra LLM calls |
| Orchestration | LangGraph | Pipeline has conditional branching — not linear chain |
| JWT Storage | httpOnly cookie | XSS immune; production pattern practice |
| Monitoring | LangSmith + RAGAS | Prometheus deferred to production |

---

## Pre-Production Checklist

- [ ] Replace Nemotron cloud with local model or Azure OpenAI + signed DPA
- [ ] Migrate auth to Azure AD (Entra ID)
- [ ] Set `COOKIE_SECURE=True`, enforce HTTPS
- [ ] Lock `allow_origins` to production domain
- [ ] Add Prometheus + Grafana for aggregate metrics
- [ ] Deploy to Azure Container Apps via Docker Compose
- [ ] Security audit all Qdrant payload filters
- [ ] GDPR/DPDP compliance review all data flows

---

## Troubleshooting

### Qdrant Connection Failure

**Symptom:** `Connection refused` or `Qdrant unhealthy`

**Solution:**
```bash
# Check if Qdrant is running
docker compose ps qdrant

# Check Qdrant logs
docker compose logs qdrant

# Restart Qdrant
docker compose restart qdrant

# Verify port is not in use
lsof -i :6333
```

### Ollama Model Not Found

**Symptom:** `model 'nemotron-3-super:cloud' not found`

**Solution:**
```bash
# Pull the model
docker compose exec ollama ollama pull nemotron-3-super:cloud

# List available models
docker compose exec ollama ollama list

# Check Ollama logs
docker compose logs ollama
```

### CORS Cookie Issues

**Symptom:** `401 Unauthorized` or cookies not being sent

**Solution:**
1. Ensure frontend is running on `http://localhost:3000`
2. Check CORS configuration in `backend/main.py`:
   ```python
   allow_origins=["http://localhost:3000"]
   allow_credentials=True
   ```
3. Verify `credentials: 'include'` in all fetch calls
4. Check cookie settings:
   - `COOKIE_HTTPONLY=True`
   - `COOKIE_SAMESITE=strict`
   - `COOKIE_SECURE=False` (for localhost)

### NeMo Guardrails Initialization Errors

**Symptom:** `NeMo init failed` or `ImportError`

**Solution:**
```bash
# Install NeMo Guardrails
pip install nemoguardrails

# Check if config files exist
ls backend/guardrails/nemo_config/

# Verify config.yml and rails.co are valid

# If NeMo fails, system falls back to regex-only guardrails
# Check logs for: "NeMo Guardrails failed to initialize"
```

### Frontend Not Loading

**Symptom:** Blank page or connection errors

**Solution:**
```bash
# Check if frontend is running
docker compose ps frontend

# Install dependencies
cd frontend && npm install

# Check for build errors
npm run build

# Verify proxy configuration in vite.config.js
```

### Ingestion Pipeline Fails

**Symptom:** `No documents found` or ingestion errors

**Solution:**
```bash
# Verify documents exist
ls backend/data/documents/

# Check supported formats: .md, .xlsx
# Check file permissions
# Run with verbose logging
python -m backend.ingestion.ingest --verbose
```

### Memory/Token Issues

**Symptom:** Slow responses or context window errors

**Solution:**
- Conversation history limited to 5 turns (10 messages)
- Parent chunks are ~400 tokens each
- Top 5 parent chunks sent to LLM
- Adjust `TOP_K_FINAL` in `hybrid_retriever.py` if needed

---

## Project Structure

```
finsolve-rag-system/
├── AGENT.md                    # Project specifications
├── README.md                   # This file
├── docker-compose.yml          # Service orchestration
├── .env                        # Environment variables
│
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── requirements.txt        # Python dependencies
│   ├── Dockerfile
│   │
│   ├── auth/                   # JWT authentication
│   ├── graph/                  # LangGraph pipeline
│   │   ├── state.py            # RAGState definition
│   │   ├── pipeline.py         # Graph compilation
│   │   └── nodes/              # Pipeline nodes
│   │
│   ├── ingestion/              # Document processing
│   ├── retrieval/              # Qdrant + hybrid search
│   ├── guardrails/             # NeMo + PII scanner
│   ├── monitoring/             # Logging + evaluation
│   ├── tests/                  # Integration + security tests
│   └── data/documents/         # Source documents
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Routing
│   │   ├── api/client.js       # Fetch wrapper
│   │   ├── context/            # React contexts
│   │   ├── hooks/              # Custom hooks
│   │   └── components/         # UI components
│   └── package.json
│
└── scripts/
    └── validate_stack.sh       # Full stack validation
```

---

## License

Internal use only. Not for distribution.

---

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review logs: `docker compose logs -f`
3. Check audit trail: `GET /audit/logs` (C-Suite only)
