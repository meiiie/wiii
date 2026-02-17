#!/bin/bash
# =============================================================================
# Wiii - Local Development Startup Script
# =============================================================================
# This script starts all required services for local development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     Wiii - Local Development Environment         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker is running${NC}"

# Change to project directory
cd "$PROJECT_DIR"

# Check for .env.local
if [ ! -f ".env.local" ]; then
    echo -e "${YELLOW}⚠️  .env.local not found. Creating from template...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env.local
        echo -e "${YELLOW}⚠️  Please update .env.local with your API keys before continuing.${NC}"
        exit 1
    else
        echo -e "${RED}❌ .env.example not found. Cannot create .env.local${NC}"
        exit 1
    fi
fi

# Export environment variables from .env.local
export $(grep -v '^#' .env.local | xargs)

echo ""
echo -e "${BLUE}📦 Starting infrastructure services...${NC}"
echo ""

# Start infrastructure services (excluding app for now)
docker-compose up -d postgres neo4j chroma redis minio minio-init

# Wait for services to be healthy
echo ""
echo -e "${BLUE}⏳ Waiting for services to be ready...${NC}"
echo ""

# Function to check service health
check_service() {
    local service=$1
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose ps $service | grep -q "healthy"; then
            echo -e "${GREEN}✅ $service is ready${NC}"
            return 0
        fi
        echo -e "${YELLOW}⏳ Waiting for $service... ($attempt/$max_attempts)${NC}"
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}❌ $service failed to start${NC}"
    return 1
}

# Check all services
check_service postgres
check_service neo4j
check_service redis
check_service minio

# ChromaDB doesn't have healthcheck, just check if running
if docker-compose ps chroma | grep -q "Up"; then
    echo -e "${GREEN}✅ chroma is ready${NC}"
else
    echo -e "${YELLOW}⚠️  chroma status unknown, continuing...${NC}"
fi

echo ""
echo -e "${BLUE}🔄 Running database migrations...${NC}"
echo ""

# Wait a bit more for databases to be fully ready
sleep 5

# Run Alembic migrations
if [ -f "alembic.ini" ]; then
    # Check if we're in a virtual environment
    if [ -n "$VIRTUAL_ENV" ]; then
        alembic upgrade head
    else
        echo -e "${YELLOW}⚠️  No virtual environment detected. Trying with python -m...${NC}"
        python -m alembic upgrade head || echo -e "${YELLOW}⚠️  Migration skipped (may need manual run)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  alembic.ini not found, skipping migrations${NC}"
fi

echo ""
echo -e "${BLUE}🌱 Seeding test data...${NC}"
echo ""

# Run seed script if it exists
if [ -f "scripts/seed-data.py" ]; then
    python scripts/seed-data.py || echo -e "${YELLOW}⚠️  Seeding skipped (may need manual run)${NC}"
else
    echo -e "${YELLOW}⚠️  No seed data script found${NC}"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ Local development environment is ready!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}📱 API Server:${NC} http://localhost:8000"
echo -e "${BLUE}📚 API Docs:${NC}   http://localhost:8000/docs"
echo -e "${BLUE}🔍 Health:${NC}     http://localhost:8000/health"
echo ""
echo -e "${BLUE}🗄️  Services:${NC}"
echo -e "  • PostgreSQL:  localhost:5433"
echo -e "  • Neo4j:       http://localhost:7474"
echo -e "  • ChromaDB:    http://localhost:8001"
echo -e "  • Redis:       localhost:6379"
echo -e "  • MinIO:       http://localhost:9001 (console)"
echo ""
echo -e "${YELLOW}⚡ Starting FastAPI with hot-reload...${NC}"
echo ""

# Check if we should run in Docker or locally
if [ "$1" == "--docker" ]; then
    echo -e "${BLUE}🐳 Running app in Docker mode...${NC}"
    docker-compose up -d app
    docker-compose logs -f app
else
    echo -e "${BLUE}🐍 Running app locally with uvicorn...${NC}"
    echo -e "${YELLOW}💡 Use --docker flag to run app in Docker instead${NC}"
    echo ""
    
    # Check for virtual environment
    if [ -z "$VIRTUAL_ENV" ]; then
        echo -e "${YELLOW}⚠️  No virtual environment detected.${NC}"
        echo -e "${YELLOW}   Please activate your virtual environment first:${NC}"
        echo -e "   source .venv/bin/activate  # Linux/Mac"
        echo -e "   .venv\\Scripts\\activate     # Windows"
        echo ""
        echo -e "${BLUE}🐳 Alternatively, run with --docker flag${NC}"
        exit 1
    fi
    
    # Run uvicorn with hot-reload
    uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --reload-dir app \
        --log-level debug
fi
