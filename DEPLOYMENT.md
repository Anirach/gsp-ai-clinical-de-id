# Clinical Text De-Identification System - Deployment Guide

## Overview

This deployment guide covers the setup and deployment of the Clinical Text De-Identification System, a comprehensive solution for bilingual (Thai/English) text de-identification with regulatory compliance.

## System Requirements

### Minimum Requirements
- **OS**: Linux, macOS, or Windows with WSL2
- **Python**: 3.8+ (3.11 recommended)
- **Node.js**: 16+ (for frontend)
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 10GB free space
- **Network**: Internet connection for initial setup

### Production Requirements
- **CPU**: 4+ cores
- **Memory**: 16GB+ RAM
- **Storage**: 50GB+ SSD storage
- **Database**: PostgreSQL 12+
- **Cache**: Redis 6+
- **Load Balancer**: Nginx/Apache (optional)

## Quick Start

### 1. Clone and Setup
```bash
# Clone the repository
git clone <repository-url>
cd webapp

# Make startup script executable
chmod +x start.sh

# Run the automatic setup
./start.sh
```

The startup script will:
- Check system requirements
- Install Python and Node.js dependencies
- Download required ML models
- Run basic functionality tests
- Start backend and frontend services
- Display access information

### 2. Access the System
- **Frontend UI**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### 3. Default Login Credentials
- **Admin**: username: `admin`, password: `admin123`
- **Reviewer**: username: `reviewer`, password: `reviewer123`
- **Operator**: username: `operator`, password: `operator123`

## Manual Installation

### Backend Setup

1. **Create Virtual Environment**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

3. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Create Directories**
```bash
mkdir -p logs logs/audit data/exports
```

5. **Start Backend**
```bash
cd backend/src
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python main.py
```

### Frontend Setup

1. **Install Dependencies**
```bash
cd frontend
npm install
```

2. **Start Development Server**
```bash
npm start
```

3. **Build for Production**
```bash
npm run build
```

## Docker Deployment

### Using Docker Compose (Recommended)

1. **Start All Services**
```bash
docker-compose up -d
```

2. **View Logs**
```bash
docker-compose logs -f api
docker-compose logs -f ui
```

3. **Stop Services**
```bash
docker-compose down
```

### Individual Docker Containers

1. **Build Backend Image**
```bash
docker build -t clinical-deid-api .
```

2. **Build Frontend Image**
```bash
docker build -t clinical-deid-ui ./frontend
```

3. **Run Containers**
```bash
# Backend
docker run -p 8000:8000 clinical-deid-api

# Frontend
docker run -p 3000:3000 clinical-deid-ui
```

## Production Deployment

### Database Setup (PostgreSQL)

1. **Install PostgreSQL**
```sql
CREATE DATABASE clinical_deid;
CREATE USER deid_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE clinical_deid TO deid_user;
```

2. **Update Configuration**
```bash
DATABASE_URL=postgresql://deid_user:secure_password@localhost:5432/clinical_deid
```

### Security Configuration

1. **Generate Secure Keys**
```bash
# Generate random secrets
openssl rand -base64 32  # For SECRET_KEY
openssl rand -base64 32  # For JWT_SECRET_KEY
openssl rand -base64 32  # For ENCRYPTION_KEY
openssl rand -base64 32  # For MASTER_SECRET_KEY
```

2. **Update Environment Variables**
```bash
SECRET_KEY=your-generated-secret-key
JWT_SECRET_KEY=your-generated-jwt-key
ENCRYPTION_KEY=your-generated-encryption-key
MASTER_SECRET_KEY=your-generated-master-secret
DEBUG=false
```

### Process Management

#### Using PM2 (Recommended)

1. **Install PM2**
```bash
npm install -g pm2
```

2. **Create Ecosystem File**
```javascript
// ecosystem.config.js
module.exports = {
  apps: [{
    name: 'clinical-deid-api',
    script: 'backend/src/main.py',
    interpreter: 'python3',
    env: {
      PYTHONPATH: './backend/src'
    }
  }, {
    name: 'clinical-deid-ui',
    script: 'npm',
    args: 'start',
    cwd: './frontend'
  }]
};
```

3. **Start Services**
```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

#### Using Systemd

1. **Create Service Files**
```ini
# /etc/systemd/system/clinical-deid-api.service
[Unit]
Description=Clinical DeID API
After=network.target

[Service]
Type=simple
User=deid
WorkingDirectory=/opt/clinical-deid
Environment=PYTHONPATH=/opt/clinical-deid/backend/src
ExecStart=/opt/clinical-deid/venv/bin/python backend/src/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

2. **Enable and Start**
```bash
sudo systemctl enable clinical-deid-api
sudo systemctl start clinical-deid-api
```

### Reverse Proxy (Nginx)

1. **Install Nginx**
```bash
sudo apt install nginx
```

2. **Configure Virtual Host**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
}
```

### SSL/TLS Configuration

1. **Install Certbot**
```bash
sudo apt install certbot python3-certbot-nginx
```

2. **Obtain Certificate**
```bash
sudo certbot --nginx -d your-domain.com
```

## Monitoring and Maintenance

### Health Checks

1. **API Health Check**
```bash
curl http://localhost:8000/health
```

2. **Database Connection**
```bash
curl http://localhost:8000/api/v1/statistics
```

### Log Management

1. **View Logs**
```bash
# Application logs
tail -f logs/app.log

# Audit logs
tail -f logs/audit/detection/$(date +%Y-%m-%d)/*.json
```

2. **Log Rotation**
```bash
# Add to /etc/logrotate.d/clinical-deid
/opt/clinical-deid/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    create 644 deid deid
}
```

### Backup Strategy

1. **Database Backup**
```bash
pg_dump clinical_deid > backup_$(date +%Y%m%d).sql
```

2. **Configuration Backup**
```bash
tar -czf config_backup_$(date +%Y%m%d).tar.gz .env config/ data/dictionaries/
```

3. **Audit Log Backup**
```bash
tar -czf audit_backup_$(date +%Y%m%d).tar.gz logs/audit/
```

## Troubleshooting

### Common Issues

1. **Python Dependencies**
```bash
# Missing spaCy model
python -m spacy download en_core_web_sm

# SSL certificate issues
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt
```

2. **Memory Issues**
```bash
# Increase memory limits
export PYTHONUNBUFFERED=1
ulimit -m 8388608  # 8GB
```

3. **Port Conflicts**
```bash
# Check port usage
lsof -i :8000
lsof -i :3000

# Kill processes if needed
sudo kill -9 <PID>
```

### Performance Tuning

1. **Backend Optimization**
```python
# Increase worker processes
uvicorn main:app --workers 4 --host 0.0.0.0 --port 8000
```

2. **Database Optimization**
```sql
-- Create indexes for better performance
CREATE INDEX idx_job_created_at ON jobs(created_at);
CREATE INDEX idx_traces_timestamp ON detection_traces(timestamp);
```

3. **Caching Configuration**
```bash
# Redis memory optimization
echo 'maxmemory 2gb' >> /etc/redis/redis.conf
echo 'maxmemory-policy allkeys-lru' >> /etc/redis/redis.conf
```

## Security Checklist

- [ ] Change all default passwords
- [ ] Generate secure random keys
- [ ] Enable HTTPS with valid certificates
- [ ] Configure firewall rules
- [ ] Set up regular security updates
- [ ] Enable audit logging
- [ ] Configure backup encryption
- [ ] Set up intrusion detection
- [ ] Review user permissions regularly
- [ ] Monitor system logs

## Support and Maintenance

### Update Procedure

1. **Backup Current System**
2. **Test Updates in Staging**
3. **Deploy with Zero Downtime**
4. **Verify Functionality**
5. **Monitor Performance**

### Key Rotation

1. **Generate New Keys**
2. **Update Configuration**
3. **Restart Services**
4. **Verify Operation**
5. **Update Documentation**

For additional support, consult the system logs and audit trails for detailed troubleshooting information.