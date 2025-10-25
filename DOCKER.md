# Docker Setup Guide

This guide explains how to set up and manage Qdrant using Docker for the DDM RAG system.

## Quick Start

### Start Qdrant
```bash
docker-compose up -d
```

### Check Status
```bash
docker-compose ps
```

### View Logs
```bash
docker-compose logs -f qdrant
```

### Stop Qdrant
```bash
docker-compose down
```

### Stop and Remove Data
```bash
docker-compose down -v
```

## Configuration Details

### Docker Compose Configuration
The [docker-compose.yml](docker-compose.yml) file sets up:

- **Service**: `qdrant`
- **Image**: `qdrant/qdrant:latest`
- **Container Name**: `ddm_rag_qdrant`
- **Ports**:
  - `6333`: REST API (used by the application)
  - `6334`: gRPC API (optional, for high-performance clients)
- **Volume**: `./qdrant_storage` (persists vector data between restarts)
- **Health Check**: Automatic health monitoring
- **Restart Policy**: `unless-stopped` (auto-restart on failure)

### Data Persistence

Vector data is stored in `./qdrant_storage/` directory:
- **Automatically created** on first run
- **Persists** across container restarts
- **Excluded from git** (via `.gitignore`)
- **Backup**: Simply copy this directory to backup your vector database

## Qdrant Web UI

Access the Qdrant dashboard at: **http://localhost:6333/dashboard**

Features:
- View collections and their statistics
- Inspect vectors and payloads
- Monitor cluster health
- Execute search queries

## Troubleshooting

### Port Already in Use
If port 6333 is already in use:

```bash
# Check what's using the port
sudo lsof -i :6333

# Kill the process or change the port in docker-compose.yml
```

### Check Container Health
```bash
# View container status
docker-compose ps

# Check health status
docker inspect ddm_rag_qdrant --format='{{.State.Health.Status}}'

# Test connectivity
curl http://localhost:6333/health
```

### Reset Qdrant Data
To completely reset the vector database:

```bash
# Stop container and remove volumes
docker-compose down -v

# Remove local storage
rm -rf qdrant_storage/

# Start fresh
docker-compose up -d
```

### View Detailed Logs
```bash
# All logs
docker-compose logs qdrant

# Follow logs in real-time
docker-compose logs -f qdrant

# Last 100 lines
docker-compose logs --tail=100 qdrant
```

## Production Considerations

### Resource Limits
Add resource limits to `docker-compose.yml`:

```yaml
services:
  qdrant:
    # ... existing config ...
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### Backup Strategy

**Manual Backup**:
```bash
# Backup vector data
tar -czf qdrant_backup_$(date +%Y%m%d).tar.gz qdrant_storage/

# Restore from backup
tar -xzf qdrant_backup_YYYYMMDD.tar.gz
```

**Automated Backup Script**:
```bash
#!/bin/bash
# backup_qdrant.sh
BACKUP_DIR="./backups"
mkdir -p $BACKUP_DIR
tar -czf "$BACKUP_DIR/qdrant_$(date +%Y%m%d_%H%M%S).tar.gz" qdrant_storage/
# Keep only last 7 backups
ls -t $BACKUP_DIR/qdrant_*.tar.gz | tail -n +8 | xargs rm -f
```

### Network Configuration

For production deployments, consider using a custom network:

```yaml
services:
  qdrant:
    networks:
      - rag_network

networks:
  rag_network:
    driver: bridge
```

## Integration with RAG System

The RAG system connects to Qdrant via the configuration in [config.py](config.py):

```python
qdrant_url: str = "http://localhost:6333"
qdrant_collection: str = "ddm_rag"
```

After starting Qdrant, initialize the system:

```bash
# Start the RAG API
python main.py

# In another terminal, initialize the vector store
curl -X POST http://localhost:8000/initialize
```

## Useful Commands

```bash
# Restart Qdrant
docker-compose restart qdrant

# Update to latest Qdrant version
docker-compose pull
docker-compose up -d

# Access container shell
docker-compose exec qdrant sh

# View resource usage
docker stats ddm_rag_qdrant

# Export logs to file
docker-compose logs qdrant > qdrant_logs.txt
```
