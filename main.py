from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import subprocess
import os
import uuid
import shutil
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Video Merger API", version="1.0.0")

# Configuration
TEMP_DIR = Path("/tmp/video_processing")
OUTPUT_DIR = Path("/tmp/video_output")
MAX_WORKERS = 3
REELS_WIDTH = 1080
REELS_HEIGHT = 1920

TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

class RedditVideo(BaseModel):
    hls_url: HttpUrl

class SecureMedia(BaseModel):
    reddit_video: RedditVideo

class VideoInput(BaseModel):
    title: str
    author_fullname: Optional[str] = None
    secure_media: SecureMedia
    url: HttpUrl

class VideoRequest(BaseModel):
    videos: List[VideoInput]

class VideoResponse(BaseModel):
    status: str
    message: str
    output_file: Optional[str] = None
    video_count: int

executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

def cleanup_files(job_id: str):
    """Clean up temporary files after processing"""
    try:
        job_dir = TEMP_DIR / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
        logger.info(f"Cleaned up files for job {job_id}")
    except Exception as e:
        logger.error(f"Error cleaning up files: {e}")

def download_video(url: str, output_path: Path) -> bool:
    """Download M3U8 video using yt-dlp"""
    try:
        cmd = [
            "yt-dlp",
            "-f", "best",
            "--no-warnings",
            "--no-check-certificate",
            "-o", str(output_path),
            str(url)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and output_path.exists():
            logger.info(f"Successfully downloaded: {output_path}")
            return True
        else:
            logger.error(f"Download failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        return False

def create_overlay_filter(index: int, total: int, title: str, duration: float, offset: float) -> str:
    """Create FFmpeg filter for text overlay with reels-style design"""
    # Escape special characters in title
    title_escaped = title.replace("'", "'\\\\\\''").replace(":", "\\:")
    
    # Counter overlay (top right)
    counter_filter = (
        f"drawtext=text='{index}/{total}':"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"fontsize=60:fontcolor=white:"
        f"x=w-tw-40:y=40:"
        f"box=1:boxcolor=black@0.6:boxborderw=10:"
        f"enable='between(t,{offset},{offset+duration})'"
    )
    
    # Title overlay (bottom, centered)
    title_filter = (
        f"drawtext=text='{title_escaped}':"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"fontsize=48:fontcolor=white:"
        f"x=(w-text_w)/2:y=h-150:"
        f"box=1:boxcolor=black@0.7:boxborderw=15:"
        f"enable='between(t,{offset},{offset+duration})'"
    )
    
    return f"{counter_filter},{title_filter}"

def get_video_duration(video_path: Path) -> float:
    """Get video duration using ffprobe"""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"Error getting duration: {e}")
        return 0.0

def process_single_video(video_path: Path, output_path: Path) -> bool:
    """Scale and pad video to reels size"""
    try:
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"scale={REELS_WIDTH}:{REELS_HEIGHT}:force_original_aspect_ratio=decrease,pad={REELS_WIDTH}:{REELS_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            logger.info(f"Processed video: {output_path}")
            return True
        else:
            logger.error(f"Processing failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        return False

def merge_videos_with_overlays(video_files: List[Path], titles: List[str], output_path: Path) -> bool:
    """Merge videos with text overlays"""
    try:
        # Get durations and create concat file
        concat_file = output_path.parent / f"concat_{uuid.uuid4().hex}.txt"
        processed_files = []
        
        # Process each video to reels size
        for i, video_file in enumerate(video_files):
            processed_file = video_file.parent / f"processed_{i}_{video_file.name}"
            if process_single_video(video_file, processed_file):
                processed_files.append(processed_file)
            else:
                logger.error(f"Failed to process video {i}")
                return False
        
        # Create concat file
        with open(concat_file, 'w') as f:
            for pf in processed_files:
                f.write(f"file '{pf}'\n")
        
        # Concatenate videos
        temp_concat = output_path.parent / f"temp_concat_{uuid.uuid4().hex}.mp4"
        concat_cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            "-y",
            str(temp_concat)
        ]
        
        subprocess.run(concat_cmd, capture_output=True, timeout=600)
        
        # Add overlays
        durations = [get_video_duration(pf) for pf in processed_files]
        overlay_filters = []
        offset = 0.0
        
        for i, (duration, title) in enumerate(zip(durations, titles), 1):
            overlay_filters.append(create_overlay_filter(i, len(titles), title, duration, offset))
            offset += duration
        
        filter_complex = ",".join(overlay_filters)
        
        final_cmd = [
            "ffmpeg",
            "-i", str(temp_concat),
            "-vf", filter_complex,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            "-y",
            str(output_path)
        ]
        
        result = subprocess.run(final_cmd, capture_output=True, text=True, timeout=900)
        
        # Cleanup
        concat_file.unlink(missing_ok=True)
        temp_concat.unlink(missing_ok=True)
        for pf in processed_files:
            pf.unlink(missing_ok=True)
        
        if result.returncode == 0:
            logger.info(f"Successfully merged videos: {output_path}")
            return True
        else:
            logger.error(f"Merge failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error merging videos: {e}")
        return False

async def process_videos(job_id: str, videos: List[VideoInput]) -> dict:
    """Main processing function"""
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    try:
        # Download videos
        downloaded_files = []
        titles = []
        
        loop = asyncio.get_event_loop()
        
        for i, video in enumerate(videos):
            output_file = job_dir / f"video_{i}.mp4"
            url = str(video.secure_media.reddit_video.hls_url)
            
            # Download in thread pool
            success = await loop.run_in_executor(
                executor,
                download_video,
                url,
                output_file
            )
            
            if success:
                downloaded_files.append(output_file)
                titles.append(video.title)
            else:
                logger.warning(f"Failed to download video {i}: {video.title}")
        
        if not downloaded_files:
            raise Exception("No videos were downloaded successfully")
        
        # Merge videos
        output_file = OUTPUT_DIR / f"{job_id}.mp4"
        success = await loop.run_in_executor(
            executor,
            merge_videos_with_overlays,
            downloaded_files,
            titles,
            output_file
        )
        
        if success:
            return {
                "status": "success",
                "message": "Videos merged successfully",
                "output_file": f"{job_id}.mp4",
                "video_count": len(downloaded_files)
            }
        else:
            raise Exception("Failed to merge videos")
            
    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temporary files
        cleanup_files(job_id)

@app.post("/merge", response_model=VideoResponse)
async def merge_videos(request: VideoRequest, background_tasks: BackgroundTasks):
    """
    Merge multiple M3U8 videos into a single reels-format video with overlays
    """
    if not request.videos:
        raise HTTPException(status_code=400, detail="No videos provided")
    
    if len(request.videos) > 15:
        raise HTTPException(status_code=400, detail="Maximum 15 videos allowed")
    
    job_id = uuid.uuid4().hex
    
    try:
        result = await process_videos(job_id, request.videos)
        return VideoResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{filename}")
async def download_video(filename: str, background_tasks: BackgroundTasks):
    """
    Download the merged video file
    """
    file_path = OUTPUT_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Schedule cleanup after 1 hour
    background_tasks.add_task(lambda: asyncio.sleep(3600) or file_path.unlink(missing_ok=True))
    
    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=filename
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Video Merger API",
        "version": "1.0.0",
        "endpoints": {
            "POST /merge": "Merge videos",
            "GET /download/{filename}": "Download merged video",
            "GET /health": "Health check"
        }
    }
