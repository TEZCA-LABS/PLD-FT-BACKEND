#!/bin/bash
# PLD-FT Backend Deployment Script
# Usage: ./scripts/deploy.sh [staging|production]
# 
# This script handles:
# - Pre-deployment checks (backups, health)
# - Database migrations
# - Container builds and restarts
# - Post-deployment validation
# - Rollback on failure

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-staging}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
LOG_FILE="logs/deployment_${TIMESTAMP}.log"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[⚠]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1" | tee -a "$LOG_FILE"
}

# ============================================================================
# Pre-Deployment Checks
# ============================================================================

pre_deployment_checks() {
    log_info "Running pre-deployment checks..."
    
    # Check required tools
    command -v docker-compose &> /dev/null || {
        log_error "docker-compose not found"
        exit 1
    }
    log_success "docker-compose installed"
    
    command -v git &> /dev/null || {
        log_error "git not found"
        exit 1
    }
    log_success "git installed"
    
    # Check if docker daemon is running
    docker info &> /dev/null || {
        log_error "Docker daemon not running"
        exit 1
    }
    log_success "Docker daemon running"
    
    # Check .env file exists
    if [ ! -f .env ]; then
        log_error ".env file not found. Copy from .env.example and update variables"
        exit 1
    fi
    log_success ".env file exists"
    
    # Check git working directory is clean
    if [ ! -z "$(git status --porcelain)" ]; then
        log_warn "Uncommitted changes detected. Stashing..."
        git stash
    fi
}

# ============================================================================
# Database Backup
# ============================================================================

backup_database() {
    log_info "Backing up database..."
    
    mkdir -p "$BACKUP_DIR"
    
    BACKUP_FILE="$BACKUP_DIR/pld_backend_${TIMESTAMP}.sql"
    
    docker-compose exec -T db pg_dump \
        -U postgres \
        -d pld_backend \
        -F custom \
        -f "/tmp/backup_${TIMESTAMP}.sql" || {
        log_error "Database backup failed"
        return 1
    }
    
    docker cp pld-ft-backend-db-1:/tmp/backup_${TIMESTAMP}.sql "$BACKUP_FILE"
    docker-compose exec -T db rm "/tmp/backup_${TIMESTAMP}.sql"
    
    log_success "Database backed up to: $BACKUP_FILE"
    
    # Keep only last 7 backups
    ls -t "$BACKUP_DIR"/pld_backend_*.sql 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true
}

# ============================================================================
# Git Update
# ============================================================================

git_update() {
    log_info "Updating code from repository..."
    
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    log_info "Current branch: $CURRENT_BRANCH"
    
    git pull origin "$CURRENT_BRANCH" || {
        log_error "Failed to pull from git"
        return 1
    }
    
    log_success "Code updated"
    
    COMMIT_HASH=$(git rev-parse --short HEAD)
    log_info "Deployed commit: $COMMIT_HASH"
}

# ============================================================================
# Docker Build & Start
# ============================================================================

build_containers() {
    log_info "Building Docker images..."
    
    docker-compose build --pull || {
        log_error "Docker build failed"
        return 1
    }
    
    log_success "Docker images built"
}

start_core_services() {
    log_info "Starting database and redis..."
    
    docker-compose up -d db redis || {
        log_error "Failed to start db and redis"
        return 1
    }
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    max_attempts=30
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose exec -T db pg_isready -U postgres &> /dev/null; then
            log_success "Database is ready"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "Database failed to start within timeout"
        return 1
    fi
}

# ============================================================================
# Database Migrations
# ============================================================================

run_migrations() {
    log_info "Running Alembic migrations..."
    
    # Check current migration state
    CURRENT=$(docker-compose run --rm backend alembic current 2>&1 | grep -oP '^[a-f0-9]+' || echo "unknown")
    log_info "Current migration: $CURRENT"
    
    # Run upgrade
    docker-compose run --rm backend alembic upgrade head || {
        log_error "Migration failed"
        log_warn "Attempting rollback..."
        docker-compose run --rm backend alembic downgrade -1 || true
        return 1
    }
    
    # Verify
    NEW_CURRENT=$(docker-compose run --rm backend alembic current 2>&1 | grep -oP '^[a-f0-9]+' || echo "unknown")
    log_success "Migrations completed. New state: $NEW_CURRENT"
}

# ============================================================================
# Application Start
# ============================================================================

start_application() {
    log_info "Starting application services..."
    
    docker-compose up -d backend worker || {
        log_error "Failed to start application"
        return 1
    }
    
    log_success "Application services started"
}

# ============================================================================
# Post-Deployment Validation
# ============================================================================

validate_deployment() {
    log_info "Validating deployment..."
    
    # Wait for backend to be ready
    log_info "Waiting for backend health check..."
    max_attempts=20
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf http://localhost:8000/health &> /dev/null; then
            log_success "Backend is healthy"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "Backend failed health check"
        return 1
    fi
    
    # Check API is responding
    log_info "Testing API endpoints..."
    
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/audit-logs)
    if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "401" ]; then
        log_error "API returned unexpected status: $HTTP_CODE"
        return 1
    fi
    log_success "API responding correctly (HTTP $HTTP_CODE)"
}

# ============================================================================
# Rollback Function
# ============================================================================

rollback() {
    log_error "Deployment failed. Attempting rollback..."
    
    # Get previous commit
    PREVIOUS_COMMIT=$(git rev-parse HEAD~1)
    log_warn "Rolling back to commit: $PREVIOUS_COMMIT"
    
    git checkout "$PREVIOUS_COMMIT"
    
    # Rebuild and restart
    docker-compose build --pull
    docker-compose up -d backend worker
    
    log_warn "Rollback completed. Please investigate the failure."
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    mkdir -p logs
    
    log_info "======================================================"
    log_info "PLD-FT Backend Deployment Script"
    log_info "Environment: $ENVIRONMENT"
    log_info "Timestamp: $TIMESTAMP"
    log_info "======================================================"
    
    # Execute deployment steps
    pre_deployment_checks || exit 1
    backup_database || exit 1
    git_update || exit 1
    build_containers || { rollback; exit 1; }
    start_core_services || { rollback; exit 1; }
    run_migrations || { rollback; exit 1; }
    start_application || { rollback; exit 1; }
    validate_deployment || { rollback; exit 1; }
    
    log_info "======================================================"
    log_success "✓ Deployment completed successfully!"
    log_info "======================================================"
    
    # Print summary
    echo ""
    echo "Deployment Summary:"
    echo "  Environment: $ENVIRONMENT"
    echo "  Timestamp: $TIMESTAMP"
    echo "  Commit: $(git rev-parse --short HEAD)"
    echo "  Backup: $BACKUP_FILE"
    echo "  Logs: $LOG_FILE"
    echo ""
    
    # Show logs
    log_info "Recent backend logs:"
    docker-compose logs --tail=10 backend
}

# Run main
main "$@"
