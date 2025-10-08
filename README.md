# Video Merger API 🎬

A high-performance FastAPI service for merging multiple M3U8 videos into Instagram Reels format with stylish overlays. Optimized for ARM64 architecture and Oracle Cloud Free Tier.

## Features ✨

- 🎥 **M3U8 Video Download**: Uses yt-dlp for reliable video downloading
- 📱 **Reels Format**: Automatically converts to 1080x1920 (9:16 aspect ratio)
- 🎨 **Stylish Overlays**: Adds video counter and titles with professional design
- ⚡ **Efficient Processing**: Optimized for ARM64 with FFmpeg hardware acceleration
- 🐳 **Docker Ready**: Complete Docker Compose setup included
- 🔄 **Auto Cleanup**: Automatic temporary file management
- 🔌 **n8n Integration**: Ready-to-use workflow examples
- 🌐 **Nginx Proxy Manager**: Full integration guide included

## Quick Start 🚀

### Prerequisites

- Docker & Docker Compose
- Nginx Proxy Manager (optional)
- Domain name with SSL (for production)

### Installation

1. **Clone or create project directory**:
```bash
mkdir video-merger-api && cd video-merger-api
```

2. **Create required files**:
   - `main.py` - FastAPI application
   - `Dockerfile` - Container configuration
   - `docker-compose.yml` - Service orchestration
   - `requirements.txt` - Python dependencies

3. **Build and run**:
```bash
docker-compose build
docker-compose up -d
```

4. **Verify installation**:
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

## API Endpoints 📡

### POST `/merge`
Merge multiple M3U8 videos into a single reels-format video.

**Request Body**:
```json
{
  "videos": [
    {
      "title": "Video Title",
      "author_fullname": "t2_username",
      "secure_media": {
        "reddit_video": {
          "hls_url": "https://v.redd.it/example/HLSPlaylist.m3u8"
        }
      },
      "url": "https://v.redd.it/example"
    }
  ]
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Videos merged successfully",
  "output_file": "abc123def456.mp4",
  "video_count": 5
}
```

### GET `/download/{filename}`
Download the merged video file.

**Response**: Binary video file (MP4)

### GET `/health`
Health check endpoint.

**Response**: `{"status": "healthy"}`

## Configuration ⚙️

### Environment Variables

Create a `.env` file (optional):
```env
# API Configuration
MAX_WORKERS=3
TEMP_DIR=/tmp/video_processing
OUTPUT_DIR=/tmp/video_output

# Video Settings
REELS_WIDTH=1080
REELS_HEIGHT=1920
```

### Resource Limits

Edit `docker-compose.yml` to adjust:
```yaml
deploy:
  resources:
    limits:
      cpus: '2'      # Adjust based on your VPS
      memory: 2G     # Adjust based on available RAM
```

## Video Output Specifications 📹

- **Resolution**: 1080x1920 (9:16 aspect ratio)
- **Video Codec**: H.264 (libx264)
- **Audio Codec**: AAC 128kbps
- **CRF**: 23 (high quality)
- **Preset**: Medium (balanced speed/quality)

### Overlays
- **Counter**: Top right corner (e.g., "1/5")
- **Title**: Bottom center, with semi-transparent background
- **Font**: DejaVu Sans Bold
- **Colors**: White text with black shadow for readability

## n8n Integration 🔄

Import the provided `n8n-workflow-example.json` into your n8n instance.

**Workflow Steps**:
1. Webhook trigger receives Reddit video data
2. Format data to API specification
3. Call Video Merger API
4. Check processing status
5. Download final video
6. Return result

**Usage in n8n**:
```javascript
// In Code node
const videos = $input.all().map(item => ({
  title: item.json.title,
  secure_media: {
    reddit_video: {
      hls_url: item.json.secure_media.reddit_video.hls_url
    }
  },
  url: item.json.url
}));

return [{ json: { videos } }];
```

## Nginx Proxy Manager Setup 🌐

### Add Proxy Host

1. Domain: `api.yourdomain.com`
2. Forward to: `video-merger-api:8000`
3. Enable SSL (Let's Encrypt)
4. Add custom Nginx configuration:

```nginx
proxy_read_timeout 900s;
proxy_connect_timeout 900s;
proxy_send_timeout 900s;
client_max_body_size 50M;
```

### Connect Networks

```bash
docker network connect nginx-proxy-manager_default video-merger-api
```

See `nginx-proxy-manager-setup.md` for detailed instructions.

## Testing 🧪

Use the provided test script:

```bash
python test_api.py https://api.yourdomain.com
```

Or test manually:

```bash
# Health check
curl https://api.yourdomain.com/health

# Merge videos (with valid URLs)
curl -X POST https://api.yourdomain.com/merge \
  -H "Content-Type: application/json" \
  -d @test_request.json

# Download result
curl -O https://api.yourdomain.com/download/OUTPUT_FILE.mp4
```

## Performance 🚀

### Expected Processing Times (Oracle Free Tier ARM64)

| Videos | Total Duration | Processing Time |
|--------|---------------|----------------|
| 2-5    | 1-3 min       | 2-4 min        |
| 6-10   | 3-7 min       | 5-8 min        |
| 11-15  | 7-12 min      | 10-15 min      |

*Times vary based on video resolution and complexity*

### Optimization Tips

1. **Adjust CRF**: Higher = smaller files, faster processing
   ```python
   # In main.py, change from 23 to 28
   "-crf", "28"
   ```

2. **Use faster preset**:
   ```python
   # Change from "medium" to "fast"
   "-preset", "fast"
   ```

3. **Reduce concurrent jobs**:
   ```python
   MAX_WORKERS = 2  # In main.py
   ```

## Monitoring 📊

### View Logs
```bash
docker-compose logs -f
```

### Check Resources
```bash
docker stats video-merger-api
```

### Disk Usage
```bash
docker exec video-merger-api du -sh /tmp/video_*
```

## Troubleshooting 🔧

### Container Won't Start
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Out of Memory
- Reduce `MAX_WORKERS` in main.py
- Decrease memory limit in docker-compose.yml
- Use faster preset for encoding

### yt-dlp Fails
```bash
# Update yt-dlp
docker exec video-merger-api pip install -U yt-dlp
```

### Videos Not Processing
- Check FFmpeg: `docker exec video-merger-api ffmpeg -version`
- Verify video URLs are accessible
- Check logs: `docker-compose logs`

## Security 🔒

- Configure firewall to allow only ports 80, 443, 22
- Use strong passwords for Nginx Proxy Manager
- Consider adding API key authentication
- Regularly update Docker images
- Monitor access logs for unusual activity

## Maintenance 🛠️

### Regular Tasks

**Weekly**:
```bash
# Check disk usage
df -h

# Review logs
docker-compose logs --tail=100
```

**Monthly**:
```bash
# Update images
docker-compose pull
docker-compose up -d

# Clean old files
docker exec video-merger-api find /tmp/video_output -type f -mtime +1 -delete
```

## Contributing 🤝

Contributions are welcome! Areas for improvement:
- Add queue system (Redis/Celery) for better job management
- Implement progress tracking via WebSocket
- Add more video format support
- Enhance overlay customization options

## License 📄

MIT License - Feel free to use in your projects!

## Support 💬

For issues and questions:
1. Check the troubleshooting section
2. Review logs: `docker-compose logs`
3. Verify your setup matches the deployment guide

## Acknowledgments 🙏

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [FFmpeg](https://ffmpeg.org/) - Video processing
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video downloading
- [Docker](https://www.docker.com/) - Containerization

---

**Made with ❤️ for the n8n and automation community**
