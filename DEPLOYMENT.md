# Video Merger API - Deployment Guide

## Prerequisites

- Oracle Cloud Free Tier ARM64 VPS
- Docker and Docker Compose installed
- Nginx Proxy Manager running
- Domain name pointed to your VPS

## Installation Steps

### 1. Connect to Your VPS

```bash
ssh your-user@your-vps-ip
```

### 2. Install Docker (if not installed)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo apt install docker-compose -y
```

### 3. Create Project Directory

```bash
mkdir -p ~/video-merger-api
cd ~/video-merger-api
```

### 4. Create Files

Create the following files in the directory:

- `main.py` (FastAPI application)
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`

### 5. Build and Run

```bash
# Build the image
docker-compose build

# Start the service
docker-compose up -d

# Check logs
docker-compose logs -f
```

### 6. Verify Installation

```bash
# Check if container is running
docker ps

# Test health endpoint
curl http://localhost:8000/health

# Expected response: {"status":"healthy"}
```

### 7. Configure Nginx Proxy Manager

Follow the instructions in `nginx-proxy-manager-setup.md` to:
1. Add a proxy host pointing to the container
2. Enable SSL with Let's Encrypt
3. Configure timeouts for video processing

### 8. Test API

```bash
# Test with curl
curl -X POST https://your-domain.com/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": [
      {
        "title": "Test Video 1",
        "secure_media": {
          "reddit_video": {
            "hls_url": "https://v.redd.it/example1/HLSPlaylist.m3u8"
          }
        },
        "url": "https://v.redd.it/example1"
      }
    ]
  }'
```

## Resource Management

### Monitoring

```bash
# Check resource usage
docker stats video-merger-api

# Check logs
docker logs -f video-merger-api

# Check disk usage
df -h
```

### Cleanup Old Files

The API automatically cleans up temporary files, but you can manually clean output files:

```bash
# Clean old output files (older than 24 hours)
docker exec video-merger-api find /tmp/video_output -type f -mtime +1 -delete
```

### Automatic Cleanup (Cron Job)

```bash
# Add to crontab
crontab -e

# Add this line to clean up daily at 3 AM
0 3 * * * docker exec video-merger-api find /tmp/video_output -type f -mtime +1 -delete
```

## Performance Optimization

### For ARM64 Oracle Free Tier (4 cores, 24GB RAM)

Edit `docker-compose.yml` to adjust resources:

```yaml
deploy:
  resources:
    limits:
      cpus: '3'      # Use 3 of 4 cores
      memory: 8G     # Allocate 8GB RAM
    reservations:
      cpus: '2'
      memory: 2G
```

### FFmpeg Optimization

The application uses these optimized settings:
- **Preset**: `medium` (balance between speed and quality)
- **CRF**: `23` (good quality, reasonable file size)
- **Audio**: `128k` AAC (optimized for reels)

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Out of Memory

```bash
# Check memory
free -h

# Reduce worker count in docker-compose.yml
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### Slow Processing

1. **Reduce video quality**:
   - Edit `main.py`: Change `crf` from `23` to `28`
   
2. **Use faster preset**:
   - Edit `main.py`: Change `preset` from `medium` to `fast`

3. **Process fewer videos**:
   - Limit concurrent processing by reducing `MAX_WORKERS`

### yt-dlp Download Fails

```bash
# Update yt-dlp in running container
docker exec video-merger-api pip install -U yt-dlp

# Or rebuild image
docker-compose build --no-cache
docker-compose up -d
```

## Security Best Practices

1. **Firewall Configuration**:
```bash
# Only allow HTTP/HTTPS and SSH
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

2. **Rate Limiting**: Add to NPM Advanced config:
```nginx
limit_req_zone $binary_remote_addr zone=videomerge:10m rate=5r/m;
limit_req zone=videomerge burst=2 nodelay;
```

3. **Environment Variables**: Never expose sensitive data in docker-compose.yml

4. **Regular Updates**:
```bash
# Update images monthly
docker-compose pull
docker-compose up -d
```

## Backup and Recovery

### Backup Configuration

```bash
# Backup docker-compose and configs
tar -czf video-merger-backup-$(date +%Y%m%d).tar.gz \
  docker-compose.yml main.py requirements.txt Dockerfile
```

### Restore from Backup

```bash
# Extract backup
tar -xzf video-merger-backup-YYYYMMDD.tar.gz

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

## Production Checklist

- [ ] Docker and Docker Compose installed
- [ ] Project files created
- [ ] Container built and running
- [ ] Health endpoint responding
- [ ] Nginx Proxy Manager configured
- [ ] SSL certificate installed
- [ ] Firewall configured
- [ ] Test API with sample data
- [ ] n8n workflow configured
- [ ] Monitoring setup (optional)
- [ ] Backup strategy in place

## Advanced Configuration

### Enable Logging to File

Add to `docker-compose.yml`:

```yaml
services:
  video-merger-api:
    volumes:
      - ./logs:/app/logs
```

Update `main.py`:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/api.log'),
        logging.StreamHandler()
    ]
)
```

### Add Authentication (Optional)

Install additional package:
```bash
# Add to requirements.txt
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
```

Add API key validation in `main.py`:

```python
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.getenv("API_KEY", "your-secret-key"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

@app.post("/merge", dependencies=[Depends(verify_api_key)])
async def merge_videos(...):
    # endpoint code
```

## Support and Maintenance

### Regular Maintenance Tasks

**Weekly**:
- Check disk usage
- Review logs for errors
- Verify API responsiveness

**Monthly**:
- Update Docker images
- Update yt-dlp
- Clean up old logs
- Review resource usage

### Getting Help

If you encounter issues:

1. Check logs: `docker-compose logs -f`
2. Verify health: `curl http://localhost:8000/health`
3. Test FFmpeg: `docker exec video-merger-api ffmpeg -version`
4. Check resources: `docker stats`

## API Usage Examples

### Using curl

```bash
# Merge videos
curl -X POST https://your-domain.com/merge \
  -H "Content-Type: application/json" \
  -d @request.json

# Download result
curl -O https://your-domain.com/download/OUTPUT_FILENAME.mp4
```

### Using Python

```python
import requests

# Prepare request
data = {
    "videos": [
        {
            "title": "Video 1",
            "secure_media": {
                "reddit_video": {
                    "hls_url": "https://v.redd.it/example/HLSPlaylist.m3u8"
                }
            },
            "url": "https://v.redd.it/example"
        }
    ]
}

# Make request
response = requests.post("https://your-domain.com/merge", json=data)
result = response.json()

# Download video
if result["status"] == "success":
    video_response = requests.get(
        f"https://your-domain.com/download/{result['output_file']}"
    )
    with open("merged_video.mp4", "wb") as f:
        f.write(video_response.content)
```

## Cost Optimization

### Oracle Free Tier Limits
- **Compute**: 4 OCPU, 24 GB RAM (ARM)
- **Storage**: 200 GB block volume
- **Bandwidth**: 10 TB/month outbound

### Tips to Stay Within Free Tier

1. **Limit concurrent processing**: Keep MAX_WORKERS at 2-3
2. **Clean up old files**: Auto-delete after 24 hours
3. **Monitor bandwidth**: Large video downloads count toward limit
4. **Use efficient encoding**: CRF 23-28 for good quality/size balance

### Estimated Processing Capacity

With 4 cores and 24GB RAM:
- **~5-10 videos per merge**: 2-5 minutes processing
- **~10-15 videos per merge**: 5-10 minutes processing
- **Concurrent merges**: 2-3 at once (with MAX_WORKERS=3)

## Scaling Considerations

If you outgrow the free tier:

1. **Horizontal Scaling**: Deploy multiple instances with load balancer
2. **Queue System**: Add Redis/RabbitMQ for job queuing
3. **Storage**: Use object storage (S3, Oracle Object Storage) for outputs
4. **CDN**: Serve videos through CDN to reduce bandwidth

---

## Quick Reference Commands

```bash
# Start service
docker-compose up -d

# Stop service
docker-compose down

# View logs
docker-compose logs -f

# Restart service
docker-compose restart

# Rebuild after code changes
docker-compose build && docker-compose up -d

# Check status
docker-compose ps

# Execute command in container
docker exec -it video-merger-api bash

# Update yt-dlp
docker exec video-merger-api pip install -U yt-dlp

# Clean volumes (WARNING: deletes all data)
docker-compose down -v
```
