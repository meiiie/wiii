# =============================================================================
# Wiii - Local Development Startup Script (Windows)
# =============================================================================
# This script starts all required services for local development

param(
    [switch]$Docker,
    [switch]$SkipMigrations,
    [switch]$SkipSeed
)

# Colors for output
$Red = "`e[0;31m"
$Green = "`e[0;32m"
$Yellow = "`e[1;33m"
$Blue = "`e[0;34m"
$NC = "`e[0m"  # No Color

# Script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Write-Host "$Blue" -NoNewline
Write-Host "╔════════════════════════════════════════════════════════════════╗" 
Write-Host "║     Wiii - Local Development Environment         ║"
Write-Host "╚════════════════════════════════════════════════════════════════╝"
Write-Host "$NC" -NoNewline

# Check if docker is running
try {
    $null = docker info 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker not running"
    }
} catch {
    Write-Host "${Red}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
}

Write-Host "${Green}✅ Docker is running${NC}"

# Change to project directory
Set-Location $ProjectDir

# Check for .env.local
if (-not (Test-Path ".env.local")) {
    Write-Host "${Yellow}⚠️  .env.local not found. Creating from template...${NC}"
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env.local"
        Write-Host "${Yellow}⚠️  Please update .env.local with your API keys before continuing.${NC}"
        exit 1
    } else {
        Write-Host "${Red}❌ .env.example not found. Cannot create .env.local${NC}"
        exit 1
    }
}

# Load environment variables from .env.local
Get-Content .env.local | ForEach-Object {
    if ($_ -match '^([^#][^=]*)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

Write-Host ""
Write-Host "${Blue}📦 Starting infrastructure services...${NC}"
Write-Host ""

# Start infrastructure services
docker-compose up -d postgres neo4j chroma redis minio minio-init

# Wait for services to be healthy
Write-Host ""
Write-Host "${Blue}⏳ Waiting for services to be ready...${NC}"
Write-Host ""

function Check-Service {
    param($Service, $MaxAttempts = 30)
    
    $attempt = 1
    while ($attempt -le $MaxAttempts) {
        $status = docker-compose ps $Service 2>$null
        if ($status -match "healthy") {
            Write-Host "${Green}✅ $Service is ready${NC}"
            return $true
        }
        Write-Host "${Yellow}⏳ Waiting for $Service... ($attempt/$MaxAttempts)${NC}"
        Start-Sleep -Seconds 2
        $attempt++
    }
    
    Write-Host "${Red}❌ $Service failed to start${NC}"
    return $false
}

# Check all services
Check-Service "postgres"
Check-Service "neo4j"
Check-Service "redis"
Check-Service "minio"

# ChromaDB check
$chromaStatus = docker-compose ps chroma 2>$null
if ($chromaStatus -match "Up") {
    Write-Host "${Green}✅ chroma is ready${NC}"
} else {
    Write-Host "${Yellow}⚠️  chroma status unknown, continuing...${NC}"
}

# Run migrations
if (-not $SkipMigrations) {
    Write-Host ""
    Write-Host "${Blue}🔄 Running database migrations...${NC}"
    Write-Host ""
    
    Start-Sleep -Seconds 5
    
    if (Test-Path "alembic.ini") {
        try {
            python -m alembic upgrade head
            Write-Host "${Green}✅ Migrations completed${NC}"
        } catch {
            Write-Host "${Yellow}⚠️  Migration skipped or failed: $_${NC}"
        }
    } else {
        Write-Host "${Yellow}⚠️  alembic.ini not found, skipping migrations${NC}"
    }
}

# Seed data
if (-not $SkipSeed) {
    Write-Host ""
    Write-Host "${Blue}🌱 Seeding test data...${NC}"
    Write-Host ""
    
    if (Test-Path "scripts/seed-data.py") {
        try {
            python scripts/seed-data.py
            Write-Host "${Green}✅ Seeding completed${NC}"
        } catch {
            Write-Host "${Yellow}⚠️  Seeding skipped or failed: $_${NC}"
        }
    } else {
        Write-Host "${Yellow}⚠️  No seed data script found${NC}"
    }
}

Write-Host ""
Write-Host "${Green}═══════════════════════════════════════════════════════════════${NC}"
Write-Host "${Green}  ✅ Local development environment is ready!${NC}"
Write-Host "${Green}═══════════════════════════════════════════════════════════════${NC}"
Write-Host ""
Write-Host "${Blue}📱 API Server:${NC} http://localhost:8000"
Write-Host "${Blue}📚 API Docs:${NC}   http://localhost:8000/docs"
Write-Host "${Blue}🔍 Health:${NC}     http://localhost:8000/health"
Write-Host ""
Write-Host "${Blue}🗄️  Services:${NC}"
Write-Host "  • PostgreSQL:  localhost:5433"
Write-Host "  • Neo4j:       http://localhost:7474"
Write-Host "  • ChromaDB:    http://localhost:8001"
Write-Host "  • Redis:       localhost:6379"
Write-Host "  • MinIO:       http://localhost:9001 (console)"
Write-Host ""

# Start the app
if ($Docker) {
    Write-Host "${Blue}🐳 Running app in Docker mode...${NC}"
    docker-compose up -d app
    docker-compose logs -f app
} else {
    Write-Host "${Blue}🐍 Running app locally with uvicorn...${NC}"
    Write-Host "${Yellow}💡 Use -Docker flag to run app in Docker instead${NC}"
    Write-Host ""
    
    # Check for virtual environment
    if (-not $env:VIRTUAL_ENV) {
        Write-Host "${Yellow}⚠️  No virtual environment detected.${NC}"
        Write-Host "${Yellow}   Please activate your virtual environment first:${NC}"
        Write-Host "   .venv\Scripts\activate"
        Write-Host ""
        Write-Host "${Blue}🐳 Alternatively, run with -Docker flag${NC}"
        exit 1
    }
    
    # Run uvicorn with hot-reload
    uvicorn app.main:app `
        --host 0.0.0.0 `
        --port 8000 `
        --reload `
        --reload-dir app `
        --log-level debug
}
