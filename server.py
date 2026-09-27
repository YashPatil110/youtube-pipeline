import os
import json
import socket
import threading
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

# Ensure environment overrides
load_dotenv(override=True)

from free_clipper import download_and_clip
from pipeline import generate_shorts_metadata, log_decision
from youtube_uploader import upload_short

app = FastAPI(title="YouTube Shorts Studio")

# Serve static assets from /web
app.mount("/static", StaticFiles(directory="web"), name="static")

# Current Job State
job_state = {
    "status": "idle",       # "idle", "processing", "review_ready", "error"
    "step": "",
    "progress": 0,
    "error_message": None,
    "local_video_path": None,
    "source_url": None,
    "transcript": None,
    "metadata": None,
    "youtube_url": None
}

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class ProcessRequest(BaseModel):
    url: str
    start_sec: int = 30
    duration_sec: int = 35

class PublishRequest(BaseModel):
    title: str
    description: str
    tags: list[str]

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open(os.path.join("web", "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.get("/manifest.json")
async def serve_manifest():
    return FileResponse(os.path.join("web", "manifest.json"), media_type="application/manifest+json")

@app.get("/sw.js")
async def serve_service_worker():
    return FileResponse(os.path.join("web", "sw.js"), media_type="application/javascript")

@app.get("/api/info")
async def get_info():
    return {
        "ip": get_local_ip(),
        "port": 8000
    }

@app.get("/api/status")
async def get_status():
    return job_state

@app.get("/api/video")
async def get_video():
    video_path = job_state.get("local_video_path") or "output_short.mp4"
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(video_path, media_type="video/mp4")

@app.get("/api/history")
async def get_history():
    log_file = "history_log.json"
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def run_pipeline_worker(url: str, start_sec: int, duration_sec: int):
    global job_state
    try:
        job_state["status"] = "processing"
        job_state["source_url"] = url
        job_state["step"] = "Downloading and 9:16 vertical cropping..."
        job_state["progress"] = 35
        job_state["error_message"] = None

        # Step 1: Clip & 9:16 Vertical Crop
        clip_result = download_and_clip(youtube_url=url, start_sec=start_sec, duration_sec=duration_sec)
        local_video_path = clip_result["local_video_path"]
        job_state["local_video_path"] = local_video_path

        # Step 2: Gemini Multimodal AI Transcription & Metadata
        job_state["step"] = "AI transcribing audio & crafting viral title/tags..."
        job_state["progress"] = 75

        metadata = generate_shorts_metadata(local_video_path)
        job_state["metadata"] = metadata
        job_state["transcript"] = metadata.get("transcript", "")
        job_state["progress"] = 100
        job_state["step"] = "Clip ready for review!"
        job_state["status"] = "review_ready"

    except Exception as e:
        job_state["status"] = "error"
        job_state["error_message"] = str(e)
        job_state["step"] = "Processing failed"

@app.post("/api/process")
async def process_video(req: ProcessRequest):
    global job_state
    if job_state["status"] == "processing":
        raise HTTPException(status_code=400, detail="A video is already processing. Please wait.")

    # Start worker in separate thread so it doesn't block FastAPI event loop
    thread = threading.Thread(
        target=run_pipeline_worker, 
        args=(req.url, req.start_sec, req.duration_sec),
        daemon=True
    )
    thread.start()
    return {"message": "Processing started"}

def run_upload_worker(video_path: str, title: str, description: str, tags: list):
    global job_state
    try:
        job_state["status"] = "uploading"
        job_state["progress"] = 5
        job_state["step"] = "Connecting to YouTube..."

        def on_upload_progress(pct):
            job_state["progress"] = pct
            job_state["step"] = f"Uploading to YouTube Shorts: {pct}%"

        video_id = upload_short(
            file_path=video_path,
            title=title,
            description=description,
            tags=tags,
            progress_callback=on_upload_progress
        )

        yt_url = f"https://youtube.com/shorts/{video_id}"
        job_state["youtube_url"] = yt_url
        job_state["status"] = "published"
        job_state["progress"] = 100
        job_state["step"] = f"🎉 Successfully Published! Video ID: {video_id}"

        # Log decision
        meta = {
            "title": title,
            "description": description,
            "tags": tags
        }
        log_decision(
            source_url=job_state.get("source_url", "Web Upload"),
            metadata=meta,
            decision="approved",
            youtube_url=yt_url
        )
    except Exception as e:
        job_state["status"] = "error"
        job_state["error_message"] = f"Upload error: {str(e)}"
        job_state["step"] = "YouTube upload failed"

@app.post("/api/publish")
async def publish_video(req: PublishRequest):
    global job_state
    video_path = job_state.get("local_video_path") or "output_short.mp4"
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="No video available to upload")

    job_state["status"] = "uploading"
    job_state["progress"] = 5
    job_state["step"] = "Starting YouTube upload..."

    thread = threading.Thread(
        target=run_upload_worker,
        args=(video_path, req.title, req.description, req.tags),
        daemon=True
    )
    thread.start()
    return {"message": "Upload started"}

@app.post("/api/discard")
async def discard_video():
    global job_state
    video_path = job_state.get("local_video_path") or "output_short.mp4"

    # Log discard decision
    meta = job_state.get("metadata") or {"title": "Discarded Clip"}
    log_decision(
        source_url=job_state.get("source_url", "Web Upload"),
        metadata=meta,
        decision="discarded",
        youtube_url=None
    )

    # Clean up local video file to free disk space
    if os.path.exists(video_path):
        try:
            os.remove(video_path)
        except OSError:
            pass

    job_state["status"] = "idle"
    job_state["metadata"] = None
    job_state["local_video_path"] = None
    return {"status": "discarded"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    local_ip = get_local_ip()
    print("=" * 60)
    print("🚀 YOUTUBE SHORTS AUTOMATION STUDIO")
    print(f"💻 Laptop access:  http://localhost:{port}")
    print(f"📱 Mobile access:  http://{local_ip}:{port}")
    print("=" * 60)
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
