from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import subprocess
import os
import uuid
import shutil
import logging
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Video Merger API")

TEMP_DIR = Path("/tmp/video_processing")
OUTPUT_DIR = Path("/tmp/output")
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

executor = ThreadPoolExecutor(max_workers=3)

class RedditVideo(BaseModel):
    title: str
    author_fullname: Optional[str] = None
    secure_media: dict
    url: HttpUrl

class VideoRequest(BaseModel):
    videos: List[RedditVideo]

def download_m3u8(url: str, output_path: str, timeout: int = 300) -> bool:
    """Download m3u8 video using yt-dlp with robust settings"""
    try:
        # Clean URL - remove query parameters
        if "?" in url:
            url = url.split("?")[0]
        
        cmd = [
            "yt-dlp",
            "--no-check-certificate",
            "--no-warnings",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "--add-header", "Referer: https://www.reddit.com/",
            "--hls-prefer-native",
            "--concurrent-fragments", "5",
            "--retries", "10",
            "--fragment-retries", "10",
            "--retry-sleep", "2",
            "--socket-timeout", "60",
            "--no-check-formats",
            "--format", "bv*+ba/b",
            "--merge-output-format", "mp4",
            "-o", output_path,
            url
        ]
        
        logger.info(f"Downloading: {url}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0 and os.path.exists(output_path):
            size = os.path.getsize(output_path)
            logger.info(f"Downloaded successfully: {output_path} ({size} bytes)")
            return True
        else:
            logger.error(f"Download failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Download timeout for {url}")
        return False
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return False

def normalize_video(input_path: str, output_path: str) -> bool:
    """Normalize video to reels format (1080x1920) without overlay"""
    try:
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-threads", "2",
            "-y",
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"Video normalized: {output_path}")
            return True
        else:
            logger.error(f"Normalization failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Normalization error: {str(e)}")
        return False

def merge_videos_with_transitions(input_files: List[str], output_path: str, transition_duration: float = 0.5) -> bool:
    """Merge multiple videos with smooth crossfade transitions"""
    try:
        if len(input_files) == 1:
            # If only one video, just copy it
            shutil.copy(input_files[0], output_path)
            return True
        
        # Build complex filter for crossfade transitions
        filter_parts = []
        
        # Load all video inputs
        for i in range(len(input_files)):
            filter_parts.append(f"[{i}:v]")
        
        # Create crossfade chain
        current_label = "[v0]"
        for i in range(len(input_files) - 1):
            if i == 0:
                filter_parts.append(f"[0:v][1:v]xfade=transition=fade:duration={transition_duration}:offset=0[v{i+1}];")
            else:
                filter_parts.append(f"[v{i}][{i+1}:v]xfade=transition=fade:duration={transition_duration}:offset=0[v{i+1}];")
            current_label = f"[v{i+1}]"
        
        # Audio mixing
        audio_parts = []
        for i in range(len(input_files)):
            audio_parts.append(f"[{i}:a]")
        audio_parts.append(f"concat=n={len(input_files)}:v=0:a=1[a]")
        
        filter_complex = "".join(filter_parts) + "".join(audio_parts)
        
        # Build ffmpeg command
        cmd = ["ffmpeg"]
        for file in input_files:
            cmd.extend(["-i", file])
        
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", current_label,
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-y",
            output_path
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"Videos merged with transitions: {output_path}")
            return True
        else:
            logger.error(f"Merge failed: {result.stderr}")
            # Fallback to simple concat if xfade fails
            return merge_videos_simple(input_files, output_path)
            
    except Exception as e:
        logger.error(f"Merge error: {str(e)}")
        # Fallback to simple concat
        return merge_videos_simple(input_files, output_path)

def merge_videos_simple(input_files: List[str], output_path: str) -> bool:
    """Simple concat merge as fallback"""
    try:
        concat_file = output_path + ".txt"
        
        with open(concat_file, 'w') as f:
            for file in input_files:
                f.write(f"file '{file}'\n")
        
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            "-movflags", "+faststart",
            "-y",
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        os.remove(concat_file)
        
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"Videos merged (simple): {output_path}")
            return True
        else:
            logger.error(f"Simple merge failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Simple merge error: {str(e)}")
        return False

def cleanup_directory(directory: Path, max_age_hours: int = 2):
    """Clean up old files"""
    try:
        current_time = time.time()
        for item in directory.iterdir():
            if item.is_file():
                if current_time - item.stat().st_mtime > max_age_hours * 3600:
                    item.unlink()
                    logger.info(f"Cleaned up: {item}")
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")

@app.post("/merge-videos")
async def merge_videos_endpoint(request: VideoRequest, background_tasks: BackgroundTasks):
    """Main endpoint to merge Reddit videos"""
    
    if not request.videos:
        raise HTTPException(status_code=400, detail="No videos provided")
    
    if len(request.videos) > 15:
        raise HTTPException(status_code=400, detail="Maximum 15 videos allowed")
    
    job_id = str(uuid.uuid4())
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    try:
        total_videos = len(request.videos)
        processed_files = []
        
        # Download and process videos
        for idx, video in enumerate(request.videos, 1):
            try:
                # Extract HLS URL
                hls_url = video.secure_media.get("reddit_video", {}).get("hls_url")
                if not hls_url:
                    logger.warning(f"No HLS URL for video {idx}")
                    continue
                
                # Download video
                raw_file = str(job_dir / f"raw_{idx}.mp4")
                if not download_m3u8(hls_url, raw_file):
                    logger.warning(f"Failed to download video {idx}")
                    continue
                
                # Normalize to reels format
                processed_file = str(job_dir / f"processed_{idx}.mp4")
                if not normalize_video(raw_file, processed_file):
                    logger.warning(f"Failed to process video {idx}")
                    continue
                
                processed_files.append(processed_file)
                
                # Clean up raw file
                os.remove(raw_file)
                
            except Exception as e:
                logger.error(f"Error processing video {idx}: {str(e)}")
                continue
        
        if not processed_files:
            raise HTTPException(status_code=500, detail="No videos could be processed")
        
        # Merge all processed videos with transitions
        output_file = OUTPUT_DIR / f"{job_id}_merged.mp4"
        if not merge_videos_with_transitions(processed_files, str(output_file)):
            raise HTTPException(status_code=500, detail="Failed to merge videos")
        
        # Cleanup job directory
        shutil.rmtree(job_dir, ignore_errors=True)
        
        # Schedule cleanup of output file after 48 hours
        background_tasks.add_task(cleanup_directory, OUTPUT_DIR, 48)
        
        return {
            "success": True,
            "job_id": job_id,
            "processed_videos": len(processed_files),
            "total_videos": total_videos,
            "download_url": f"/download/{job_id}"
        }
        
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{job_id}")
async def download_video(job_id: str):
    """Download the merged video"""
    output_file = OUTPUT_DIR / f"{job_id}_merged.mp4"
    
    if not output_file.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    
    return FileResponse(
        path=str(output_file),
        media_type="video/mp4",
        filename=f"merged_reels_{job_id}.mp4"
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    """Cleanup old files on startup"""
    cleanup_directory(TEMP_DIR, 48)
    cleanup_directory(OUTPUT_DIR, 48)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
