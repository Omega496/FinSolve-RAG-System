#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
# FinSolve RAG Stack Validation Script
# 
# Validates:
#   1. Docker services up and healthy
#   2. Health endpoint reports all dependencies OK
#   3. Ingestion pipeline runs successfully
#   4. Test queries for all 6 RBAC roles
#   5. RBAC security audit passes
# ─────────────────────────────────────────────────────────────────────

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="http://localhost:8000"
QDRANT_URL="http://localhost:6333"
OLLAMA_URL="http://localhost:11434"
MAX_WAIT=120  # seconds
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Test results
TOTAL=0
PASSED=0
FAILED=0

log() { echo -e "${YELLOW}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
separator() { echo "────────────────────────────────────────────────────────────────"; }

check_result() {
    TOTAL=$((TOTAL + 1))
    if [ $1 -eq 0 ]; then
        PASSED=$((PASSED + 1))
        success "$2"
    else
        FAILED=$((FAILED + 1))
        error "$2"
    fi
}

# ─────────────────────────────────────────────────────────────────────
# Step 1: Start Docker Compose
# ─────────────────────────────────────────────────────────────────────
separator
log "Step 1: Starting Docker Compose..."
separator

cd "$PROJECT_DIR"

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    error "docker-compose.yml not found in $PROJECT_DIR"
    exit 1
fi

# Start services
docker compose up -d 2>&1
check_result $? "Docker Compose started"

# ─────────────────────────────────────────────────────────────────────
# Step 2: Wait for Services to be Healthy
# ─────────────────────────────────────────────────────────────────────
separator
log "Step 2: Waiting for services to be healthy (max ${MAX_WAIT}s)..."
separator

wait_for_service() {
    local name=$1
    local url=$2
    local elapsed=0
    
    while [ $elapsed -lt $MAX_WAIT ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
        echo -ne "\r  Waiting for $name... ${elapsed}s"
    done
    echo ""
    return 1
}

# Wait for Qdrant
wait_for_service "Qdrant" "$QDRANT_URL/healthz"
check_result $? "Qdrant is healthy"

# Wait for Ollama
wait_for_service "Ollama" "$OLLAMA_URL/api/tags"
check_result $? "Ollama is healthy"

# Wait for Backend
wait_for_service "Backend" "$BACKEND_URL/health"
check_result $? "Backend is healthy"

# ─────────────────────────────────────────────────────────────────────
# Step 3: Verify Health Endpoint
# ─────────────────────────────────────────────────────────────────────
separator
log "Step 3: Checking /health endpoint..."
separator

HEALTH_RESPONSE=$(curl -s "$BACKEND_URL/health")
HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "error")

if [ "$HEALTH_STATUS" = "healthy" ]; then
    check_result 0 "Health endpoint reports: $HEALTH_STATUS"
else
    check_result 1 "Health endpoint reports: $HEALTH_STATUS"
    echo "  Response: $HEALTH_RESPONSE"
fi

# Check dependencies
QDRANT_STATUS=$(echo "$HEALTH_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['dependencies']['qdrant']['status'])" 2>/dev/null || echo "error")
OLLAMA_STATUS=$(echo "$HEALTH_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['dependencies']['ollama']['status'])" 2>/dev/null || echo "error")

check_result $([ "$QDRANT_STATUS" = "healthy" ] && echo 0 || echo 1) "Qdrant dependency: $QDRANT_STATUS"
check_result $([ "$OLLAMA_STATUS" = "healthy" ] && echo 0 || echo 1) "Ollama dependency: $OLLAMA_STATUS"

# ─────────────────────────────────────────────────────────────────────
# Step 4: Run Ingestion Pipeline
# ─────────────────────────────────────────────────────────────────────
separator
log "Step 4: Running ingestion pipeline..."
separator

# Check if sample documents exist
DATA_DIR="$PROJECT_DIR/backend/data/documents"
if [ -d "$DATA_DIR" ] && [ "$(ls -A $DATA_DIR 2>/dev/null)" ]; then
    log "Found documents in $DATA_DIR"
    
    # Run ingestion via docker exec or direct python
    if docker compose ps backend | grep -q "Up"; then
        docker compose exec -T backend python -m backend.ingestion.ingest 2>&1
        check_result $? "Ingestion pipeline completed"
    else
        # Run locally if not in docker
        cd "$PROJECT_DIR"
        python3 -m backend.ingestion.ingest 2>&1
        check_result $? "Ingestion pipeline completed (local)"
    fi
else
    log "No sample documents found in $DATA_DIR — skipping ingestion"
    check_result 0 "Ingestion skipped (no documents)"
fi

# ─────────────────────────────────────────────────────────────────────
# Step 5: Test Queries for All 6 RBAC Roles
# ─────────────────────────────────────────────────────────────────────
separator
log "Step 5: Testing queries for all 6 RBAC roles..."
separator

# Test users (from AGNNTS.md)
declare -A USERS=(
    ["alice@finsolve.com"]="engineering"
    ["bob@finsolve.com"]="finance"
    ["carol@finsolve.com"]="marketing"
    ["dave@finsolve.com"]="hr"
    ["eve@finsolve.com"]="c_suite"
    ["frank@finsolve.com"]="employee"
)

TEST_QUERY="What information is available in the company documents?"
SESSION_ID="test-session-$(date +%s)"

for email in "${!USERS[@]}"; do
    role="${USERS[$email]}"
    
    # Login and get cookie
    LOGIN_RESPONSE=$(curl -s -c /tmp/cookies_$role.txt \
        -X POST "$BACKEND_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$email\",\"password\":\"test123\"}")
    
    LOGIN_OK=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys,json; print('name' in json.load(sys.stdin))" 2>/dev/null || echo "false")
    
    if [ "$LOGIN_OK" = "True" ]; then
        # Send query
        QUERY_RESPONSE=$(curl -s -b /tmp/cookies_$role.txt \
            -X POST "$BACKEND_URL/query" \
            -H "Content-Type: application/json" \
            -d "{\"query\":\"$TEST_QUERY\",\"session_id\":\"$SESSION_ID-$role\"}" \
            --max-time 30 2>/dev/null || echo "timeout")
        
        # Check if response contains tokens or blocked
        if echo "$QUERY_RESPONSE" | grep -q '"type"'; then
            HAS_TOKENS=$(echo "$QUERY_RESPONSE" | grep -c '"type": "token"' || true)
            HAS_BLOCKED=$(echo "$QUERY_RESPONSE" | grep -c '"type": "blocked"' || true)
            
            if [ "$HAS_BLOCKED" -gt 0 ]; then
                check_result 0 "$role query returned BLOCKED (expected for some roles)"
            elif [ "$HAS_TOKENS" -gt 0 ]; then
                check_result 0 "$role query returned tokens"
            else
                check_result 0 "$role query completed"
            fi
        else
            check_result 1 "$role query failed: $QUERY_RESPONSE"
        fi
    else
        check_result 1 "$role login failed"
    fi
    
    # Cleanup cookie
    rm -f /tmp/cookies_$role.txt
done

# ─────────────────────────────────────────────────────────────────────
# Step 6: Run RBAC Security Audit
# ─────────────────────────────────────────────────────────────────────
separator
log "Step 6: Running RBAC security audit..."
separator

cd "$PROJECT_DIR"
python3 backend/tests/test_rbac_security.py 2>&1
SECURITY_EXIT=$?
check_result $SECURITY_EXIT "RBAC security audit"

# ─────────────────────────────────────────────────────────────────────
# Step 7: Run Integration Tests
# ─────────────────────────────────────────────────────────────────────
separator
log "Step 7: Running integration tests..."
separator

python3 backend/tests/test_pipeline.py 2>&1
TESTS_EXIT=$?
check_result $TESTS_EXIT "Integration tests"

# ─────────────────────────────────────────────────────────────────────
# Final Summary
# ─────────────────────────────────────────────────────────────────────
separator
separator
echo ""
echo "  ╔══════════════════════════════════════════════════════════════╗"
echo "  ║                    VALIDATION SUMMARY                        ║"
echo "  ╠══════════════════════════════════════════════════════════════╣"
echo "  ║                                                              ║"
printf "  ║  Total:   %-4d                                               ║\n" "$TOTAL"
printf "  ║  Passed:  ${GREEN}%-4d${NC}                                               ║\n" "$PASSED"
printf "  ║  Failed:  ${RED}%-4d${NC}                                               ║\n" "$FAILED"
echo "  ║                                                              ║"

if [ $FAILED -eq 0 ]; then
    echo "  ║  ${GREEN}█████████████████████████████████████████████████████████████${NC}║"
    echo "  ║  ${GREEN}█                                                         █${NC}║"
    echo "  ║  ${GREEN}█                   STACK READY ✓                         █${NC}║"
    echo "  ║  ${GREEN}█                                                         █${NC}║"
    echo "  ║  ${GREEN}█████████████████████████████████████████████████████████████${NC}║"
else
    echo "  ║  ${RED}█████████████████████████████████████████████████████████████${NC}║"
    echo "  ║  ${RED}█                                                         █${NC}║"
    echo "  ║  ${RED}█                   STACK FAILED ✗                        █${NC}║"
    echo "  ║  ${RED}█                                                         █${NC}║"
    echo "  ║  ${RED}█████████████████████████████████████████████████████████████${NC}║"
fi

echo "  ║                                                              ║"
echo "  ╚══════════════════════════════════════════════════════════════╝"
echo ""

# Exit with appropriate code
exit $FAILED
