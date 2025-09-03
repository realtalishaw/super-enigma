# Deployment Guide

## Overview

This guide covers deploying the Workflow Automation Engine in different environments, from development to production.

## Development Deployment

### Local Development

1. **Quick Setup**
   ```bash
   ./quick_setup.sh
   ```

2. **Start Services**
   ```bash
   python start_both.py
   ```

3. **Access Points**
   - Backend API: http://localhost:8001
   - API Docs: http://localhost:8001/docs

### Development with Docker

Create a `docker-compose.dev.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes

  api:
    build: .
    ports:
      - "8001:8001"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=${DATABASE_URL}
      - COMPOSIO_API_KEY=${COMPOSIO_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - redis
    volumes:
      - .:/app
    command: python api/run.py

  scheduler:
    build: .
    ports:
      - "8003:8003"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - redis
    volumes:
      - .:/app
    command: python services/scheduler/run.py
```

Run with:
```bash
docker-compose -f docker-compose.dev.yml up
```

## Staging Deployment

### Environment Setup

1. **Create staging environment file**
   ```bash
   cp .env .env.staging
   ```

2. **Update staging configuration**
   ```bash
   # .env.staging
   DATABASE_URL=mongodb+srv://user:pass@staging-cluster.mongodb.net/weave-staging
   REDIS_URL=redis://staging-redis:6379
   DEBUG=false
   LOG_LEVEL=INFO
   ```

3. **Deploy to staging server**
   ```bash
   # On staging server
   git clone <repository>
   cd workflow-automation-engine
   python setup.py
   ```

### Staging with Docker

Create `docker-compose.staging.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

  api:
    build: .
    ports:
      - "8001:8001"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=${DATABASE_URL}
      - COMPOSIO_API_KEY=${COMPOSIO_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DEBUG=false
      - LOG_LEVEL=INFO
    depends_on:
      - redis
    restart: unless-stopped

  scheduler:
    build: .
    ports:
      - "8003:8003"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=${DATABASE_URL}
      - DEBUG=false
      - LOG_LEVEL=INFO
    depends_on:
      - redis
    restart: unless-stopped

volumes:
  redis_data:
```

## Production Deployment

### Production Requirements

- **Load Balancer**: Nginx or similar
- **Process Manager**: PM2, systemd, or Docker
- **Database**: MongoDB Atlas or self-hosted
- **Cache**: Redis Cluster or Redis Cloud
- **Monitoring**: Prometheus, Grafana
- **Logging**: ELK Stack or similar
- **SSL/TLS**: Let's Encrypt or commercial certificate

### Production Environment Variables

```bash
# Production .env
DATABASE_URL=mongodb+srv://user:pass@prod-cluster.mongodb.net/weave-prod
REDIS_URL=redis://prod-redis-cluster:6379
COMPOSIO_API_KEY=prod_composio_key
ANTHROPIC_API_KEY=prod_anthropic_key
GROQ_API_KEY=prod_groq_key
DEBUG=false
LOG_LEVEL=WARNING
API_HOST=0.0.0.0
API_PORT=8001
```

### Production with Docker

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - api
      - scheduler

  api:
    build: .
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=${DATABASE_URL}
      - COMPOSIO_API_KEY=${COMPOSIO_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DEBUG=false
      - LOG_LEVEL=WARNING
    depends_on:
      - redis
    restart: unless-stopped
    deploy:
      replicas: 3

  scheduler:
    build: .
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=${DATABASE_URL}
      - DEBUG=false
      - LOG_LEVEL=WARNING
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

### Nginx Configuration

Create `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream api_backend {
        server api:8001;
    }

    upstream scheduler_backend {
        server scheduler:8003;
    }

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        location /api/ {
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /scheduler/ {
            proxy_pass http://scheduler_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location / {
            # Serve frontend static files
            root /var/www/html;
            try_files $uri $uri/ /index.html;
        }
    }
}
```

### Production Deployment Steps

1. **Prepare server**
   ```bash
   # Install Docker and Docker Compose
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   
   # Install Docker Compose
   sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

2. **Deploy application**
   ```bash
   # Clone repository
   git clone <repository>
   cd workflow-automation-engine
   
   # Set up environment
   cp .env.production .env
   # Edit .env with production values
   
   # Build and start
   docker-compose -f docker-compose.prod.yml up -d
   ```

3. **Set up SSL**
   ```bash
   # Using Let's Encrypt
   sudo apt install certbot
   sudo certbot certonly --standalone -d your-domain.com
   
   # Copy certificates
   sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ./ssl/cert.pem
   sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ./ssl/key.pem
   ```

4. **Set up monitoring**
   ```bash
   # Add monitoring stack
   docker-compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml up -d
   ```

## Kubernetes Deployment

### Namespace and ConfigMap

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: workflow-engine

---
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: workflow-config
  namespace: workflow-engine
data:
  REDIS_URL: "redis://redis-service:6379"
  DEBUG: "false"
  LOG_LEVEL: "INFO"
```

### Redis Deployment

```yaml
# redis.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: workflow-engine
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-data
          mountPath: /data
      volumes:
      - name: redis-data
        persistentVolumeClaim:
          claimName: redis-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: workflow-engine
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-pvc
  namespace: workflow-engine
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

### API Deployment

```yaml
# api.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: workflow-engine
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: workflow-engine:latest
        ports:
        - containerPort: 8001
        env:
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: workflow-config
              key: REDIS_URL
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: workflow-secrets
              key: DATABASE_URL
        - name: COMPOSIO_API_KEY
          valueFrom:
            secretKeyRef:
              name: workflow-secrets
              key: COMPOSIO_API_KEY
        command: ["python", "api/run.py"]

---
apiVersion: v1
kind: Service
metadata:
  name: api-service
  namespace: workflow-engine
spec:
  selector:
    app: api
  ports:
  - port: 8001
    targetPort: 8001
  type: LoadBalancer
```

### Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: workflow-ingress
  namespace: workflow-engine
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  tls:
  - hosts:
    - your-domain.com
    secretName: workflow-tls
  rules:
  - host: your-domain.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 8001
      - path: /scheduler
        pathType: Prefix
        backend:
          service:
            name: scheduler-service
            port:
              number: 8003
```

## Monitoring and Observability

### Health Checks

Add health check endpoints:

```python
# In api/main.py
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@app.get("/health/ready")
async def readiness_check():
    # Check database connection
    # Check Redis connection
    # Check external services
    return {"status": "ready"}
```

### Metrics

Add Prometheus metrics:

```python
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### Logging

Configure structured logging:

```python
import structlog

logger = structlog.get_logger()

# In your endpoints
logger.info("Request received", endpoint="/api/suggestions", user_id=user_id)
```

## Security Considerations

### Environment Variables

- Use secrets management (Kubernetes secrets, AWS Secrets Manager, etc.)
- Never commit API keys to version control
- Rotate keys regularly

### Network Security

- Use HTTPS in production
- Implement rate limiting
- Use firewall rules
- Consider VPN for internal services

### Application Security

- Validate all inputs
- Implement authentication and authorization
- Use CORS properly
- Sanitize user data

## Backup and Recovery

### Database Backups

```bash
# MongoDB backup
mongodump --uri="$DATABASE_URL" --out=backup-$(date +%Y%m%d)

# Restore
mongorestore --uri="$DATABASE_URL" backup-20240101/
```

### Configuration Backups

```bash
# Backup configuration
tar -czf config-backup-$(date +%Y%m%d).tar.gz .env docker-compose*.yml nginx.conf
```

## Troubleshooting

### Common Issues

1. **Service won't start**
   - Check logs: `docker-compose logs <service>`
   - Verify environment variables
   - Check port conflicts

2. **Database connection issues**
   - Verify DATABASE_URL
   - Check network connectivity
   - Verify credentials

3. **Redis connection issues**
   - Check Redis is running
   - Verify REDIS_URL
   - Check firewall rules

### Debug Commands

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f api

# Execute commands in container
docker-compose exec api bash

# Check health
curl http://localhost:8001/health
```

## Scaling

### Horizontal Scaling

- Use load balancer
- Scale API replicas
- Use Redis cluster
- Implement database sharding

### Vertical Scaling

- Increase container resources
- Optimize database queries
- Use caching strategies
- Monitor resource usage

---

For more detailed information, see [HANDOFF_DOCUMENTATION.md](HANDOFF_DOCUMENTATION.md).
