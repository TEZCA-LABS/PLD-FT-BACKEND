#!/bin/bash
# Emergency Rollback Script
# Usage: ./scripts/rollback.sh <backup_file>
# Example: ./scripts/rollback.sh backups/pld_backend_20260220_040000.sql

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

# ============================================================================
# Rollback Database
# ============================================================================

rollback_database() {
    local backup_file=$1
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    log_warn "⚠️  This will restore database from backup: $backup_file"
    read -p "Are you sure? (yes/no): " confirmation
    
    if [ "$confirmation" != "yes" ]; then
        log_warn "Rollback cancelled"
        exit 0
    fi
    
    log_info "Stopping application services..."
    docker-compose stop backend worker
    
    log_info "Dropping current database..."
    docker-compose exec -T db psql -U postgres -c "DROP DATABASE pld_backend;" || true
    
    log_info "Creating new database..."
    docker-compose exec -T db psql -U postgres -c "CREATE DATABASE pld_backend;"
    
    log_info "Restoring from backup..."
    docker cp "$backup_file" pld-ft-db-1:/tmp/backup.sql
    docker-compose exec -T db pg_restore -U postgres -d pld_backend -Fc /tmp/backup.sql
    docker-compose exec -T db rm /tmp/backup.sql
    
    log_success "Database restored from backup"
    
    log_info "Starting application services..."
    docker-compose up -d backend worker
    
    log_info "Waiting for services to be healthy..."
    sleep 5
    
    if curl -sf http://localhost:8000/health &> /dev/null; then
        log_success "✓ Rollback completed successfully!"
        log_info "Backend is healthy"
    else
        log_error "Backend health check failed after rollback"
        exit 1
    fi
}

# ============================================================================
# Rollback Code
# ============================================================================

rollback_code() {
    local commit=${1:-HEAD~1}
    
    log_warn "⚠️  This will revert code to commit: $commit"
    read -p "Are you sure? (yes/no): " confirmation
    
    if [ "$confirmation" != "yes" ]; then
        log_warn "Rollback cancelled"
        exit 0
    fi
    
    log_info "Stopping application..."
    docker-compose stop backend worker
    
    log_info "Reverting to commit: $commit"
    git checkout "$commit"
    
    log_info "Rebuilding containers..."
    docker-compose build
    
    log_info "Starting application..."
    docker-compose up -d backend worker
    
    log_success "✓ Code rollback completed!"
}

# ============================================================================
# Main
# ============================================================================

main() {
    if [ $# -eq 0 ]; then
        log_error "Usage: $0 <backup_file_or_commit>"
        log_info "Examples:"
        log_info "  - Database rollback: $0 backups/pld_backend_20260220_040000.sql"
        log_info "  - Code rollback: $0 HEAD~1"
        exit 1
    fi
    
    local target=$1
    
    if [[ $target == backups/* ]] || [[ $target == *.sql ]]; then
        log_info "Performing database rollback..."
        rollback_database "$target"
    else
        log_info "Performing code rollback..."
        rollback_code "$target"
    fi
}

main "$@"
